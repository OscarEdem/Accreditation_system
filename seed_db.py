import asyncio
from datetime import date, datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
from app.models.venue import Venue
from app.models.tournament import Tournament

async def seed_database():
    print("Connecting to live database...")
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        # 1. Create a Test Venue
        venue = Venue(
            name="Accra Olympic Stadium",
            address="123 Sports Avenue, Accra",
            capacity=50000,
            contact_email="stadium@example.com",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        session.add(venue)
        await session.commit()
        
        # 2. Create a Test Tournament
        tournament = Tournament(
            name="African Games 2026",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 15),
            venue_id=venue.id,
            description="The premier continental sporting event.",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        session.add(tournament)
        await session.commit()
        
        print(f"✅ Seed complete!\nVenue ID: {venue.id}\nTournament ID: {tournament.id}")

if __name__ == "__main__":
    asyncio.run(seed_database())