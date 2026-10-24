import sys
from loguru import logger
from app.config.settings import settings

# Remove default handler and configure structured output
logger.remove()
logger.add(
    sys.stdout,
    level=settings.LOG_LEVEL,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} | {message}",
    colorize=True,
)

__all__ = ["logger"]
