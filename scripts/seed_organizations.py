import csv
import re
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config.settings import settings
from app.schemas.application import ApplicationCategory

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
                    
            # 1. Auto-seed missing categories to prevent dropdown missing items
            print("Ensuring all required categories exist in the database...")
            for cat in ApplicationCategory:
                cat_name = cat.value
                check_cat = text("SELECT id FROM categories WHERE name = :name LIMIT 1")
                if not (await conn.execute(check_cat, {"name": cat_name})).fetchone():
                    insert_cat = text("INSERT INTO categories (id, name, created_at) VALUES (gen_random_uuid(), :name, NOW())")
                    await conn.execute(insert_cat, {"name": cat_name})
                    print(f"Created missing category: {cat_name}")

            reader = csv.DictReader(content.splitlines())
            
            # Fix: Strip hidden newlines/spaces from CSV headers (especially the last column!)
            if reader.fieldnames:
                reader.fieldnames = [field.strip() for field in reader.fieldnames if field]
            
            for row in reader:
                # Normalize spaces: trim edges and replace multiple internal spaces with a single space
                org_name = re.sub(r'\s+', ' ', row["Organisation"].strip())
                org_type = row.get("Category", "Generic").strip()
                
                # Fuzzy matching: Safely capture TRUE, 1, YES, or Y using keyword detection in the headers
                allowed_categories = []
                for key, val in row.items():
                    if not key or not val:
                        continue
                    key_upper = key.strip().upper()
                    val_upper = str(val).strip().upper()
                    
                    if val_upper in ["TRUE", "1", "YES", "Y", "X"]:
                        if "ATHLETE" in key_upper: allowed_categories.append(ApplicationCategory.athlete.value)
                        elif "TEAM OFFICIAL" in key_upper: allowed_categories.append(ApplicationCategory.team_officials.value)
                        elif "COACH" in key_upper: allowed_categories.append(ApplicationCategory.coaches.value)
                        elif "MEDICAL" in key_upper: allowed_categories.append(ApplicationCategory.medical_staff.value)
                        elif "TECHNICAL" in key_upper: allowed_categories.append(ApplicationCategory.technical_officials.value)
                        elif "LOC" in key_upper: allowed_categories.append(ApplicationCategory.loc_staff.value)
                        elif "VOLUNTEER" in key_upper: allowed_categories.append(ApplicationCategory.volunteer.value)
                        elif "MEDIA" in key_upper: allowed_categories.append(ApplicationCategory.media.value)
                        elif "VIP" in key_upper: allowed_categories.append(ApplicationCategory.vip_guests.value)
                        elif "SERVICE" in key_upper: allowed_categories.append(ApplicationCategory.service_staff.value)
                        
                # Remove any accidental duplicates
                allowed_categories = list(set(allowed_categories))
                
                # Use ILIKE to match "Team Ghana" in the DB even if the CSV just says "Ghana"
                search_name = f"%{org_name}%"
                check_query = text("SELECT id FROM organizations WHERE name ILIKE :name LIMIT 1")
                result = await conn.execute(check_query, {"name": search_name})
                existing_org = result.fetchone()
                
                if existing_org:
                    # Update existing organization (Safely cast array for PostgreSQL)
                    update_query = text("""
                        UPDATE organizations 
                        SET type = :type, allowed_categories = CAST(:allowed_categories AS VARCHAR[]) 
                        WHERE id = :id
                    """)
                    await conn.execute(update_query, {"type": org_type, "allowed_categories": allowed_categories, "id": existing_org[0]})
                else:
                    # Insert new organization
                    insert_query = text("""
                        INSERT INTO organizations (id, name, type, allowed_categories)
                        VALUES (gen_random_uuid(), :name, :type, CAST(:allowed_categories AS VARCHAR[]))
                    """)
                    await conn.execute(insert_query, {"name": org_name, "type": org_type, "allowed_categories": allowed_categories})
        print("Successfully seeded all organizations and their allowed categories from the CSV!")
    except Exception as e:
        print(f"Failed to seed database: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_organizations())