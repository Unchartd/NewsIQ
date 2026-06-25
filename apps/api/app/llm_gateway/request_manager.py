import logging
from contextvars import ContextVar
from typing import Any

from pydantic import BaseModel

from app.core.trace import track_llm_call
from app.llm_gateway.base_provider import GatewayRequest, GatewayResponse
from app.llm_gateway.cost_tracker import CostTracker
from app.llm_gateway.fallback_chain import FallbackChain
from app.llm_gateway.health_monitor import HealthMonitor
from app.llm_gateway.metrics import (
    newsiq_llm_gateway_calls_total,
    newsiq_llm_gateway_cost_usd,
    newsiq_llm_gateway_key_cooldowns,
    newsiq_llm_gateway_latency_seconds,
    newsiq_llm_gateway_tokens_total,
)
from app.llm_gateway.provider_pool import APIKeyPool
from app.llm_gateway.provider_router import ProviderRouter
from app.llm_gateway.rate_limit_manager import RateLimitManager

logger = logging.getLogger(__name__)

# Context variables for replaying stages with model/provider overrides
model_override_ctx: ContextVar[str] = ContextVar("model_override", default="")
provider_override_ctx: ContextVar[str] = ContextVar("provider_override", default="")


class KeyCooldownError(RuntimeError):
    """Raised when an API key is selected but is currently cooling down."""

    pass


class RequestManager:
    """Orchestrates the lifecycle of LLM requests with automatic rate-limiting, key rotation, and fallbacks."""

    def __init__(self) -> None:
        self.key_pool = APIKeyPool()
        self.rate_limiter = RateLimitManager()
        self.health_monitor = HealthMonitor()
        self.cost_tracker = CostTracker()
        self.fallback_chain = FallbackChain()

        self.router = ProviderRouter(
            key_pool=self.key_pool,
            rate_limiter=self.rate_limiter,
            health_monitor=self.health_monitor,
        )

    def _extract_prompts(self, messages: list[dict[str, Any]]) -> tuple[str, str]:
        """Helper to extract system and user prompts for logging and database traces."""
        system_prompt = ""
        user_prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_prompt = content
            elif role == "user":
                user_prompt += content + "\n"
        return system_prompt.strip(), user_prompt.strip()

    async def execute_request(
        self,
        model: str,
        stage: str,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | type[BaseModel] | None = None,
        temperature: float = 0.0,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        story_id: str = "",
        article_id: str = "",
    ) -> GatewayResponse:
        """Asynchronously execute LLM requests through the gateway's fallback chain."""
        # 1. Retrieve prioritized list of provider/model fallbacks
        chain = self.fallback_chain.get_fallback_chain(model)

        provider_override = provider_override_ctx.get("")
        model_override = model_override_ctx.get("")
        if provider_override and model_override:
            chain = [{"provider": provider_override, "model": model_override}]

        system_prompt, user_prompt = self._extract_prompts(messages)

        errors_encountered = []

        # 2. Iterate through the fallback chain
        for entry in chain:
            provider_name = entry["provider"]
            model_name = entry["model"]
            selected_key = None

            try:
                # Select client and API Key
                selected_key, client = self.router.select_key_and_client(provider_name, model_name)

                # Check key cooldown
                if selected_key.is_cooling_down():
                    import asyncio
                    from datetime import datetime

                    remaining = (selected_key.cooldown_until - datetime.utcnow()).total_seconds()
                    if remaining > 0:
                        is_last_resort = entry == chain[-1] or (
                            len(chain) > 1
                            and entry == chain[-2]
                            and chain[-1]["provider"] == "mock"
                        )
                        if remaining <= 20.0 or is_last_resort:
                            logger.info(
                                "API key for %s is cooling down. Sleeping for %.2f seconds before proceeding.",
                                provider_name,
                                remaining,
                            )
                            await asyncio.sleep(remaining)
                        else:
                            # Record metric for key cooldown hit
                            newsiq_llm_gateway_key_cooldowns.labels(
                                provider=provider_name, key_hash=selected_key.get_masked()
                            ).inc()
                            raise KeyCooldownError(f"API key for {provider_name} is cooling down.")

                # Build the request payload
                request = GatewayRequest(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    response_format=response_format,
                    tools=tools,
                    tool_choice=tool_choice,
                    stage=stage,
                    story_id=story_id,
                    article_id=article_id,
                )

                # Record request hit in rate limit manager
                self.rate_limiter.record_request(selected_key.key)

                logger.info(
                    "Executing gateway call to provider=%s model=%s (stage=%s)",
                    provider_name,
                    model_name,
                    stage,
                )

                # 3. Call within DB distributed tracing span
                async with track_llm_call(
                    provider=provider_name,
                    model=model_name,
                    stage=stage,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    story_id=story_id,
                    article_id=article_id,
                ) as trace_call:
                    response = await client.execute(request, selected_key)

                    # Update database trace record details
                    trace_call.response_text = response.content or response.error
                    trace_call.input_tokens = response.input_tokens
                    trace_call.output_tokens = response.output_tokens
                    trace_call.total_tokens = response.total_tokens

                    if response.error:
                        trace_call.status = "error"
                        trace_call.error = response.error
                        raise RuntimeError(response.error)

                    # Compute cost and update details
                    cost = self.cost_tracker.calculate_cost(
                        model_name, response.input_tokens, response.output_tokens
                    )
                    response.cost_usd = cost
                    trace_call.cost_usd = cost

                # 4. Report health check success
                self.health_monitor.report_success(selected_key)

                # Expose metrics to Prometheus
                newsiq_llm_gateway_calls_total.labels(
                    provider=provider_name, model=model_name, stage=stage, status="success"
                ).inc()
                newsiq_llm_gateway_cost_usd.labels(
                    provider=provider_name, model=model_name, stage=stage
                ).inc(cost)
                newsiq_llm_gateway_tokens_total.labels(
                    provider=provider_name, model=model_name, stage=stage, token_type="input"
                ).inc(response.input_tokens)
                newsiq_llm_gateway_tokens_total.labels(
                    provider=provider_name, model=model_name, stage=stage, token_type="output"
                ).inc(response.output_tokens)
                newsiq_llm_gateway_latency_seconds.labels(
                    provider=provider_name, model=model_name, stage=stage
                ).observe(response.latency_ms / 1000.0)

                return response

            except KeyCooldownError as e:
                err_msg = str(e)
                errors_encountered.append(f"{provider_name}/{model_name}: {err_msg}")
                logger.warning(
                    "Gateway attempt failed for provider=%s model=%s: %s. Trying next fallback.",
                    provider_name,
                    model_name,
                    err_msg,
                )
                newsiq_llm_gateway_calls_total.labels(
                    provider=provider_name, model=model_name, stage=stage, status="error"
                ).inc()

            except Exception as e:
                err_msg = str(e)
                errors_encountered.append(f"{provider_name}/{model_name}: {err_msg}")
                logger.warning(
                    "Gateway attempt failed for provider=%s model=%s: %s. Trying next fallback.",
                    provider_name,
                    model_name,
                    err_msg,
                )

                # Report key health failure
                try:
                    if selected_key is not None:
                        self.health_monitor.report_failure(selected_key, err_msg)
                except Exception as health_exc:
                    logger.error("Health report failed: %s", health_exc)

                newsiq_llm_gateway_calls_total.labels(
                    provider=provider_name, model=model_name, stage=stage, status="error"
                ).inc()

        # If all fail, raise exception
        combined_errors = " | ".join(errors_encountered)
        raise RuntimeError(f"All LLM Gateway providers failed. Details: {combined_errors}")

    def execute_request_sync(
        self,
        model: str,
        stage: str,
        messages: list[dict[str, Any]],
        response_format: dict[str, Any] | type[BaseModel] | None = None,
        temperature: float = 0.0,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        story_id: str = "",
        article_id: str = "",
    ) -> GatewayResponse:
        """Synchronously execute LLM requests through the gateway's fallback chain."""
        chain = self.fallback_chain.get_fallback_chain(model)

        provider_override = provider_override_ctx.get("")
        model_override = model_override_ctx.get("")
        if provider_override and model_override:
            chain = [{"provider": provider_override, "model": model_override}]

        errors_encountered = []

        for entry in chain:
            provider_name = entry["provider"]
            model_name = entry["model"]
            selected_key = None

            try:
                selected_key, client = self.router.select_key_and_client(provider_name, model_name)

                if selected_key.is_cooling_down():
                    import time
                    from datetime import datetime

                    remaining = (selected_key.cooldown_until - datetime.utcnow()).total_seconds()
                    if remaining > 0:
                        is_last_resort = entry == chain[-1] or (
                            len(chain) > 1
                            and entry == chain[-2]
                            and chain[-1]["provider"] == "mock"
                        )
                        if remaining <= 20.0 or is_last_resort:
                            logger.info(
                                "API key for %s is cooling down. Sleeping for %.2f seconds (sync) before proceeding.",
                                provider_name,
                                remaining,
                            )
                            time.sleep(remaining)
                        else:
                            raise KeyCooldownError(f"API key for {provider_name} is cooling down.")

                request = GatewayRequest(
                    model=model_name,
                    messages=messages,
                    temperature=temperature,
                    response_format=response_format,
                    tools=tools,
                    tool_choice=tool_choice,
                    stage=stage,
                    story_id=story_id,
                    article_id=article_id,
                )

                self.rate_limiter.record_request(selected_key.key)

                # Synchronous client execution
                response = client.execute_sync(request, selected_key)

                if response.error:
                    raise RuntimeError(response.error)

                # Cost and telemetry metrics
                cost = self.cost_tracker.calculate_cost(
                    model_name, response.input_tokens, response.output_tokens
                )
                response.cost_usd = cost

                self.health_monitor.report_success(selected_key)

                newsiq_llm_gateway_calls_total.labels(
                    provider=provider_name, model=model_name, stage=stage, status="success"
                ).inc()
                newsiq_llm_gateway_cost_usd.labels(
                    provider=provider_name, model=model_name, stage=stage
                ).inc(cost)

                return response

            except KeyCooldownError as e:
                err_msg = str(e)
                errors_encountered.append(f"{provider_name}/{model_name}: {err_msg}")
                newsiq_llm_gateway_calls_total.labels(
                    provider=provider_name, model=model_name, stage=stage, status="error"
                ).inc()

            except Exception as e:
                err_msg = str(e)
                errors_encountered.append(f"{provider_name}/{model_name}: {err_msg}")
                try:
                    if selected_key is not None:
                        self.health_monitor.report_failure(selected_key, err_msg)
                except Exception:
                    pass
                newsiq_llm_gateway_calls_total.labels(
                    provider=provider_name, model=model_name, stage=stage, status="error"
                ).inc()

        combined_errors = " | ".join(errors_encountered)
        raise RuntimeError(f"All LLM Gateway providers failed (sync). Details: {combined_errors}")


# Singleton Instance
llm_gateway = RequestManager()
