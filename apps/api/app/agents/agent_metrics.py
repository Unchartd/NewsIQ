import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram

    # Agent execution metrics
    newsiq_agent_runs_total: Any = Counter(
        "newsiq_agent_runs_total",
        "Total number of Agno agent runs triggered.",
        ["agent_name", "status"],
    )

    newsiq_agent_runs_latency_seconds: Any = Histogram(
        "newsiq_agent_runs_latency_seconds",
        "Latency of Agno agent runs in seconds.",
        ["agent_name"],
        buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    )

except ImportError:
    logger.warning("prometheus_client not installed. Dummy agent metrics will be used.")

    class DummyMetric:
        def labels(self, *args, **kwargs):
            return self

        def inc(self, *args, **kwargs):
            pass

        def observe(self, *args, **kwargs):
            pass

    newsiq_agent_runs_total = DummyMetric()
    newsiq_agent_runs_latency_seconds = DummyMetric()
