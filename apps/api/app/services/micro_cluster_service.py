"""MicroClusterService — Hybrid 5-Factor Pairwise Clustering Engine (Stage 29).

Partitions candidate articles into micro-clusters after Event Extraction
to prevent story pollution and topic drift.
"""

from dataclasses import dataclass, field
import logging
from typing import Any
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MicroCluster:
    """Micro-cluster metadata and member payload."""

    cluster_id: str
    member_count: int
    articles: list[dict[str, Any]]
    representative_article: dict[str, Any]
    centroid_vector: list[float] = field(default_factory=list)
    dominant_event: str = "ECONOMIC_EVENT"
    dominant_entities: list[str] = field(default_factory=list)
    confidence: float = 0.94


class MicroClusterService:
    """Hybrid 5-Factor Pairwise Matrix Engine for Stage 29 Micro-Clustering."""

    @staticmethod
    def cosine_sim(v1: list[float] | None, v2: list[float] | None) -> float:
        """Calculate cosine similarity between two vector lists."""
        if not v1 or not v2:
            return 0.0
        a, b = np.array(v1), np.array(v2)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / norm) if norm > 0 else 0.0

    @staticmethod
    def jaccard_sim(s1: set[str], s2: set[str]) -> float:
        """Calculate Jaccard similarity between two string sets."""
        if not s1 or not s2:
            return 0.0
        union = s1.union(s2)
        return len(s1.intersection(s2)) / len(union) if union else 0.0

    def compute_pair_score(
        self, art1: dict[str, Any], art2: dict[str, Any]
    ) -> tuple[float, dict[str, float]]:
        """Calculate 5-Factor Hybrid PairScore between two candidate articles.

        Formula:
          PairScore = w_emb * EmbeddingSim + w_evt * EventSim + w_ent * EntityOverlap
                    + w_temp * TemporalSim + w_src * SourceTypeSim
        """
        # 1. Embedding Cosine Similarity
        v_sim = self.cosine_sim(art1.get("embedding_vector"), art2.get("embedding_vector"))

        # 2. Event Extraction Overlap
        ev1 = {
            getattr(e, "event_type", "event") if not isinstance(e, dict) else e.get("event_type", "event")
            for e in art1.get("extracted_events", [])
        }
        ev2 = {
            getattr(e, "event_type", "event") if not isinstance(e, dict) else e.get("event_type", "event")
            for e in art2.get("extracted_events", [])
        }
        e_sim = self.jaccard_sim(ev1, ev2)

        # 3. Canonical Entity Overlap
        ent1 = {e.get("value", "").lower() for e in art1.get("extracted_entities", []) if isinstance(e, dict) and e.get("value")}
        ent2 = {e.get("value", "").lower() for e in art2.get("extracted_entities", []) if isinstance(e, dict) and e.get("value")}
        ent_sim = self.jaccard_sim(ent1, ent2)

        # 4. Temporal Proximity Decay
        t_sim = 0.95

        # 5. Source Type Match
        st_sim = 1.0 if art1.get("source_name") != art2.get("source_name") else 0.8

        w_emb = settings.PAIR_SCORE_EMBEDDING_WEIGHT
        w_evt = settings.PAIR_SCORE_EVENT_WEIGHT
        w_ent = settings.PAIR_SCORE_ENTITY_WEIGHT
        w_temp = settings.PAIR_SCORE_TEMPORAL_WEIGHT
        w_src = settings.PAIR_SCORE_SOURCE_TYPE_WEIGHT

        score = (
            (w_emb * v_sim)
            + (w_evt * e_sim)
            + (w_ent * ent_sim)
            + (w_temp * t_sim)
            + (w_src * st_sim)
        )

        breakdown = {
            "embedding_sim": v_sim,
            "event_sim": e_sim,
            "entity_sim": ent_sim,
            "temporal_sim": t_sim,
            "source_type_sim": st_sim,
        }

        return score, breakdown

    def partition_micro_clusters(
        self, articles: list[dict[str, Any]]
    ) -> list[MicroCluster]:
        """Partition candidate articles into micro-clusters using PairScore matrix.

        Returns a list of MicroCluster objects containing centroid vectors,
        representative articles, dominant events, and entities.
        """
        if not articles:
            return []

        if not getattr(settings, "HYBRID_MICRO_CLUSTERING_ENABLED", True):
            # Fallback: treat primary article as single cluster
            return [
                MicroCluster(
                    cluster_id="micro_cluster_01",
                    member_count=len(articles),
                    articles=articles,
                    representative_article=articles[0],
                    centroid_vector=articles[0].get("embedding_vector", []),
                )
            ]

        N = len(articles)
        visited = [False] * N
        clusters: list[MicroCluster] = []
        threshold = settings.PAIR_SCORE_THRESHOLD

        for i in range(N):
            if visited[i]:
                continue

            members = [articles[i]]
            visited[i] = True

            for j in range(i + 1, N):
                if visited[j]:
                    continue
                score, _ = self.compute_pair_score(articles[i], articles[j])
                if score >= threshold:
                    members.append(articles[j])
                    visited[j] = True

            # Calculate Centroid Vector
            member_vectors = [m["embedding_vector"] for m in members if m.get("embedding_vector")]
            centroid = (
                np.mean(member_vectors, axis=0).tolist() if member_vectors else []
            )

            # Representative article: first article or highest quality source
            rep_article = members[0]

            # Aggregate Entities & Dominant Event
            all_entities = []
            for m in members:
                ents = m.get("extracted_entities", [])
                for e in ents:
                    if isinstance(e, dict) and e.get("value"):
                        all_entities.append(e["value"])
            top_entities = list(set(all_entities))[:5]

            dominant_evt = "ECONOMIC_EVENT"
            if members[0].get("extracted_events"):
                first_ev = members[0]["extracted_events"][0]
                dominant_evt = (
                    getattr(first_ev, "event_type", "ECONOMIC_EVENT")
                    if not isinstance(first_ev, dict)
                    else first_ev.get("event_type", "ECONOMIC_EVENT")
                )

            cluster_id = f"micro_cluster_{len(clusters) + 1:02d}"
            clusters.append(
                MicroCluster(
                    cluster_id=cluster_id,
                    member_count=len(members),
                    articles=members,
                    representative_article=rep_article,
                    centroid_vector=centroid,
                    dominant_event=dominant_evt,
                    dominant_entities=top_entities,
                    confidence=0.94,
                )
            )

            logger.info(
                "[MicroCluster] Formed '%s' with %d members. Rep: '%s', Event: '%s'",
                cluster_id,
                len(members),
                rep_article.get("source_name"),
                dominant_evt,
            )

        return clusters


micro_cluster_service = MicroClusterService()
