"""Price detector for events."""
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.product import Product
from database.models.search_task import SearchTask
from database.repositories.product_repository import ProductRepository
from database.repositories.price_repository import ProductPriceRepository
from event_detector.detector.price_cache import PriceCacheManager
from notifier.worker.rate_limiter import EventDeduplication
from core.config import config
from core.logger import logger


class PriceDetector:
    """Detector for price changes and new products."""
    
    EVENT_NEW_PRODUCT = "new_product"
    EVENT_ENTER_RANGE = "enter_range"
    EVENT_PRICE_DROP = "price_drop"
    
    def __init__(self, session: AsyncSession):
        """Initialize price detector."""
        self.session = session
        self.product_repo = ProductRepository(session)
        self.price_repo = ProductPriceRepository(session)
        self.price_cache = PriceCacheManager(self.price_repo)
    
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
        last_price = await self.price_cache.get_last_price(product.id)
        
        # Check event deduplication
        if await EventDeduplication.check_exists(task.user_id, product.id):
            logger.info(
                f"Product {product.id} ({product.name[:50]}...): "
                f"no event - already processed (deduplication)"
            )
            return None
        
        # Detect event type
        event_type = None
        
        if last_price is None:
            # New product - check if price is in range
            price_in_range = (
                (task.price_min is None or current_price >= task.price_min)
                and (task.price_max is None or current_price <= task.price_max)
            )
            
            if price_in_range:
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
            
            # Check price drop
            elif (
                task.price_min is not None
                and last_price >= task.price_min
                and current_price < last_price
                and abs(last_price - current_price) >= config.MIN_PRICE_CHANGE
            ):
                event_type = self.EVENT_PRICE_DROP
            
            if not event_type:
                logger.info(
                    f"Product {product.id} ({product.name[:50]}...): "
                    f"no event - existing product, last_price={last_price}, "
                    f"current_price={current_price}, price_range=[{task.price_min}, {task.price_max}]"
                )
        
        if not event_type:
            return None
        
        # Mark event as processed
        await EventDeduplication.mark_processed(task.user_id, product.id)
        
        # Update price cache
        await self.price_cache.update_price(product.id, current_price)
        
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
