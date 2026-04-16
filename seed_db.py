import asyncio
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.config.settings import settings
from app.models.organization import Organization
from app.models.category import Category
from app.models.venue import Venue
from app.models.tournament import Tournament
from app.schemas.application import ApplicationCategory
from app.core.constants import SEEDED_ORGANIZATIONS

async def seed_database():
    print("Connecting to live database...")
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        # 1. Seed Categories dynamically from the ApplicationCategory Enum
        print("Seeding categories...")
        cat_result = await session.execute(select(Category.name))
        existing_cats = set(cat_result.scalars().all())
        
        new_cats = [Category(name=cat.value) for cat in ApplicationCategory if cat.value not in existing_cats]
        if new_cats:
            session.add_all(new_cats)
            await session.commit()
        print(f"✅ Categories Seeded: {len(new_cats)}")

        # 2. Seed Organizations
        # This mapping is illustrative. A more robust system might store types in the constants file too.
        org_types = {name: "Country Team" for name in SEEDED_ORGANIZATIONS if name.startswith("Team")}
        org_types.update({
            "LOC Staff": "LOC", "Media": "Media", "International Technical Official": "Technical Official",
            "Ghana Athletics Association": "National Federation", "Volunteer": "Volunteer",
            "Service Staff": "Service Staff", "VIP/Guest": "VIP/Guest",
            "Confederation of African Athletics": "African Federation", "World Athletics": "World Federation"
        })
        orgs_data = [{"name": name, "type": org_types.get(name, "Generic")} for name in SEEDED_ORGANIZATIONS]
        
        print(f"Seeding {len(orgs_data)} organizations...")
        result = await session.execute(select(Organization.name))
        existing_orgs = set(result.scalars().all())
        
        new_orgs = [Organization(**data) for data in orgs_data if data["name"] not in existing_orgs]
        if new_orgs:
            session.add_all(new_orgs)
            await session.commit()
            
        print(f"✅ Organizations Seeded: {len(new_orgs)}")

        # 3. Seed Default Venue
        print("Seeding default venue...")
        venue_result = await session.execute(select(Venue).where(Venue.name == "University of Ghana Sports Stadium"))
        default_venue = venue_result.scalars().first()
        if not default_venue:
            default_venue = Venue(
                name="University of Ghana Sports Stadium",
                address="Legon, Accra, Ghana",
                capacity=10000,
                contact_email="venue@accra2026.com"
            )
            session.add(default_venue)
            await session.commit()
            await session.refresh(default_venue)
            print("✅ Default Venue Seeded")

        # 4. Seed Default Tournament
        print("Seeding default tournament...")
        tourn_result = await session.execute(select(Tournament).where(Tournament.name == "ACCRA 2026 African Athletics Championships"))
        default_tourn = tourn_result.scalars().first()
        if not default_tourn:
            default_tourn = Tournament(
                name="ACCRA 2026 African Athletics Championships",
                start_date=date(2026, 4, 1),
                end_date=date(2026, 4, 15),
                host_city="Accra",
                venue_id=default_venue.id,
                description="The official African Athletics Championships."
            )
            session.add(default_tourn)
            await session.commit()
            print("✅ Default Tournament Seeded")
            
        print("✅ Database Seeding Complete!")

if __name__ == "__main__":
    asyncio.run(seed_database())