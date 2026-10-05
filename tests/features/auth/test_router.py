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


@pytest.fixture
def mock_admin_user():
    """Mock an admin user returned by get_user_by_id for require_admin checks."""
    return User(
        id=1, email="admin@test.com", username="admin",
        hashed_password="x", is_active=True, is_admin=True,
    )


# --- /register (closed) ---


@pytest.mark.asyncio
async def test_register_returns_403(mock_db):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/register", json={
            "email": "a@b.com", "username": "alice", "password": "pass123"
        })
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"].lower()


# --- /admin/users ---


@pytest.mark.asyncio
async def test_admin_create_user_returns_201(mock_db, mock_admin_user):
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=mock_admin_user), \
         patch("app.features.auth.router.get_user_by_username", new_callable=AsyncMock, return_value=None), \
         patch("app.features.auth.router.get_user_by_email", new_callable=AsyncMock, return_value=None), \
         patch("app.features.auth.router.create_user") as mock_create:
        mock_create.return_value = User(
            id=2, email="a@b.com", username="alice",
            hashed_password="x", is_active=True, is_admin=False,
        )
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/admin/users", json={
                "email": "a@b.com", "username": "alice", "password": "pass123"
            })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "a@b.com"
    assert data["username"] == "alice"
    assert data["is_admin"] is False


@pytest.mark.asyncio
async def test_admin_create_user_duplicate_username_returns_409(mock_db, mock_admin_user):
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=mock_admin_user), \
         patch("app.features.auth.router.get_user_by_username", new_callable=AsyncMock, return_value=MagicMock()), \
         patch("app.features.auth.router.get_user_by_email", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/admin/users", json={
                "email": "a@b.com", "username": "alice", "password": "pass123"
            })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_admin_create_user_duplicate_email_returns_409(mock_db, mock_admin_user):
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=mock_admin_user), \
         patch("app.features.auth.router.get_user_by_username", new_callable=AsyncMock, return_value=None), \
         patch("app.features.auth.router.get_user_by_email", new_callable=AsyncMock, return_value=MagicMock()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/admin/users", json={
                "email": "a@b.com", "username": "alice", "password": "pass123"
            })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_admin_create_user_non_admin_returns_403(mock_db):
    non_admin = User(
        id=1, email="user@test.com", username="user",
        hashed_password="x", is_active=True, is_admin=False,
    )
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=non_admin):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/admin/users", json={
                "email": "a@b.com", "username": "alice", "password": "pass123"
            })
    assert response.status_code == 403
    assert "Admin access required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_admin_create_user_missing_fields_returns_422(mock_db, mock_admin_user):
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=mock_admin_user):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/auth/admin/users", json={
                "email": "a@b.com"
            })
    assert response.status_code == 422


# --- /admin/users (list + grant/revoke admin) ---


def _user(id, username, is_admin=False):
    return User(id=id, email=f"{username}@test.com", username=username, hashed_password="x", is_active=True, is_admin=is_admin)


@pytest.mark.asyncio
async def test_admin_list_users_returns_all_users(mock_db, mock_admin_user):
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=mock_admin_user), \
         patch("app.features.auth.router.list_users", new_callable=AsyncMock, return_value=[mock_admin_user, _user(2, "alice")]):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/auth/admin/users")
    assert response.status_code == 200
    data = response.json()
    assert [(u["username"], u["is_admin"]) for u in data] == [("admin", True), ("alice", False)]
    assert "hashed_password" not in data[0]


@pytest.mark.asyncio
async def test_admin_list_users_non_admin_returns_403(mock_db):
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=_user(1, "user")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/auth/admin/users")
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("start,requested", [(False, True), (True, False)])
async def test_admin_can_grant_and_revoke_admin(mock_db, mock_admin_user, start, requested):
    target = _user(2, "alice", is_admin=start)
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=mock_admin_user), \
         patch("app.features.auth.router.get_user_by_id", new_callable=AsyncMock, return_value=target):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/api/v1/auth/admin/users/2", json={"is_admin": requested})
    assert response.status_code == 200
    assert response.json()["is_admin"] is requested
    assert target.is_admin is requested


@pytest.mark.asyncio
async def test_admin_cannot_demote_self(mock_db, mock_admin_user):
    # conftest's fake token has sub="1", the same id as mock_admin_user
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=mock_admin_user), \
         patch("app.features.auth.router.get_user_by_id", new_callable=AsyncMock, return_value=mock_admin_user):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/api/v1/auth/admin/users/1", json={"is_admin": False})
    assert response.status_code == 400
    assert mock_admin_user.is_admin is True


@pytest.mark.asyncio
async def test_built_in_admin_cannot_be_demoted(mock_db, mock_admin_user):
    seeded = _user(5, "root", is_admin=True)
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=mock_admin_user), \
         patch("app.features.auth.router.get_user_by_id", new_callable=AsyncMock, return_value=seeded), \
         patch.object(settings, "admin_username", "root"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/api/v1/auth/admin/users/5", json={"is_admin": False})
    assert response.status_code == 400
    assert seeded.is_admin is True


@pytest.mark.asyncio
async def test_admin_update_unknown_user_returns_404(mock_db, mock_admin_user):
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=mock_admin_user), \
         patch("app.features.auth.router.get_user_by_id", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/api/v1/auth/admin/users/99", json={"is_admin": True})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_update_user_non_admin_returns_403(mock_db):
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=_user(1, "user")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/api/v1/auth/admin/users/2", json={"is_admin": True})
    assert response.status_code == 403


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
        hashed_password="x", is_active=True, is_admin=False,
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
    assert data["is_admin"] is False


@pytest.mark.asyncio
async def test_me_user_not_found_returns_404(mock_db):
    with patch("app.features.auth.router.get_user_by_id", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/auth/me")
    assert response.status_code == 404


@pytest.fixture
def fake_db():
    from app.core.database import get_db
    db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_a_role_change_is_committed_before_the_response_is_sent(fake_db, mock_admin_user):
    """The Users page reloads its list the moment this returns; it must not see the old role."""
    target = _user(2, "alice", is_admin=False)
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=mock_admin_user), \
         patch("app.features.auth.router.get_user_by_id", new_callable=AsyncMock, return_value=target):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/api/v1/auth/admin/users/2", json={"is_admin": True})
    assert response.status_code == 200
    fake_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_new_user_is_committed_before_the_response_is_sent(fake_db, mock_admin_user):
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=mock_admin_user), \
         patch("app.features.auth.router.get_user_by_username", new_callable=AsyncMock, return_value=None), \
         patch("app.features.auth.router.get_user_by_email", new_callable=AsyncMock, return_value=None), \
         patch("app.features.auth.router.create_user", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = User(id=3, email="a@b.com", username="alice", hashed_password="x", is_active=True, is_admin=False)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/auth/admin/users", json={"email": "a@b.com", "username": "alice", "password": "pass123"})
    assert response.status_code == 201
    fake_db.commit.assert_awaited_once()
