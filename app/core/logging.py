from logging.handlers import TimedRotatingFileHandler
import logging
import sys
from pathlib import Path

from app.core.config import settings


def setup_logging() -> logging.Logger:
    log_dir = Path("storage/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logger = logging.getLogger("rag")
    logger.setLevel(
        logging.DEBUG if settings.app_env == "development" else logging.INFO
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)

    # Daily rotating file handler
    file_handler = TimedRotatingFileHandler(
        filename=log_dir / "app.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        delay=True,          # ← fixes Windows file lock
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)
    file_handler.suffix = "%Y-%m-%d.log"
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()