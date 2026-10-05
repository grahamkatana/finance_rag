from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class AppRelease(Base):
    """One published version of the Android app. Every version is kept."""

    __tablename__ = "app_releases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_name: Mapped[str] = mapped_column(String(40), nullable=False)       # what people read: "0.1.0"
    version_code: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)  # what Android compares; higher = newer
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AppReleaseFile(Base):
    """The APK itself, kept apart from the release row so listing releases never reads megabytes."""

    __tablename__ = "app_release_files"

    release_id: Mapped[int] = mapped_column(Integer, ForeignKey("app_releases.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
