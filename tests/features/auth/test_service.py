import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from jose import jwt

from app.features.auth.service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    authenticate_user,
    create_user,
    get_user_by_id,
    get_user_by_username,
    get_user_by_email,
)
from app.core.config import settings
from app.features.auth.models import User


# --- hash_password / verify_password ---


def test_hash_password_returns_bcrypt_hash():
    hashed = hash_password("mypassword")
    assert hashed.startswith("$2")


def test_verify_password_correct():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


# --- create_access_token ---


def test_create_access_token_contains_sub_and_email():
    token = create_access_token(user_id=42, email="test@example.com")
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == "42"
    assert payload["email"] == "test@example.com"
    assert payload["type"] == "access"


def test_create_access_token_has_expiration():
    token = create_access_token(user_id=1, email="a@b.com")
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert "exp" in payload


# --- create_refresh_token ---


def test_create_refresh_token_contains_sub():
    token = create_refresh_token(user_id=99)
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == "99"
    assert payload["type"] == "refresh"


def test_create_refresh_token_has_longer_expiry_than_access():
    access = create_access_token(user_id=1, email="a@b.com")
    refresh = create_refresh_token(user_id=1)
    access_payload = jwt.decode(access, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    refresh_payload = jwt.decode(refresh, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert refresh_payload["exp"] > access_payload["exp"]


# --- authenticate_user ---


@pytest.mark.asyncio
async def test_authenticate_user_valid_credentials():
    mock_db = AsyncMock()
    fake_user = User(id=1, email="a@b.com", username="alice", hashed_password=hash_password("pass123"), is_active=True)
    with patch("app.features.auth.service.get_user_by_username", new_callable=AsyncMock, return_value=fake_user):
        result = await authenticate_user("alice", "pass123", mock_db)
    assert result is not None
    assert result.username == "alice"


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password():
    mock_db = AsyncMock()
    fake_user = User(id=1, email="a@b.com", username="alice", hashed_password=hash_password("pass123"), is_active=True)
    with patch("app.features.auth.service.get_user_by_username", new_callable=AsyncMock, return_value=fake_user):
        result = await authenticate_user("alice", "wrong", mock_db)
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_nonexistent():
    mock_db = AsyncMock()
    with patch("app.features.auth.service.get_user_by_username", new_callable=AsyncMock, return_value=None):
        result = await authenticate_user("nobody", "pass", mock_db)
    assert result is None


# --- create_user ---


@pytest.mark.asyncio
async def test_create_user_returns_user():
    mock_db = AsyncMock()
    result = await create_user("a@b.com", "alice", "password123", mock_db)
    assert result.email == "a@b.com"
    assert result.username == "alice"
    assert result.hashed_password != "password123"
    assert verify_password("password123", result.hashed_password)


# --- get_user_by_id ---


@pytest.mark.asyncio
async def test_get_user_by_id_found():
    mock_db = AsyncMock()
    fake_user = User(id=1, email="a@b.com", username="alice", hashed_password="x", is_active=True)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_user
    mock_db.execute.return_value = mock_result
    result = await get_user_by_id(1, mock_db)
    assert result is not None
    assert result.username == "alice"


@pytest.mark.asyncio
async def test_get_user_by_id_not_found():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    result = await get_user_by_id(999, mock_db)
    assert result is None


# --- get_user_by_username ---


@pytest.mark.asyncio
async def test_get_user_by_username_found():
    mock_db = AsyncMock()
    fake_user = User(id=1, email="a@b.com", username="alice", hashed_password="x", is_active=True)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_user
    mock_db.execute.return_value = mock_result
    result = await get_user_by_username("alice", mock_db)
    assert result is not None
    assert result.username == "alice"


@pytest.mark.asyncio
async def test_get_user_by_username_not_found():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    result = await get_user_by_username("nobody", mock_db)
    assert result is None


# --- get_user_by_email ---


@pytest.mark.asyncio
async def test_get_user_by_email_found():
    mock_db = AsyncMock()
    fake_user = User(id=1, email="a@b.com", username="alice", hashed_password="x", is_active=True)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = fake_user
    mock_db.execute.return_value = mock_result
    result = await get_user_by_email("a@b.com", mock_db)
    assert result is not None
    assert result.username == "alice"


@pytest.mark.asyncio
async def test_get_user_by_email_not_found():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    result = await get_user_by_email("nobody@x.com", mock_db)
    assert result is None
