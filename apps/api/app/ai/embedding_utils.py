"""Shared embedding constants and vector hygiene helpers.

Lives under app.ai so provider modules can use it without importing from
app.services (which would be a layering inversion and risks import cycles).
"""

import math

# Canonical embedding dimension for the entire pipeline. Every provider must
# emit exactly this many components, and the Qdrant collection is created with
# this size. Changing it requires re-embedding the corpus and recreating the
# collection.
EMBEDDING_DIM = 768


def l2_normalize(vector: list[float]) -> list[float]:
    """Scale a vector to unit length.

    Embedding models that support Matryoshka truncation return unit vectors
    only at their native dimensionality; any other size must be re-normalized
    by the caller. Skipping this leaves vectors whose norm varies per input
    (measured: 0.579–0.592 for gemini-embedding-001 truncated 3072→768), which
    breaks any consumer that assumes unit length — notably distance metrics
    that do not normalize internally.

    A zero vector is returned unchanged; there is no meaningful direction to
    preserve and dividing would produce NaNs.
    """
    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return vector
    return [component / norm for component in vector]
