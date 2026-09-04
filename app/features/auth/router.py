from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenUser, get_current_user, require_admin
from app.core.config import settings
from app.core.database import get_db
from app.features.auth.schemas import (
    TokenRefresh,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.features.auth.service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Public registration is disabled. Contact an admin to create an account.",
    )


@router.post("/admin/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    body: UserCreate,
    _admin: TokenUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if await get_user_by_username(body.username, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    if await get_user_by_email(body.email, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = await create_user(body.email, body.username, body.password, db)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(body.username, body.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: TokenRefresh, db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
    )
    try:
        payload = jwt.decode(
            body.refresh_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "refresh":
            raise credentials_exception
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise credentials_exception

    user = await get_user_by_id(user_id, db)
    if not user or not user.is_active:
        raise credentials_exception

    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: TokenUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_by_id(int(current_user.sub), db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user
