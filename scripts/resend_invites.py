import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config.settings import settings
from app.services.user import UserService
from app.workers.main import send_email_notification

#  List the emails of the people who missed their invite here:
EMAILS_TO_RESEND = [
    "lamine.faty@caaweb.org",
    "caa@caaweb.org",
    "ezofat@gmail.com",
    "caa2026accra@gmail.com",
]

async def resend_invites():
    print("Connecting to database...")
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        service = UserService(session)
        
        for email in EMAILS_TO_RESEND:
            user = await service.get_user_by_email(email)
            if user:
                print(f"Queueing invite email for {email}...")
                token = service.create_invite_token(user.email)
                invite_link = f"{settings.FRONTEND_URL}/accept-invite?token={token}"
                resend_link = f"{settings.FRONTEND_URL}/resend-invite"
                
                # Dispatch to the newly fixed Celery worker
                send_email_notification.delay(
                    recipient_email=user.email,
                    template_key="user_invite",
                    language=user.preferred_language or 'en',
                    context={
                        "first_name": user.first_name,
                        "role": user.role.value if hasattr(user.role, 'value') else user.role,
                        "invite_link": invite_link,
                        "resend_link": resend_link
                    }
                )
            else:
                print(f"⚠️ User not found in database: {email}")
        
    print("✅ All specified invites have been queued for sending!")

if __name__ == "__main__":
    asyncio.run(resend_invites())