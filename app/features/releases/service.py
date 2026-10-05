import hashlib
import io
import re
import zipfile
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.features.releases.models import AppRelease, AppReleaseFile

MAX_APK_BYTES = 50 * 1024 * 1024  # the frontend's nginx accepts uploads up to 50 MB
DOWNLOAD_LINK_SECONDS = 120
_VERSION_NAME = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,39}$")


def validate_version_name(name: str) -> str:
    name = name.strip()
    if not _VERSION_NAME.match(name):
        raise ValueError("Version name may use letters, digits and . _ + - only (up to 40 characters), e.g. 0.1.0")
    return name


def validate_apk(data: bytes) -> None:
    """An APK is a zip holding AndroidManifest.xml and compiled code. Anything else is refused.

    This does not prove the app is safe or properly signed -- only admins can upload, and the
    sha256 is shown so the file can be checked -- it stops a wrong file being published by mistake.
    """
    if not data:
        raise ValueError("The file is empty.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as apk:
            names = set(apk.namelist())
    except zipfile.BadZipFile:
        raise ValueError("This is not an APK: it is not a valid zip archive.")
    if "AndroidManifest.xml" not in names or not any(n.endswith(".dex") for n in names):
        raise ValueError("This is not an APK: it has no AndroidManifest.xml or compiled code.")


def release_dict(release: AppRelease, latest_code: int | None) -> dict:
    return {
        "id": release.id,
        "version_name": release.version_name,
        "version_code": release.version_code,
        "size_bytes": release.size_bytes,
        "sha256": release.sha256,
        "notes": release.notes or "",
        "created_at": release.created_at.isoformat() if release.created_at else None,
        "is_latest": release.version_code == latest_code,
    }


def filename_for(release: AppRelease) -> str:
    # Built from the version, never from whatever name the uploaded file had.
    return f"finance-rag-{release.version_name}.apk"


def create_download_token(user_id: int, release_id: int) -> str:
    """A link good for 2 minutes and for one release only.

    A plain link cannot carry the Authorization header, so the file is fetched with this
    instead. Its type ("download") is not the "access" type the API's own endpoints require,
    so it cannot be used for anything else, and an access token cannot be used here.
    """
    payload = {
        "sub": str(user_id),
        "rel": release_id,
        "type": "download",
        "exp": datetime.now(timezone.utc) + timedelta(seconds=DOWNLOAD_LINK_SECONDS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def download_token_is_valid(token: str, release_id: int) -> bool:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return False
    return payload.get("type") == "download" and payload.get("rel") == release_id


class ReleaseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_releases(self) -> list[AppRelease]:
        result = await self.db.execute(select(AppRelease).order_by(AppRelease.version_code.desc()))
        return list(result.scalars().all())

    async def get(self, release_id: int) -> AppRelease | None:
        result = await self.db.execute(select(AppRelease).where(AppRelease.id == release_id))
        return result.scalar_one_or_none()

    async def get_file(self, release_id: int) -> bytes | None:
        result = await self.db.execute(select(AppReleaseFile.data).where(AppReleaseFile.release_id == release_id))
        return result.scalar_one_or_none()

    async def create(self, uploader_id: int, version_name: str, version_code: int, notes: str, data: bytes) -> AppRelease:
        existing = await self.db.execute(select(AppRelease.id).where(AppRelease.version_code == version_code))
        if existing.scalar_one_or_none() is not None:
            raise FileExistsError(f"Version code {version_code} is already published. Use a higher number for a new version.")
        release = AppRelease(
            version_name=version_name,
            version_code=version_code,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            notes=notes.strip() or None,
            uploaded_by=uploader_id,
        )
        self.db.add(release)
        await self.db.flush()
        self.db.add(AppReleaseFile(release_id=release.id, data=data))
        await self.db.flush()
        await self.db.refresh(release)
        return release

    async def delete(self, release_id: int) -> bool:
        # The file row goes with it: app_release_files.release_id is ON DELETE CASCADE.
        result = await self.db.execute(delete(AppRelease).where(AppRelease.id == release_id))
        return result.rowcount > 0
