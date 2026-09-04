import pytest
from unittest.mock import MagicMock, patch
from app.core.auth import get_current_user, TokenUser
from app.main import app


def fake_user():
    return TokenUser(
        sub="1",
        email="test@ragfinance.com",
        name="Test User",
    )


app.dependency_overrides[get_current_user] = fake_user


@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = fake_user
    yield


# Mock Celery tasks globally — prevents Redis connection attempts in tests
@pytest.fixture(autouse=True)
def mock_celery_tasks():
    with patch("app.features.ingestion.router.process_ingestion_audit") as mock_ing, \
         patch("app.features.generation.router.process_query_audit") as mock_query:
        mock_ing.delay = MagicMock()
        mock_query.delay = MagicMock()
        yield