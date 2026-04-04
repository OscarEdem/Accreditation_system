import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.models.user import User
from app.api.v1.endpoints.scan import get_scan_service
from app.db.redis import get_redis

client = TestClient(app)

# 1. Create a mock service so we don't need real DB/Redis for RBAC tests
class MockScanService:
    async def process_scan(self, participant_id: uuid.UUID, zone_id: uuid.UUID, serial_number: str, signature: str, scanner_id: uuid.UUID) -> dict:
        return {"access": "GRANTED", "reason": None, "role": "athlete"}

def override_get_scan_service():
    return MockScanService()

# Apply the mock service globally for this test file
app.dependency_overrides[get_scan_service] = override_get_scan_service

# Mock Redis so tests don't require a real connection for the rate limiter
class MockRedis:
    async def incr(self, key: str):
        return 1
    async def expire(self, key: str, seconds: int):
        pass

app.dependency_overrides[get_redis] = lambda: MockRedis()

def test_scan_endpoint_unauthorized_role_blocked():
    # Mock a user with 'applicant' role (not allowed)
    def override_get_current_user_applicant():
        return User(id=uuid.uuid4(), email="applicant@test.com", role="applicant")

    # Override the user dependency
    app.dependency_overrides[get_current_user] = override_get_current_user_applicant

    response = client.post(
        "/api/v1/scan/",
        json={"participant_id": str(uuid.uuid4()), "zone_id": str(uuid.uuid4()), "serial_number": "TEST-123", "signature": "abc"}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Operation not permitted"

def test_scan_endpoint_authorized_admin_allowed():
    # Mock a user with 'admin' role (allowed)
    def override_get_current_user_admin():
        return User(id=uuid.uuid4(), email="admin@test.com", role="admin")

    app.dependency_overrides[get_current_user] = override_get_current_user_admin

    response = client.post(
        "/api/v1/scan/",
        json={"participant_id": str(uuid.uuid4()), "zone_id": str(uuid.uuid4()), "serial_number": "TEST-123", "signature": "abc"}
    )

    assert response.status_code == 200
    assert response.json()["access"] == "GRANTED"

def test_scan_endpoint_authorized_scanner_allowed():
    # Mock a user with 'scanner' role (allowed)
    def override_get_current_user_scanner():
        return User(id=uuid.uuid4(), email="scanner@test.com", role="scanner")

    app.dependency_overrides[get_current_user] = override_get_current_user_scanner

    response = client.post(
        "/api/v1/scan/",
        json={"participant_id": str(uuid.uuid4()), "zone_id": str(uuid.uuid4()), "serial_number": "TEST-123", "signature": "abc"}
    )

    assert response.status_code == 200
    assert response.json()["access"] == "GRANTED"