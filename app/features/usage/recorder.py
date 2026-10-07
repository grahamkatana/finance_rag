from sqlalchemy import text

from app.core.logging import logger
from app.database.audit import get_audit_session

log = logger.getChild("usage")


def estimate_tokens(text_: str) -> int:
    """About four characters a token. Only used when a provider reports no usage."""
    return max(1, len(text_) // 4)


async def record(kind: str, provider: str, model: str, input_tokens: int, output_tokens: int = 0, estimated: bool = False) -> None:
    """Write one usage row. Never raises: counting spend must not break an answer or an upload."""
    try:
        async with get_audit_session() as session:
            await session.execute(
                text("INSERT INTO usage_events (kind, provider, model, input_tokens, output_tokens, estimated) "
                     "VALUES (:kind, :provider, :model, :i, :o, :e)"),
                {"kind": kind, "provider": provider, "model": model, "i": int(input_tokens), "o": int(output_tokens), "e": estimated},
            )
    except Exception as exc:  # noqa: BLE001
        log.warning(f"usage not recorded: {exc}")
