"""Entity linking service — canonicalize entity references across articles.

Uses a hybrid approach:
1. Local heuristic-based coreference resolution within story clusters.
2. DB lookup and Redis caching (7-day TTL).
3. LLM-assisted search query generation for context/disambiguation.
4. Wikidata Search API to retrieve globally unique Wikidata IDs.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.models.models import CanonicalEntity
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

REDIS_TTL_ENTITY = 7 * 24 * 60 * 60  # 7 days


# ── Pydantic Schema for LLM Disambiguation ─────────────────────────────────────


class EntityResolution(BaseModel):
    """LLM representation for entity canonicalization and Wikidata query."""

    canonical_name: str = Field(
        description="The standardized/canonical name for the entity (e.g. 'Rahul Gandhi')"
    )
    wikidata_search_query: str = Field(
        description="Focused query to find this entity on Wikidata (e.g. 'Rahul Gandhi politician')"
    )
    description: str | None = Field(
        default=None,
        description="A very brief description of who/what this entity is, to verify match",
    )


# ── Local Heuristics Helper Functions ─────────────────────────────────────────


def are_coreferent_persons(name1: str, name2: str) -> bool:
    """Determine if two PERSON names refer to the same person.

    Matches if one is a single surname contained in the other, but
    prevents false positive merges between different people with same last name.
    """
    n1_clean = re.sub(r"[^\w\s]", "", name1.strip().lower())
    n2_clean = re.sub(r"[^\w\s]", "", name2.strip().lower())
    if n1_clean == n2_clean:
        return True

    t1 = set(n1_clean.split())
    t2 = set(n2_clean.split())

    # Ignore common honorifics
    honorifics = {
        "mr",
        "ms",
        "mrs",
        "dr",
        "prof",
        "president",
        "minister",
        "pm",
        "chief",
        "leader",
    }
    t1_clean = t1 - honorifics
    t2_clean = t2 - honorifics

    if not t1_clean or not t2_clean:
        return False

    # If one is a single word (e.g., "Trump" or "Gandhi") and matches the other
    if len(t1_clean) == 1:
        val = next(iter(t1_clean))
        if val in t2_clean:
            return True
    if len(t2_clean) == 1:
        val = next(iter(t2_clean))
        if val in t1_clean:
            return True

    return False


def are_coreferent_orgs(name1: str, name2: str) -> bool:
    """Determine if two ORG names refer to the same organization.

    Matches acronyms and substring prefixes with corporate suffixes.
    """
    n1_clean = re.sub(r"[^\w\s]", "", name1.strip().lower())
    n2_clean = re.sub(r"[^\w\s]", "", name2.strip().lower())
    if n1_clean == n2_clean:
        return True

    # Check substring corporate extensions
    if len(n1_clean) > 3 and len(n2_clean) > 3:
        if n1_clean in n2_clean or n2_clean in n1_clean:
            suffixes = {
                "corp",
                "corporation",
                "inc",
                "incorporated",
                "ltd",
                "limited",
                "co",
                "company",
                "group",
                "association",
                "university",
                "college",
                "institute",
            }
            t1 = n1_clean.split()
            t2 = n2_clean.split()
            diff = set(t1) ^ set(t2)
            if diff.issubset(suffixes):
                return True

    # Check acronyms
    def get_acronym(name: str) -> str:
        words = [w for w in name.split() if w not in {"of", "the", "and", "for", "in"}]
        if len(words) > 1:
            return "".join(w[0] for w in words if w)
        return ""

    acr1 = get_acronym(n1_clean)
    acr2 = get_acronym(n2_clean)

    if acr1 and acr1 == n2_clean:
        return True
    if acr2 and acr2 == n1_clean:
        return True

    return False


# ── Entity Linker Service ─────────────────────────────────────────────────────


class EntityLinker:
    """Links story entities to globally unique Wikidata items using a hybrid approach."""

    def __init__(self) -> None:
        pass

    # ── Local Coreference Resolution ──────────────────────────────────────────

    def group_entities_locally(
        self, entities: list[dict[str, str]]
    ) -> dict[str, list[dict[str, str]]]:
        """Perform local coreference resolution within a story's extracted entities.

        Returns a mapping from representative entity string to the list of matched raw entity dicts.
        """
        # Group by entity type to avoid cross-type collisions
        by_type: dict[str, list[dict[str, str]]] = {}
        for ent in entities:
            by_type.setdefault(ent["type"], []).append(ent)

        groups: dict[str, list[dict[str, str]]] = {}

        for etype, items in by_type.items():
            # Sort by name length descending so we merge shorter names into longer, more descriptive names
            sorted_items = sorted(items, key=lambda x: len(x["value"]), reverse=True)

            representatives: list[str] = []
            rep_to_items: dict[str, list[dict[str, str]]] = {}

            for item in sorted_items:
                val = item["value"].strip()
                if not val:
                    continue

                matched_rep: str | None = None

                # Apply heuristics based on entity type
                for rep in representatives:
                    is_match = False
                    if etype in ("PERSON",):
                        is_match = are_coreferent_persons(rep, val)
                    elif etype in (
                        "ORG",
                        "COMPANY",
                        "GOVERNMENT_BODY",
                        "POLITICAL_PARTY",
                    ):
                        is_match = are_coreferent_orgs(rep, val)
                    else:
                        # Exact case-insensitive match for CITY, STATE, COUNTRY, etc.
                        is_match = rep.lower() == val.lower()

                    if is_match:
                        matched_rep = rep
                        break

                if matched_rep:
                    rep_to_items[matched_rep].append(item)
                else:
                    representatives.append(val)
                    rep_to_items[val] = [item]

            # Merge into master groups
            for rep, grouped_items in rep_to_items.items():
                groups[rep] = grouped_items

        return groups

    # ── Deterministic search query generation ──────────────────────────────────

    def _build_deterministic_search_query(self, name: str, entity_type: str) -> str:
        """Build a Wikidata search query without LLM.

        Uses entity type to add disambiguation context:
        - PERSON → "name politician/athlete/etc" (use just the name, it's usually enough)
        - ORG/COMPANY → "name organization"
        - COUNTRY/CITY/STATE → name as-is (locations are unambiguous in Wikidata)
        """
        clean_name = name.strip()

        # Type-based disambiguation suffix
        type_suffixes: dict[str, str] = {
            "POLITICAL_PARTY": "political party",
            "MILITARY_UNIT": "military",
            "GOVERNMENT_BODY": "government",
            "SPORTS_TEAM": "sports team",
            "WEAPON": "weapon",
            "TECHNOLOGY": "technology",
            "PRODUCT": "product",
            "LAW": "law",
            "AGREEMENT": "agreement",
            "DISEASE": "disease",
        }

        suffix = type_suffixes.get(entity_type, "")
        if suffix:
            return f"{clean_name} {suffix}"
        return clean_name

    # ── LLM search query generation (opt-in fallback) ──────────────────────────

    def _build_disambiguation_prompt(self, name: str, entity_type: str, context: str) -> str:
        return (
            "You are an entity resolution assistant.\n"
            f"Given the entity name '{name}' of type '{entity_type}', "
            "determine its canonical name and generate a specific Wikidata search query.\n\n"
            "Context from articles:\n"
            f"{context[:3000]}\n\n"
            "Identify what/who this entity is in the context. E.g., if it's 'Gandhi' and the context is Indian politics, "
            "canonical name is 'Rahul Gandhi' and query is 'Rahul Gandhi politician'.\n"
            "If the entity is already clear (e.g. 'United States'), "
            "canonical name is 'United States' and query is 'United States'.\n\n"
            "Respond in JSON matching this schema:\n"
            '{"canonical_name": "...", "wikidata_search_query": "...", "description": "..."}\n'
        )

    async def _disambiguate_with_llm(
        self, name: str, entity_type: str, context: str
    ) -> EntityResolution:
        """Query LLM to generate a clean search query and description via central AI Gateway."""
        from app.ai.gateway import ai_gateway
        from app.core.trace import story_id_ctx

        story_id = story_id_ctx.get("")

        try:
            prompt_variables = {
                "name": name,
                "entity_type": entity_type,
                "context": context[:3000],
            }

            response = await ai_gateway.generate_stage(
                stage="entity_linking",
                prompt_variables=prompt_variables,
                schema=EntityResolution,
                story_id=story_id,
            )

            if response.parsed:
                return response.parsed

            try:
                import json

                data = json.loads(response.content)
                return EntityResolution(**data)
            except Exception:
                pass
        except Exception as exc:
            logger.warning("AI Gateway disambiguation failed for %s: %s", name, exc)

        # Fallback if AI Gateway is disabled or failed
        return EntityResolution(
            canonical_name=name,
            wikidata_search_query=name,
            description=f"Extracted {entity_type} entity",
        )

    # ── Wikidata API Resolution ────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=False,
    )
    async def _query_wikidata_multi(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Search Wikidata using wbsearchentities API and return multiple results."""
        url = "https://www.wikidata.org/w/api.php"
        params: dict[str, Any] = {
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "format": "json",
            "limit": limit,
        }
        headers = {"User-Agent": "NewsIQ/1.0 (admin@newsiq.com)"}

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return data.get("search", [])
        return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=False,
    )
    async def _query_wikidata(self, query: str) -> dict[str, str | None] | None:
        """Search Wikidata using wbsearchentities API."""
        results = await self._query_wikidata_multi(query, limit=1)
        if results:
            top_result = results[0]
            return {
                "wikidata_id": top_result.get("id"),
                "description": top_result.get("description"),
                "label": top_result.get("label"),
            }
        return None

    # ── Ambiguity & Confidence Gating ──────────────────────────────────────────

    @staticmethod
    def _is_name_ambiguous(name: str) -> bool:
        """Check if an entity name is inherently ambiguous (e.g. single words or specific terms)."""
        clean = name.strip().lower()
        # Single-word names are often ambiguous (e.g., "Washington", "Jordan", "Apple", "Mercury")
        if " " not in clean:
            return True

        # Curated list of known ambiguous entities
        ambiguous_names = {
            "washington",
            "mercury",
            "jordan",
            "apple",
            "amazon",
            "columbia",
            "georgia",
            "delta",
            "china",
            "turkey",
            "clinton",
            "bush",
            "obama",
            "trump",
            "biden",
            "tesla",
            "meta",
            "alphabet",
            "microsoft",
        }
        if clean in ambiguous_names:
            return True
        return False

    def _assess_confidence(
        self,
        name: str,
        entity_type: str,
        results: list[dict[str, Any]],
    ) -> float:
        """Assess the confidence score (0.0 to 1.0) of Wikidata search results."""
        if not results:
            return 0.0

        # Inherently ambiguous names start with lower baseline confidence
        if self._is_name_ambiguous(name):
            confidence = 0.5
        else:
            confidence = 0.8

        top_result = results[0]
        top_desc = (top_result.get("description") or "").lower()
        top_label = (top_result.get("label") or "").lower()

        # Check type matching in description
        type_keywords: dict[str, list[str]] = {
            "PERSON": [
                "person",
                "politician",
                "actor",
                "athlete",
                "writer",
                "singer",
                "officer",
                "president",
                "minister",
                "activist",
            ],
            "ORG": [
                "organization",
                "company",
                "association",
                "institution",
                "agency",
                "foundation",
                "union",
                "party",
                "club",
            ],
            "COMPANY": ["company", "corporation", "enterprise", "manufacturer", "firm", "business"],
            "COUNTRY": ["country", "nation", "state", "republic"],
            "CITY": ["city", "town", "municipality", "capital"],
            "STATE": ["state", "province", "region", "territory"],
        }

        keywords = type_keywords.get(entity_type, [])
        if keywords:
            has_keyword = any(kw in top_desc for kw in keywords)
            if has_keyword:
                confidence += 0.2
            else:
                confidence -= 0.3

        # Exactly 1 result indicates low competition / clear match
        if len(results) == 1:
            confidence += 0.1

        # If there are multiple results, check if they compete/conflict
        if len(results) > 1:
            second_result = results[1]
            second_label = (second_result.get("label") or "").lower()
            # If the second result has the exact same name/label but a different description, it's a conflict
            if second_label == name.strip().lower() or second_label == top_label:
                confidence -= 0.3

        # Clamp confidence between 0.0 and 1.0 and round to 2 decimal places to prevent float precision issues
        return round(max(0.0, min(1.0, confidence)), 2)

    # ── Public API ────────────────────────────────────────────────────────────

    async def link_entity(
        self,
        name: str,
        entity_type: str,
        context: str,
        session: AsyncSession,
    ) -> CanonicalEntity:
        """Resolve a single entity mention to a database CanonicalEntity record.

        Checks:
        1. PostgreSQL DB by canonical_name (case-insensitive)
        2. Redis cache for wikidata ID resolution
        3. LLM query generation + Wikidata API call
        4. Saves and returns CanonicalEntity
        """
        clean_name = name.strip()
        slug = re.sub(r"[^a-z0-9]+", "_", clean_name.lower())
        cache_key = f"newsiq:entity_link:{slug}"

        # ── 1. DB Lookup ──────────────────────────────────────────────────────
        stmt = select(CanonicalEntity).where(CanonicalEntity.canonical_name.ilike(clean_name))
        res = await session.execute(stmt)
        db_entity = res.scalar_one_or_none()
        if db_entity:
            return db_entity

        # ── 2. Redis Cache Lookup ─────────────────────────────────────────────
        cached = await cache_service.get(cache_key)
        if cached:
            # Check DB again by wikidata_id if cached resolution had one
            cached_wikidata_id = cached.get("wikidata_id")
            if cached_wikidata_id:
                stmt = select(CanonicalEntity).where(
                    CanonicalEntity.wikidata_id == cached_wikidata_id
                )
                res = await session.execute(stmt)
                db_entity = res.scalar_one_or_none()
                if db_entity:
                    # Update cache and return
                    return db_entity

            # Not in DB yet under this name/ID — create it
            new_entity = CanonicalEntity(
                canonical_name=cached.get("canonical_name", clean_name),
                entity_type=cached.get("entity_type", entity_type),
                wikidata_id=cached_wikidata_id,
                aliases=cached.get("aliases", [clean_name]),
                metadata_payload={"description": cached.get("description")},
            )
            try:
                async with session.begin_nested():
                    session.add(new_entity)
                await session.commit()
                return new_entity
            except Exception:
                # Concurrent insert of the same canonical name might have succeeded.
                # Let's query it from DB.
                stmt = select(CanonicalEntity).where(
                    CanonicalEntity.canonical_name.ilike(new_entity.canonical_name)
                )
                res = await session.execute(stmt)
                db_entity = res.scalar_one_or_none()
                if db_entity:
                    return db_entity
                raise

        # ── 3. Resolve via Wikidata (hybrid confidence-gated approach) ────────────
        logger.info("Resolving new entity: %s (%s)", clean_name, entity_type)

        linking_mode = getattr(settings, "ENTITY_LINKING_MODE", "hybrid").lower()

        resolution = None
        wikidata_id: str | None = None
        wikidata_desc: str | None = None

        if linking_mode == "deterministic":
            # Pure deterministic path (no LLM falls back)
            search_query = self._build_deterministic_search_query(clean_name, entity_type)
            resolution = EntityResolution(
                canonical_name=clean_name,
                wikidata_search_query=search_query,
                description=f"Extracted {entity_type} entity",
            )
        elif linking_mode == "llm":
            # Pure LLM path
            resolution = await self._disambiguate_with_llm(clean_name, entity_type, context)
        else:
            # Hybrid path (default): deterministic first, check confidence, run LLM only on low confidence
            search_query = self._build_deterministic_search_query(clean_name, entity_type)
            # Query multiple Wikidata results
            wiki_results = await self._query_wikidata_multi(search_query, limit=3)
            confidence = self._assess_confidence(clean_name, entity_type, wiki_results)

            if confidence >= 0.8:
                # High confidence deterministic match
                top_res = wiki_results[0]
                wikidata_id = top_res.get("id")
                wikidata_desc = top_res.get("description")
                canonical_name = top_res.get("label") or clean_name
                resolution = EntityResolution(
                    canonical_name=canonical_name,
                    wikidata_search_query=search_query,
                    description=wikidata_desc or f"Extracted {entity_type} entity",
                )
                logger.info(
                    "Deterministic entity resolution HIGH confidence (%.2f) for %s",
                    confidence,
                    clean_name,
                )
            else:
                # Low confidence / ambiguous: fall back to LLM disambiguation
                logger.info(
                    "Deterministic entity resolution LOW confidence (%.2f) or ambiguous for %s. Triggering LLM fallback.",
                    confidence,
                    clean_name,
                )
                resolution = await self._disambiguate_with_llm(clean_name, entity_type, context)

        # Query Wikidata if not resolved yet (e.g. from LLM fallback or deterministic fallback)
        if not wikidata_id and resolution:
            wikidata_desc = resolution.description
            try:
                wiki_res = await self._query_wikidata(resolution.wikidata_search_query)
                if wiki_res:
                    wikidata_id = wiki_res["wikidata_id"]
                    wikidata_desc = wiki_res["description"] or resolution.description
                    if wiki_res.get("label"):
                        resolution.canonical_name = wiki_res["label"]
            except Exception as e:
                logger.warning("Wikidata lookup failed for %s: %s", clean_name, e)

        # Agentic fallback if Wikidata did not resolve QID
        if not wikidata_id:
            logger.info(
                "Wikidata lookup failed to find QID for %s. Invoking EntityDisambiguationAgent.",
                clean_name,
            )
            try:
                from app.agents.entity_disambiguation_agent import disambiguate_entity

                agent_res = await disambiguate_entity(
                    entity_value=clean_name, entity_type=entity_type, context=context
                )
                if agent_res:
                    resolution.canonical_name = agent_res.canonical_name
                    entity_type = agent_res.entity_type
                    wikidata_id = agent_res.wikidata_id
                    wikidata_desc = agent_res.explanation
            except Exception as e:
                logger.error("EntityDisambiguationAgent failed for %s: %s", clean_name, e)

        # Check DB by wikidata_id if found
        if wikidata_id:
            stmt = select(CanonicalEntity).where(CanonicalEntity.wikidata_id == wikidata_id)
            res = await session.execute(stmt)
            db_entity = res.scalar_one_or_none()
            if db_entity:
                # Add current clean_name to aliases if it's not there
                aliases = list(db_entity.aliases or [])
                if clean_name not in aliases:
                    aliases.append(clean_name)
                    db_entity.aliases = aliases
                    await session.commit()
                return db_entity

        # Create new entity record
        aliases = [clean_name]
        if resolution.canonical_name != clean_name:
            aliases.append(resolution.canonical_name)

        new_entity = CanonicalEntity(
            canonical_name=resolution.canonical_name,
            entity_type=entity_type,
            wikidata_id=wikidata_id,
            aliases=aliases,
            metadata_payload={"description": wikidata_desc},
        )
        try:
            async with session.begin_nested():
                session.add(new_entity)
            await session.commit()
        except Exception:
            # Query the existing one
            stmt = select(CanonicalEntity).where(
                CanonicalEntity.canonical_name.ilike(new_entity.canonical_name)
            )
            res = await session.execute(stmt)
            db_entity = res.scalar_one_or_none()
            if db_entity:
                new_entity = db_entity
            else:
                raise

        # Cache in Redis
        cache_val = {
            "canonical_name": resolution.canonical_name,
            "entity_type": entity_type,
            "wikidata_id": wikidata_id,
            "aliases": aliases,
            "description": wikidata_desc,
        }
        await cache_service.set(cache_key, cache_val, REDIS_TTL_ENTITY)

        return new_entity


entity_linker = EntityLinker()
