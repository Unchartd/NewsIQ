"""Seed script — populates categories and initial sources.

Run with:
    python -m app.scripts.seed
"""

import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.models import Category, Source

CATEGORIES = [
    {"slug": "politics", "name": "Politics", "icon": "landmark"},
    {"slug": "technology", "name": "Technology", "icon": "cpu"},
    {"slug": "business", "name": "Business", "icon": "briefcase"},
    {"slug": "sports", "name": "Sports", "icon": "trophy"},
    {"slug": "health", "name": "Health", "icon": "heart-pulse"},
    {"slug": "science", "name": "Science", "icon": "flask-conical"},
    {"slug": "entertainment", "name": "Entertainment", "icon": "clapperboard"},
    {"slug": "weather", "name": "Weather", "icon": "cloud-sun"},
    {"slug": "world", "name": "World", "icon": "globe"},
]

SOURCES = [
    {
        "name": "Reuters",
        "slug": "reuters",
        "website_url": "https://www.reuters.com",
        "rss_url": "https://www.rss.reuters.com/news/topnews",
        "country_code": "US",
    },
    {
        "name": "BBC News",
        "slug": "bbc-news",
        "website_url": "https://www.bbc.com/news",
        "rss_url": "http://feeds.bbci.co.uk/news/rss.xml",
        "country_code": "GB",
    },
    {
        "name": "TechCrunch",
        "slug": "techcrunch",
        "website_url": "https://techcrunch.com",
        "rss_url": "https://techcrunch.com/feed/",
        "country_code": "US",
    },
    {
        "name": "The Verge",
        "slug": "the-verge",
        "website_url": "https://www.theverge.com",
        "rss_url": "https://www.theverge.com/rss/index.xml",
        "country_code": "US",
    },
    {
        "name": "NDTV",
        "slug": "ndtv",
        "website_url": "https://www.ndtv.com",
        "rss_url": "https://feeds.feedburner.com/ndtvnews-top-stories",
        "country_code": "IN",
    },
    {
        "name": "The Times of India",
        "slug": "times-of-india",
        "website_url": "https://timesofindia.indiatimes.com",
        "rss_url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        "country_code": "IN",
    },
    {
        "name": "Hindustan Times",
        "slug": "hindustan-times",
        "website_url": "https://www.hindustantimes.com",
        "rss_url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
        "country_code": "IN",
    },
    {
        "name": "The Indian Express",
        "slug": "indian-express",
        "website_url": "https://indianexpress.com",
        "rss_url": "https://indianexpress.com/section/india/feed/",
        "country_code": "IN",
    },
    {
        "name": "Al Jazeera",
        "slug": "al-jazeera",
        "website_url": "https://www.aljazeera.com",
        "rss_url": "https://www.aljazeera.com/xml/rss/all.xml",
        "country_code": "QA",
    },
    {
        "name": "Ars Technica",
        "slug": "ars-technica",
        "website_url": "https://arstechnica.com",
        "rss_url": "https://feeds.arstechnica.com/arstechnica/index",
        "country_code": "US",
    },
    {
        "name": "The Guardian",
        "slug": "the-guardian",
        "website_url": "https://www.theguardian.com",
        "rss_url": "https://www.theguardian.com/world/rss",
        "country_code": "GB",
    },
    {
        "name": "CNN",
        "slug": "cnn",
        "website_url": "https://www.cnn.com",
        "rss_url": "http://rss.cnn.com/rss/edition.rss",
        "country_code": "US",
    },
]


async def seed():
    """Seed database with categories and initial news sources."""
    async with async_session_factory() as session:
        # Seed categories
        for cat_data in CATEGORIES:
            result = await session.execute(
                select(Category).where(Category.slug == cat_data["slug"])
            )
            existing = result.scalar_one_or_none()
            if not existing:
                category = Category(
                    id=uuid.uuid4(),
                    slug=cat_data["slug"],
                    name=cat_data["name"],
                    icon=cat_data["icon"],
                    created_at=datetime.utcnow(),
                )
                session.add(category)
                print(f"  ✅ Category: {cat_data['name']}")
            else:
                print(f"  ⏭️  Category already exists: {cat_data['name']}")

        # Seed sources
        for src_data in SOURCES:
            result = await session.execute(select(Source).where(Source.slug == src_data["slug"]))
            existing = result.scalar_one_or_none()
            if not existing:
                source = Source(
                    id=uuid.uuid4(),
                    name=src_data["name"],
                    slug=src_data["slug"],
                    website_url=src_data["website_url"],
                    rss_url=src_data["rss_url"],
                    country_code=src_data["country_code"],
                    active=True,
                    created_at=datetime.utcnow(),
                )
                session.add(source)
                print(f"  ✅ Source: {src_data['name']}")
            else:
                print(f"  ⏭️  Source already exists: {src_data['name']}")

        await session.commit()
    print("\n🎉 Seeding complete!")


if __name__ == "__main__":
    print("🌱 Seeding NewsIQ database...\n")
    asyncio.run(seed())
