"""Сервис для бизнес-логики пользователей"""
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.user_repository import UserRepository
from database.models.user import User


class UserService:
    """Сервис для бизнес-логики пользователей"""
    
    def __init__(self, session: AsyncSession):
        """Инициализация сервиса для бизнес-логики пользователей"""
        self.session = session
        self.user_repo = UserRepository(session)
    
    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str = None,
    ) -> tuple[User, bool]:
        """Получить или создать пользователя"""
        return await self.user_repo.get_or_create(telegram_id, username)
