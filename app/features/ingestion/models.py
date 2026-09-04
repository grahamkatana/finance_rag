from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class DocumentShare(Base):
    """Tracks which files an owner has shared with other users.

    Sharing is at the file (file_name) level. A row here means the user
    `granted_to_user_id` can search/retrieve chunks of `file_name`.
    """

    __tablename__ = "document_shares"
    __table_args__ = (
        UniqueConstraint(
            "file_name",
            "granted_to_user_id",
            name="uq_document_shares_file_user",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    granted_to_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentShare file={self.file_name} "
            f"owner={self.owner_id} -> {self.granted_to_user_id}>"
        )


class Document(Base):
    __tablename__ = "documents"

    # 1. Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 2. File metadata
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False, default="pdf")
    source: Mapped[str] = mapped_column(String(500), nullable=True)

    # 3. Content
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # 4. Qdrant reference
    qdrant_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    # 5. Full-text search
    fts_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        nullable=True,
    )

    # 6. Ownership / scoping
    owner_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        default=0,
    )

    # 7. Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} file={self.file_name} chunk={self.chunk_index}>"
