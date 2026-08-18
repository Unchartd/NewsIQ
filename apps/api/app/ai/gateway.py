import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from app.ai.cache.redis_cache import ai_cache
from app.ai.errors import (
    AIGatewayError,
    AuthenticationError,
    ProviderUnavailableError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)
from app.ai.interfaces import GatewayRequest, GatewayResponse
from app.ai.metrics.telemetry import (
    newsiq_ai_gateway_cache_total,
    newsiq_ai_gateway_calls_total,
    newsiq_ai_gateway_cost_usd,
    newsiq_ai_gateway_latency_seconds,
    newsiq_ai_gateway_retries_total,
    newsiq_ai_gateway_timeouts_total,
    newsiq_ai_gateway_tokens_total,
    newsiq_ai_gateway_validation_failures_total,
    newsiq_prompt_executions_total,
    newsiq_prompt_latency_seconds,
    newsiq_prompt_tokens_total,
    newsiq_provider_fallback_executions_total,
)
from app.ai.model_health import filter_healthy, mark_exhausted
from app.ai.prompts.registry import prompt_registry
from app.ai.router.capability_router import capability_router
from app.core.trace import article_id_ctx, story_id_ctx, track_llm_call
from app.services.cost_budget import cost_budget_manager

logger = logging.getLogger(__name__)


# Pricing is defined once, in app/core/llm_pricing.py. This module and app/core/trace
# previously kept separate tables that disagreed about which models exist, and
# the tracer's copy — holding only models this deployment has never run — won.
from app.core.llm_pricing import PRICING_TABLE  # noqa: E402


def clean_json_for_schema(data: Any, schema: type[BaseModel]) -> Any:
    """Clean and map JSON fields to align with the expected Pydantic schema.

    1. Unnesting: If the JSON has nested dictionary wrapper fields (e.g. 'news_summary'), unnest them.
    2. Mapping 'summary' to specific summary fields.
    3. Key Mapping: Map camelCase/PascalCase field names to snake_case field names defined in the schema.
    4. Safe list conversion for fields expecting list[str].
    """
    if not isinstance(data, dict):
        return data

    schema_fields = set(schema.model_fields.keys())

    # 1. Unnesting
    top_level_matches = len(schema_fields.intersection(data.keys()))
    if top_level_matches < len(schema_fields) / 2:
        for key, value in data.items():
            if isinstance(value, dict):
                nested_matches = len(schema_fields.intersection(value.keys()))
                if nested_matches > top_level_matches:
                    data = value
                    break

    # 2. General Summary field extraction
    #
    # A lone "summary" is the model ignoring the three-tier schema. It is a
    # comprehensive prose summary, so it maps to detailed_summary and NOTHING
    # else: copying it into one_line_summary/short_summary fabricates two
    # summaries that were never generated and puts a full paragraph behind a
    # tab labelled "1-line". Leaving the other fields absent fails schema
    # validation, which the gateway retries (and then falls back on) — a real
    # repair path instead of silently shipping three identical strings.
    if "summary" in data and "detailed_summary" not in {k for k, v in data.items() if v}:
        data["detailed_summary"] = data["summary"]
        logger.warning(
            "Model returned a single 'summary' for %s instead of the three-tier fields; "
            "mapped to detailed_summary — schema validation will force a retry.",
            schema.__name__,
        )

    # 3. Key Mapping (camelCase/PascalCase to snake_case)
    camel_to_snake = {}
    for field in schema_fields:
        parts = field.split("_")
        camel = parts[0] + "".join(p.title() for p in parts[1:])
        camel_to_snake[camel] = field
        pascal = "".join(p.title() for p in parts)
        camel_to_snake[pascal] = field

    cleaned = {}
    for k, v in data.items():
        mapped_key = camel_to_snake.get(k, k)

        # 4. Safe list conversion for fields expecting list[str]
        field_info = schema.model_fields.get(mapped_key)
        if field_info:
            from typing import get_origin

            origin = get_origin(field_info.annotation)
            # Check if list type
            is_list = (origin is list) or (
                isinstance(field_info.annotation, type) and issubclass(field_info.annotation, list)
            )
            if is_list:
                if isinstance(v, str):
                    v = [v]
                elif isinstance(v, dict):
                    v = [
                        f"{key_k}: {key_v}"
                        if not isinstance(key_v, list)
                        else f"{key_k}: {', '.join(map(str, key_v))}"
                        for key_k, key_v in v.items()
                    ]

        cleaned[mapped_key] = v

    return cleaned


class AIGateway:
    """Centralized AI Gateway for NewsIQ.

    Supports capability routing, failover, exponential backoff retries,
    caching, observability, and structured output validation.
    """

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        pricing = PRICING_TABLE.get(model, {"input": 0.0, "output": 0.0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return round(input_cost + output_cost, 8)

    async def _persist_execution_record(
        self,
        execution_id: Any,
        stage: str,
        provider: str | None,
        model: str | None,
        capability: str | None,
        prompt_name: str | None,
        prompt_version: str | None,
        temperature: float | None,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        cost: float,
        cache_hit: bool,
        retry_count: int,
        fallback_count: int,
        schema_repaired: bool,
        decision: str | None,
        confidence: float | None,
        input_hash: str | None,
        story_id: str | None = None,
        article_id: str | None = None,
        unsupported_claims_count: int | None = None,
        missing_citations_count: int | None = None,
        contradictions_count: int | None = None,
        bias_corrections_count: int | None = None,
        regeneration_count: int | None = None,
        reflection_confidence: float | None = None,
    ) -> None:
        """Create and persist an AIExecutionRecord in the database."""
        import uuid

        from app.core.database import async_session_factory
        from app.core.trace import trace_id_ctx
        from app.models.observability_models import AIExecutionRecordModel

        def _to_uuid(val: Any) -> uuid.UUID | None:
            if not val:
                return None
            if isinstance(val, uuid.UUID):
                return val
            try:
                return uuid.UUID(str(val))
            except ValueError:
                return None

        try:
            async with async_session_factory() as session:
                record = AIExecutionRecordModel(
                    execution_id=_to_uuid(execution_id) or uuid.uuid4(),
                    trace_id=_to_uuid(trace_id_ctx.get(None)),
                    story_id=_to_uuid(story_id),
                    article_id=_to_uuid(article_id),
                    stage=stage,
                    provider=provider,
                    model=model,
                    capability=capability,
                    prompt_name=prompt_name,
                    prompt_version=prompt_version,
                    temperature=temperature,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    cost=cost,
                    cache_hit=cache_hit,
                    retry_count=retry_count,
                    fallback_count=fallback_count,
                    schema_repaired=schema_repaired,
                    decision=decision,
                    confidence=confidence,
                    input_hash=input_hash,
                    unsupported_claims_count=unsupported_claims_count,
                    missing_citations_count=missing_citations_count,
                    contradictions_count=contradictions_count,
                    bias_corrections_count=bias_corrections_count,
                    regeneration_count=regeneration_count,
                    reflection_confidence=reflection_confidence,
                )
                session.add(record)
                await session.commit()
        except Exception as persist_exc:
            logger.warning("Failed to persist AI execution record to DB: %s", persist_exc)

    async def generate_stage(
        self,
        stage: str,
        prompt_variables: dict[str, Any],
        schema: type[BaseModel] | None = None,
        story_id: str = "",
        article_id: str = "",
    ) -> GatewayResponse:
        """
        Execute a prompt stage through the gateway. Model, temperature, fallbacks,
        and cache policy are resolved entirely from PromptRepository.

        This is the canonical entrypoint. Callers never specify a model.

        Args:
            stage: Prompt stage name. e.g. 'summary_generation'
            prompt_variables: Template variables to fill {placeholders}.
            schema: Optional Pydantic model for structured output validation.
                    If None, the manifest's response_model is used if declared.
            story_id: For cost tracking and tracing.
            article_id: For cost tracking and tracing.
        """
        from app.ai.prompts.repository import prompt_repository

        if prompt_repository is None:
            raise AIGatewayError(
                "PromptRepository is not initialized. "
                "Ensure startup validation completed successfully."
            )

        manifest = prompt_repository.get(stage)
        cfg = prompt_repository.model_config(stage)
        messages = prompt_repository.messages(stage, **prompt_variables)

        system_prompt = manifest.system
        user_prompt = manifest.template.format(**prompt_variables)

        # Resolve schema: explicit arg wins, then manifest response_model
        resolved_schema = schema
        if resolved_schema is None and manifest.response_model:
            try:
                import importlib

                module = importlib.import_module("app.models.llm_responses")
                resolved_schema = getattr(module, manifest.response_model, None)
            except Exception as schema_exc:
                logger.warning(
                    "Could not auto-resolve response_model '%s' for stage '%s': %s",
                    manifest.response_model,
                    stage,
                    schema_exc,
                )

        s_id = story_id or story_id_ctx.get("")
        a_id = article_id or article_id_ctx.get("")

        prompt_text = system_prompt + "\n" + user_prompt

        # Cache check (only for cacheable prompts)
        if manifest.is_cacheable():
            cached_response = await ai_cache.get(
                capability=stage,
                model=cfg.model,
                prompt_version=manifest.version,
                prompt_text=prompt_text,
                temperature=cfg.temperature,
            )
            if cached_response is not None:
                newsiq_ai_gateway_cache_total.labels(capability=stage, status="hit").inc()
                parsed = None
                if resolved_schema:
                    try:
                        parsed = resolved_schema.model_validate(cached_response["parsed"])
                    except Exception as e:
                        logger.warning("Cache deserialization failed for stage '%s': %s", stage, e)

                try:
                    import hashlib

                    input_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
                    decision = None
                    confidence = None
                    if parsed:
                        if hasattr(parsed, "same_event"):
                            decision = str(getattr(parsed, "same_event"))
                        elif hasattr(parsed, "has_hallucinations"):
                            decision = (
                                "hallucination_detected"
                                if getattr(parsed, "has_hallucinations")
                                else "clean"
                            )
                        if hasattr(parsed, "confidence"):
                            confidence = float(getattr(parsed, "confidence"))

                    unsupported_claims_count = None
                    missing_citations_count = None
                    contradictions_count = None
                    bias_corrections_count = None
                    reflection_confidence = None
                    if stage == "summary_reflection" and parsed:
                        unsupported_claims_count = len(getattr(parsed, "invented_facts", []))
                        missing_citations_count = len(getattr(parsed, "omitted_critical_facts", []))
                        contradictions_count = (
                            1 if getattr(parsed, "contradicts_graph", False) else 0
                        )
                        reflection_confidence = (
                            1.0 if not getattr(parsed, "has_hallucinations", False) else 0.0
                        )

                    import uuid

                    await self._persist_execution_record(
                        execution_id=uuid.uuid4(),
                        stage=stage,
                        provider=cached_response["provider"],
                        model=cached_response["model"],
                        capability=cfg.model,
                        prompt_name=stage,
                        prompt_version=manifest.version,
                        temperature=cfg.temperature,
                        input_tokens=0,
                        output_tokens=0,
                        latency_ms=0.0,
                        cost=0.0,
                        cache_hit=True,
                        retry_count=0,
                        fallback_count=0,
                        schema_repaired=False,
                        decision=decision,
                        confidence=confidence,
                        input_hash=input_hash,
                        story_id=s_id,
                        article_id=a_id,
                        unsupported_claims_count=unsupported_claims_count,
                        missing_citations_count=missing_citations_count,
                        contradictions_count=contradictions_count,
                        bias_corrections_count=bias_corrections_count,
                        reflection_confidence=reflection_confidence,
                    )
                except Exception as cache_rec_exc:
                    logger.warning("Failed to emit cache hit execution record: %s", cache_rec_exc)

                return GatewayResponse(
                    content=cached_response["content"],
                    parsed=parsed,
                    provider=cached_response["provider"],
                    model=cached_response["model"],
                    latency_ms=0.0,
                    cost_usd=0.0,
                )

        newsiq_ai_gateway_cache_total.labels(capability=stage, status="miss").inc()

        # Build fallback chain from manifest: preferred_model + fallback_models
        # Skip models already known to be out of quota. Without this a stage
        # whose preferred model is exhausted spends nine calls and ~7s of
        # backoff on Gemini before reaching a Bedrock fallback that would have
        # answered immediately.
        all_models = await filter_healthy([cfg.model] + list(cfg.fallback_models))
        last_error: Exception | None = None

        for idx, model_name in enumerate(all_models):
            chain = capability_router.get_model_route(model_name)
            level_name = "primary" if idx == 0 else "fallback" if idx == 1 else "lastFallback"

            # A model whose quota is spent must abandon the rest of its chain,
            # not just the rest of its attempts. MODEL_FALLBACKS lists three
            # entries per Gemini model, all provider="gemini", and the request
            # below sends `model_name` rather than route_cfg["model"] — so with
            # a single Gemini key in the pool the three entries are the same
            # key, the same model, three times. Breaking only the attempt loop
            # left a 429'd model burning all three before moving on.
            model_exhausted = False

            for client, api_key, route_cfg in chain:
                provider_name = route_cfg["provider"]

                newsiq_provider_fallback_executions_total.labels(
                    provider=provider_name, stage=stage, level=level_name
                ).inc()

                max_attempts = 3
                backoff = 1.0

                for attempt in range(max_attempts):
                    schema_repaired = False
                    try:
                        req = GatewayRequest(
                            model=model_name,
                            messages=messages,
                            temperature=cfg.temperature,
                            response_format=resolved_schema,
                            stage=stage,
                            story_id=s_id,
                            article_id=a_id,
                            timeout=cfg.timeout_seconds,
                        )

                        logger.info(
                            "Gateway [stage=%s] provider=%s model=%s (attempt %d/%d)",
                            stage,
                            provider_name,
                            model_name,
                            attempt + 1,
                            max_attempts,
                        )

                        async with track_llm_call(
                            provider=provider_name,
                            model=model_name,
                            stage=stage,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            temperature=cfg.temperature,
                            story_id=s_id,
                            article_id=a_id,
                        ) as trace_call:
                            response = await client.generate(req, api_key)

                            trace_call.response_text = response.content or response.error
                            trace_call.input_tokens = response.input_tokens
                            trace_call.output_tokens = response.output_tokens
                            trace_call.total_tokens = response.total_tokens

                            if response.error:
                                trace_call.status = "error"
                                trace_call.error = response.error
                                raise ProviderUnavailableError(response.error)

                            if resolved_schema and response.parsed is None:
                                try:
                                    data = json.loads(response.content)
                                    cleaned = clean_json_for_schema(data, resolved_schema)
                                    response.parsed = resolved_schema.model_validate(cleaned)
                                    schema_repaired = True
                                except (ValueError, PydanticValidationError) as val_err:
                                    newsiq_ai_gateway_validation_failures_total.labels(
                                        capability=stage, model=model_name
                                    ).inc()
                                    raise ValidationError(
                                        f"[{stage}] Response validation failed: {val_err}"
                                    )

                            cost = self._calculate_cost(
                                model_name, response.input_tokens, response.output_tokens
                            )
                            response.cost_usd = cost
                            trace_call.cost_usd = cost

                            if s_id:
                                try:
                                    await cost_budget_manager.add_story_cost(s_id, cost)
                                except Exception as cost_exc:
                                    logger.warning("Failed to record story cost: %s", cost_exc)

                        # Prometheus metrics
                        try:
                            newsiq_prompt_executions_total.labels(
                                stage=stage, version=manifest.version, status="success"
                            ).inc()
                            newsiq_prompt_latency_seconds.labels(
                                stage=stage, version=manifest.version
                            ).observe(response.latency_ms / 1000.0)
                            newsiq_prompt_tokens_total.labels(
                                stage=stage, version=manifest.version, token_type="input"
                            ).inc(response.input_tokens)
                            newsiq_prompt_tokens_total.labels(
                                stage=stage, version=manifest.version, token_type="output"
                            ).inc(response.output_tokens)
                        except Exception as prom_exc:
                            logger.debug("Prompt metrics failed (stage=%s): %s", stage, prom_exc)

                        newsiq_ai_gateway_calls_total.labels(
                            provider=provider_name,
                            model=model_name,
                            capability=stage,
                            status="success",
                        ).inc()
                        newsiq_ai_gateway_cost_usd.labels(
                            provider=provider_name, model=model_name, capability=stage
                        ).inc(cost)

                        capability_router.health_trackers[provider_name].report_success()

                        # Store in cache if cacheable
                        if manifest.is_cacheable():
                            await ai_cache.set(
                                capability=stage,
                                model=model_name,
                                prompt_version=manifest.version,
                                prompt_text=prompt_text,
                                response_data={
                                    "content": response.content,
                                    "parsed": response.parsed.model_dump(mode="json")
                                    if isinstance(response.parsed, BaseModel)
                                    else response.parsed,
                                    "provider": provider_name,
                                    "model": model_name,
                                },
                                temperature=cfg.temperature,
                            )

                        # Emit execution record for cache miss (Phase 1)
                        try:
                            import hashlib

                            input_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
                            decision = None
                            confidence = None
                            parsed = response.parsed
                            if parsed:
                                if hasattr(parsed, "same_event"):
                                    decision = str(getattr(parsed, "same_event"))
                                elif hasattr(parsed, "has_hallucinations"):
                                    decision = (
                                        "hallucination_detected"
                                        if getattr(parsed, "has_hallucinations")
                                        else "clean"
                                    )
                                if hasattr(parsed, "confidence"):
                                    confidence = float(getattr(parsed, "confidence"))

                            unsupported_claims_count = None
                            missing_citations_count = None
                            contradictions_count = None
                            bias_corrections_count = None
                            reflection_confidence = None
                            if stage == "summary_reflection" and parsed:
                                unsupported_claims_count = len(
                                    getattr(parsed, "invented_facts", [])
                                )
                                missing_citations_count = len(
                                    getattr(parsed, "omitted_critical_facts", [])
                                )
                                contradictions_count = (
                                    1 if getattr(parsed, "contradicts_graph", False) else 0
                                )
                                reflection_confidence = (
                                    1.0 if not getattr(parsed, "has_hallucinations", False) else 0.0
                                )

                            import uuid

                            await self._persist_execution_record(
                                execution_id=uuid.uuid4(),
                                stage=stage,
                                provider=provider_name,
                                model=model_name,
                                capability=cfg.model,
                                prompt_name=stage,
                                prompt_version=manifest.version,
                                temperature=cfg.temperature,
                                input_tokens=response.input_tokens,
                                output_tokens=response.output_tokens,
                                latency_ms=response.latency_ms,
                                cost=cost,
                                cache_hit=False,
                                retry_count=attempt,
                                fallback_count=idx,
                                schema_repaired=schema_repaired,
                                decision=decision,
                                confidence=confidence,
                                input_hash=input_hash,
                                story_id=s_id,
                                article_id=a_id,
                                unsupported_claims_count=unsupported_claims_count,
                                missing_citations_count=missing_citations_count,
                                contradictions_count=contradictions_count,
                                bias_corrections_count=bias_corrections_count,
                                reflection_confidence=reflection_confidence,
                            )
                        except Exception as emit_exc:
                            logger.warning("Failed to emit AI execution record: %s", emit_exc)

                        return response

                    except ValidationError as ve:
                        last_error = ve
                        newsiq_ai_gateway_retries_total.labels(
                            provider=provider_name,
                            model=model_name,
                            capability=stage,
                            reason="validation_failure",
                        ).inc()
                        if attempt == max_attempts - 1:
                            break
                        await asyncio.sleep(backoff)
                        backoff *= 2.0

                    except (
                        RateLimitError,
                        TimeoutError,
                        ProviderUnavailableError,
                        AuthenticationError,
                    ) as err:
                        logger.warning(
                            "Gateway [stage=%s] provider=%s model=%s failed: %s",
                            stage,
                            provider_name,
                            model_name,
                            err,
                        )
                        if not isinstance(err, RateLimitError):
                            capability_router.health_trackers[provider_name].report_failure(
                                str(err)
                            )
                        try:
                            newsiq_prompt_executions_total.labels(
                                stage=stage, version=manifest.version, status="failed"
                            ).inc()
                        except Exception as metrics_err:
                            logger.debug(
                                "Failed to record prompt execution failure metric [stage=%s, provider=%s, model=%s]: %s",
                                stage,
                                provider_name,
                                model_name,
                                metrics_err,
                            )
                        newsiq_ai_gateway_calls_total.labels(
                            provider=provider_name,
                            model=model_name,
                            capability=stage,
                            status="error",
                        ).inc()
                        if isinstance(err, TimeoutError):
                            newsiq_ai_gateway_timeouts_total.labels(
                                provider=provider_name, model=model_name, capability=stage
                            ).inc()
                        newsiq_ai_gateway_retries_total.labels(
                            provider=provider_name,
                            model=model_name,
                            capability=stage,
                            reason=err.__class__.__name__,
                        ).inc()
                        last_error = err

                        # A spent quota does not refill during a backoff sleep.
                        # Record the model as exhausted and abandon it now, so
                        # the chain reaches a model that can actually answer.
                        if isinstance(err, RateLimitError):
                            await mark_exhausted(model_name, str(err))
                            model_exhausted = True
                            break

                        await asyncio.sleep(backoff)
                        backoff *= 2.0

                if model_exhausted:
                    break

        # Emit failed execution record (Phase 1)
        try:
            import hashlib

            input_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
            import uuid

            await self._persist_execution_record(
                execution_id=uuid.uuid4(),
                stage=stage,
                provider=None,
                model=None,
                capability=cfg.model,
                prompt_name=stage,
                prompt_version=manifest.version,
                temperature=cfg.temperature,
                input_tokens=0,
                output_tokens=0,
                latency_ms=0.0,
                cost=0.0,
                cache_hit=False,
                retry_count=max_attempts,
                fallback_count=len(all_models),
                schema_repaired=False,
                decision="failed",
                confidence=None,
                input_hash=input_hash,
                story_id=s_id,
                article_id=a_id,
            )
        except Exception as record_exc:
            logger.warning("Failed to emit failed execution record: %s", record_exc)

        raise AIGatewayError(f"All providers failed for stage='{stage}'. Last error: {last_error}")

    async def generate(
        self,
        capability: str,
        prompt_variables: dict[str, Any],
        schema: type[BaseModel] | None = None,
        temperature: float | None = None,
        story_id: str = "",
        article_id: str = "",
        variant: str | None = None,
    ) -> GatewayResponse:
        """Execute a text generation call through the gateway fallback chain.

        .. deprecated::
            Use ``generate_stage(stage=..., prompt_variables=...)`` instead.
            Model, temperature, and routing are now resolved from PromptRepository.
            This method will be removed after all callers are migrated.
        """
        logger.warning(
            "DEPRECATION: ai_gateway.generate(capability='%s') is deprecated. "
            "Migrate to ai_gateway.generate_stage(stage='%s', prompt_variables={...}). "
            "This method will be removed in a future release.",
            capability,
            capability,
        )

        # 1. Load prompt template
        prompt_template = prompt_registry.get(capability, variant)
        messages = prompt_template.messages(**prompt_variables)

        system_prompt = prompt_template.system
        user_prompt = prompt_template.user_message(**prompt_variables)["content"]
        prompt_text = system_prompt + "\n" + user_prompt

        # Set IDs in context if provided
        s_id = story_id or story_id_ctx.get("")
        a_id = article_id or article_id_ctx.get("")

        # 2. Retrieve capability execution chain
        chain = capability_router.get_route(capability)

        # 3. Check Cache (Exact match check on first model in chain)
        first_client, first_key, first_cfg = chain[0]
        temp = temperature if temperature is not None else first_cfg["temperature"]
        model_name = first_cfg["model"]

        cached_response = await ai_cache.get(
            capability=capability,
            model=model_name,
            prompt_version=prompt_template.version,
            prompt_text=prompt_text,
            temperature=temp,
        )

        if cached_response is not None:
            newsiq_ai_gateway_cache_total.labels(capability=capability, status="hit").inc()
            parsed = None
            if schema:
                try:
                    parsed = schema.model_validate(cached_response["parsed"])
                except Exception as e:
                    logger.warning("Cache deserialization failed: %s", e)

            try:
                import hashlib

                input_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
                decision = None
                confidence = None
                if parsed:
                    if hasattr(parsed, "same_event"):
                        decision = str(getattr(parsed, "same_event"))
                    elif hasattr(parsed, "has_hallucinations"):
                        decision = (
                            "hallucination_detected"
                            if getattr(parsed, "has_hallucinations")
                            else "clean"
                        )
                    if hasattr(parsed, "confidence"):
                        confidence = float(getattr(parsed, "confidence"))

                unsupported_claims_count = None
                missing_citations_count = None
                contradictions_count = None
                bias_corrections_count = None
                reflection_confidence = None
                if capability == "summary_reflection" and parsed:
                    unsupported_claims_count = len(getattr(parsed, "invented_facts", []))
                    missing_citations_count = len(getattr(parsed, "omitted_critical_facts", []))
                    contradictions_count = 1 if getattr(parsed, "contradicts_graph", False) else 0
                    reflection_confidence = (
                        1.0 if not getattr(parsed, "has_hallucinations", False) else 0.0
                    )

                import uuid

                await self._persist_execution_record(
                    execution_id=uuid.uuid4(),
                    stage=capability,
                    provider=cached_response["provider"],
                    model=cached_response["model"],
                    capability=capability,
                    prompt_name=capability,
                    prompt_version=prompt_template.version,
                    temperature=temp,
                    input_tokens=0,
                    output_tokens=0,
                    latency_ms=0.0,
                    cost=0.0,
                    cache_hit=True,
                    retry_count=0,
                    fallback_count=0,
                    schema_repaired=False,
                    decision=decision,
                    confidence=confidence,
                    input_hash=input_hash,
                    story_id=s_id,
                    article_id=a_id,
                    unsupported_claims_count=unsupported_claims_count,
                    missing_citations_count=missing_citations_count,
                    contradictions_count=contradictions_count,
                    bias_corrections_count=bias_corrections_count,
                    reflection_confidence=reflection_confidence,
                )
            except Exception as cache_rec_exc:
                logger.warning("Failed to emit cache hit execution record: %s", cache_rec_exc)

            return GatewayResponse(
                content=cached_response["content"],
                parsed=parsed,
                provider=cached_response["provider"],
                model=cached_response["model"],
                latency_ms=0.0,
                cost_usd=0.0,
            )

        newsiq_ai_gateway_cache_total.labels(capability=capability, status="miss").inc()

        # 4. Iterate through the fallback chain
        last_error: Exception | None = None
        for idx, (client, api_key, route_cfg) in enumerate(chain):
            provider_name = route_cfg["provider"]
            model_name = route_cfg["model"]
            timeout = route_cfg["timeout"]
            temp = temperature if temperature is not None else route_cfg["temperature"]
            level_name = "primary" if idx == 0 else "fallback" if idx == 1 else "lastFallback"

            # Record fallback execution
            newsiq_provider_fallback_executions_total.labels(
                provider=provider_name, stage=capability, level=level_name
            ).inc()

            # Retries logic on provider level (max retries = 2, exponential backoff)
            max_attempts = 3  # 1 initial + 2 retries
            backoff = 1.0

            for attempt in range(max_attempts):
                schema_repaired = False
                try:
                    req = GatewayRequest(
                        model=model_name,
                        messages=messages,
                        temperature=temp,
                        response_format=schema,
                        stage=capability,
                        story_id=s_id,
                        article_id=a_id,
                        timeout=timeout,
                    )

                    logger.info(
                        "Gateway call: provider=%s model=%s capability=%s (attempt %d/%d)",
                        provider_name,
                        model_name,
                        capability,
                        attempt + 1,
                        max_attempts,
                    )

                    # Wrap in DB tracing context manager
                    async with track_llm_call(
                        provider=provider_name,
                        model=model_name,
                        stage=capability,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=temp,
                        story_id=s_id,
                        article_id=a_id,
                    ) as trace_call:
                        response = await client.generate(req, api_key)

                        # Update trace call
                        trace_call.response_text = response.content or response.error
                        trace_call.input_tokens = response.input_tokens
                        trace_call.output_tokens = response.output_tokens
                        trace_call.total_tokens = response.total_tokens

                        if response.error:
                            trace_call.status = "error"
                            trace_call.error = response.error
                            raise ProviderUnavailableError(response.error)

                        # Validate output schema if requested
                        if schema and response.parsed is None:
                            # Try to parse text as JSON manually if parsed field is empty
                            try:
                                data = json.loads(response.content)
                                cleaned_data = clean_json_for_schema(data, schema)
                                response.parsed = schema.model_validate(cleaned_data)
                                schema_repaired = True
                            except (ValueError, PydanticValidationError) as val_err:
                                newsiq_ai_gateway_validation_failures_total.labels(
                                    capability=capability, model=model_name
                                ).inc()
                                raise ValidationError(
                                    f"Response validation failed against schema: {val_err}"
                                )

                        # Calculate and set cost
                        cost = self._calculate_cost(
                            model_name, response.input_tokens, response.output_tokens
                        )
                        response.cost_usd = cost
                        trace_call.cost_usd = cost

                        # Update story cost budget (awaited directly — create_task() can be
                        # silently dropped when the Celery worker loop exits before the task runs)
                        if s_id:
                            try:
                                await cost_budget_manager.add_story_cost(s_id, cost)
                            except Exception as cost_exc:
                                logger.warning("Failed to record story cost: %s", cost_exc)

                    # Record prompt metrics on success
                    try:
                        newsiq_prompt_executions_total.labels(
                            stage=capability, version=prompt_template.version, status="success"
                        ).inc()
                        newsiq_prompt_latency_seconds.labels(
                            stage=capability, version=prompt_template.version
                        ).observe(response.latency_ms / 1000.0)
                        newsiq_prompt_tokens_total.labels(
                            stage=capability, version=prompt_template.version, token_type="input"
                        ).inc(response.input_tokens)
                        newsiq_prompt_tokens_total.labels(
                            stage=capability, version=prompt_template.version, token_type="output"
                        ).inc(response.output_tokens)
                    except Exception as prom_exc:
                        logger.debug("Prompt metrics recording failed (success path): %s", prom_exc)

                    # Record metrics
                    newsiq_ai_gateway_calls_total.labels(
                        provider=provider_name,
                        model=model_name,
                        capability=capability,
                        status="success",
                    ).inc()
                    newsiq_ai_gateway_cost_usd.labels(
                        provider=provider_name, model=model_name, capability=capability
                    ).inc(cost)
                    newsiq_ai_gateway_tokens_total.labels(
                        provider=provider_name,
                        model=model_name,
                        capability=capability,
                        token_type="input",
                    ).inc(response.input_tokens)
                    newsiq_ai_gateway_tokens_total.labels(
                        provider=provider_name,
                        model=model_name,
                        capability=capability,
                        token_type="output",
                    ).inc(response.output_tokens)
                    newsiq_ai_gateway_latency_seconds.labels(
                        provider=provider_name, model=model_name, capability=capability
                    ).observe(response.latency_ms / 1000.0)

                    # Report health check success to capability router
                    capability_router.health_trackers[provider_name].report_success()

                    # Save to Redis Cache (Exact hash)
                    cache_data = {
                        "content": response.content,
                        "parsed": response.parsed.model_dump(mode="json")
                        if isinstance(response.parsed, BaseModel)
                        else response.parsed,
                        "provider": provider_name,
                        "model": model_name,
                    }
                    await ai_cache.set(
                        capability=capability,
                        model=model_name,
                        prompt_version=prompt_template.version,
                        prompt_text=prompt_text,
                        response_data=cache_data,
                        temperature=temp,
                    )

                    # Emit execution record for cache miss (Phase 1)
                    try:
                        import hashlib

                        input_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
                        decision = None
                        confidence = None
                        parsed = response.parsed
                        if parsed:
                            if hasattr(parsed, "same_event"):
                                decision = str(getattr(parsed, "same_event"))
                            elif hasattr(parsed, "has_hallucinations"):
                                decision = (
                                    "hallucination_detected"
                                    if getattr(parsed, "has_hallucinations")
                                    else "clean"
                                )
                            if hasattr(parsed, "confidence"):
                                confidence = float(getattr(parsed, "confidence"))

                        unsupported_claims_count = None
                        missing_citations_count = None
                        contradictions_count = None
                        bias_corrections_count = None
                        reflection_confidence = None
                        if capability == "summary_reflection" and parsed:
                            unsupported_claims_count = len(getattr(parsed, "invented_facts", []))
                            missing_citations_count = len(
                                getattr(parsed, "omitted_critical_facts", [])
                            )
                            contradictions_count = (
                                1 if getattr(parsed, "contradicts_graph", False) else 0
                            )
                            reflection_confidence = (
                                1.0 if not getattr(parsed, "has_hallucinations", False) else 0.0
                            )

                        import uuid

                        await self._persist_execution_record(
                            execution_id=uuid.uuid4(),
                            stage=capability,
                            provider=provider_name,
                            model=model_name,
                            capability=capability,
                            prompt_name=capability,
                            prompt_version=prompt_template.version,
                            temperature=temp,
                            input_tokens=response.input_tokens,
                            output_tokens=response.output_tokens,
                            latency_ms=response.latency_ms,
                            cost=cost,
                            cache_hit=False,
                            retry_count=attempt,
                            fallback_count=idx,
                            schema_repaired=schema_repaired,
                            decision=decision,
                            confidence=confidence,
                            input_hash=input_hash,
                            story_id=s_id,
                            article_id=a_id,
                            unsupported_claims_count=unsupported_claims_count,
                            missing_citations_count=missing_citations_count,
                            contradictions_count=contradictions_count,
                            bias_corrections_count=bias_corrections_count,
                            reflection_confidence=reflection_confidence,
                        )
                    except Exception as emit_exc:
                        logger.warning("Failed to emit AI execution record: %s", emit_exc)

                    return response

                except ValidationError as ve:
                    # Do not retry API validation issues, but we can retry on LLM validation failures
                    # maximum 2 times for schema failures
                    logger.warning("LLM output schema validation failed: %s. Attempting retry.", ve)
                    last_error = ve
                    newsiq_ai_gateway_retries_total.labels(
                        provider=provider_name,
                        model=model_name,
                        capability=capability,
                        reason="validation_failure",
                    ).inc()
                    if attempt == max_attempts - 1:
                        # Break and try next provider if we exhausted attempts
                        break
                    await asyncio.sleep(backoff)
                    backoff *= 2.0

                except (
                    RateLimitError,
                    TimeoutError,
                    ProviderUnavailableError,
                    AuthenticationError,
                ) as err:
                    # Map to standard gateway exceptions and report failure to tracker
                    logger.warning(
                        "Gateway attempt failed for provider=%s model=%s capability=%s: %s",
                        provider_name,
                        model_name,
                        capability,
                        err,
                    )
                    # Rate limit errors are transient quota limits; do not trip the circuit breaker for them globally
                    if not isinstance(err, RateLimitError):
                        capability_router.health_trackers[provider_name].report_failure(str(err))
                    else:
                        logger.info(
                            "Gateway: RateLimitError encountered for %s. Skipping circuit breaker health degradation.",
                            provider_name,
                        )
                    last_error = err

                    # Record prompt metrics on failure
                    try:
                        newsiq_prompt_executions_total.labels(
                            stage=capability, version=prompt_template.version, status="failed"
                        ).inc()
                    except Exception as prom_exc:
                        logger.debug("Prompt metrics recording failed (failure path): %s", prom_exc)

                    # Metric tracking
                    newsiq_ai_gateway_calls_total.labels(
                        provider=provider_name,
                        model=model_name,
                        capability=capability,
                        status="error",
                    ).inc()
                    if isinstance(err, TimeoutError):
                        newsiq_ai_gateway_timeouts_total.labels(
                            provider=provider_name, model=model_name, capability=capability
                        ).inc()

                    newsiq_ai_gateway_retries_total.labels(
                        provider=provider_name,
                        model=model_name,
                        capability=capability,
                        reason=err.__class__.__name__,
                    ).inc()

                    # Wait and backoff
                    await asyncio.sleep(backoff)
                    backoff *= 2.0

        # Emit failed execution record (Phase 1)
        try:
            import hashlib

            input_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
            import uuid

            await self._persist_execution_record(
                execution_id=uuid.uuid4(),
                stage=capability,
                provider=None,
                model=None,
                capability=capability,
                prompt_name=capability,
                prompt_version=prompt_template.version,
                temperature=temp,
                input_tokens=0,
                output_tokens=0,
                latency_ms=0.0,
                cost=0.0,
                cache_hit=False,
                retry_count=max_attempts,
                fallback_count=len(chain),
                schema_repaired=False,
                decision="failed",
                confidence=None,
                input_hash=input_hash,
                story_id=s_id,
                article_id=a_id,
            )
        except Exception as record_exc:
            logger.warning("Failed to emit failed execution record: %s", record_exc)

        raise AIGatewayError(f"All AI Gateway providers in chain failed. Last error: {last_error}")

    async def stream(
        self,
        capability: str,
        prompt_variables: dict[str, Any],
        temperature: float | None = None,
        story_id: str = "",
        article_id: str = "",
        variant: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream raw response tokens from the primary provider."""
        prompt_template = prompt_registry.get(capability, variant)
        messages = prompt_template.messages(**prompt_variables)

        s_id = story_id or story_id_ctx.get("")
        a_id = article_id or article_id_ctx.get("")

        chain = capability_router.get_route(capability)
        client, api_key, route_cfg = chain[0]  # Try streaming only on primary provider
        model_name = route_cfg["model"]
        timeout = route_cfg["timeout"]
        temp = temperature if temperature is not None else route_cfg["temperature"]

        req = GatewayRequest(
            model=model_name,
            messages=messages,
            temperature=temp,
            stage=capability,
            story_id=s_id,
            article_id=a_id,
            timeout=timeout,
        )

        async for token in client.stream(req, api_key):
            yield token

    async def health(self) -> dict[str, Any]:
        """Expose current health status of all providers."""
        results = {}
        for provider, tracker in capability_router.health_trackers.items():
            results[provider] = {
                "healthy": tracker.healthy,
                "consecutive_failures": tracker.consecutive_failures,
                "disabled_until": tracker.disabled_until.isoformat()
                if tracker.disabled_until
                else None,
            }
        return results

    async def embeddings(self, text: str, capability: str = "embedding") -> list[float]:
        """Generate a text embedding, never mixing embedding spaces.

        Embeddings are NOT interchangeable across models the way chat
        completions are. Every article vector lands in one shared Qdrant
        collection and is compared by cosine similarity, so a vector from a
        different model is not "slightly worse" — it is noise. Measured on the
        models proposed for this chain, the SAME sentence embedded by
        all-mpnet-base-v2 vs qwen3-embedding-8b scores cosine 0.02, while two
        DIFFERENT paraphrases within one model score 0.84-0.92. Stage B's
        match threshold is ~0.67.

        Falling back to another model would therefore silently produce
        articles that can never cluster — indistinguishable from success. So
        the chain may only span providers serving the SAME model; entries
        naming a different model are skipped, and if none remain the call
        fails so the article is retried later with its embedding_status intact.
        """
        # Refuse here rather than at import. A bad embedding setting must fail
        # embeddings, not crash-loop every container and take the product down.
        from app.ai.config import EMBEDDING_CONFIG_ERROR

        if EMBEDDING_CONFIG_ERROR:
            raise AIGatewayError(f"Embedding configuration invalid: {EMBEDDING_CONFIG_ERROR}")

        chain = capability_router.get_route(capability)
        if not chain:
            raise AIGatewayError("No embedding route configured.")

        # The first entry defines the pipeline's embedding space for this call.
        expected_model = chain[0][2].get("model")
        last_err: Exception | None = None
        attempted = 0

        for client, api_key, route_cfg in chain:
            route_model = route_cfg.get("model")
            if route_model != expected_model:
                logger.debug(
                    "Skipping embedding fallback %s/%s: different model from primary "
                    "%s (mixing embedding spaces corrupts clustering).",
                    route_cfg.get("provider"),
                    route_model,
                    expected_model,
                )
                continue

            attempted += 1
            try:
                return await client.embeddings(text, api_key, model=route_model)
            except Exception as e:
                logger.warning(
                    "Embedding failed for provider %s (model %s): %s",
                    route_cfg.get("provider"),
                    route_model,
                    e,
                )
                last_err = e

        raise AIGatewayError(
            f"All {attempted} same-model embedding provider(s) failed for "
            f"'{expected_model}'. Last error: {last_err}"
        )

    def count_tokens(self, text: str, capability: str = "summary") -> int:
        """Count tokens of the text locally using the primary provider tokenizer."""
        chain = capability_router.get_route(capability)
        client, _, _ = chain[0]
        return client.count_tokens(text)

    def _apply_token_budget_guard(
        self, messages: list[dict[str, Any]], model_name: str
    ) -> list[dict[str, Any]]:
        """Count prompt tokens and truncate if budget for Pro models is exceeded."""
        from app.core.config import settings

        if "pro" not in model_name.lower():
            return messages

        full_text = "\n".join(msg.get("content", "") for msg in messages)
        total_tokens = self.count_tokens(full_text)

        if total_tokens <= settings.MAX_PRO_MODEL_TOKENS:
            return messages

        logger.warning(
            "Pro model token budget exceeded (%d > %d tokens) for model %s. Truncating content.",
            total_tokens,
            settings.MAX_PRO_MODEL_TOKENS,
            model_name,
        )

        # Find the longest message (typically the user prompt)
        longest_idx = -1
        longest_len = -1
        for idx, msg in enumerate(messages):
            content_len = len(msg.get("content", ""))
            if content_len > longest_len:
                longest_len = content_len
                longest_idx = idx

        if longest_idx != -1:
            # Simple heuristic truncation: truncate character length by half and re-evaluate
            msg = messages[longest_idx]
            content = msg.get("content", "")
            while total_tokens > settings.MAX_PRO_MODEL_TOKENS and len(content) > 100:
                content = content[: int(len(content) * 0.8)]
                temp_messages = list(messages)
                temp_messages[longest_idx] = {"role": msg["role"], "content": content}
                full_text = "\n".join(m.get("content", "") for m in temp_messages)
                total_tokens = self.count_tokens(full_text)

            messages[longest_idx] = {
                "role": msg["role"],
                "content": content + "\n[TRUNCATED BY BUDGET GUARD]",
            }

        return messages

    async def execute_request(
        self,
        model: str,
        stage: str,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | type[BaseModel] | None = None,
        temperature: float = 0.1,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        story_id: str = "",
        article_id: str = "",
    ) -> GatewayResponse:
        """Execute custom requests (directly by model name) using the fallback routing logic.

        Used by Agno agents and services requiring non-templated generation.

        .. deprecated::
            For prompt-backed stages, use ``generate_stage(stage=..., prompt_variables=...)``.
            For agent-driven non-templated calls, this method will remain available
            until a dedicated agent entrypoint is introduced.
            This method logs a deprecation warning to track migration progress.
        """
        logger.warning(
            "DEPRECATION: ai_gateway.execute_request(model='%s', stage='%s') is deprecated. "
            "If this stage has a PromptManifest, migrate to generate_stage(stage='%s'). "
            "grep for 'execute_request' to find remaining callers.",
            model,
            stage,
            stage,
        )

        # 1. Resolve fallback chain for this model name
        chain = capability_router.get_model_route(model)

        s_id = story_id or story_id_ctx.get("")
        a_id = article_id or article_id_ctx.get("")

        # 2. Check Cache
        first_client, first_key, first_cfg = chain[0]
        model_name = first_cfg["model"]
        prompt_text = "\n".join(msg.get("content", "") for msg in messages)

        cached_response = await ai_cache.get(
            capability=stage,
            model=model_name,
            prompt_version="v_direct",
            prompt_text=prompt_text,
            temperature=temperature,
        )

        schema = None
        if response_format:
            if isinstance(response_format, type) and issubclass(response_format, BaseModel):
                schema = response_format

        if cached_response is not None:
            newsiq_ai_gateway_cache_total.labels(capability=stage, status="hit").inc()
            parsed = None
            if schema:
                try:
                    parsed = schema.model_validate(cached_response["parsed"])
                except Exception as e:
                    logger.warning("Cache deserialization failed: %s", e)

            return GatewayResponse(
                content=cached_response["content"],
                parsed=parsed,
                provider=cached_response["provider"],
                model=cached_response["model"],
                latency_ms=0.0,
                cost_usd=0.0,
            )

        newsiq_ai_gateway_cache_total.labels(capability=stage, status="miss").inc()

        # 3. Apply token budget guard for pro models
        messages = self._apply_token_budget_guard(messages, model_name)

        # 4. Iterate through fallback chain
        last_error: Exception | None = None
        for idx, (client, api_key, route_cfg) in enumerate(chain):
            provider_name = route_cfg["provider"]
            model_name = route_cfg["model"]
            timeout = route_cfg.get("timeout", 30.0)
            level_name = "primary" if idx == 0 else "fallback" if idx == 1 else "lastFallback"

            newsiq_provider_fallback_executions_total.labels(
                provider=provider_name, stage=stage, level=level_name
            ).inc()

            max_attempts = 3
            backoff = 1.0

            for attempt in range(max_attempts):
                try:
                    req = GatewayRequest(
                        model=model_name,
                        messages=messages,
                        temperature=temperature,
                        response_format=schema,
                        stage=stage,
                        story_id=s_id,
                        article_id=a_id,
                        timeout=timeout,
                    )

                    logger.info(
                        "Gateway execute: provider=%s model=%s stage=%s (attempt %d/%d)",
                        provider_name,
                        model_name,
                        stage,
                        attempt + 1,
                        max_attempts,
                    )

                    async with track_llm_call(
                        provider=provider_name,
                        model=model_name,
                        stage=stage,
                        system_prompt="",
                        user_prompt=prompt_text,
                        temperature=temperature,
                        story_id=s_id,
                        article_id=a_id,
                    ) as trace_call:
                        response = await client.generate(req, api_key)

                        trace_call.response_text = response.content or response.error
                        trace_call.input_tokens = response.input_tokens
                        trace_call.output_tokens = response.output_tokens
                        trace_call.total_tokens = response.total_tokens

                        if response.error:
                            trace_call.status = "error"
                            trace_call.error = response.error
                            raise ProviderUnavailableError(response.error)

                        if schema and response.parsed is None:
                            try:
                                data = json.loads(response.content)
                                cleaned_data = clean_json_for_schema(data, schema)
                                response.parsed = schema.model_validate(cleaned_data)
                            except (ValueError, PydanticValidationError) as val_err:
                                newsiq_ai_gateway_validation_failures_total.labels(
                                    capability=stage, model=model_name
                                ).inc()
                                raise ValidationError(
                                    f"Response validation failed against schema: {val_err}"
                                )

                        cost = self._calculate_cost(
                            model_name, response.input_tokens, response.output_tokens
                        )
                        response.cost_usd = cost
                        trace_call.cost_usd = cost

                        if s_id:
                            try:
                                await cost_budget_manager.add_story_cost(s_id, cost)
                            except Exception as cost_exc:
                                logger.warning("Failed to record story cost: %s", cost_exc)

                    # Metrics
                    newsiq_ai_gateway_calls_total.labels(
                        provider=provider_name, model=model_name, capability=stage, status="success"
                    ).inc()
                    newsiq_ai_gateway_cost_usd.labels(
                        provider=provider_name, model=model_name, capability=stage
                    ).inc(cost)

                    # Save to Cache
                    cache_data = {
                        "content": response.content,
                        "parsed": response.parsed.model_dump(mode="json")
                        if isinstance(response.parsed, BaseModel)
                        else response.parsed,
                        "provider": provider_name,
                        "model": model_name,
                    }
                    await ai_cache.set(
                        capability=stage,
                        model=model_name,
                        prompt_version="v_direct",
                        prompt_text=prompt_text,
                        response_data=cache_data,
                        temperature=temperature,
                    )

                    return response

                except ValidationError as ve:
                    logger.warning("LLM output validation failed: %s. Retrying.", ve)
                    last_error = ve
                    if attempt == max_attempts - 1:
                        break
                    await asyncio.sleep(backoff)
                    backoff *= 2.0
                except Exception as err:
                    logger.warning(
                        "Gateway execute attempt failed for provider=%s model=%s stage=%s: %s",
                        provider_name,
                        model_name,
                        stage,
                        err,
                    )
                    capability_router.health_trackers[provider_name].report_failure(str(err))
                    last_error = err
                    await asyncio.sleep(backoff)
                    backoff *= 2.0

        raise AIGatewayError(
            f"All AI Gateway providers failed in execute_request fallback. Last error: {last_error}"
        )

    def execute_request_sync(
        self,
        model: str,
        stage: str,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | type[BaseModel] | None = None,
        temperature: float = 0.1,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        story_id: str = "",
        article_id: str = "",
    ) -> GatewayResponse:
        """Synchronously execute custom requests through the gateway fallback chain."""
        import anyio

        return anyio.from_thread.run(
            self.execute_request,
            model,
            stage,
            messages,
            response_format,
            temperature,
            tools,
            tool_choice,
            story_id,
            article_id,
        )


# Singleton Gateway
ai_gateway = AIGateway()
