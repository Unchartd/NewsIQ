import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class FallbackChain:
    """Manages the fallback sequences for models when the primary provider fails."""

    DEFAULT_FALLBACKS: Dict[str, List[Dict[str, str]]] = {
        "gemini-3.5-flash": [
            {"provider": "google", "model": "gemini-3.5-flash"},
            {"provider": "google", "model": "gemini-3.1-flash-lite"},
            {"provider": "google", "model": "gemini-3-flash"},
            {"provider": "google", "model": "gemini-2.5-flash"},
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "nvidia", "model": "mistralai/mistral-medium-3.5-128b"},
            {"provider": "groq", "model": "llama-3.3-70b-specdec"},
            {"provider": "cerebras", "model": "gpt-oss-120b"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemini-3.1-pro": [
            {"provider": "google", "model": "gemini-3.1-pro"},
            {"provider": "google", "model": "gemini-2.5-pro"},
            {"provider": "google", "model": "gemini-3.5-flash"},
            {"provider": "google", "model": "gemini-3-flash"},
            {"provider": "nvidia", "model": "mistralai/mistral-medium-3.5-128b"},
            {"provider": "groq", "model": "llama-3.3-70b-specdec"},
            {"provider": "cerebras", "model": "gpt-oss-120b"},
            {"provider": "openai", "model": "gpt-4o"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemini-3.1-flash-lite": [
            {"provider": "google", "model": "gemini-3.1-flash-lite"},
            {"provider": "google", "model": "gemini-3-flash"},
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "groq", "model": "llama-3.1-8b-instant"},
            {"provider": "cerebras", "model": "zai-glm-4.7"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemini-3-flash": [
            {"provider": "google", "model": "gemini-3-flash"},
            {"provider": "google", "model": "gemini-3.1-flash-lite"},
            {"provider": "google", "model": "gemini-2.5-flash"},
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "groq", "model": "llama-3.3-70b-specdec"},
            {"provider": "cerebras", "model": "gpt-oss-120b"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemini-2.5-pro": [
            {"provider": "google", "model": "gemini-2.5-pro"},
            {"provider": "google", "model": "gemini-3.1-pro"},
            {"provider": "google", "model": "gemini-3.5-flash"},
            {"provider": "nvidia", "model": "mistralai/mistral-medium-3.5-128b"},
            {"provider": "groq", "model": "llama-3.3-70b-specdec"},
            {"provider": "cerebras", "model": "gpt-oss-120b"},
            {"provider": "openai", "model": "gpt-4o"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemma-4-31b": [
            {"provider": "google", "model": "gemma-4-31b"},
            {"provider": "google", "model": "gemma-4-26b"},
            {"provider": "google", "model": "gemini-3.1-flash-lite"},
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemma-4-26b": [
            {"provider": "google", "model": "gemma-4-26b"},
            {"provider": "google", "model": "gemma-4-31b"},
            {"provider": "google", "model": "gemini-3.1-flash-lite"},
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemini-2.5-flash-lite": [
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "google", "model": "gemini-3.1-flash-lite"},
            {"provider": "google", "model": "gemini-2.5-flash"},
            {"provider": "groq", "model": "llama-3.1-8b-instant"},
            {"provider": "cerebras", "model": "zai-glm-4.7"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemini-2.5-flash": [
            {"provider": "google", "model": "gemini-2.5-flash"},
            {"provider": "google", "model": "gemini-3.5-flash"},
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "nvidia", "model": "mistralai/mistral-medium-3.5-128b"},
            {"provider": "groq", "model": "llama-3.3-70b-specdec"},
            {"provider": "cerebras", "model": "gpt-oss-120b"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "mock", "model": "mock"},
        ],
        "gpt-4o-mini": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "google", "model": "gemini-3.1-flash-lite"},
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "groq", "model": "llama-3.1-8b-instant"},
            {"provider": "cerebras", "model": "zai-glm-4.7"},
            {"provider": "mock", "model": "mock"},
        ],
        # NVIDIA NIM Reasoning Models (agentic stages)
        "mistralai/mistral-medium-3.5-128b": [
            {"provider": "nvidia", "model": "mistralai/mistral-medium-3.5-128b"},
            {"provider": "nvidia", "model": "deepseek-ai/deepseek-v4-flash"},
            {"provider": "google", "model": "gemini-3.5-flash"},
            {"provider": "google", "model": "gemini-2.5-flash"},
            {"provider": "groq", "model": "llama-3.3-70b-specdec"},
            {"provider": "mock", "model": "mock"},
        ],
        "deepseek-ai/deepseek-v4-flash": [
            {"provider": "nvidia", "model": "deepseek-ai/deepseek-v4-flash"},
            {"provider": "nvidia", "model": "mistralai/mistral-medium-3.5-128b"},
            {"provider": "google", "model": "gemini-3.5-flash"},
            {"provider": "groq", "model": "llama-3.3-70b-specdec"},
            {"provider": "mock", "model": "mock"},
        ],
        "nvidia/nemotron-3-super-120b-a12b": [
            {"provider": "nvidia", "model": "nvidia/nemotron-3-super-120b-a12b"},
            {"provider": "nvidia", "model": "mistralai/mistral-medium-3.5-128b"},
            {"provider": "google", "model": "gemini-3.5-flash"},
            {"provider": "groq", "model": "llama-3.3-70b-specdec"},
            {"provider": "mock", "model": "mock"},
        ],
        "z-ai/glm-5.1": [
            {"provider": "nvidia", "model": "z-ai/glm-5.1"},
            {"provider": "nvidia", "model": "mistralai/mistral-medium-3.5-128b"},
            {"provider": "google", "model": "gemini-3.5-flash"},
            {"provider": "groq", "model": "llama-3.3-70b-specdec"},
            {"provider": "mock", "model": "mock"},
        ],
    }

    def get_fallback_chain(self, primary_model: str) -> List[Dict[str, str]]:
        """Return the fallback sequence of {'provider', 'model'} for the requested model."""
        # Strip any provider prefix (e.g., "google/gemini-2.5-flash" -> "gemini-2.5-flash")
        model_key = primary_model.split("/")[-1] if "/" in primary_model else primary_model
        
        # Check full model ID first (for NVIDIA models like "mistralai/mistral-medium-3.5-128b")
        if primary_model in self.DEFAULT_FALLBACKS:
            chain = self.DEFAULT_FALLBACKS[primary_model]
        elif model_key in self.DEFAULT_FALLBACKS:
            chain = self.DEFAULT_FALLBACKS[model_key]
        else:
            # Generic default fallback chain
            provider = "google"
            if "gpt" in model_key or "openai" in primary_model:
                provider = "openai"
            elif "llama" in model_key or "groq" in primary_model:
                provider = "groq"
            elif "cerebras" in primary_model:
                provider = "cerebras"
            elif "nvidia" in primary_model or "mistralai" in model_key or "deepseek" in model_key or "nemotron" in model_key or "glm" in model_key:
                provider = "nvidia"

            chain = [
                {"provider": provider, "model": primary_model},
                {"provider": "google", "model": "gemini-3.1-flash-lite"},
                {"provider": "google", "model": "gemini-2.5-flash-lite"},
                {"provider": "nvidia", "model": "mistralai/mistral-medium-3.5-128b"},
                {"provider": "groq", "model": "llama-3.3-70b-specdec"},
                {"provider": "cerebras", "model": "gpt-oss-120b"},
                {"provider": "openai", "model": "gpt-4o-mini"},
                {"provider": "mock", "model": "mock"},
            ]

        # Filter out 'mock' provider in production pipelines (not running under test frameworks)
        import sys
        is_testing = "pytest" in sys.modules or any("pytest" in arg or "unittest" in arg for arg in sys.argv)
        if not is_testing:
            chain = [item for item in chain if item["provider"] != "mock"]

        return chain

