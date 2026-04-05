"""User repository."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.user import User


class UserRepository:
    """Repository for User model."""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        self.session = session
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by telegram_id."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def create(self, telegram_id: int, username: Optional[str] = None) -> User:
        """Create new user."""
        user = User(telegram_id=telegram_id, username=username)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user
    
    async def get_or_create(
        self, 
        telegram_id: int, 
        username: Optional[str] = None
    ) -> tuple[User, bool]:
        """Get user or create if not exists. Returns (user, created)."""
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return user, False
        
        user = await self.create(telegram_id, username)
        return user, True
