import logging

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram

    # Total calls
    newsiq_ai_gateway_calls_total = Counter(
        "newsiq_ai_gateway_calls_total",
        "Total number of AI Gateway calls.",
        ["provider", "model", "capability", "status"],
    )

    # Cost
    newsiq_ai_gateway_cost_usd = Counter(
        "newsiq_ai_gateway_cost_usd",
        "Total cost incurred in USD from AI Gateway calls.",
        ["provider", "model", "capability"],
    )

    # Token consumption
    newsiq_ai_gateway_tokens_total = Counter(
        "newsiq_ai_gateway_tokens_total",
        "Total input and output tokens consumed.",
        ["provider", "model", "capability", "token_type"],
    )

    # Latency
    newsiq_ai_gateway_latency_seconds = Histogram(
        "newsiq_ai_gateway_latency_seconds",
        "Latency of AI Gateway calls in seconds.",
        ["provider", "model", "capability"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0),
    )

    # Retries
    newsiq_ai_gateway_retries_total = Counter(
        "newsiq_ai_gateway_retries_total",
        "Total number of retry attempts.",
        ["provider", "model", "capability", "reason"],
    )

    # Cache hits/misses
    newsiq_ai_gateway_cache_total = Counter(
        "newsiq_ai_gateway_cache_total",
        "Total cache hits and misses.",
        ["capability", "status"],
    )

    # Timeout count
    newsiq_ai_gateway_timeouts_total = Counter(
        "newsiq_ai_gateway_timeouts_total",
        "Total timeout events.",
        ["provider", "model", "capability"],
    )

    # Validation failures
    newsiq_ai_gateway_validation_failures_total = Counter(
        "newsiq_ai_gateway_validation_failures_total",
        "Total structured output schema validation failures.",
        ["capability", "model"],
    )

    # Circuit breaker state
    newsiq_ai_gateway_circuit_state = Gauge(
        "newsiq_ai_gateway_circuit_state",
        "Circuit breaker state (1 for open/tripped, 0 for closed/healthy).",
        ["provider"],
    )

    # Prompt executions total
    newsiq_prompt_executions_total = Counter(
        "newsiq_prompt_executions_total",
        "Total execution counts for templates from PromptRegistry.",
        ["stage", "version", "status"],
    )

    # Prompt execution latency
    newsiq_prompt_latency_seconds = Histogram(
        "newsiq_prompt_latency_seconds",
        "Execution latency of prompt templates in seconds.",
        ["stage", "version"],
        buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0),
    )

    # Prompt tokens consumed
    newsiq_prompt_tokens_total = Counter(
        "newsiq_prompt_tokens_total",
        "Tokens consumed by prompt template runs.",
        ["stage", "version", "token_type"],
    )

    # Provider fallbacks executed
    newsiq_provider_fallback_executions_total = Counter(
        "newsiq_provider_fallback_executions_total",
        "Count of times fallback providers in route chain were utilized.",
        ["provider", "stage", "level"],
    )

except ImportError:
    logger.warning("prometheus_client not installed. Dummy metrics will be used.")

    class DummyMetric:
        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            pass

        def dec(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

        def set(self, *args, **kwargs):
            pass

    newsiq_ai_gateway_calls_total = DummyMetric()
    newsiq_ai_gateway_cost_usd = DummyMetric()
    newsiq_ai_gateway_tokens_total = DummyMetric()
    newsiq_ai_gateway_latency_seconds = DummyMetric()
    newsiq_ai_gateway_retries_total = DummyMetric()
    newsiq_ai_gateway_cache_total = DummyMetric()
    newsiq_ai_gateway_timeouts_total = DummyMetric()
    newsiq_ai_gateway_validation_failures_total = DummyMetric()
    newsiq_ai_gateway_circuit_state = DummyMetric()
    newsiq_prompt_executions_total = DummyMetric()
    newsiq_prompt_latency_seconds = DummyMetric()
    newsiq_prompt_tokens_total = DummyMetric()
    newsiq_provider_fallback_executions_total = DummyMetric()
