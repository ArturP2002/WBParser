"""Price cache for event detector."""
from typing import Optional
from infrastructure.redis.redis_cache import PriceCache
from database.repositories.price_repository import ProductPriceRepository
from core.logger import logger


class PriceCacheManager:
    """Manager for price caching."""
    
    def __init__(self, price_repo: ProductPriceRepository):
        """Initialize price cache manager."""
        self.price_repo = price_repo
        self.price_cache = PriceCache()
    
    async def get_last_price(self, product_id: int) -> Optional[int]:
        """Get last price from Redis cache or DB.
        
        O(1) operation with Redis, much faster than SQL query.
        """
        # Try Redis first (O(1))
        cached_price = await self.price_cache.get_cached_price(product_id)
        if cached_price is not None:
            return cached_price
        
        # Fallback to DB
        db_price = await self.price_repo.get_latest_price(product_id)
        if db_price is not None:
            # Cache it for next time
            await self.price_cache.cache_price(product_id, db_price)
        
        return db_price
    
    async def update_price(
        self, 
        product_id: int, 
        price: int
    ) -> None:
        """Update price in cache and DB."""
        # Update cache
        await self.price_cache.cache_price(product_id, price)
        
        # Save to DB (only if changed significantly)
        last_price = await self.get_last_price(product_id)
        if last_price is None or abs(last_price - price) >= 200:
            await self.price_repo.create(product_id, price)
