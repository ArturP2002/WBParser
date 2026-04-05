"""Price cache for event detector (per search task + product)."""
from typing import Optional
from infrastructure.redis.redis_cache import PriceCache
from database.repositories.task_product_price_repository import TaskProductPriceRepository
from core.config import config


class PriceCacheManager:
    """Manager for task-scoped price caching."""

    def __init__(self, price_repo: TaskProductPriceRepository):
        self.price_repo = price_repo
        self.price_cache = PriceCache()

    async def get_last_price(self, task_id: int, product_id: int) -> Optional[int]:
        """Last known price for this task seeing this product (Redis then DB)."""
        cached_price = await self.price_cache.get_cached_price(task_id, product_id)
        if cached_price is not None:
            return cached_price

        db_price = await self.price_repo.get_latest_price(task_id, product_id)
        if db_price is not None:
            await self.price_cache.cache_price(task_id, product_id, db_price)

        return db_price

    async def update_price(self, task_id: int, product_id: int, price: int) -> None:
        """Update cache and persist when change is significant vs previous snapshot."""
        previous = await self.get_last_price(task_id, product_id)
        await self.price_cache.cache_price(task_id, product_id, price)
        if previous is None or abs(previous - price) >= config.MIN_PRICE_CHANGE:
            await self.price_repo.create(task_id, product_id, price)
