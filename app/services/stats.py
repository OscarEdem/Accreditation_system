from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.application import Application
from app.models.participant import Participant
from app.models.scan_log import ScanLog
from app.models.organization import Organization
from app.schemas.stats import DashboardStats

class StatsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_dashboard_stats(self) -> DashboardStats:
        # 1. Aggregate Application Data
        app_stmt = select(Application.status, func.count(Application.id)).group_by(Application.status)
        app_result = await self.session.execute(app_stmt)
        app_counts = dict(app_result.all())

        total_apps = sum(app_counts.values())
        pending_apps = app_counts.get("pending", 0)
        approved_apps = app_counts.get("approved", 0)
        rejected_apps = app_counts.get("rejected", 0)

        # 2. Count Total Participants
        part_stmt = select(func.count(Participant.id))
        total_parts = (await self.session.execute(part_stmt)).scalar() or 0

        # 3. Count Total Organizations
        org_stmt = select(func.count(Organization.id))
        total_orgs = (await self.session.execute(org_stmt)).scalar() or 0

        # 4. Aggregate Scan Data
        scan_stmt = select(ScanLog.access_granted, func.count(ScanLog.id)).group_by(ScanLog.access_granted)
        scan_result = await self.session.execute(scan_stmt)
        scan_counts = dict(scan_result.all())
        
        return DashboardStats(
            total_applications=total_apps,
            pending_applications=pending_apps,
            approved_applications=approved_apps,
            rejected_applications=rejected_apps,
            total_participants=total_parts,
            total_organizations=total_orgs,
            total_scans=sum(scan_counts.values()),
            granted_scans=scan_counts.get(True, 0),
            denied_scans=scan_counts.get(False, 0)
        )