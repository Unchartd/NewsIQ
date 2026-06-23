import logging
from typing import Dict

logger = logging.getLogger(__name__)

class CostTracker:
    """Calculates LLM consumption costs in USD based on token counts and model pricing."""

    # Pricing per million tokens (input/output)
    PRICING_TABLE: Dict[str, Dict[str, float]] = {
        "gemini-3.5-flash": {"input": 0.15, "output": 0.60},
        "gemini-3.1-pro": {"input": 1.25, "output": 5.00},
        "gemini-3.1-flash-lite": {"input": 0.075, "output": 0.30},
        "gemini-3-flash": {"input": 0.15, "output": 0.60},
        "gemini-2.5-pro": {"input": 1.25, "output": 5.00},
        "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
        "gemini-2.5-flash-lite": {"input": 0.075, "output": 0.30},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
        "gemma-4-31b": {"input": 0.10, "output": 0.20},
        "gemma-4-26b": {"input": 0.08, "output": 0.16},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
        "llama-3.3-70b-specdec": {"input": 0.59, "output": 0.79},
        "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
        "mock": {"input": 0.0, "output": 0.0},
        # NVIDIA NIM Models (free prototyping tier — $0.00, update for enterprise)
        "mistralai/mistral-medium-3.5-128b": {"input": 0.0, "output": 0.0},
        "deepseek-ai/deepseek-v4-flash": {"input": 0.0, "output": 0.0},
        "nvidia/nemotron-3-super-120b-a12b": {"input": 0.0, "output": 0.0},
        "z-ai/glm-5.1": {"input": 0.0, "output": 0.0},
    }

    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost in USD of a request based on input and output tokens."""
        pricing = self.PRICING_TABLE.get(model)
        if not pricing:
            # Strip any provider prefix (e.g. "openai/gpt-4o-mini" -> "gpt-4o-mini")
            model_key = model.split("/")[-1] if "/" in model else model
            pricing = self.PRICING_TABLE.get(model_key, {"input": 0.0, "output": 0.0})
        
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        
        return round(input_cost + output_cost, 8)
