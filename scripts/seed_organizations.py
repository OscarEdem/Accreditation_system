import csv
import re
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config.settings import settings

# Map the CSV headers to the exact Category enums expected by your database
CATEGORY_MAP = {
    "Athletes": "Athlete",  # Maps the 'Athletes' header from the CSV
    "Team Officials": "Team Officials",
    "Technical Officials": "Technical Officials",
    "LOC Staff": "LOC Staff",
    "Volunteers": "Volunteer",
    "Media": "Media",
    "VIP/Guests": "VIP/Guests",
    "Service Staff": "Service Staff"
}

async def seed_organizations():
    print(f"Connecting to database: {settings.DATABASE_URL.split('@')[-1]}")
    engine = create_async_engine(settings.DATABASE_URL)
    
    csv_path = "Accreditation_Management_Organisations(Organisations).csv"
    
    try:
        async with engine.begin() as conn:
            # Robustly read the file, falling back to Windows encoding if UTF-8 fails
            try:
                with open(csv_path, mode='r', encoding='utf-8-sig') as file:
                    content = file.read()
            except UnicodeDecodeError:
                # Fallback for CSVs saved using standard Excel on Windows
                with open(csv_path, mode='r', encoding='cp1252') as file:
                    content = file.read()
                    
            reader = csv.DictReader(content.splitlines())
            
            for row in reader:
                    # Normalize spaces: trim edges and replace multiple internal spaces with a single space
                    org_name = re.sub(r'\s+', ' ', row["Organisation"].strip())
                    org_type = row["Category"].strip()
                    
                    # Build the array of allowed categories based on TRUE values
                    allowed_categories = [
                        db_cat for csv_col, db_cat in CATEGORY_MAP.items()
                        if row.get(csv_col, "").strip().upper() == "TRUE"
                    ]
                    
                    # Check if organization already exists since 'name' lacks a UNIQUE constraint
                    check_query = text("SELECT id FROM organizations WHERE name = :name LIMIT 1")
                    result = await conn.execute(check_query, {"name": org_name})
                    existing_org = result.fetchone()
                    
                    if existing_org:
                        # Update existing organization
                        update_query = text("""
                            UPDATE organizations 
                            SET type = :type, allowed_categories = :allowed_categories 
                            WHERE id = :id
                        """)
                        await conn.execute(update_query, {"type": org_type, "allowed_categories": allowed_categories, "id": existing_org[0]})
                    else:
                        # Insert new organization
                        insert_query = text("""
                            INSERT INTO organizations (id, name, type, allowed_categories)
                            VALUES (gen_random_uuid(), :name, :type, :allowed_categories)
                        """)
                        await conn.execute(insert_query, {"name": org_name, "type": org_type, "allowed_categories": allowed_categories})
        print("Successfully seeded all organizations and their allowed categories from the CSV!")
    except Exception as e:
        print(f"Failed to seed database: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_organizations())