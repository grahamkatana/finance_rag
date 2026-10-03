from fastapi import Depends, HTTPException, Request
from redis.asyncio import Redis

from app.core.auth import TokenUser, get_current_user
from app.core.config import settings

_client: Redis | None = None


def _get_client() -> Redis:
    """Lazily create the Redis client — never connect at import time."""
    global _client
    if _client is None:
        _client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def client_ip(request: Request) -> str:
    """Best-effort client IP: honour X-Forwarded-For from the ingress, else the socket peer."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _enforce(key: str, limit: int, window: int) -> None:
    client = _get_client()
    # Fixed window: INCR + EXPIRE NX so the TTL is set once per window, not reset each hit.
    # ponytail: up to ~2x burst allowed at the boundary; swap for a sliding-window ZSET if that matters.
    pipe = client.pipeline()
    pipe.incr(key)
    pipe.expire(key, window, nx=True)
    count, _ = await pipe.execute()
    if count > limit:
        ttl = await client.ttl(key)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
            headers={"Retry-After": str(max(0, ttl or window))},
        )


def ip_rate_limit(limit: int, scope: str):
    """Rate limit keyed by client IP — for unauthenticated routes (e.g. /login)."""

    async def _dep(request: Request) -> None:
        await _enforce(f"ratelimit:{scope}:ip:{client_ip(request)}", limit, window=60)

    return _dep


def user_rate_limit(limit: int, scope: str):
    """Rate limit keyed by authenticated user id — for authed routes (generate/eval)."""

    async def _dep(current_user: TokenUser = Depends(get_current_user)) -> None:
        await _enforce(f"ratelimit:{scope}:user:{current_user.sub}", limit, window=60)

    return _dep
