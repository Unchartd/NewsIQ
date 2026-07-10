import logging
from typing import Any

from redis.exceptions import ResponseError
from sqlalchemy import select

from app.models.models import Article
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class URLBloomFilter:
    """
    Bloom filter for fast URL deduplication checks.
    Uses RedisBloom if available, with a seamless fallback to Redis Sets.
    """

    KEY_BLOOM = "newsiq:bloom:url"
    KEY_SET = "newsiq:set:url"

    def __init__(self, cache_service: CacheService):
        self.redis = cache_service._redis
        self.use_bloom = True
        self.metrics = {
            "hit_count": 0,
            "miss_count": 0,
            "false_positives": 0,
            "fallback_used": False,
        }

    async def add(self, url_hash: str) -> bool:
        """
        Adds a url_hash to the filter.
        Returns True if it was added (wasn't there), False if it might already exist.
        """
        if not self.redis:
            return True  # Fail open

        try:
            if self.use_bloom:
                # BF.ADD returns 1 if item was newly added, 0 if it may exist
                res = await self.redis.execute_command("BF.ADD", self.KEY_BLOOM, url_hash)
                return res == 1
            else:
                res = await self.redis.sadd(self.KEY_SET, url_hash)  # type: ignore[misc]
                return res == 1
        except ResponseError as e:
            if "unknown command" in str(e).lower() and self.use_bloom:
                logger.warning(
                    "RedisBloom not available. Falling back to SADD for URL deduplication."
                )
                self.use_bloom = False
                self.metrics["fallback_used"] = True
                res = await self.redis.sadd(self.KEY_SET, url_hash)  # type: ignore[misc]
                return res == 1
            logger.error("Redis error adding to URL filter: %s", e)
            return True  # Fail open
        except Exception as e:
            logger.error("Error adding to URL filter: %s", e)
            return True

    async def exists(self, url_hash: str) -> bool:
        """
        Checks if a url_hash is in the filter.
        Returns True if it might exist, False if it definitely does not.
        """
        if not self.redis:
            return False  # Fail open, assume miss so we check DB

        try:
            if self.use_bloom:
                # BF.EXISTS returns 1 if item might exist, 0 if it definitely doesn't
                res = await self.redis.execute_command("BF.EXISTS", self.KEY_BLOOM, url_hash)
                if res == 1:
                    self.metrics["hit_count"] += 1
                else:
                    self.metrics["miss_count"] += 1
                return res == 1
            else:
                res = await self.redis.sismember(self.KEY_SET, url_hash)  # type: ignore[misc]
                if res:
                    self.metrics["hit_count"] += 1
                else:
                    self.metrics["miss_count"] += 1
                return bool(res)
        except ResponseError as e:
            if "unknown command" in str(e).lower() and self.use_bloom:
                self.use_bloom = False
                self.metrics["fallback_used"] = True
                res = await self.redis.sismember(self.KEY_SET, url_hash)  # type: ignore[misc]
                return bool(res)
            logger.error("Redis error checking URL filter: %s", e)
            return False  # Fail open
        except Exception as e:
            logger.error("Error checking URL filter: %s", e)
            return False

    async def rebuild(self, session: Any) -> None:
        """
        Repopulate the Bloom filter or Set from the database.
        Typically runs on startup to ensure persistence after Redis resets.
        """
        if not self.redis:
            return

        logger.info("Rebuilding URL filter from database...")
        # Get all non-null url_hashes from the DB
        stmt = select(Article.url_hash).where(Article.url_hash.is_not(None))
        result = await session.execute(stmt)
        url_hashes = result.scalars().all()

        if not url_hashes:
            logger.info("No URLs to rebuild.")
            return

        try:
            if self.use_bloom:
                # Clean up existing
                await self.redis.delete(self.KEY_BLOOM)
                # RedisBloom BF.MADD could be used, but BF.ADD in loop or pipeline is fine
                pipeline = self.redis.pipeline()
                for h in url_hashes:
                    pipeline.execute_command("BF.ADD", self.KEY_BLOOM, h)
                await pipeline.execute()
            else:
                await self.redis.delete(self.KEY_SET)
                # Can SADD multiple at once
                await self.redis.sadd(self.KEY_SET, *url_hashes)  # type: ignore[misc]
            logger.info("Rebuilt URL filter with %d entries.", len(url_hashes))
        except ResponseError as e:
            if "unknown command" in str(e).lower() and self.use_bloom:
                self.use_bloom = False
                self.metrics["fallback_used"] = True
                await self.redis.delete(self.KEY_SET)
                if url_hashes:
                    await self.redis.sadd(self.KEY_SET, *url_hashes)  # type: ignore[misc]
                logger.info("Rebuilt URL filter (fallback) with %d entries.", len(url_hashes))
            else:
                logger.error("Failed to rebuild URL filter: %s", e)
        except Exception as e:
            logger.error("Failed to rebuild URL filter: %s", e)
