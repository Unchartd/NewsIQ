import asyncio
import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update

from app.core.database import async_session_factory
from app.models.models import (
    Article,
    ArticleEntity,
    ArticleEvent,
    DiscoveryQueue,
    StoryArticle,
)
from app.services.pipeline_coordinator import pipeline_coordinator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_ai_mocks():
    logger.info("Applying mock interfaces for offline execution.")
    from app.ai.gateway import ai_gateway
    from app.ai.interfaces import GatewayResponse
    from app.services.embedding_service import embedding_service
    from app.services.event_service import ArticleEventResponse, ExtractedEvent
    from app.services.ner_service_v2 import NERServiceV2

    ner_service_v2 = NERServiceV2()

    async def mock_get_embeddings(texts, model=None):
        return [[0.1] * 768 for _ in texts]
    embedding_service.get_embeddings = mock_get_embeddings

    async def mock_extract_entities(text):
        return {"locations": ["Mock City"], "people": ["Mock Person"], "organizations": ["Mock Org"]}
    ner_service_v2.extract_entities = mock_extract_entities

    async def mock_gateway_generate(capability, *args, **kwargs):
        schema = kwargs.get("schema")
        if capability == "event_extraction":
            parsed = ArticleEventResponse(
                primary_event=ExtractedEvent(
                    event_type="OTHER",
                    actors=["[Mock] Actor"],
                    targets=[],
                    objects=[],
                    location="[Mock] Location",
                    event_time=None,
                    numbers={},
                    confidence=0.5
                ),
                secondary_events=[],
                entities=[]
            )
            return GatewayResponse(
                content="{}",
                parsed=parsed,
                provider="mock",
                model="mock",
                latency_ms=1.0,
                cost_usd=0.0
            )

        parsed = None
        if schema:
            try:
                parsed = schema()
            except Exception:
                pass
        return GatewayResponse(
            content="Mocked AI Response",
            parsed=parsed,
            provider="mock",
            model="mock",
            latency_ms=1.0,
            cost_usd=0.0
        )
    ai_gateway.generate = mock_gateway_generate

async def replay_pipeline(limit: int = 100, live: bool = False, dataset: str = "historical", compare: bool = False):
    """
    Replays the pipeline for a set of historical articles.
    Resets their state, runs them through the PipelineCoordinator, triggers clustering,
    and logs quality evaluation metrics (silhouette score, outliers).
    """
    if not live:
        apply_ai_mocks()

    async with async_session_factory() as session:
        logger.info("Fetching %d articles from dataset '%s'...", limit, dataset)

        # 1. Fetch articles based on dataset
        if dataset == "yesterday":
            now = datetime.now(UTC).replace(tzinfo=None)
            one_day_ago = now - timedelta(days=1)
            stmt = select(Article).where(Article.published_at >= one_day_ago).order_by(Article.published_at.desc()).limit(limit)
        elif dataset == "custom":
            stmt = select(Article).where(Article.content is not None).order_by(Article.published_at.desc()).limit(limit)
        else: # historical
            stmt = select(Article).order_by(Article.published_at.desc().nulls_last()).limit(limit)

        res = await session.execute(stmt)
        articles = list(res.scalars().all())

        if not articles:
            logger.info("No articles found to replay.")
            return

        article_ids = [a.id for a in articles]
        logger.info("Resetting state for %d articles...", len(article_ids))

        # 2. Reset state (Remove from stories, events, entities, etc)
        await session.execute(delete(StoryArticle).where(StoryArticle.article_id.in_(article_ids)))
        await session.execute(delete(ArticleEvent).where(ArticleEvent.article_id.in_(article_ids)))
        await session.execute(delete(ArticleEntity).where(ArticleEntity.article_id.in_(article_ids)))
        await session.execute(delete(DiscoveryQueue).where(DiscoveryQueue.article_id.in_(article_ids)))

        # Reset article status
        await session.execute(
            update(Article)
            .where(Article.id.in_(article_ids))
            .values(
                embedding_status="pending",
                event_extraction_status="pending"
            )
        )
        await session.commit()

        logger.info("State reset complete. Beginning replay...")

        # 3. Feed through pipeline
        from app.services.embedding_service import embedding_service
        from app.services.event_service import event_service
        from app.services.vector_service import vector_service

        success_count = 0
        merged_count = 0
        discovery_count = 0

        for art in articles:
            logger.info("Replaying article %s: %s", art.id, art.title)

            # Step 1: Embed
            text_to_embed = f"{art.title or ''} {art.description or ''} {(art.content or '')[:4000]}".strip()
            if not text_to_embed: text_to_embed = "Empty news article"

            try:
                vectors = await embedding_service.get_embeddings([text_to_embed])
                if vectors:
                    payload = {
                        "title": art.title,
                        "url": art.url,
                        "source_id": str(art.source_id),
                        "published_at": art.published_at.isoformat() if art.published_at else None,
                    }
                    await vector_service.upsert_article(
                        article_id=art.id,
                        vector=vectors[0],
                        payload=payload
                    )
                    art.embedding_status = "completed"
            except Exception as e:
                logger.error("Embedding failed for %s: %s", art.id, e)
                continue

            # Step 2: Event Extraction
            content = art.content or art.description or ""
            pub_at = art.published_at.isoformat() if art.published_at else None
            try:
                event_response = await event_service.extract_events(
                    title=art.title or "",
                    content=content,
                    published_at=pub_at
                )

                pe = event_response.primary_event
                from app.services.event_taxonomy import get_parent_type
                from app.workers.tasks import _try_parse_event_time

                parsed_time = _try_parse_event_time(pe.event_time)
                fingerprint = event_service.compute_event_fingerprint(pe)

                primary_event = ArticleEvent(
                    id=uuid.uuid4(),
                    article_id=art.id,
                    is_primary=True,
                    event_type=pe.event_type,
                    event_type_canonical=get_parent_type(pe.event_type),
                    actors=pe.actors,
                    targets=pe.targets,
                    objects=pe.objects,
                    location=pe.location,
                    event_time=parsed_time,
                    event_time_raw=pe.event_time,
                    numbers=pe.numbers,
                    confidence=pe.confidence,
                    event_fingerprint=fingerprint,
                )
                session.add(primary_event)
                art.event_extraction_status = "completed"
                await session.commit()

            except Exception as e:
                logger.error("Extraction failed for %s: %s", art.id, e)
                continue

            # Step 3: Pipeline Coordinator (Stage A -> Stage B -> Reflection / Merge / Discovery)
            is_merged = await pipeline_coordinator.process_article(session, art.id)
            if is_merged:
                merged_count += 1
            else:
                discovery_count += 1

            success_count += 1

        # Step 4: Run batch clustering (Trigger HDBSCAN)
        logger.info("Triggering HDBSCAN batch clustering for Discovery Queue...")
        from app.services.clustering_service import clustering_service

        cluster_start = time.perf_counter()
        await clustering_service._run_batch_clustering_locked(session)
        cluster_latency = (time.perf_counter() - cluster_start) * 1000.0

        # Calculate quality metrics
        stmt_sa = select(StoryArticle.article_id, StoryArticle.story_id).where(StoryArticle.article_id.in_(article_ids))
        res_sa = await session.execute(stmt_sa)
        story_mappings = {row.article_id: row.story_id for row in res_sa.all()}

        clusters = {}
        outliers_count = 0
        for aid in article_ids:
            sid = story_mappings.get(aid)
            if sid:
                clusters.setdefault(sid, []).append(aid)
            else:
                outliers_count += 1

        cluster_count = len(clusters)
        avg_cluster_size = sum(len(v) for v in clusters.values()) / cluster_count if cluster_count > 0 else 0.0

        # Calculate silhouette score using scikit-learn
        import numpy as np
        from sklearn.metrics import silhouette_score

        silhouette = 0.0
        try:
            clustered_aids = [aid for aids in clusters.values() for aid in aids]
            if len(clustered_aids) >= 2 and cluster_count >= 2:
                points = await vector_service.client.retrieve(
                    collection_name="articles", ids=[str(aid) for aid in clustered_aids], with_vectors=True
                )
                points_dict = {uuid.UUID(str(p.id)): p.vector for p in points if p.vector}

                X = []
                labels = []
                for label_idx, (sid, aids) in enumerate(clusters.items()):
                    for aid in aids:
                        if aid in points_dict:
                            X.append(points_dict[aid])
                            labels.append(label_idx)

                if len(set(labels)) >= 2:
                    silhouette = float(silhouette_score(np.array(X), np.array(labels)))
        except Exception as sil_err:
            logger.debug("Silhouette calculation skipped: %s", sil_err)

        # Store benchmark statistics in local history JSON
        history_file = "pipeline_replay_history.json"
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file) as f:
                    history = json.load(f)
            except Exception:
                pass

        run_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "dataset": dataset,
            "live": live,
            "articles_processed": len(article_ids),
            "success_count": success_count,
            "merged_count": merged_count,
            "discovery_count": discovery_count,
            "cluster_count": cluster_count,
            "outliers_count": outliers_count,
            "avg_cluster_size": avg_cluster_size,
            "silhouette_score": silhouette,
            "cluster_latency_ms": cluster_latency
        }

        history.append(run_data)
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)

        # Write markdown report
        report_md = f"""# Pipeline Replay Benchmark Report
**Timestamp**: {run_data['timestamp']}
**Dataset**: {run_data['dataset']}
**Mode**: {"Live (NIM/Gemini)" if run_data['live'] else "Mocked (Offline)"}

## Run Metrics
- Total Articles Processed: {run_data['articles_processed']}
- Success Rate: {(run_data['success_count']/run_data['articles_processed'])*100:.1f}%
- Stage B Direct Merges: {run_data['merged_count']}
- Sent to Discovery Queue: {run_data['discovery_count']}

## Clustering & Quality Metrics
- HDBSCAN Clusters Formed: {run_data['cluster_count']}
- Outliers (Unclustered): {run_data['outliers_count']}
- Average Cluster Size: {run_data['avg_cluster_size']:.1f} articles
- Silhouette Score: {run_data['silhouette_score']:.4f}
- HDBSCAN Execution Latency: {run_data['cluster_latency_ms']:.1f}ms
"""

        if compare and len(history) >= 2:
            prev = history[-2]
            report_md += f"""
## Regression Comparison (vs Previous Run)
| Metric | Previous ({prev['timestamp'][:16]}) | Current | Change |
| :--- | :--- | :--- | :--- |
| Processed | {prev['articles_processed']} | {run_data['articles_processed']} | {run_data['articles_processed'] - prev['articles_processed']} |
| Merged | {prev['merged_count']} | {run_data['merged_count']} | {run_data['merged_count'] - prev['merged_count']} |
| Discovery | {prev['discovery_count']} | {run_data['discovery_count']} | {run_data['discovery_count'] - prev['discovery_count']} |
| Clusters | {prev['cluster_count']} | {run_data['cluster_count']} | {run_data['cluster_count'] - prev['cluster_count']} |
| Outliers | {prev['outliers_count']} | {run_data['outliers_count']} | {run_data['outliers_count'] - prev['outliers_count']} |
| Silhouette | {prev['silhouette_score']:.4f} | {run_data['silhouette_score']:.4f} | {run_data['silhouette_score'] - prev['silhouette_score']:.4f} |
| Latency | {prev['cluster_latency_ms']:.1f}ms | {run_data['cluster_latency_ms']:.1f}ms | {run_data['cluster_latency_ms'] - prev['cluster_latency_ms']:.1f}ms |
"""

        with open("pipeline_benchmark_report.md", "w") as f:
            f.write(report_md)

        logger.info("Replay complete! Benchmark report saved to pipeline_benchmark_report.md")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline Replay Tool")
    parser.add_argument("--limit", type=int, default=100, help="Number of articles to replay")
    parser.add_argument("--live", action="store_true", help="Use live AI models (no mocks)")
    parser.add_argument("--dataset", type=str, default="historical", choices=["historical", "yesterday", "custom"], help="Source dataset")
    parser.add_argument("--compare", action="store_true", help="Compare with the previous replay runs")
    args = parser.parse_args()

    asyncio.run(replay_pipeline(args.limit, args.live, args.dataset, args.compare))
