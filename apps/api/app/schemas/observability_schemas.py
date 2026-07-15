"""Observability Pydantic schemas for admin analytics endpoints."""

from pydantic import BaseModel


class PromptAnalyticsResponse(BaseModel):
    prompt_name: str
    prompt_version: str
    success_rate: float
    avg_latency_ms: float
    avg_cost: float
    validation_failures: int
    retry_rate: float
    cache_hit_rate: float
    total_runs: int


class ModelBenchmarkResponse(BaseModel):
    model: str
    capability: str
    success_rate: float
    avg_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    json_validity_rate: float
    retry_frequency: float
    avg_cost: float
    fallback_frequency: float
    total_runs: int


class ContextAnalyticsResponse(BaseModel):
    stage: str
    p50_input_tokens: float
    p90_input_tokens: float
    p99_input_tokens: float
    p50_output_tokens: float
    p90_output_tokens: float
    p99_output_tokens: float
    avg_total_tokens: float
    max_total_tokens: int
    abnormally_large_count: int
    total_runs: int


class CacheEffectivenessResponse(BaseModel):
    stage: str
    prompt_name: str
    model: str
    hit_rate: float
    total_requests: int
    low_value: bool


class HallucinationAnalyticsResponse(BaseModel):
    total_reflections: int
    avg_unsupported_claims: float
    avg_missing_citations: float
    contradiction_rate: float
    avg_bias_corrections: float
    avg_regeneration_count: float
    avg_reflection_confidence: float


class ForecastItem(BaseModel):
    volume: int
    daily_cost: float
    monthly_cost: float


class CostForecastingResponse(BaseModel):
    avg_cost_per_article: float
    avg_cost_per_story: float
    forecasts: list[ForecastItem]


class ProviderSLAResponse(BaseModel):
    provider: str
    availability: float
    avg_latency_ms: float
    total_retries: int
    rate_limit_429_count: int
    server_error_500_count: int
    circuit_breaker_openings: int
    fallback_rate: float
    timeout_rate: float
