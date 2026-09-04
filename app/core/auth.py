from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
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
