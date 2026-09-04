from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import logger

security = HTTPBearer()
log = logger.getChild("auth")


class TokenUser(BaseModel):
    sub: str
    email: str = ""
    name: str = ""


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenUser:
    token = credentials.credentials

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "access":
            raise credentials_exception

        sub = payload.get("sub")
        if not sub:
            raise credentials_exception

        return TokenUser(
            sub=sub,
            email=payload.get("email", ""),
        )
    except JWTError as e:
        log.warning(f"JWT validation failed: {e}")
        raise credentials_exception


async def require_admin(
    current_user: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TokenUser:
    from app.features.auth.service import get_user_by_id

    user = await get_user_by_id(int(current_user.sub), db)
    if not user or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


class UserScope(BaseModel):
    """Resolved user scope for per-user data scoping."""
    user_id: int
    is_admin: bool


async def get_user_scope(
    current_user: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserScope:
    """
    Resolve the current token into a user_id + is_admin pair.
    Used by endpoints that need to enforce per-user data visibility.
    """
    from app.features.auth.service import get_user_by_id

    try:
        user_id = int(current_user.sub)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user in token",
        )

    user = await get_user_by_id(user_id, db)
    is_admin = bool(user and user.is_admin)
    return UserScope(user_id=user_id, is_admin=is_admin)
