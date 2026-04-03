import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from app.schemas.user import UserCreate
from app.api.v1.endpoints.auth import get_user_service

client = TestClient(app)

# 1. Create a mock user service to bypass DB and password hashing
mock_user_id = uuid.uuid4()
mock_email = "testuser@example.com"

class MockUserService:
    async def create_user(self, user_in: UserCreate) -> User:
        return User(
            id=mock_user_id,
            first_name=user_in.first_name,
            last_name=user_in.last_name,
            email=user_in.email,
            role=user_in.role,
            created_at=datetime.now(timezone.utc)
        )

    async def authenticate_user(self, email: str, password: str) -> User | None:
        if email == mock_email and password == "correct_password":
            return User(id=mock_user_id, email=email, role="applicant")
        return None

def override_get_user_service():
    return MockUserService()

app.dependency_overrides[get_user_service] = override_get_user_service

def test_register_user_success():
    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@example.com",
        "password": "securepassword123"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["first_name"] == payload["first_name"]
    assert "id" in data
    assert "password" not in data  # Ensure password is not leaked in the response

def test_login_success():
    # OAuth2PasswordRequestForm expects form data (x-www-form-urlencoded), not JSON
    response = client.post("/api/v1/auth/login", data={"username": mock_email, "password": "correct_password"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_failure_wrong_password():
    response = client.post("/api/v1/auth/login", data={"username": mock_email, "password": "wrong_password"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"