"""Конфигурация логирования с loguru"""
import sys
from loguru import logger
from core.config import config


# Удалить стандартный обработчик
logger.remove()

# Добавить консольный обработчик с форматированием
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=config.LOG_LEVEL,
    colorize=True,
)

# Добавить файловый обработчик с ротацией
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level=config.LOG_LEVEL,
)

# Добавить файловый обработчик для ошибок
logger.add(
    "logs/errors_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="90 days",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="ERROR",
)

__all__ = ["logger"]
