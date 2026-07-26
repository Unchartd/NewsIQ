import asyncio
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.models.models import Source

DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_teKmQ68VBwnb@ep-sweet-moon-aoen0iyx.c-2.ap-southeast-1.aws.neon.tech/neondb"

WHITELIST = {
    "reuters",
    "cnn",
    "fox news",
    "the guardian",
    "al jazeera",
    "france 24",
    "dw",
    "the hindu",
    "the times of india",
    "ndtv",
    "hindustan times",
    "the indian express",
    "ani news",
    "cnbc",
    "techcrunch",
    "the verge"
}

async def process_sources(commit=False):
    engine = create_async_engine(DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as session:
        stmt = select(Source)
        res = await session.execute(stmt)
        sources = res.scalars().all()
        
        deactivated_count = 0
        activated_count = 0
        ignored_count = 0
        
        active_list = []
        
        print("Dry Run Details:" if not commit else "Execution Details:")
        for src in sources:
            name_lower = src.name.strip().lower()
            # Special case for "reuters", "dw", etc. that could be sub-brands or exact matches
            is_whitelisted = name_lower in WHITELIST or any(w == name_lower for w in WHITELIST)
            
            if is_whitelisted:
                active_list.append(src.name)
                if not src.active:
                    print(f"  [ACTIVATE] '{src.name}' (slug: {src.slug}, active: {src.active})")
                    src.active = True
                    activated_count += 1
                else:
                    ignored_count += 1
            else:
                if src.active:
                    print(f"  [DEACTIVATE] '{src.name}' (slug: {src.slug}, active: {src.active})")
                    src.active = False
                    deactivated_count += 1
                else:
                    ignored_count += 1
                    
        print(f"\nActive Whitelisted Sources Found:")
        print(f"  {sorted(active_list)}")
        
        print(f"\nSummary:")
        print(f"  To deactivate (active=True -> active=False): {deactivated_count}")
        print(f"  To activate (active=False -> active=True): {activated_count}")
        print(f"  Total untouched sources: {ignored_count}")
        
        if commit:
            await session.commit()
            print("\nDatabase changes committed successfully!")
        else:
            print("\nThis was a DRY RUN. No changes were saved to the database. Run with --commit to execute.")

async def main():
    commit = "--commit" in sys.argv
    await process_sources(commit=commit)

if __name__ == "__main__":
    asyncio.run(main())
