import hashlib
import io
import zipfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from jose import jwt

from app.core.config import settings
from app.features.releases import service as svc
from app.features.releases.models import AppRelease, AppReleaseFile


def make_apk(extra: dict[str, bytes] | None = None, manifest=True, dex=True) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        if manifest:
            z.writestr("AndroidManifest.xml", b"<manifest/>")
        if dex:
            z.writestr("classes.dex", b"dex")
        for name, content in (extra or {}).items():
            z.writestr(name, content)
    return buffer.getvalue()


# ---- validation ----

def test_a_real_looking_apk_passes():
    svc.validate_apk(make_apk({"resources.arsc": b"x"}))


@pytest.mark.parametrize("data,reason", [
    (b"", "empty"),
    (b"this is not a zip file at all", "not a valid zip"),
    (make_apk(manifest=False), "no AndroidManifest.xml"),
    (make_apk(dex=False), "no compiled code"),
])
def test_things_that_are_not_apks_are_refused(data, reason):
    with pytest.raises(ValueError) as error:
        svc.validate_apk(data)
    assert reason.split()[0] in str(error.value).lower() or "not an apk" in str(error.value).lower() or "empty" in str(error.value).lower()


@pytest.mark.parametrize("name", ["0.1.0", "1.2.3-beta+4", "2026.10.05", "v1_final"])
def test_sensible_version_names_are_accepted(name):
    assert svc.validate_version_name(f"  {name} ") == name


@pytest.mark.parametrize("name", ["", "   ", "a b", "../etc", "1.0/evil", "x" * 41, '1.0"; rm', "-1.0"])
def test_unsafe_or_odd_version_names_are_refused(name):
    with pytest.raises(ValueError):
        svc.validate_version_name(name)


def test_the_download_filename_comes_from_the_version_not_the_upload():
    assert svc.filename_for(AppRelease(version_name="0.2.0", version_code=2)) == "finance-rag-0.2.0.apk"


# ---- download links ----

def test_a_download_token_works_for_its_own_release_only():
    token = svc.create_download_token(user_id=5, release_id=3)
    assert svc.download_token_is_valid(token, 3)
    assert not svc.download_token_is_valid(token, 4)


def test_an_expired_download_token_is_refused():
    payload = {"sub": "5", "rel": 3, "type": "download", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}
    expired = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    assert not svc.download_token_is_valid(expired, 3)


def test_a_login_token_cannot_be_used_as_a_download_token_and_the_reverse():
    from app.features.auth.service import create_access_token
    assert not svc.download_token_is_valid(create_access_token(5, "a@b.c"), 3)
    # ...and a download token is not an "access" token, so it opens nothing else in the API
    payload = jwt.decode(svc.create_download_token(5, 3), settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert payload["type"] == "download" and payload["type"] != "access"


def test_garbage_and_tokens_signed_with_another_key_are_refused():
    assert not svc.download_token_is_valid("not-a-token", 3)
    forged = jwt.encode({"sub": "1", "rel": 3, "type": "download", "exp": datetime.now(timezone.utc) + timedelta(minutes=1)}, "some-other-secret", algorithm="HS256")
    assert not svc.download_token_is_valid(forged, 3)


def test_the_link_lifetime_is_short():
    assert svc.DOWNLOAD_LINK_SECONDS <= 300


# ---- storage ----

def _db(existing_id=None):
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=existing_id))
    db.flush.side_effect = lambda: [setattr(c.args[0], "id", 9) for c in db.add.call_args_list if isinstance(c.args[0], AppRelease)] and None
    return db


@pytest.mark.asyncio
async def test_create_stores_the_file_with_its_size_and_sha256():
    data = make_apk()
    db = _db()
    release = await svc.ReleaseService(db).create(uploader_id=1, version_name="0.1.0", version_code=1, notes="  First build  ", data=data)
    added = [c.args[0] for c in db.add.call_args_list]
    row = next(a for a in added if isinstance(a, AppRelease))
    blob = next(a for a in added if isinstance(a, AppReleaseFile))
    assert (row.size_bytes, row.sha256, row.notes, row.uploaded_by) == (len(data), hashlib.sha256(data).hexdigest(), "First build", 1)
    assert blob.data == data and blob.release_id == 9


@pytest.mark.asyncio
async def test_publishing_the_same_version_code_twice_is_refused():
    with pytest.raises(FileExistsError, match="already published"):
        await svc.ReleaseService(_db(existing_id=4)).create(1, "0.1.0", 1, "", make_apk())


@pytest.mark.asyncio
async def test_releases_are_listed_newest_version_first():
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    await svc.ReleaseService(db).list_releases()
    sql = str(db.execute.await_args.args[0].compile(compile_kwargs={"literal_binds": True}))
    assert "ORDER BY app_releases.version_code DESC" in sql


def test_the_listing_never_reads_the_file_bytes():
    sql = str(__import__("sqlalchemy").select(AppRelease))
    assert "data" not in sql and "app_release_files" not in sql
