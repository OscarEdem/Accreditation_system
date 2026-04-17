import csv
import re
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config.settings import settings

# Map the CSV headers to the exact Category enums expected by your database
CATEGORY_MAP = {
    "a": "Athlete",  # 'a' header from CSV mapped to Athlete
    "Team Officials": "Team Official",
    "Technical Officials": "Technical Official",
    "LOC Staff": "LOC Staff",
    "Volunteers": "Volunteer",
    "Media": "Media",
    "VIP/Guests": "VIP/Guest",
    "Service Staff": "Service Staff"
}

async def seed_organizations():
    print(f"Connecting to database: {settings.DATABASE_URL.split('@')[-1]}")
    engine = create_async_engine(settings.DATABASE_URL)
    
    csv_path = "Accreditation_Management_Organisations(Organisations).csv"
    
    try:
        async with engine.begin() as conn:
            with open(csv_path, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    # Normalize spaces: trim edges and replace multiple internal spaces with a single space
                    org_name = re.sub(r'\s+', ' ', row["Organisation"].strip())
                    org_type = row["Category"].strip()
                    
                    # Build the array of allowed categories based on TRUE values
                    allowed_categories = [
                        db_cat for csv_col, db_cat in CATEGORY_MAP.items()
                        if row.get(csv_col, "").strip().upper() == "TRUE"
                    ]
                    
                    # Upsert logic (Insert or Update if the organization name already exists)
                    query = text("""
                        INSERT INTO organizations (id, name, type, allowed_categories)
                        VALUES (gen_random_uuid(), :name, :type, :allowed_categories)
                        ON CONFLICT (name) DO UPDATE 
                        SET type = EXCLUDED.type, 
                            allowed_categories = EXCLUDED.allowed_categories;
                    """)
                    
                    await conn.execute(query, {
                        "name": org_name,
                        "type": org_type,
                        "allowed_categories": allowed_categories
                    })
        print("Successfully seeded all organizations and their allowed categories from the CSV!")
    except Exception as e:
        print(f"Failed to seed database: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_organizations())