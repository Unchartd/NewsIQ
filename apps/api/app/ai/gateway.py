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
from app.ai.prompts.registry import prompt_registry
from app.ai.router.capability_router import capability_router
from app.core.trace import article_id_ctx, story_id_ctx, track_llm_call
from app.services.cost_budget import cost_budget_manager

logger = logging.getLogger(__name__)


# Cost pricing per million tokens
PRICING_TABLE = {
    # Gemini
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
    "gemini-3.1-flash-lite": {"input": 0.075, "output": 0.30},
    "text-embedding-004": {"input": 0.025, "output": 0.0},
    # NVIDIA DeepSeek V4 Flash / Pro (Enterprise estimates or flat free)
    "deepseek-ai/deepseek-v4-flash": {"input": 0.14, "output": 0.28},
    "deepseek-ai/deepseek-v4-pro": {"input": 0.55, "output": 2.19},
    "nvidia/llama-3.2-nv-embedqa-4b-v1": {"input": 0.0, "output": 0.0},
    # OpenRouter fallbacks
    "deepseek/deepseek-chat": {"input": 0.14, "output": 0.28},
    "qwen/qwen-2.5-72b-instruct": {"input": 0.40, "output": 0.40},
    "nomic/nomic-embed-text-v1.5": {"input": 0.0, "output": 0.0},
}


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
    if "summary" in data:
        s_val = data["summary"]
        if "one_line_summary" not in data or not data["one_line_summary"]:
            data["one_line_summary"] = s_val
        if "short_summary" not in data or not data["short_summary"]:
            data["short_summary"] = s_val
        if "detailed_summary" not in data or not data["detailed_summary"]:
            data["detailed_summary"] = s_val

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
        """Execute a text generation call through the gateway fallback chain."""
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
                    capability_router.health_trackers[provider_name].report_failure(str(err))
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
        """Generate text embeddings using the routing configuration."""
        chain = capability_router.get_route(capability)
        last_err = None

        for client, api_key, route_cfg in chain:
            provider_name = route_cfg["provider"]
            try:
                return await client.embeddings(text, api_key)
            except Exception as e:
                logger.warning("Embedding failed for provider %s: %s", provider_name, e)
                last_err = e

        raise AIGatewayError(f"All embedding providers failed. Last error: {last_err}")

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
        """
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
