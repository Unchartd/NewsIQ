import base64
import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import EventAlias

logger = logging.getLogger(__name__)

class EventIdentityService:
    """
    Manages generation, lifecycle, and merging of Canonical Event IDs.
    Provides immutable, non-human-readable identifiers separated from display slugs.
    """

    def __init__(self):
        self.metrics = {
            "tmp_ids_created": 0,
            "canonical_ids_created": 0,
            "aliases_created": 0,
            "merges_handled": 0
        }

    def generate_temporary_id(self) -> str:
        """
        Generates a temporary event ID used during the noisy discovery phase.
        Format: tmp_evt_<uuid>
        """
        self.metrics["tmp_ids_created"] += 1
        logger.info('METRIC: event_identity_action{action="tmp_ids_created"} 1')
        return f"tmp_evt_{uuid.uuid4().hex}"

    def generate_canonical_id(self) -> str:
        """
        Generates an immutable canonical event ID.
        Format: evt_<base32_id> (e.g. evt_01K3X7Y5...)
        Uses UUID4 encoded in Crockford's Base32 for readability and URL safety without semantics.
        """
        u = uuid.uuid4()
        # Crockford's Base32 encoding mapping (no padding)
        b32 = base64.b32encode(u.bytes).decode('ascii').rstrip('=')
        # Standardize for readability (omit O, I, L, U to avoid confusion if needed,
        # but standard base32 is fine for internal immutable ID)
        self.metrics["canonical_ids_created"] += 1
        logger.info('METRIC: event_identity_action{action="canonical_ids_created"} 1')
        return f"evt_{b32}"

    def generate_display_slug(self, headline: str, year: int) -> str:
        """
        Generates a human-readable display slug purely for UI/URL routing.
        This is completely decoupled from the system canonical ID.
        """
        if not headline:
            return f"event-{uuid.uuid4().hex[:8]}-{year}"

        # Lowercase, replace non-alphanumerics with hyphens, collapse multiple hyphens
        slug = re.sub(r'[^a-z0-9]+', '-', headline.lower()).strip('-')

        # Truncate to avoid massive slugs, add year
        slug = slug[:50].strip('-')
        if not slug:
            return f"event-{uuid.uuid4().hex[:8]}-{year}"

        return f"{slug}-{year}"

    async def handle_merge(
        self, old_id: str, new_id: str, reason: str, session: AsyncSession
    ) -> None:
        """
        Handles merging an old canonical ID into a new canonical ID.
        Records an EventAlias to preserve history and allow redirects.
        """
        if not old_id or not new_id or old_id == new_id:
            return

        # Don't alias temporary IDs
        if old_id.startswith("tmp_evt_"):
            return

        logger.info(
            "Merging event IDs: alias=%s -> canonical=%s (reason=%s)",
            old_id, new_id, reason
        )

        alias = EventAlias(
            alias_event_id=old_id,
            canonical_event_id=new_id,
            reason=reason
        )
        session.add(alias)

        self.metrics["aliases_created"] += 1
        self.metrics["merges_handled"] += 1
        logger.info('METRIC: event_identity_action{action="aliases_created"} 1')
        logger.info('METRIC: event_identity_action{action="merges_handled"} 1')

    async def resolve_alias(self, alias_id: str, session: AsyncSession) -> str:
        """
        Follows the redirect chain to find the current canonical ID.
        """
        if not alias_id:
            return alias_id

        current_id = alias_id
        visited = set()

        while current_id not in visited:
            visited.add(current_id)
            stmt = select(EventAlias.canonical_event_id).where(
                EventAlias.alias_event_id == current_id
            )
            res = await session.execute(stmt)
            next_id = res.scalar_one_or_none()
            if next_id:
                current_id = next_id
                logger.info('METRIC: event_identity_action{action="alias_resolved"} 1')
            else:
                break

        return current_id

event_identity_service = EventIdentityService()
