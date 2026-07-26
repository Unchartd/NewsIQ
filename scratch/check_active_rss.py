import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.models.models import Source

DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_teKmQ68VBwnb@ep-sweet-moon-aoen0iyx.c-2.ap-southeast-1.aws.neon.tech/neondb"

async def main():
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        res = await session.execute(select(Source).where(Source.rss_url != None))
        sources = res.scalars().all()
        print(f"Total RSS sources in database: {len(sources)}")
        for s in sources:
            print(f"Name: '{s.name}' | Active: {s.active} | RSS: {s.rss_url}")

if __name__ == "__main__":
    asyncio.run(main())
