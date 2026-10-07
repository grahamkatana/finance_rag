import calendar
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def cost_usd(input_tokens: int, output_tokens: int, price: dict | None) -> float | None:
    """Dollars for a token count, or None when no price is set for the model."""
    if price is None:
        return None
    return (input_tokens * float(price["input_per_million"]) + output_tokens * float(price["output_per_million"])) / 1_000_000


def project_month(spent: float, now: datetime) -> float:
    """Month-end spend if the month carries on at its average daily rate so far."""
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    elapsed = (now.day - 1) + (now.hour + now.minute / 60) / 24
    return spent / max(elapsed, 1 / 24) * days_in_month


async def prices(db: AsyncSession) -> dict[tuple[str, str], dict]:
    rows = (await db.execute(text("SELECT provider, model, input_per_million, output_per_million, note FROM model_prices"))).all()
    return {(r.provider, r.model): {"input_per_million": r.input_per_million, "output_per_million": r.output_per_million, "note": r.note} for r in rows}


async def summary(db: AsyncSession, days: int = 30, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    price_map = await prices(db)

    async def grouped(start):
        return (await db.execute(text(
            "SELECT date_trunc('day', created_at) AS day, kind, provider, model, "
            "SUM(input_tokens)::bigint AS i, SUM(output_tokens)::bigint AS o, COUNT(*)::bigint AS calls, BOOL_OR(estimated) AS estimated "
            "FROM usage_events WHERE created_at >= :s GROUP BY 1, 2, 3, 4 ORDER BY 1"), {"s": start})).all()

    rows = await grouped(since)
    by_day: dict[str, float] = {}
    by_model: dict[tuple, dict] = {}
    for r in rows:
        c = cost_usd(r.i, r.o, price_map.get((r.provider, r.model)))
        key = (r.provider, r.model, r.kind)
        m = by_model.setdefault(key, {"provider": r.provider, "model": r.model, "kind": r.kind, "calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "priced": c is not None, "estimated": False})
        m["calls"] += r.calls; m["input_tokens"] += r.i; m["output_tokens"] += r.o; m["estimated"] |= bool(r.estimated)
        if c is not None:
            m["cost_usd"] += c
            by_day[r.day.date().isoformat()] = by_day.get(r.day.date().isoformat(), 0.0) + c
    month_cost = 0.0
    for r in await grouped(month_start):
        month_cost += cost_usd(r.i, r.o, price_map.get((r.provider, r.model))) or 0.0
    return {
        "days": days,
        "by_model": sorted(by_model.values(), key=lambda m: -m["cost_usd"]),
        "by_day": [{"day": d, "cost_usd": c} for d, c in sorted(by_day.items())],
        "month_to_date_usd": month_cost,
        "projected_month_usd": project_month(month_cost, now),
        "unpriced": sorted({f"{m['provider']}/{m['model']}" for m in by_model.values() if not m["priced"]}),
    }


async def set_price(db: AsyncSession, provider: str, model: str, input_per_million: Decimal, output_per_million: Decimal, note: str = "") -> None:
    await db.execute(text(
        "INSERT INTO model_prices (provider, model, input_per_million, output_per_million, note) VALUES (:p, :m, :i, :o, :n) "
        "ON CONFLICT (provider, model) DO UPDATE SET input_per_million = :i, output_per_million = :o, note = :n, updated_at = now()"),
        {"p": provider, "m": model, "i": input_per_million, "o": output_per_million, "n": note})


async def set_credit(db: AsyncSession, provider: str, amount_usd: Decimal) -> None:
    await db.execute(text(
        "INSERT INTO provider_credits (provider, amount_usd, as_of) VALUES (:p, :a, now()) "
        "ON CONFLICT (provider) DO UPDATE SET amount_usd = :a, as_of = now()"), {"p": provider, "a": amount_usd})


async def estimated_credit_left(db: AsyncSession, provider: str) -> dict | None:
    """Manual top-up figure minus priced usage since it was entered: an estimate, for providers with no balance API."""
    row = (await db.execute(text("SELECT amount_usd, as_of FROM provider_credits WHERE provider = :p"), {"p": provider})).first()
    if row is None:
        return None
    price_map = await prices(db)
    used = (await db.execute(text(
        "SELECT model, SUM(input_tokens)::bigint AS i, SUM(output_tokens)::bigint AS o FROM usage_events "
        "WHERE provider = :p AND created_at >= :s GROUP BY model"), {"p": provider, "s": row.as_of})).all()
    spent = sum(cost_usd(u.i, u.o, price_map.get((provider, u.model))) or 0.0 for u in used)
    return {"provider": provider, "entered_usd": float(row.amount_usd), "as_of": row.as_of.isoformat(), "spent_since_usd": spent, "estimated_left_usd": float(row.amount_usd) - spent}
