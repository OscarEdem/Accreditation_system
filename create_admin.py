import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.config.settings import settings
from app.models.user import User

from app.core.security import get_password_hash

async def create_admin():
    print("Connecting to database...")
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        # 1. Check if the admin already exists
        result = await session.execute(select(User).where(User.email == "admin@example.com"))
        user = result.scalars().first()
        
        if user:
            print("Admin user already exists!")
            return

        # 2. Create the new admin user
        admin = User(
            first_name="Super",
            last_name="Admin",
            email="admin@example.com",
            role="admin",
            password_hash=get_password_hash("admin123"),
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )
        session.add(admin)
        await session.commit()
        print("✅ Admin user created successfully! Email: admin@example.com")

if __name__ == "__main__":
    asyncio.run(create_admin())