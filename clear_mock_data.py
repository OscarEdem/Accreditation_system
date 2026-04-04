import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.config.settings import settings

async def clear_data():
    print("Connecting to live database...")
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        # We explicitly omit 'users' and 'organizations' to protect your Admin accounts.
        # CASCADE will automatically delete participants, badges, scan_logs, zone_access, etc.
        tables_to_clear = [
            "applications",
            "tournaments",
            "venues",
            "categories",
            "zones",
            "audit_logs"
        ]
        
        print(f"Clearing tables: {', '.join(tables_to_clear)} (and all dependent data)...")
        
        truncate_query = f"TRUNCATE {', '.join(tables_to_clear)} CASCADE;"
        
        await session.execute(text(truncate_query))
        await session.commit()
        
        print("✅ All mock data successfully wiped! Your Admin users are perfectly safe.")

if __name__ == "__main__":
    asyncio.run(clear_data())