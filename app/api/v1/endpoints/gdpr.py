from typing import Annotated
from fastapi import APIRouter, Depends, Query
from app.api.deps import RoleChecker
from app.models.user import User
from app.workers.main import scrub_gdpr_data

router = APIRouter()

allow_super_admin = RoleChecker(["admin"])

@router.post("/scrub")
async def trigger_gdpr_scrub(
    current_user: Annotated[User, Depends(allow_super_admin)],
    days_after_end: int = Query(30, description="Number of days after tournament end date to scrub data")
):
    """Manually trigger the GDPR scrubbing background task."""
    task = scrub_gdpr_data.delay(days_after_end)
    return {
        "message": f"GDPR scrub task dispatched for tournaments ended {days_after_end} days ago.", 
        "task_id": task.id
    }