"""Сервис для бизнес-логики задач"""
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.task_repository import SearchTaskRepository
from core.logger import logger


class TaskService:
    """Сервис для бизнес-логики задач"""
    
    MAX_TASKS_PER_USER = 100
    
    def __init__(self, session: AsyncSession):
        """Инициализация сервиса для бизнес-логики задач"""
        self.session = session
        self.task_repo = SearchTaskRepository(session)
    
    async def check_task_limit(self, user_id: int) -> bool:
        """Проверить, может ли пользователь добавить больше задач"""
        tasks = await self.task_repo.get_by_user(user_id)
        return len(tasks) < self.MAX_TASKS_PER_USER
