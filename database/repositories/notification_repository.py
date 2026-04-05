"""Notification repository."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.notification import Notification


class NotificationRepository:
    """Repository for Notification model."""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        self.session = session
    
    async def check_exists(
        self, 
        user_id: int, 
        product_id: int, 
        price: int
    ) -> bool:
        """Check if notification already exists (for deduplication)."""
        result = await self.session.execute(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.product_id == product_id,
                Notification.price == price,
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def create(
        self, 
        user_id: int, 
        product_id: int, 
        price: int
    ) -> Notification:
        """Create new notification record."""
        notification = Notification(
            user_id=user_id,
            product_id=product_id,
            price=price,
        )
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification
    
    async def get_by_user(self, user_id: int) -> List[Notification]:
        """Get all notifications for user."""
        result = await self.session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())
