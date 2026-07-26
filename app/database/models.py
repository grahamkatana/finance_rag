from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.core.database import Base


class AuditQueryEvent(Base):
    __tablename__ = "audit_query_events"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    client_id: Mapped[str] = mapped_column(
        String(255), nullable=False, default="anonymous"
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunks: Mapped[str] = mapped_column(Text, nullable=False)
    faithfulness_score: Mapped[float] = mapped_column(Float, nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=True)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    embed_model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AuditQueryEvent id={self.id} client={self.client_id}>"