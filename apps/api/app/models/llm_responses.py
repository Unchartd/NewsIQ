"""
Pydantic schemas for LLM responses.
Provides the registry for response models used in Prompt manifests.
"""

from app.agents.cluster_verification_agent import (
    ClusterVerificationSchema as ClusterVerificationResponse,
)
from app.agents.reflection_agent import ReflectionSchema as SummaryReflectionResponse
from app.services.ai_service import StorySummaryResponse
from app.services.contradiction_service import ContradictionResolution as ContradictionResponse
from app.services.entity_linker import EntityResolution as EntityLinkingResponse
from app.services.event_service import ArticleEventResponse
from app.services.ner_service_v2 import EntityExtractionResponse
from app.services.source_comparison_service import (
    SourceComparisonResolution as SourceComparisonResponse,
)

__all__ = [
    "ArticleEventResponse",
    "EntityExtractionResponse",
    "EntityLinkingResponse",
    "ClusterVerificationResponse",
    "ContradictionResponse",
    "SourceComparisonResponse",
    "StorySummaryResponse",
    "SummaryReflectionResponse",
]
