import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from app.main import app


@pytest.fixture
def mock_deps():
    with patch("app.features.audit.router.get_db") as mock_db:
        mock_db.return_value = AsyncMock()
        yield


@pytest.fixture
def mock_query_events():
    return [
        {
            "id": 1,
            "client_id": "graham-test",
            "query": "What was Apple net sales in 2024?",
            "answer": "Apple net sales were $391,035 million.",
            "faithfulness_score": 1.0,
            "relevance_score": 1.0,
            "model_used": "phi4-mini",
            "embed_model_used": "nomic-embed-text",
            "duration_ms": 4230.5,
            "created_at": "2024-01-15T10:00:00+00:00",
        }
    ]


@pytest.fixture
def mock_ingestion_events():
    return [
        {
            "id": 1,
            "client_id": "graham-test",
            "file_name": "apple_10k.pdf",
            "source": "https://investor.apple.com",
            "chunks_ingested": 971,
            "file_size_bytes": 5242880,
            "embed_model_used": "nomic-embed-text",
            "duration_ms": 161213.5,
            "status": "success",
            "error_message": None,
            "created_at": "2024-01-15T10:00:00+00:00",
        }
    ]


@pytest.fixture
def mock_audit_service(mock_query_events, mock_ingestion_events):
    with patch("app.features.audit.router.AuditService") as mock_cls:
        mock_service = AsyncMock()
        mock_service.get_query_events.return_value = mock_query_events
        mock_service.get_ingestion_events.return_value = mock_ingestion_events
        mock_cls.return_value = mock_service
        yield mock_service


@pytest.mark.asyncio
async def test_get_query_events_returns_200(mock_audit_service, mock_deps):
    """Query audit endpoint should return 200"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/audit/queries")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_query_events_returns_correct_schema(
    mock_audit_service, mock_deps
):
    """Response must contain events list and total"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/audit/queries")
    data = response.json()
    assert "events" in data
    assert "total" in data
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_get_query_events_has_correct_fields(
    mock_audit_service, mock_deps
):
    """Each event must have required audit fields"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/audit/queries")
    event = response.json()["events"][0]
    assert "id" in event
    assert "client_id" in event
    assert "query" in event
    assert "faithfulness_score" in event
    assert "relevance_score" in event
    assert "created_at" in event


@pytest.mark.asyncio
async def test_get_query_events_filter_by_client(
    mock_audit_service, mock_deps
):
    """Should accept client_id filter"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/audit/queries?client_id=graham-test"
        )
    assert response.status_code == 200
    assert mock_audit_service.get_query_events.called


@pytest.mark.asyncio
async def test_get_ingestion_events_returns_200(
    mock_audit_service, mock_deps
):
    """Ingestion audit endpoint should return 200"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/audit/ingestions")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_ingestion_events_returns_correct_schema(
    mock_audit_service, mock_deps
):
    """Response must contain events list and total"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/audit/ingestions")
    data = response.json()
    assert "events" in data
    assert "total" in data
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_get_ingestion_events_has_correct_fields(
    mock_audit_service, mock_deps
):
    """Each ingestion event must have required fields"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/audit/ingestions")
    event = response.json()["events"][0]
    assert "id" in event
    assert "client_id" in event
    assert "file_name" in event
    assert "chunks_ingested" in event
    assert "status" in event
    assert "created_at" in event


@pytest.mark.asyncio
async def test_get_ingestion_events_filter_by_status(
    mock_audit_service, mock_deps
):
    """Should accept status filter"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/audit/ingestions?status=success"
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_query_events_pagination(mock_audit_service, mock_deps):
    """Should accept limit and offset for pagination"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/audit/queries?limit=10&offset=0"
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_low_faithfulness_queries(mock_audit_service, mock_deps):
    """Should be able to filter queries with low faithfulness"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/audit/queries?max_faithfulness=0.5"
        )
    assert response.status_code == 200


# ---- Scoping tests ----


@pytest.mark.asyncio
async def test_non_admin_query_audit_forces_own_client_id(
    mock_audit_service, mock_deps
):
    """Non-admin requests: client_id param is ignored and replaced with their own."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/audit/queries?client_id=someone-else"
        )
    assert response.status_code == 200
    # Service was called, and the forced client_id should be "1" (fake_scope user_id)
    call_kwargs = mock_audit_service.get_query_events.call_args
    assert call_kwargs.kwargs.get("client_id") == "1"


@pytest.mark.asyncio
async def test_non_admin_ingestion_audit_forces_own_client_id(
    mock_audit_service, mock_deps
):
    """Non-admin ingestion audit also forces client_id to own."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/audit/ingestions?client_id=someone-else"
        )
    assert response.status_code == 200
    call_kwargs = mock_audit_service.get_ingestion_events.call_args
    assert call_kwargs.kwargs.get("client_id") == "1"


@pytest.mark.asyncio
async def test_admin_query_audit_passes_requested_client_id(
    mock_audit_service, mock_deps, admin_scope
):
    """Admin requests: requested client_id is passed through unchanged."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/audit/queries?client_id=other-user"
        )
    assert response.status_code == 200
    call_kwargs = mock_audit_service.get_query_events.call_args
    assert call_kwargs.kwargs.get("client_id") == "other-user"


@pytest.mark.asyncio
async def test_admin_ingestion_audit_passes_requested_client_id(
    mock_audit_service, mock_deps, admin_scope
):
    """Admin ingestion audit passes requested client_id through."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/audit/ingestions?client_id=other-user"
        )
    assert response.status_code == 200
    call_kwargs = mock_audit_service.get_ingestion_events.call_args
    assert call_kwargs.kwargs.get("client_id") == "other-user"


@pytest.mark.asyncio
async def test_admin_query_audit_no_client_id_passes_none(
    mock_audit_service, mock_deps, admin_scope
):
    """Admin without client_id param passes None (sees all)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/audit/queries")
    assert response.status_code == 200
    call_kwargs = mock_audit_service.get_query_events.call_args
    assert call_kwargs.kwargs.get("client_id") is None