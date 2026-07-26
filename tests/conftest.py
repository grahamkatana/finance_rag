import pytest
from app.core.auth import get_current_user, TokenUser
from app.main import app


def fake_user():
    return TokenUser(
        sub="test-user-id-123",
        email="test@ragfinance.com",
        name="Test User",
    )


# Override at module level — before any test runs
app.dependency_overrides[get_current_user] = fake_user


@pytest.fixture(autouse=True)
def override_auth():
    """Ensure auth is always overridden"""
    app.dependency_overrides[get_current_user] = fake_user
    yield
    # Don't clear — keep override for all tests