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
        orgs_data = [
            {"name": "Team Algeria", "type": "Country Team"},
            {"name": "Team Angola", "type": "Country Team"},
            {"name": "Team Benin", "type": "Country Team"},
            {"name": "Team Botswana", "type": "Country Team"},
            {"name": "Team Burkina Faso", "type": "Country Team"},
            {"name": "Team Burundi", "type": "Country Team"},
            {"name": "Team Cabo Verde", "type": "Country Team"},
            {"name": "Team Cameroon", "type": "Country Team"},
            {"name": "Team Central African Republic", "type": "Country Team"},
            {"name": "Team Chad", "type": "Country Team"},
            {"name": "Team Comoros", "type": "Country Team"},
            {"name": "Team Congo", "type": "Country Team"},
            {"name": "Team Congo (DRC)", "type": "Country Team"},
            {"name": "Team Côte d'Ivoire", "type": "Country Team"},
            {"name": "Team Djibouti", "type": "Country Team"},
            {"name": "Team Egypt", "type": "Country Team"},
            {"name": "Team Equatorial Guinea", "type": "Country Team"},
            {"name": "Team Eritrea", "type": "Country Team"},
            {"name": "Team Eswatini", "type": "Country Team"},
            {"name": "Team Ethiopia", "type": "Country Team"},
            {"name": "Team Gabon", "type": "Country Team"},
            {"name": "Team Gambia", "type": "Country Team"},
            {"name": "Team Ghana", "type": "Country Team"},
            {"name": "Team Guinea", "type": "Country Team"},
            {"name": "Team Guinea-Bissau", "type": "Country Team"},
            {"name": "Team Kenya", "type": "Country Team"},
            {"name": "Team Lesotho", "type": "Country Team"},
            {"name": "Team Liberia", "type": "Country Team"},
            {"name": "Team Libya", "type": "Country Team"},
            {"name": "Team Madagascar", "type": "Country Team"},
            {"name": "Team Malawi", "type": "Country Team"},
            {"name": "Team Mali", "type": "Country Team"},
            {"name": "Team Mauritania", "type": "Country Team"},
            {"name": "Team Mauritius", "type": "Country Team"},
            {"name": "Team Morocco", "type": "Country Team"},
            {"name": "Team Mozambique", "type": "Country Team"},
            {"name": "Team Namibia", "type": "Country Team"},
            {"name": "Team Niger", "type": "Country Team"},
            {"name": "Team Nigeria", "type": "Country Team"},
            {"name": "Team Rwanda", "type": "Country Team"},
            {"name": "Team São Tomé and Príncipe", "type": "Country Team"},
            {"name": "Team Senegal", "type": "Country Team"},
            {"name": "Team Seychelles", "type": "Country Team"},
            {"name": "Team Sierra Leone", "type": "Country Team"},
            {"name": "Team Somalia", "type": "Country Team"},
            {"name": "Team South Africa", "type": "Country Team"},
            {"name": "Team South Sudan", "type": "Country Team"},
            {"name": "Team Sudan", "type": "Country Team"},
            {"name": "Team Tanzania", "type": "Country Team"},
            {"name": "Team Togo", "type": "Country Team"},
            {"name": "Team Tunisia", "type": "Country Team"},
            {"name": "Team Uganda", "type": "Country Team"},
            {"name": "Team Zambia", "type": "Country Team"},
            {"name": "Team Zimbabwe", "type": "Country Team"},
            {"name": "LOC Staff", "type": "LOC"},
            {"name": "Media", "type": "Media"},
            {"name": "Technical Official", "type": "Technical Official"},
            {"name": "Ghana Athletics Association", "type": "National Federation"},
            {"name": "Volunteer", "type": "Volunteer"},
            {"name": "Service Staff", "type": "Service Staff"},
            {"name": "VIP/Guest", "type": "VIP/Guest"},
            {"name": "Confederation of African Athletics", "type": "African Federation"},
            {"name": "World Athletics", "type": "World Federation"}
        ]
        
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