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
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemini-3.1-pro": [
            {"provider": "google", "model": "gemini-3.1-pro"},
            {"provider": "google", "model": "gemini-2.5-pro"},
            {"provider": "google", "model": "gemini-3.5-flash"},
            {"provider": "google", "model": "gemini-3-flash"},
            {"provider": "openai", "model": "gpt-4o"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemini-3.1-flash-lite": [
            {"provider": "google", "model": "gemini-3.1-flash-lite"},
            {"provider": "google", "model": "gemini-3-flash"},
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "groq", "model": "llama-3.1-8b-instant"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemini-3-flash": [
            {"provider": "google", "model": "gemini-3-flash"},
            {"provider": "google", "model": "gemini-3.1-flash-lite"},
            {"provider": "google", "model": "gemini-2.5-flash"},
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemini-2.5-pro": [
            {"provider": "google", "model": "gemini-2.5-pro"},
            {"provider": "google", "model": "gemini-3.1-pro"},
            {"provider": "google", "model": "gemini-3.5-flash"},
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
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "mock", "model": "mock"},
        ],
        "gemini-2.5-flash": [
            {"provider": "google", "model": "gemini-2.5-flash"},
            {"provider": "google", "model": "gemini-3.5-flash"},
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "groq", "model": "llama-3.3-70b-specdec"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "mock", "model": "mock"},
        ],
        "gpt-4o-mini": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "google", "model": "gemini-3.1-flash-lite"},
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "groq", "model": "llama-3.1-8b-instant"},
            {"provider": "mock", "model": "mock"},
        ],
    }

    def get_fallback_chain(self, primary_model: str) -> List[Dict[str, str]]:
        """Return the fallback sequence of {'provider', 'model'} for the requested model."""
        # Strip any provider prefix (e.g., "google/gemini-2.5-flash" -> "gemini-2.5-flash")
        model_key = primary_model.split("/")[-1] if "/" in primary_model else primary_model
        
        if model_key in self.DEFAULT_FALLBACKS:
            return self.DEFAULT_FALLBACKS[model_key]

        # Generic default fallback chain
        provider = "google"
        if "gpt" in model_key or "openai" in primary_model:
            provider = "openai"
        elif "llama" in model_key or "groq" in primary_model:
            provider = "groq"

        return [
            {"provider": provider, "model": primary_model},
            {"provider": "google", "model": "gemini-3.1-flash-lite"},
            {"provider": "google", "model": "gemini-2.5-flash-lite"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "mock", "model": "mock"},
        ]
