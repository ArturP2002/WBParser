"""Redis cache for prices."""
from typing import Optional
from infrastructure.redis.redis_client import redis_client
from core.config import config


class PriceCache:
    """Cache for product prices."""
    
    @staticmethod
    def _get_key(task_id: int, product_id: int) -> str:
        """Cache key: last price for this task–product pair."""
        return f"price:last:{task_id}:{product_id}"

    @staticmethod
    async def cache_price(task_id: int, product_id: int, price: int) -> None:
        """Cache price for a task–product pair."""
        key = PriceCache._get_key(task_id, product_id)
        await redis_client.set(key, price, ex=86400)

    @staticmethod
    async def get_cached_price(task_id: int, product_id: int) -> Optional[int]:
        """Get cached price for a task–product pair."""
        key = PriceCache._get_key(task_id, product_id)
        value = await redis_client.get(key)
        if value:
            return int(value)
        return None

    @staticmethod
    async def clear_price_cache(task_id: int, product_id: int) -> None:
        """Clear cached price for a task–product pair."""
        key = PriceCache._get_key(task_id, product_id)
        await redis_client.delete(key)
