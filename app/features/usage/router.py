from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenUser, require_admin
from app.core.database import get_db
from app.features.usage import balances, service

router = APIRouter(prefix="/api/v1/admin/usage", tags=["usage"])


class PriceBody(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=100)
    input_per_million: Decimal = Field(ge=0, le=100000)
    output_per_million: Decimal = Field(ge=0, le=100000)
    note: str = Field(default="", max_length=200)


class CreditBody(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    amount_usd: Decimal = Field(ge=0, le=10_000_000)


@router.get("/summary")
async def get_summary(days: int = Query(30, ge=1, le=365), _a: TokenUser = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await service.summary(db, days)


@router.get("/prices")
async def list_prices(_a: TokenUser = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return {"prices": [{"provider": p, "model": m, **{k: (float(v) if k != "note" else v) for k, v in row.items()}} for (p, m), row in (await service.prices(db)).items()]}


@router.put("/prices")
async def put_price(body: PriceBody, _a: TokenUser = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    await service.set_price(db, body.provider, body.model, body.input_per_million, body.output_per_million, body.note)
    return {"ok": True}


@router.put("/credits")
async def put_credit(body: CreditBody, _a: TokenUser = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    await service.set_credit(db, body.provider, body.amount_usd)
    return {"ok": True}


@router.get("/balances")
async def get_balances(_a: TokenUser = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    providers = [r.provider for r in (await db.execute(text("SELECT provider FROM provider_credits"))).all()]
    estimates = [e for e in [await service.estimated_credit_left(db, p) for p in providers] if e]
    return {"checked": await balances.check_all(), "estimated_from_top_up": estimates}
