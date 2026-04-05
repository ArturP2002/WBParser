"""Price detector for events."""
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.product import Product
from database.models.search_task import SearchTask
from database.repositories.task_product_price_repository import TaskProductPriceRepository
from event_detector.detector.price_cache import PriceCacheManager
from notifier.worker.rate_limiter import EventDeduplication
from core.config import config
from core.logger import logger


def _price_in_task_range(task: SearchTask, price: int) -> bool:
    """True if price is inside the task bounds (same rule as new-product filter)."""
    return (
        (task.price_min is None or price >= task.price_min)
        and (task.price_max is None or price <= task.price_max)
    )


class PriceDetector:
    """Detector for price changes and new products."""

    EVENT_NEW_PRODUCT = "new_product"
    EVENT_ENTER_RANGE = "enter_range"
    EVENT_PRICE_DROP = "price_drop"
    EVENT_PRICE_CHANGE = "price_change"
    
    def __init__(self, session: AsyncSession):
        """Initialize price detector."""
        self.session = session
        self.task_price_repo = TaskProductPriceRepository(session)
        self.price_cache = PriceCacheManager(self.task_price_repo)
    
    async def detect_event(
        self,
        product: Product,
        task: SearchTask,
        current_price: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        """Detect event for product.
        
        Returns:
            Event dict or None if no event
        """
        # Skip products without price - cannot detect events without price
        if current_price is None:
            logger.info(
                f"Product {product.id} ({product.name[:50]}...): "
                f"no event - current_price is None"
            )
            return None
        
        # Get last price from cache (O(1))
        last_price = await self.price_cache.get_last_price(task.id, product.id)

        # Check event deduplication (same new price → skip repeat within TTL)
        if await EventDeduplication.check_exists(
            task.id, product.id, current_price
        ):
            logger.info(
                f"Product {product.id} ({product.name[:50]}...): "
                f"no event - already processed (deduplication)"
            )
            return None
        
        # Detect event type
        event_type = None
        
        if last_price is None:
            if _price_in_task_range(task, current_price):
                event_type = self.EVENT_NEW_PRODUCT
            else:
                logger.info(
                    f"Product {product.id} ({product.name[:50]}...): "
                    f"no event - new product but price {current_price} not in range "
                    f"[{task.price_min}, {task.price_max}]"
                )
        else:
            # Check entrance to range
            if (
                task.price_max is not None
                and last_price > task.price_max
                and current_price <= task.price_max
            ):
                event_type = self.EVENT_ENTER_RANGE

            # Price drop (kept for explicit ⬇️ messaging; subset of price_change)
            elif (
                task.price_min is not None
                and last_price >= task.price_min
                and current_price < last_price
                and abs(last_price - current_price) >= config.MIN_PRICE_CHANGE
            ):
                event_type = self.EVENT_PRICE_DROP

            # Any other significant change while still matching task filters (incl. rises)
            elif (
                last_price != current_price
                and abs(last_price - current_price) >= config.MIN_PRICE_CHANGE
                and _price_in_task_range(task, current_price)
            ):
                event_type = self.EVENT_PRICE_CHANGE

            if not event_type:
                logger.info(
                    f"Product {product.id} ({product.name[:50]}...): "
                    f"no event - existing product, last_price={last_price}, "
                    f"current_price={current_price}, price_range=[{task.price_min}, {task.price_max}]"
                )
        
        if not event_type:
            return None
        
        await EventDeduplication.mark_processed(
            task.id, product.id, current_price
        )

        await self.price_cache.update_price(task.id, product.id, current_price)
        
        # Create event
        event = {
            "event_type": event_type,
            "product_id": product.id,
            "name": product.name,
            "price": current_price,
            "seller": product.seller,
            "url": product.url,
            "task_id": task.id,
            "user_id": task.user_id,
            "price_old": last_price,
            "price_new": current_price,
        }
        
        logger.info(
            f"Event detected: {event_type} for product {product.id}, "
            f"price: {last_price} -> {current_price}"
        )
        
        return event
