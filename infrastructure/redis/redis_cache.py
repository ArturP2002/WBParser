"""Redis cache for prices."""
from typing import Optional
from infrastructure.redis.redis_client import redis_client
from core.config import config


class PriceCache:
    """Cache for product prices."""
    
    @staticmethod
    def _get_key(product_id: int) -> str:
        """Get cache key for product price."""
        return f"price:last:{product_id}"
    
    @staticmethod
    async def cache_price(product_id: int, price: int) -> None:
        """Cache product price."""
        key = PriceCache._get_key(product_id)
        # Cache for 24 hours
        await redis_client.set(key, price, ex=86400)
    
    @staticmethod
    async def get_cached_price(product_id: int) -> Optional[int]:
        """Get cached price for product."""
        key = PriceCache._get_key(product_id)
        value = await redis_client.get(key)
        if value:
            return int(value)
        return None
    
    @staticmethod
    async def clear_price_cache(product_id: int) -> None:
        """Clear cached price for product."""
        key = PriceCache._get_key(product_id)
        await redis_client.delete(key)
