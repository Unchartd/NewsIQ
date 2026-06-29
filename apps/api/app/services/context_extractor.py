"""Adaptive Context Extractor — paragraph-aware article truncation.

Instead of a naive hard character limit (e.g. text[:6000]) which cuts off in
the middle of sentences or paragraphs and loses ending conclusions, this
extractor preserves:
1. The lead paragraph (often contains who, what, where, when)
2. The concluding paragraph (current status, final resolution)
3. As many middle paragraphs as possible up to the limit.
"""

from __future__ import annotations

import logging
import re

from app.core.config import settings

logger = logging.getLogger(__name__)


class ContextExtractor:
    """Paragraph-aware adaptive context extractor."""

    @staticmethod
    def extract(text: str, max_chars: int = 6000) -> str:
        """Extract a structured subset of article text up to max_chars.

        If CONTEXT_EXTRACTOR_ENABLED is False, falls back to simple text[:max_chars].
        """
        if not text:
            return ""

        enabled = getattr(settings, "CONTEXT_EXTRACTOR_ENABLED", True)
        if not enabled or len(text) <= max_chars:
            return text[:max_chars]

        # 1. Normalize line endings and split into paragraphs
        raw_paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
        if not raw_paragraphs:
            return text[:max_chars]

        # If we only have 1 or 2 paragraphs, return text truncated normally
        if len(raw_paragraphs) <= 2:
            return text[:max_chars]

        # 2. Identify lead and concluding paragraphs
        lead_paragraph = raw_paragraphs[0]
        concluding_paragraph = raw_paragraphs[-1]

        # If lead + concluding is already larger than max_chars, fallback to simple truncation
        if len(lead_paragraph) + len(concluding_paragraph) + 50 > max_chars:
            return text[:max_chars]

        # 3. Fill middle paragraphs
        middle_paragraphs = raw_paragraphs[1:-1]
        allowed_middle_chars = max_chars - len(lead_paragraph) - len(concluding_paragraph) - 50

        selected_middle = []
        current_middle_chars = 0

        for p in middle_paragraphs:
            # Add 2 chars for separator '\n\n'
            p_len = len(p) + 2
            if current_middle_chars + p_len <= allowed_middle_chars:
                selected_middle.append(p)
                current_middle_chars += p_len
            else:
                # If we can't fit the whole paragraph, stop.
                # Alternatively, we could split by sentences, but stopping keeps paragraph integrity.
                break

        # 4. Reconstruct the article with an ellipsis indicator if we skipped anything
        result_parts = [lead_paragraph]

        # Determine if we skipped any paragraphs in the middle
        total_processed_paragraphs = 2 + len(selected_middle)
        if total_processed_paragraphs < len(raw_paragraphs):
            # We skipped some paragraphs
            if selected_middle:
                result_parts.append("\n\n".join(selected_middle))
            result_parts.append("[... Content omitted for context window optimization ...]")
        else:
            if selected_middle:
                result_parts.append("\n\n".join(selected_middle))

        result_parts.append(concluding_paragraph)

        reconstructed = "\n\n".join(result_parts)

        # Safety fallback: if we somehow exceeded max_chars, return naive truncation
        if len(reconstructed) > max_chars:
            return text[:max_chars]

        return reconstructed


context_extractor = ContextExtractor()
