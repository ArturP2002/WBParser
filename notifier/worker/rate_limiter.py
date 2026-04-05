"""Rate limiter for notifications."""
from datetime import datetime, timedelta
from infrastructure.redis.redis_client import redis_client
from core.config import config


class RateLimiter:
    """Rate limiter for notifications."""
    
    @staticmethod
    def _get_counter_key(user_id: int) -> str:
        """Get counter key for user."""
        return f"notify_limit:{user_id}"
    
    @staticmethod
    def _get_minute_key(user_id: int) -> str:
        """Get minute key for user."""
        minute = datetime.now().strftime("%Y%m%d%H%M")
        return f"notify_limit:{user_id}:{minute}"
    
    @staticmethod
    async def increment_counter(user_id: int) -> int:
        """Increment notification counter for user."""
        key = RateLimiter._get_minute_key(user_id)
        count = await redis_client.incr(key)
        # Set expiration to 60 seconds
        await redis_client.expire(key, 60)
        return count
    
    @staticmethod
    async def check_limit(user_id: int) -> bool:
        """Check if user has reached notification limit."""
        key = RateLimiter._get_minute_key(user_id)
        count = await redis_client.get(key)
        if count:
            return int(count) < config.NOTIFICATION_LIMIT_PER_MINUTE
        return True


class NotificationDeduplication:
    """Deduplication for notifications."""
    
    @staticmethod
    def _get_key(task_id: int, product_id: int, price: int) -> str:
        """Get deduplication key (per search task)."""
        return f"notify:task:{task_id}:product:{product_id}:price:{price}"

    @staticmethod
    async def check_exists(
        task_id: int,
        product_id: int,
        price: int,
    ) -> bool:
        """Check if notification already sent for this task/product/price."""
        key = NotificationDeduplication._get_key(task_id, product_id, price)
        return await redis_client.exists(key)

    @staticmethod
    async def mark_sent(
        task_id: int,
        product_id: int,
        price: int,
    ) -> None:
        """Mark notification as sent."""
        key = NotificationDeduplication._get_key(task_id, product_id, price)
        await redis_client.set(
            key, 
            "1", 
            ex=config.NOTIFICATION_DEDUP_TTL
        )


class EventDeduplication:
    """Deduplication for events (per search task, product, and settled price)."""

    @staticmethod
    def _get_key(task_id: int, product_id: int, new_price: int) -> str:
        """Key allows another event after price moves again."""
        return f"event:task:{task_id}:product:{product_id}:price:{new_price}"

    @staticmethod
    async def check_exists(task_id: int, product_id: int, new_price: int) -> bool:
        """Check if this emission was already processed for this task."""
        key = EventDeduplication._get_key(task_id, product_id, new_price)
        return await redis_client.exists(key)

    @staticmethod
    async def mark_processed(task_id: int, product_id: int, new_price: int) -> None:
        """Mark event as processed."""
        key = EventDeduplication._get_key(task_id, product_id, new_price)
        await redis_client.set(key, "1", ex=config.EVENT_DEDUP_TTL)
