# Plan: Replace Authentik with Custom JWT Auth

## Overview
Remove all Authentik dependencies and infrastructure. Implement a self-contained auth system with a `users` table, bcrypt password hashing, and locally-signed HS256 JWTs (access + refresh tokens).

## Steps

### Step 1: Add dependencies
- Add `passlib[bcrypt]` to `pyproject.toml` for password hashing
- `python-jose[cryptography]` is already present (keep it)

### Step 2: Create User model — `app/features/auth/models.py` (new file)
SQLAlchemy model for `users` table:
| Column | Type |
|---|---|
| id | Integer PK |
| email | String(255), unique, indexed |
| username | String(100), unique |
| hashed_password | String(255) |
| is_active | Boolean, default True |
| created_at | DateTime(tz) |

### Step 3: Create auth schemas — `app/features/auth/schemas.py` (new file)
Pydantic models: `UserCreate`, `UserLogin`, `TokenResponse` (access_token + refresh_token + token_type)

### Step 4: Create auth service — `app/features/auth/service.py` (new file)
Functions: `create_user()`, `authenticate_user()`, `create_access_token()`, `create_refresh_token()`, `get_user_by_id()`

### Step 5: Create auth router — `app/features/auth/router.py` (new file)
Endpoints:
- `POST /api/v1/auth/register` — create user, return tokens
- `POST /api/v1/auth/login` — validate credentials, return tokens
- `POST /api/v1/auth/refresh` — validate refresh token, return new access token
- `GET /api/v1/auth/me` — return current user profile

### Step 6: Rewrite `app/core/auth.py`
- Remove `httpx`/JWKS fetching
- `get_current_user()` now decodes HS256 JWT using a local `JWT_SECRET` from settings
- Validates `exp` claim, extracts `sub` (user ID) and `email` from payload
- `TokenUser` model stays the same (keeps all router code untouched)

### Step 7: Update `app/core/config.py`
- Remove 4 `authentik_*` fields
- Add: `jwt_secret`, `jwt_algorithm` (default "HS256"), `access_token_expire_minutes` (default 30), `refresh_token_expire_days` (default 7)

### Step 8: Update `app/main.py`
- Mount the new `auth_router`

### Step 9: Create Alembic migration — `004_create_users_table.py`
- Follows existing migration pattern (revision-based, `op.create_table`)

### Step 10: Update `alembic/env.py`
- Import `app.features.auth.models` so Alembic detects the new table

### Step 11: Update `.env`
- Remove Authentik vars
- Add: `JWT_SECRET=<random-secret>`, `JWT_ALGORITHM=HS256`, `ACCESS_TOKEN_EXPIRE_MINUTES=30`, `REFRESH_TOKEN_EXPIRE_DAYS=7`

### Step 12: Update `docker-compose.yaml`
- Remove all 4 Authentik services (`authentik_postgres`, `authentik_redis`, `authentik_server`, `authentik_worker`)
- Remove their volumes

### Step 13: Update `requests.http`
- Add example register/login/me requests with Bearer token

### Step 14: Update tests — `tests/conftest.py`
- No changes needed (it already mocks `get_current_user` with a `TokenUser`)

### Step 15: Install + migrate + verify
- `uv sync` to install passlib
- `uv run alembic upgrade head` to create users table
- Run `uv run pytest` to verify nothing broke

## Files changed
| Action | File |
|---|---|
| **New** | `app/features/auth/__init__.py` |
| **New** | `app/features/auth/models.py` |
| **New** | `app/features/auth/schemas.py` |
| **New** | `app/features/auth/service.py` |
| **New** | `app/features/auth/router.py` |
| **New** | `alembic/versions/004_create_users_table.py` |
| **Edit** | `app/core/auth.py` |
| **Edit** | `app/core/config.py` |
| **Edit** | `app/main.py` |
| **Edit** | `alembic/env.py` |
| **Edit** | `.env` |
| **Edit** | `docker-compose.yaml` |
| **Edit** | `pyproject.toml` |
| **Edit** | `requests.http` |

## Key design decisions
- **HS256** (symmetric) instead of RS256 — simpler, no key pair management needed since only our app signs and verifies tokens
- **Access token** = 30 min, **Refresh token** = 7 days (configurable via env)
- **No RBAC** — all authenticated users have same access (matches current behavior)
- **`current_user.sub`** becomes the user's integer ID (as string), preserving audit logging compatibility
