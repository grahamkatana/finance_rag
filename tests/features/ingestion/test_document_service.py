from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.features.ingestion.document_service import DocumentService


@pytest.mark.asyncio
async def test_list_shares_includes_email_so_clients_can_unshare():
    """Unsharing is by email, so each share must carry the grantee's email."""
    result = MagicMock()
    result.fetchall.return_value = [
        MagicMock(granted_to_user_id=2, created_at=datetime(2026, 1, 15, 10, 0), email="bob@example.com"),
        MagicMock(granted_to_user_id=3, created_at=None, email=None),  # grantee since deleted
    ]
    db = AsyncMock()
    db.execute.return_value = result

    shares = await DocumentService(db=db, qdrant=AsyncMock()).list_shares("apple_10k.pdf", owner_id=1)

    assert shares == [
        {"granted_to_user_id": 2, "email": "bob@example.com", "created_at": "2026-01-15T10:00:00"},
        {"granted_to_user_id": 3, "email": None, "created_at": None},
    ]
    sql = str(db.execute.call_args.args[0])
    assert "JOIN users" in sql
    assert db.execute.call_args.args[1] == {"file_name": "apple_10k.pdf", "owner_id": 1}


def _doc_row(file_name, is_owner):
    return MagicMock(file_name=file_name, source="sec.gov", chunk_count=3, created_at=datetime(2026, 1, 15, 10, 0), is_owner=is_owner)


@pytest.mark.asyncio
async def test_list_documents_flags_owned_vs_shared():
    """A non-admin sees owned + shared files, each marked with whether it is theirs."""
    owned, shared, docs = MagicMock(), MagicMock(), MagicMock()
    owned.fetchall.return_value = [MagicMock(file_name="mine.pdf")]
    shared.fetchall.return_value = [MagicMock(file_name="theirs.pdf")]
    docs.fetchall.return_value = [_doc_row("mine.pdf", True), _doc_row("theirs.pdf", False)]
    db = AsyncMock()
    db.execute.side_effect = [owned, shared, docs]

    result = await DocumentService(db=db, qdrant=AsyncMock()).list_documents(owner_id=7, is_admin=False)

    assert [(d["file_name"], d["is_owner"]) for d in result] == [("mine.pdf", True), ("theirs.pdf", False)]
    sql, params = db.execute.call_args.args
    assert "BOOL_OR(owner_id = :owner_id)" in str(sql)
    assert params["owner_id"] == 7 and sorted(params["files"]) == ["mine.pdf", "theirs.pdf"]


@pytest.mark.asyncio
async def test_list_documents_admin_sees_all_with_ownership_flag():
    """An admin's listing is unfiltered but still says which files are their own."""
    docs = MagicMock()
    docs.fetchall.return_value = [_doc_row("someone_elses.pdf", False)]
    db = AsyncMock()
    db.execute.return_value = docs

    result = await DocumentService(db=db, qdrant=AsyncMock()).list_documents(owner_id=1, is_admin=True)

    assert result[0]["is_owner"] is False
    sql, params = db.execute.call_args.args
    assert "WHERE" not in str(sql) and params == {"owner_id": 1}
