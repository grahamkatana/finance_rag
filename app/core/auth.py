import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import logger

security = HTTPBearer()
log = logger.getChild("auth")


class TokenUser(BaseModel):
    sub: str           # user ID from Authentik
    email: str = ""    # user email
    name: str = ""     # user display name


async def get_jwks() -> dict:
    """
    Fetch public keys from Authentik JWKS endpoint.
    Used to verify JWT signatures.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(settings.authentik_jwks_uri)
        response.raise_for_status()
        return response.json()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenUser:
    """
    FastAPI dependency — validates JWT and returns the current user.
    Inject this into any route that requires authentication.
    """
    token = credentials.credentials

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # 1. Fetch JWKS from Authentik
        jwks = await get_jwks()

        # 2. Decode and validate the JWT
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=settings.authentik_client_id,
            issuer=settings.authentik_issuer,
            options={"verify_at_hash": False},
        )

        # 3. Extract user identity
        sub = payload.get("sub")
        if not sub:
            raise credentials_exception

        return TokenUser(
            sub=sub,
            email=payload.get("email", ""),
            name=payload.get("name", ""),
        )

    except JWTError as e:
        log.warning(f"JWT validation failed: {e}")
        raise credentials_exception