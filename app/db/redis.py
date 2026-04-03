from typing import AsyncGenerator
from redis.asyncio import Redis, from_url
from app.config.settings import settings

async def get_redis() -> AsyncGenerator[Redis, None]:
    client = from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()