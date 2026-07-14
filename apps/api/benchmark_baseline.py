"""Baseline benchmark runner for NewsIQ AI pipeline.

Fetches a story with articles from the DB, regenerates it, and logs performance.
"""

import asyncio
import json
import os
import sys
import time

from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Ensure apps/api is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import async_session_factory
from app.models.models import Story, StoryArticle
from app.services.clustering_service import clustering_service
from app.services.cost_budget import cost_budget_manager


async def run_benchmark():
    print("Starting baseline benchmarking...")

    async with async_session_factory() as session:
        # 1. Fetch a story that has associated articles
        stmt = (
            select(Story)
            .join(StoryArticle)
            .options(selectinload(Story.articles).selectinload(StoryArticle.article))
            .limit(1)
        )
        res = await session.execute(stmt)
        story = res.scalar_one_or_none()

        if not story:
            print(
                "ERROR: No stories with articles found in the database. Please seed or run ingestion first."
            )
            sys.exit(1)

        print(f"Selected Story ID: {story.id} | Headline: '{story.headline}'")
        articles = [sa.article for sa in story.articles]
        print(f"Associated articles count: {len(articles)}")

        # 2. Reset story cost budget tracker in Redis to ensure clean start
        from app.services.cache_service import cache_service

        await cache_service.delete(f"story_cost:{story.id}")

        # 3. Regenerate story content and measure latency + cost
        start_time = time.perf_counter()

        try:
            await clustering_service.generate_story_content(story, articles, session, commit=True)
            success = True
            error_msg = None
        except Exception as e:
            success = False
            error_msg = str(e)
            print(f"Story content generation failed: {e}")

        duration = time.perf_counter() - start_time
        accumulated_cost = await cost_budget_manager.get_story_cost(str(story.id))

        # 4. Compile benchmark report
        report = {
            "story_id": str(story.id),
            "articles_count": len(articles),
            "generation_success": success,
            "error": error_msg,
            "latency_seconds": round(duration, 4),
            "accumulated_cost_usd": accumulated_cost,
            "timestamp": datetime_now_iso(),
            "environment": "baseline",
        }

        print("\n--- BENCHMARK REPORT ---")
        print(json.dumps(report, indent=2))

        # Save report
        out_path = r"C:\Users\zakau\NewsIQ\apps\api\benchmark_baseline.json"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to: {out_path}")


def datetime_now_iso():
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    asyncio.run(run_benchmark())
