from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenUser, get_current_user, require_admin
from app.core.database import get_db
from app.features.releases.service import (
    DOWNLOAD_LINK_SECONDS,
    MAX_APK_BYTES,
    ReleaseService,
    create_download_token,
    download_token_is_valid,
    filename_for,
    release_dict,
    validate_apk,
    validate_version_name,
)

router = APIRouter(prefix="/api/v1/releases", tags=["releases"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release not found")


@router.get("")
async def list_releases(
    _user: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Every published version of the Android app, newest first."""
    releases = await ReleaseService(db).list_releases()
    latest = releases[0].version_code if releases else None
    return {"releases": [release_dict(r, latest) for r in releases], "total": len(releases)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_release(
    file: UploadFile = File(...),
    version_name: str = Form(...),
    version_code: int = Form(..., ge=1),
    notes: str = Form(""),
    admin: TokenUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Publish a new version (admin only). Older versions are kept."""
    try:
        version_name = validate_version_name(version_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    data = await file.read(MAX_APK_BYTES + 1)
    if len(data) > MAX_APK_BYTES:
        raise HTTPException(status_code=413, detail=f"The file is larger than {MAX_APK_BYTES // (1024 * 1024)} MB.")
    try:
        validate_apk(data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        release = await ReleaseService(db).create(int(admin.sub), version_name, version_code, notes, data)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    # Commit BEFORE answering. get_db commits only after the response has gone out, and a client
    # that asks for the new version straight away (the page reloading its list, or a download
    # link) would otherwise find nothing. The file can be megabytes, so the gap is not small.
    await db.commit()
    latest = (await ReleaseService(db).list_releases())[0].version_code
    return release_dict(release, latest)


@router.post("/{release_id}/download-url")
async def download_url(
    release_id: int,
    user: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """A short-lived link to the file. Open it in the phone's browser to download."""
    release = await ReleaseService(db).get(release_id)
    if release is None:
        raise NOT_FOUND
    token = create_download_token(int(user.sub), release_id)
    return {
        "url": f"/api/v1/releases/{release_id}/file?t={token}",
        "expires_in": DOWNLOAD_LINK_SECONDS,
        "filename": filename_for(release),
    }


@router.get("/{release_id}/file")
async def download_file(
    release_id: int,
    t: str = Query(..., description="The token from POST /{id}/download-url"),
    db: AsyncSession = Depends(get_db),
):
    if not download_token_is_valid(t, release_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This download link is invalid or has expired. Request a new one.")
    service = ReleaseService(db)
    release = await service.get(release_id)
    data = await service.get_file(release_id)
    if release is None or data is None:
        raise NOT_FOUND
    return Response(
        content=data,
        media_type="application/vnd.android.package-archive",
        headers={
            "Content-Disposition": f'attachment; filename="{filename_for(release)}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{release_id}")
async def delete_release(
    release_id: int,
    _admin: TokenUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if not await ReleaseService(db).delete(release_id):
        raise NOT_FOUND
    await db.commit()  # before answering, so the list the page reloads next no longer shows it
    return {"id": release_id, "deleted": True}
