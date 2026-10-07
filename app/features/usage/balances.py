from datetime import datetime, timezone

import httpx

from app.core.config import settings

TIMEOUT = 10.0


async def deepseek_balance(api_key: str, base: str = "https://api.deepseek.com") -> dict:
    """DeepSeek publishes a real balance endpoint: GET /user/balance."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get(f"{base}/user/balance", headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"})
    r.raise_for_status()
    body = r.json()
    return {"provider": "deepseek", "kind": "balance", "available": body.get("is_available"), "balances": body.get("balance_infos", [])}


async def openai_month_spend(admin_key: str, now: datetime | None = None) -> dict:
    """OpenAI has no balance endpoint. The Costs API (admin key) reports spend, so this is month-to-date spend, not credit left."""
    now = now or datetime.now(timezone.utc)
    start = int(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.get("https://api.openai.com/v1/organization/costs", params={"start_time": start, "bucket_width": "1d", "limit": 31},
                             headers={"Authorization": f"Bearer {admin_key}"})
    r.raise_for_status()
    total = sum(float(res["amount"]["value"]) for b in r.json().get("data", []) for res in b.get("results", []))
    return {"provider": "openai", "kind": "month_spend", "month_to_date_usd": total}


async def check_all() -> list[dict]:
    """Each configured provider is checked on its own; one failing never hides the others."""
    out: list[dict] = []
    checks = []
    if settings.deepseek_api_key:
        checks.append(("deepseek", deepseek_balance(settings.deepseek_api_key)))
    if settings.openai_admin_key:
        checks.append(("openai", openai_month_spend(settings.openai_admin_key)))
    for name, coro in checks:
        try:
            out.append(await coro)
        except Exception as exc:  # noqa: BLE001
            out.append({"provider": name, "kind": "error", "error": f"{type(exc).__name__}: {str(exc)[:120]}"})
    out.append({"provider": "ollama", "kind": "unsupported", "note": "Ollama Cloud is plan-based and has no balance API; usage is counted here."})
    out.append({"provider": "openai", "kind": "unsupported_balance", "note": "OpenAI has no credit-balance API. Enter your top-up below for an estimate."})
    return out
