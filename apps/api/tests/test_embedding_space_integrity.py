"""Regression tests: one embedding model, one vector space.

Embeddings are not interchangeable the way chat completions are. Every article
vector lands in a single Qdrant collection and is compared by cosine
similarity, so a vector from a different model is not "slightly worse" — it is
noise. Measured live on the models proposed for the embedding chain:

    same sentence, all-mpnet-base-v2 vs qwen3-embedding-8b : cosine 0.02
    two different paraphrases, within all-mpnet-base-v2    : cosine 0.84
    two different paraphrases, within qwen3-embedding-8b   : cosine 0.92

Stage B matches at ~0.67. A cross-model "fallback" therefore yields articles
that can never cluster, and is indistinguishable from success — the same class
of silent-corruption failure as the fabricated-events incident.
"""

import inspect

import pytest

from app.ai.config import CAPABILITY_ROUTING


def test_all_embedding_tiers_use_one_model():
    """primary/fallback/lastFallback must name the same model.

    This is the invariant a cost-optimisation PR is most likely to break: the
    tiers look like independent redundancy, but for embeddings they are not.
    """
    route = CAPABILITY_ROUTING["embedding"]
    models = {route[tier]["model"] for tier in ("primary", "fallback", "lastFallback")}
    assert len(models) == 1, (
        f"embedding tiers name {len(models)} different models ({sorted(models)}). "
        "Mixing embedding models makes cosine similarity meaningless and "
        "silently breaks clustering."
    )


def test_embedding_tiers_track_the_configured_model():
    """One source of truth, so the cache key and Qdrant payload cannot drift."""
    from app.core.config import settings

    assert CAPABILITY_ROUTING["embedding"]["primary"]["model"] == settings.EMBEDDING_MODEL


def test_gateway_skips_cross_model_embedding_fallbacks():
    """Defence in depth: even a mis-edited config must not mix spaces."""
    from app.ai.gateway import AIGateway

    src = inspect.getsource(AIGateway.embeddings)
    assert "expected_model" in src
    assert "continue" in src, "a differing-model tier must be skipped, not used"


def test_openrouter_refuses_non_matryoshka_models():
    """Slicing a fixed-dim model to 768 produces a different, meaningless space.

    The NVIDIA and Bedrock providers already refuse dimension mismatches;
    OpenRouter must not be the one place that truncates instead.
    """
    from app.ai.providers.openrouter import OPENROUTER_FIXED_DIM_MODELS, OpenRouterProvider

    assert "baai/bge-m3" in OPENROUTER_FIXED_DIM_MODELS
    src = inspect.getsource(OpenRouterProvider.embeddings)
    assert "raise ValueError" in src
    assert "OPENROUTER_FIXED_DIM_MODELS" in src


@pytest.mark.asyncio
async def test_openrouter_embeddings_rejects_fixed_dim_model():
    from app.ai.interfaces import APIKey
    from app.ai.providers.openrouter import OpenRouterProvider

    key = APIKey(key="k", provider="openrouter", requests_per_minute=1, requests_per_day=1)
    with pytest.raises(ValueError, match="fixed dimensionality"):
        await OpenRouterProvider().embeddings("text", key, model="baai/bge-m3")


@pytest.mark.asyncio
async def test_vector_service_refuses_to_mix_embedding_models():
    """A model switch must fail loudly, not quietly poison the collection.

    Behavioral, not source-level, deliberately: the first version of this guard
    passed a source-inspection test ("does it contain `raise ValueError`?")
    while silently accepting a mixed-model write against real Qdrant, because
    it sampled one arbitrary point that happened to predate provenance. Only
    driving the code caught that.
    """
    from unittest.mock import AsyncMock, MagicMock

    from app.services.vector_service import VectorService

    svc = VectorService()

    existing = MagicMock()
    existing.payload = {"embedding_model": "gemini-embedding-001"}
    client = AsyncMock()
    # scroll() filters for points whose model differs from the incoming one;
    # a hit means the collection already holds another model's vectors.
    client.scroll = AsyncMock(return_value=([existing], None))
    svc.client = client

    with pytest.raises(ValueError, match="Refusing to write"):
        await svc._assert_embedding_space(
            {"embedding_model": "sentence-transformers/all-mpnet-base-v2"}
        )

    # And the same model passes.
    svc2 = VectorService()
    clean = AsyncMock()
    clean.scroll = AsyncMock(return_value=([], None))
    svc2.client = clean
    await svc2._assert_embedding_space({"embedding_model": "gemini-embedding-001"})


def test_upsert_runs_the_embedding_space_check():
    from app.services.vector_service import VectorService

    assert "_assert_embedding_space" in inspect.getsource(VectorService.upsert_article)
    assert "reembed_corpus" in inspect.getsource(VectorService._assert_embedding_space), (
        "the error must name the migration path"
    )


def test_provider_and_model_must_agree():
    """A mismatched pair sends the model name to the wrong API.

    Setting only EMBEDDING_MODEL (leaving EMBEDDING_PROVIDER on gemini) would
    POST an OpenRouter model name to Google and 404 every embedding — the same
    silent failure the Bedrock chat models suffered for days. app/ai/config.py
    detects it and disables embeddings, loudly, without killing the process.
    """
    import importlib
    import inspect

    # importlib, not `import ... as`: the module is already imported
    # module-style at the top of this file for CAPABILITY_ROUTING.
    src = inspect.getsource(importlib.import_module("app.ai.config"))
    assert "_MODEL_PREFIX_OWNER" in src
    assert "belongs to provider" in src, "the mismatch must be detected"

    # ...but NOT by raising at import. An earlier version did, and a single
    # mistyped env var crash-looped every container — API, worker, beat and web
    # — taking the whole site down twice. The blast radius of a bad embedding
    # setting must be embeddings, not the product.
    assert "raise ValueError" not in src, (
        "embedding config errors must not raise at import; gate them at the "
        "point of use so the application stays up"
    )


def test_configured_embedding_model_is_registered_and_owned_by_its_provider():
    from app.ai.config import EMBEDDING_PROVIDER, MODEL_FALLBACKS
    from app.core.config import settings

    model = settings.EMBEDDING_MODEL
    assert model in MODEL_FALLBACKS, f"{model} is not registered for routing"
    for cfg in MODEL_FALLBACKS[model]:
        assert cfg["provider"] == EMBEDDING_PROVIDER, (
            f"{model} routes to {cfg['provider']} but EMBEDDING_PROVIDER is {EMBEDDING_PROVIDER}"
        )


def test_bad_embedding_config_disables_embeddings_without_crashing_the_app():
    """A misconfiguration must degrade one capability, not the process.

    Regression for a self-inflicted outage: an import-time `raise` for a
    provider/model mismatch crash-looped every container. Production went down
    twice before the guard was moved to the point of use.
    """
    import importlib

    cfg = importlib.import_module("app.ai.config")

    # The module must import and expose a routable provider regardless.
    assert cfg.EMBEDDING_PROVIDER in ("nvidia", "gemini", "openrouter", "mock", "bedrock")
    assert hasattr(cfg, "EMBEDDING_CONFIG_ERROR")

    # And the gateway must refuse embeddings when the config is bad.
    src = inspect.getsource(importlib.import_module("app.ai.gateway").AIGateway.embeddings)
    assert "EMBEDDING_CONFIG_ERROR" in src, (
        "embeddings must be gated at the point of use, not at import"
    )
