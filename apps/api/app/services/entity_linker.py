"""Entity linking service — canonicalize entity references across articles.

Uses a hybrid approach:
1. Local heuristic-based coreference resolution within story clusters.
2. DB lookup and Redis caching (7-day TTL).
3. LLM-assisted search query generation for context/disambiguation.
4. Wikidata Search API to retrieve globally unique Wikidata IDs.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
import httpx

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.trace import track_llm_call

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
        # LLM Clients setup
        self._gemini_client = None
        self.gemini_enabled = False
        api_key = settings.GEMINI_API_KEY_SYNTH or settings.GEMINI_API_KEY
        if api_key:
            try:
                from google import genai as google_genai

                self._gemini_client = google_genai.Client(api_key=api_key)
                self.gemini_enabled = True
            except ImportError:
                pass

        self._openai_client = None
        self.openai_enabled = False
        if settings.OPENAI_API_KEY:
            try:
                from openai import AsyncOpenAI

                self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                self.openai_enabled = True
            except Exception:
                pass

    # ── Local Coreference Resolution ──────────────────────────────────────────

    def group_entities_locally(self, entities: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
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

    # ── LLM search query generation ───────────────────────────────────────────

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
        """Query LLM to generate a clean search query and description."""
        prompt = self._build_disambiguation_prompt(name, entity_type, context)

        if self.gemini_enabled:
            from app.services.ai_service import _wait_for_synthesis_quota
            from google.genai import types

            await _wait_for_synthesis_quota()
            model = settings.SUMMARIZATION_MODEL or "gemini-2.5-flash-lite"

            try:
                async with track_llm_call("gemini", model, "entity_linking", user_prompt=prompt) as call:
                    response = await self._gemini_client.aio.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=EntityResolution,
                            temperature=0.1,
                        ),
                    )
                    call.response_text = response.text
                    if getattr(response, "usage_metadata", None):
                        call.input_tokens = response.usage_metadata.prompt_token_count or 0
                        call.output_tokens = response.usage_metadata.candidates_token_count or 0
                    data = json.loads(response.text)
                    return EntityResolution(**data)
            except Exception as e:
                logger.warning("Gemini disambiguation failed for %s: %s", name, e)

        if self.openai_enabled and self._openai_client:
            try:
                async with track_llm_call("openai", "gpt-4o-mini", "entity_linking", user_prompt=prompt) as call:
                    response = await self._openai_client.beta.chat.completions.parse(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a named entity resolution engine.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        response_format=EntityResolution,
                        temperature=0.1,
                    )
                    call.response_text = response.choices[0].message.content or ""
                    if getattr(response, "usage", None):
                        call.input_tokens = response.usage.prompt_tokens or 0
                        call.output_tokens = response.usage.completion_tokens or 0
                    return response.choices[0].message.parsed
            except Exception as e:
                logger.warning("OpenAI disambiguation failed for %s: %s", name, e)

        # Fallback if LLM is disabled or failed
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
    async def _query_wikidata(self, query: str) -> dict[str, str | None] | None:
        """Search Wikidata using wbsearchentities API."""
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "format": "json",
            "limit": 1,
        }
        headers = {"User-Agent": "NewsIQ/1.0 (admin@newsiq.com)"}

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                search_results = data.get("search", [])
                if search_results:
                    top_result = search_results[0]
                    return {
                        "wikidata_id": top_result.get("id"),
                        "description": top_result.get("description"),
                        "label": top_result.get("label"),
                    }
        return None

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
        stmt = select(CanonicalEntity).where(
            CanonicalEntity.canonical_name.ilike(clean_name)
        )
        res = await session.execute(stmt)
        db_entity = res.scalar_one_or_none()
        if db_entity:
            return db_entity

        # ── 2. Redis Cache Lookup ─────────────────────────────────────────────
        cached = await cache_service.get(cache_key)
        if cached:
            # Check DB again by wikidata_id if cached resolution had one
            wikidata_id = cached.get("wikidata_id")
            if wikidata_id:
                stmt = select(CanonicalEntity).where(
                    CanonicalEntity.wikidata_id == wikidata_id
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
                wikidata_id=wikidata_id,
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

        # ── 3. LLM + Wikidata Call ────────────────────────────────────────────
        logger.info("Resolving new entity: %s (%s)", clean_name, entity_type)
        resolution = await self._disambiguate_with_llm(clean_name, entity_type, context)

        wikidata_id: str | None = None
        wikidata_desc: str | None = resolution.description

        try:
            wiki_res = await self._query_wikidata(resolution.wikidata_search_query)
            if wiki_res:
                wikidata_id = wiki_res["wikidata_id"]
                wikidata_desc = wiki_res["description"] or resolution.description
                # If Wikidata returns a better canonical label, use it
                if wiki_res.get("label"):
                    resolution.canonical_name = wiki_res["label"]
        except Exception as e:
            logger.warning("Wikidata lookup failed for %s: %s", clean_name, e)

        # Agentic fallback if Wikidata did not resolve QID
        if not wikidata_id:
            logger.info("Wikidata lookup failed to find QID for %s. Invoking EntityDisambiguationAgent.", clean_name)
            try:
                from app.agents.entity_disambiguation_agent import disambiguate_entity
                agent_res = await disambiguate_entity(
                    entity_value=clean_name,
                    entity_type=entity_type,
                    context=context
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
            stmt = select(CanonicalEntity).where(
                CanonicalEntity.wikidata_id == wikidata_id
            )
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
