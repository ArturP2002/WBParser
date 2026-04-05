"""Notification worker for processing events."""
import asyncio
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.redis.redis_streams import RedisStreams
from infrastructure.telegram.telegram_client import telegram_client
from database.repositories.notification_repository import NotificationRepository
from sqlalchemy import select
from database.models.product import Product
from database.models.user import User
from database.repositories.product_seller_repository import ProductSellerRepository
from notifier.worker.rate_limiter import (
    RateLimiter,
    NotificationDeduplication,
)
from notifier.services.notification_service import NotificationService
from core.logger import logger


class NotificationWorker:
    """Worker for processing notification events."""
    
    def __init__(self, session: AsyncSession):
        """Initialize notification worker."""
        self.session = session
        self.notification_repo = NotificationRepository(session)
        self.seller_repo = ProductSellerRepository(session)
        self.notification_service = NotificationService()
        self.rate_limiter = RateLimiter()
    
    async def process_event(self, event: Dict[str, Any]) -> None:
        """Process single event."""
        try:
            user_id = event.get("user_id")
            product_id = event.get("product_id")
            price = event.get("price")
            
            logger.info(
                f"Processing event: user_id={user_id}, product_id={product_id}, "
                f"price={price}, event_type={event.get('event_type')}"
            )
            
            if not user_id:
                logger.error(f"Event has no user_id! Event: {event}")
                return
            
            # Get telegram_id from user_id
            user_result = await self.session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                logger.error(f"User not found: user_id={user_id}")
                return
            
            telegram_id = user.telegram_id
            logger.info(f"Found telegram_id={telegram_id} for user_id={user_id}")
            
            # Check rate limit
            if not await self.rate_limiter.check_limit(user_id):
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return
            
            # Check deduplication (Redis + DB)
            if await NotificationDeduplication.check_exists(
                user_id, product_id, price
            ):
                logger.debug(
                    f"Notification already sent: user={user_id}, "
                    f"product={product_id}, price={price}"
                )
                return
            
            # Double check in DB
            if await self.notification_repo.check_exists(
                user_id, product_id, price
            ):
                logger.debug("Notification exists in DB, skipping")
                return
            
            # Get product by id
            result = await self.session.execute(
                select(Product).where(Product.id == product_id)
            )
            product = result.scalar_one_or_none()
            
            if not product:
                logger.warning(f"Product not found: {product_id}")
                return
            
            sellers = await self.seller_repo.get_by_product(product.id)
            
            # Format notification message
            message = self.notification_service.format_notification(
                product=product,
                price=price,
                sellers=sellers,
                event_type=event.get("event_type"),
                price_old=event.get("price_old"),
                price_new=event.get("price_new"),
            )
            
            # Send notification to telegram_id (not user_id!)
            await telegram_client.send_message(
                chat_id=telegram_id,
                text=message,
            )
            
            # Mark as sent
            await NotificationDeduplication.mark_sent(user_id, product_id, price)
            await self.notification_repo.create(user_id, product_id, price)
            
            # Increment counter
            await self.rate_limiter.increment_counter(user_id)
            
            logger.info(
                f"✅ Notification sent to telegram_id={telegram_id} (user_id={user_id}) for product {product_id}"
            )
            
        except Exception as e:
            logger.error(f"Error processing event: {e}", exc_info=True)
    
    async def process_events_batch(self, events: List[Dict[str, Any]]) -> None:
        """Process batch of events with grouping."""
        # Group events by user
        events_by_user = {}
        for event in events:
            user_id = event.get("user_id")
            if user_id not in events_by_user:
                events_by_user[user_id] = []
            events_by_user[user_id].append(event)
        
        # Process each user's events
        for user_id, user_events in events_by_user.items():
            # Check rate limit
            if not await self.rate_limiter.check_limit(user_id):
                logger.warning(f"Rate limit exceeded for user {user_id}")
                continue
            
            # Group events if too many
            if len(user_events) > 10:
                # Send grouped notification
                await self._send_grouped_notification(user_id, user_events)
            else:
                # Send individual notifications
                for event in user_events:
                    await self.process_event(event)
    
    async def _send_grouped_notification(
        self,
        user_id: int,
        events: List[Dict[str, Any]],
    ) -> None:
        """Send grouped notification for many events."""
        # Get telegram_id from user_id
        user_result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User not found: user_id={user_id}")
            return
        
        telegram_id = user.telegram_id
        
        message = f"Найдено {len(events)} новых товаров:\n\n"
        
        for event in events[:20]:  # Limit to 20
            product_id = event.get("product_id")
            result = await self.session.execute(
                select(Product).where(Product.id == product_id)
            )
            product = result.scalar_one_or_none()
            if product:
                message += f"📱 {product.name}\n"
                message += f"💰 {event.get('price')} руб\n"
                if product.url:
                    message += f"{product.url}\n"
                message += "\n"
        
        if len(events) > 20:
            message += f"\n... и еще {len(events) - 20} товаров"
        
        await telegram_client.send_message(chat_id=telegram_id, text=message)
    
    async def run(self) -> None:
        """Main worker loop."""
        logger.info("Notification worker started")
        
        while True:
            try:
                # Read events from stream
                events = await RedisStreams.read_events(count=10, block=1000)
                
                if events:
                    logger.info(f"Processing {len(events)} events")
                    for message_id, event_data in events:
                        await self.process_event(event_data)
                        # Acknowledge event
                        await RedisStreams.acknowledge_event(message_id)
                
            except Exception as e:
                logger.error(f"Error in notification worker: {e}", exc_info=True)
                await asyncio.sleep(1)
