"""Combined Telegram middlewares.

This module consolidates multiple middleware classes to reduce GitHub file
count. It preserves the same public names that `main.py` uses.
"""

import time
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from database.db import AsyncSessionLocal
from core.logger import logger


class DatabaseMiddleware(BaseMiddleware):
    """Middleware for providing a DB session per update."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with AsyncSessionLocal() as session:
            data["session"] = session
            return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware for limiting request rate per user."""

    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self._last_request: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id if event.from_user else None

        if user_id:
            current_time = time.time()
            last_time = self._last_request.get(user_id, 0)

            if current_time - last_time < self.rate_limit:
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return

            self._last_request[user_id] = current_time

        return await handler(event, data)

