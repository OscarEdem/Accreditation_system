import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from redis.asyncio import Redis

# Import your dependencies and models
from app.db.session import get_db
from app.db.redis import get_redis
from app.schemas.stats import PublicStatsResponse
from app.models.application import Application
from app.models.category import Category
from app.models.zone import Zone

router = APIRouter()

@router.get("/stats", response_model=PublicStatsResponse, summary="Get Public Tournament Stats")
async def get_public_stats(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
):
    """
    Public endpoint to expose aggregate tournament statistics.
    Results are cached in Redis for 10 minutes to protect the database from public traffic spikes.
    """
    cache_key = "public_tournament_stats"
    cached_stats = await redis.get(cache_key)
    
    # 1. Return cached stats instantly if available
    if cached_stats:
        return json.loads(cached_stats)
        
    # 2. Cache miss: Query the database with optimized count aggregations
    applications_count = await db.scalar(select(func.count(Application.id)))
    
    # Count unique countries applied from
    countries_count = await db.scalar(select(func.count(func.distinct(Application.country))))
    
    # Count Categories and Zones
    categories_count = await db.scalar(select(func.count(Category.id)))
    zones_count = await db.scalar(select(func.count(Zone.id)))
    
    stats = {
        "total_applications": applications_count or 0,
        "total_countries": countries_count or 0,
        "total_categories": categories_count or 0,
        "total_zones": zones_count or 0
    }
    
    # 3. Store the result in Redis with a 10-minute (600 seconds) expiration
    await redis.set(cache_key, json.dumps(stats), ex=600)
    
    return stats