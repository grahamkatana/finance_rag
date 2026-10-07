from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import TokenUser, get_current_user, require_admin
from app.features.usage import balances
from app.features.usage.service import cost_usd, project_month
from app.main import app

PRICE = {"input_per_million": 0.02, "output_per_million": 0}


def test_cost_uses_both_directions_per_million():
    assert cost_usd(1_000_000, 0, PRICE) == pytest.approx(0.02)
    assert cost_usd(500_000, 2_000_000, {"input_per_million": 1, "output_per_million": 3}) == pytest.approx(6.5)


def test_cost_is_none_without_a_price():
    assert cost_usd(10, 10, None) is None


def test_projection_extends_the_average_rate_to_month_end():
    # $10 after 10 full days of a 31-day month -> $31
    assert project_month(10.0, datetime(2026, 10, 11, 0, 0, tzinfo=timezone.utc)) == pytest.approx(31.0)


def test_projection_survives_the_first_minute_of_the_month():
    assert project_month(0.0, datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)) == 0.0


@pytest.mark.asyncio
async def test_deepseek_balance_reads_the_documented_shape():
    reply = MagicMock(); reply.raise_for_status = MagicMock()
    reply.json.return_value = {"is_available": True, "balance_infos": [{"currency": "USD", "total_balance": "4.20", "granted_balance": "0.00", "topped_up_balance": "4.20"}]}
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=reply)) as get:
        out = await balances.deepseek_balance("k")
    assert out["balances"][0]["total_balance"] == "4.20" and out["available"] is True
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer k"


@pytest.mark.asyncio
async def test_openai_month_spend_adds_every_bucket():
    reply = MagicMock(); reply.raise_for_status = MagicMock()
    reply.json.return_value = {"data": [{"results": [{"amount": {"value": 1.5}}, {"amount": {"value": 0.25}}]}, {"results": [{"amount": {"value": 2}}]}]}
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=reply)):
        assert (await balances.openai_month_spend("k"))["month_to_date_usd"] == pytest.approx(3.75)


@pytest.mark.asyncio
async def test_one_failing_provider_does_not_hide_the_rest():
    with patch.object(balances.settings, "deepseek_api_key", "x"), patch.object(balances.settings, "openai_admin_key", ""), \
         patch("app.features.usage.balances.deepseek_balance", AsyncMock(side_effect=RuntimeError("boom"))):
        out = await balances.check_all()
    assert out[0]["kind"] == "error" and any(o["provider"] == "ollama" for o in out)


@pytest.mark.asyncio
async def test_usage_endpoints_refuse_non_admins():
    from fastapi import HTTPException
    async def deny(): raise HTTPException(status_code=403, detail="Admin access required")
    app.dependency_overrides[require_admin] = deny
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            for path in ("/summary", "/prices", "/balances"):
                assert (await c.get("/api/v1/admin/usage" + path)).status_code == 403
    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_openai_embedder_records_reported_tokens():
    from app.core.llm.providers.openai import OpenAIEmbedder
    e = OpenAIEmbedder(api_key="k", model="text-embedding-3-small")
    resp = MagicMock(); resp.usage.prompt_tokens = 42; resp.data = [MagicMock(embedding=[0.1], index=0)]
    e.client.embeddings.create = AsyncMock(return_value=resp)
    with patch("app.core.llm.providers.openai.record", AsyncMock()) as rec:
        await e.embed_batch(["a"])
    rec.assert_awaited_once_with("embed", "openai", "text-embedding-3-small", 42)


@pytest.mark.asyncio
async def test_recorder_never_raises_when_the_database_is_down():
    from app.features.usage import recorder
    with patch.object(recorder, "get_audit_session", side_effect=RuntimeError("db down")):
        await recorder.record("chat", "openai", "m", 1, 1)
