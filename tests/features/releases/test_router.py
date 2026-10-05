from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.features.auth.models import User
from app.features.releases import router as releases_router
from app.features.releases.models import AppRelease
from app.features.releases.service import create_download_token
from app.main import app
from tests.features.releases.test_service import make_apk

APK = make_apk({"resources.arsc": b"x"})


def _release(id=1, name="0.1.0", code=1):
    return AppRelease(id=id, version_name=name, version_code=code, size_bytes=len(APK), sha256="ab" * 32, notes="First build",
                      created_at=datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc))


@pytest.fixture
def service():
    with patch("app.features.releases.router.ReleaseService") as mock_cls:
        svc = AsyncMock()
        svc.list_releases.return_value = [_release(2, "0.2.0", 2), _release(1, "0.1.0", 1)]
        svc.get.return_value = _release()
        svc.get_file.return_value = APK
        svc.create.return_value = _release(2, "0.2.0", 2)
        svc.delete.return_value = True
        mock_cls.return_value = svc
        yield svc


@pytest.fixture
def as_admin():
    admin = User(id=1, email="a@b.c", username="admin", hashed_password="x", is_active=True, is_admin=True)
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=admin):
        yield


@pytest.fixture
def as_member():
    member = User(id=1, email="m@b.c", username="member", hashed_password="x", is_active=True, is_admin=False)
    with patch("app.features.auth.service.get_user_by_id", new_callable=AsyncMock, return_value=member):
        yield


async def _request(method, path, **kwargs):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def _upload(data=APK, name="0.2.0", code="2", notes="Adds follow-ups", filename="finance-rag.apk"):
    return {"files": {"file": (filename, data, "application/vnd.android.package-archive")}, "data": {"version_name": name, "version_code": code, "notes": notes}}


# ---- list ----

@pytest.mark.asyncio
async def test_list_returns_every_version_and_marks_the_latest(service):
    body = (await _request("GET", "/api/v1/releases")).json()
    assert [(r["version_name"], r["is_latest"]) for r in body["releases"]] == [("0.2.0", True), ("0.1.0", False)]
    assert body["total"] == 2
    assert "data" not in body["releases"][0]  # metadata only, never the file


# ---- upload ----

@pytest.mark.asyncio
async def test_an_admin_can_publish_a_version(service, as_admin):
    response = await _request("POST", "/api/v1/releases", **_upload())
    assert response.status_code == 201
    service.create.assert_awaited_once_with(1, "0.2.0", 2, "Adds follow-ups", APK)


@pytest.mark.asyncio
async def test_a_member_cannot_publish(service, as_member):
    response = await _request("POST", "/api/v1/releases", **_upload())
    assert response.status_code == 403
    service.create.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs,status", [
    (dict(data=b"not an apk"), 422),
    (dict(name="../evil"), 422),
    (dict(code="0"), 422),
    (dict(code="abc"), 422),
])
async def test_bad_uploads_are_refused_and_nothing_is_stored(service, as_admin, kwargs, status):
    response = await _request("POST", "/api/v1/releases", **_upload(**kwargs))
    assert response.status_code == status
    service.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_file_over_the_size_limit_is_413(service, as_admin):
    with patch.object(releases_router, "MAX_APK_BYTES", 10):
        response = await _request("POST", "/api/v1/releases", **_upload())
    assert response.status_code == 413
    service.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_publishing_an_existing_version_code_is_409(service, as_admin):
    service.create.side_effect = FileExistsError("Version code 2 is already published.")
    response = await _request("POST", "/api/v1/releases", **_upload())
    assert response.status_code == 409
    assert "already published" in response.json()["detail"]


# ---- download ----

@pytest.mark.asyncio
async def test_a_download_link_is_issued_and_opens_that_file(service):
    link = (await _request("POST", "/api/v1/releases/1/download-url")).json()
    assert link["filename"] == "finance-rag-0.1.0.apk" and link["expires_in"] <= 300
    assert link["url"].startswith("/api/v1/releases/1/file?t=")
    response = await _request("GET", link["url"])  # note: no Authorization header, as a browser download has none
    assert response.status_code == 200
    assert response.content == APK
    assert response.headers["content-type"] == "application/vnd.android.package-archive"
    assert response.headers["content-disposition"] == 'attachment; filename="finance-rag-0.1.0.apk"'
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in response.headers["cache-control"]


@pytest.mark.asyncio
async def test_a_link_for_an_unknown_release_is_404(service):
    service.get.return_value = None
    assert (await _request("POST", "/api/v1/releases/99/download-url")).status_code == 404


@pytest.mark.asyncio
async def test_the_file_needs_a_valid_token(service):
    assert (await _request("GET", "/api/v1/releases/1/file")).status_code == 422  # token missing
    assert (await _request("GET", "/api/v1/releases/1/file?t=garbage")).status_code == 401
    other_release = create_download_token(1, 2)
    assert (await _request("GET", f"/api/v1/releases/1/file?t={other_release}")).status_code == 401
    service.get_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_login_token_does_not_open_the_file(service):
    from app.features.auth.service import create_access_token
    response = await _request("GET", f"/api/v1/releases/1/file?t={create_access_token(1, 'a@b.c')}")
    assert response.status_code == 401


# ---- delete ----

@pytest.mark.asyncio
async def test_an_admin_can_delete_a_version(service, as_admin):
    response = await _request("DELETE", "/api/v1/releases/1")
    assert response.json() == {"id": 1, "deleted": True}
    service.delete.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_deleting_an_unknown_version_is_404(service, as_admin):
    service.delete.return_value = False
    assert (await _request("DELETE", "/api/v1/releases/99")).status_code == 404


@pytest.mark.asyncio
async def test_a_member_cannot_delete(service, as_member):
    assert (await _request("DELETE", "/api/v1/releases/1")).status_code == 403
    service.delete.assert_not_awaited()


@pytest.fixture
def fake_db():
    from app.core.database import get_db
    db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_a_published_version_is_committed_before_the_response_is_sent(service, as_admin, fake_db):
    """Otherwise a client asking for it straight away (the page reloading, a download link) finds nothing."""
    order = []
    service.create.side_effect = lambda *a: order.append("create") or _release(2, "0.2.0", 2)
    fake_db.commit.side_effect = lambda: order.append("commit")
    service.list_releases.side_effect = lambda: order.append("list") or [_release(2, "0.2.0", 2)]
    assert (await _request("POST", "/api/v1/releases", **_upload())).status_code == 201
    assert order.index("commit") > order.index("create") and order.index("commit") < order.index("list")


@pytest.mark.asyncio
async def test_a_deletion_is_committed_before_the_response_is_sent(service, as_admin, fake_db):
    assert (await _request("DELETE", "/api/v1/releases/1")).status_code == 200
    fake_db.commit.assert_awaited_once()

