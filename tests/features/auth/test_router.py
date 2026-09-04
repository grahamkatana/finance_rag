import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock
from jose import jwt

from app.main import app
from app.features.auth.models import User
from app.features.auth.service import hash_password, create_access_token, create_refresh_token
from app.core.config import settings


@pytest.fixture
def mock_db():
    with patch("app.features.auth.router.get_db") as mock:
        session = AsyncMock()
        mock.return_value = session
        yield session


# --- /register ---


@pytest.mark.asyncio
async def test_register_returns_201(mock_db):
    with patch("app.features.auth.router.get_user_by_username", new_callable=AsyncMock, return_value=None), \
         patch("app.features.auth.router.get_user_by_email", new_callable=AsyncMock, return_value=None), \
         patch("app.features.auth.router.create_user") as mock_create:
        mock_create.return_value = User(
            id=1, email="a@b.com", username="alice",
            hashed_password="x", is_active=True,
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/register", json={
                "email": "a@b.com", "username": "alice", "password": "pass123"
            })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_username_returns_409(mock_db):
    with patch("app.features.auth.router.get_user_by_username", new_callable=AsyncMock, return_value=MagicMock()), \
         patch("app.features.auth.router.get_user_by_email", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/register", json={
                "email": "a@b.com", "username": "alice", "password": "pass123"
            })
    assert response.status_code == 409
    assert "Username already taken" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(mock_db):
    with patch("app.features.auth.router.get_user_by_username", new_callable=AsyncMock, return_value=None), \
         patch("app.features.auth.router.get_user_by_email", new_callable=AsyncMock, return_value=MagicMock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/register", json={
                "email": "a@b.com", "username": "alice", "password": "pass123"
            })
    assert response.status_code == 409
    assert "Email already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_missing_fields_returns_422(mock_db):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/register", json={
            "email": "a@b.com"
        })
    assert response.status_code == 422


# --- /login ---


@pytest.mark.asyncio
async def test_login_returns_200_with_tokens(mock_db):
    fake_user = User(
        id=1, email="a@b.com", username="alice",
        hashed_password=hash_password("pass123"), is_active=True,
    )
    with patch("app.features.auth.router.authenticate_user", new_callable=AsyncMock, return_value=fake_user):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/login", json={
                "username": "alice", "password": "pass123"
            })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_401(mock_db):
    with patch("app.features.auth.router.authenticate_user", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/login", json={
                "username": "alice", "password": "wrong"
            })
    assert response.status_code == 401
    assert "Invalid username or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_missing_fields_returns_422(mock_db):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/login", json={
            "username": "alice"
        })
    assert response.status_code == 422


# --- /refresh ---


@pytest.mark.asyncio
async def test_refresh_returns_new_tokens(mock_db):
    refresh_token = create_refresh_token(user_id=42)
    fake_user = User(
        id=42, email="a@b.com", username="alice",
        hashed_password="x", is_active=True,
    )
    with patch("app.features.auth.router.get_user_by_id", new_callable=AsyncMock, return_value=fake_user):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/refresh", json={
                "refresh_token": refresh_token
            })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_refresh_invalid_token_returns_401(mock_db):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "not-a-valid-token"
        })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_access_token_rejected(mock_db):
    access_token = create_access_token(user_id=1, email="a@b.com")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": access_token
        })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_expired_token_returns_401(mock_db):
    from datetime import datetime, timedelta, timezone
    payload = {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(hours=1), "type": "refresh"}
    expired_token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": expired_token
        })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_nonexistent_user_returns_401(mock_db):
    refresh_token = create_refresh_token(user_id=99999)
    with patch("app.features.auth.router.get_user_by_id", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/refresh", json={
                "refresh_token": refresh_token
            })
    assert response.status_code == 401


# --- /me ---


@pytest.mark.asyncio
async def test_me_returns_current_user(mock_db):
    fake_user = User(
        id=1, email="a@b.com", username="alice",
        hashed_password="x", is_active=True,
    )
    with patch("app.features.auth.router.get_user_by_id", new_callable=AsyncMock, return_value=fake_user):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["email"] == "a@b.com"
    assert data["username"] == "alice"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_me_user_not_found_returns_404(mock_db):
    with patch("app.features.auth.router.get_user_by_id", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/auth/me")
    assert response.status_code == 404
