import pytest
from unittest.mock import MagicMock, patch
from app.core.auth import get_current_user, get_user_scope, TokenUser, UserScope
from app.main import app


def fake_user():
    return TokenUser(
        sub="1",
        email="test@ragfinance.com",
        name="Test User",
    )


def fake_scope():
    return UserScope(user_id=1, is_admin=False)


def make_admin_scope():
    return UserScope(user_id=1, is_admin=True)


app.dependency_overrides[get_current_user] = fake_user
app.dependency_overrides[get_user_scope] = fake_scope


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_user_scope] = fake_scope
    yield


@pytest.fixture
def admin_scope():
    """Override user scope resolution to an admin user for admin-only tests."""
    app.dependency_overrides[get_user_scope] = make_admin_scope
    yield
    app.dependency_overrides[get_user_scope] = fake_scope


# Mock Celery tasks globally — prevents Redis connection attempts in tests
@pytest.fixture(autouse=True)
def mock_celery_tasks():
    with patch("app.features.ingestion.router.process_ingestion_audit") as mock_ing, \
         patch("app.features.generation.router.process_query_audit") as mock_query:
        mock_ing.delay = MagicMock()
        mock_query.delay = MagicMock()
        yield