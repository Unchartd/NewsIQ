import logging

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram

    # Gateway metrics
    newsiq_llm_gateway_calls_total = Counter(
        "newsiq_llm_gateway_calls_total",
        "Total number of LLM calls made via the gateway.",
        ["provider", "model", "stage", "status"]
    )

    newsiq_llm_gateway_cost_usd = Counter(
        "newsiq_llm_gateway_cost_usd",
        "Total cost incurred in USD from LLM calls via the gateway.",
        ["provider", "model", "stage"]
    )

    newsiq_llm_gateway_tokens_total = Counter(
        "newsiq_llm_gateway_tokens_total",
        "Total input and output tokens consumed via the gateway.",
        ["provider", "model", "stage", "token_type"]
    )

    newsiq_llm_gateway_latency_seconds = Histogram(
        "newsiq_llm_gateway_latency_seconds",
        "Latency of LLM calls via the gateway in seconds.",
        ["provider", "model", "stage"],
        buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 60.0)
    )

    newsiq_llm_gateway_key_cooldowns = Counter(
        "newsiq_llm_gateway_key_cooldowns",
        "Total number of API key cooldown events triggered.",
        ["provider", "key_hash"]
    )

except ImportError:
    logger.warning("prometheus_client not installed. Dummy metrics will be used.")
    
    # Dummy classes to prevent imports from failing in test environments
    class DummyMetric:
        def labels(self, *args, **kwargs):
            return self
        def inc(self, *args, **kwargs):
            pass
        def observe(self, *args, **kwargs):
            pass

    newsiq_llm_gateway_calls_total = DummyMetric()
    newsiq_llm_gateway_cost_usd = DummyMetric()
    newsiq_llm_gateway_tokens_total = DummyMetric()
    newsiq_llm_gateway_latency_seconds = DummyMetric()
    newsiq_llm_gateway_key_cooldowns = DummyMetric()
