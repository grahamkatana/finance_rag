import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from app.core.config import settings


def setup_logging() -> logging.Logger:
    """
    Sets up application logging with:
    - Console output (development)
    - Daily rotating log files under storage/logs/
    """
    # 1. Create logs directory
    log_dir = Path("storage/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # 2. Log format
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 3. Root logger
    logger = logging.getLogger("rag")
    logger.setLevel(
        logging.DEBUG if settings.app_env == "development" else logging.INFO
    )

    # 4. Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)

    # 5. Daily rotating file handler
    file_handler = TimedRotatingFileHandler(
        filename=log_dir / "app.log",
        when="midnight",        # rotate at midnight
        interval=1,             # every 1 day
        backupCount=30,         # keep 30 days of logs
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)
    file_handler.suffix = "%Y-%m-%d.log"  # app.2024-01-15.log
    logger.addHandler(file_handler)

    return logger


# Single instance imported everywhere
logger = setup_logging()