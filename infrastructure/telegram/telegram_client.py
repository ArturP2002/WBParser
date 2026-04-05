"""Telegram client for sending notifications."""
import asyncio
from typing import Optional
from aiogram import Bot
from aiogram.types import Message
from core.config import config
from core.logger import logger


class TelegramNotificationClient:
    """Telegram client for sending notifications."""
    
    def __init__(self):
        """Initialize Telegram bot."""
        self._bot: Optional[Bot] = None
    
    async def _get_bot(self) -> Bot:
        """Get or create bot instance."""
        if self._bot is None:
            self._bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        return self._bot
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = "HTML",
        retries: int = 3,
    ) -> Message:
        """Send message to user with retry logic."""
        bot = await self._get_bot()
        
        for attempt in range(retries):
            try:
                message = await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode,
                )
                logger.info(f"✅ Message sent successfully to chat {chat_id}")
                return message
            except Exception as e:
                error_msg = str(e)
                if "Cannot connect to host" in error_msg or "api.telegram.org" in error_msg:
                    logger.warning(
                        f"Failed to connect to Telegram API (attempt {attempt + 1}/{retries}): {e}. "
                        "This might be due to VPN blocking or network issues."
                    )
                    if attempt < retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        logger.info(f"Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(
                            f"Failed to send message to {chat_id} after {retries} attempts. "
                            "Check VPN settings or network connection."
                        )
                        raise
                else:
                    logger.error(f"Failed to send message to {chat_id}: {e}")
                    raise
        
        raise Exception("Failed to send message after all retries")
    
    async def close(self) -> None:
        """Close bot session."""
        if self._bot:
            await self._bot.session.close()
            self._bot = None


# Global Telegram client instance
telegram_client = TelegramNotificationClient()
