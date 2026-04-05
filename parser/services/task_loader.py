"""Task loader for caching tasks."""
import asyncio
from typing import List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from database.repositories.task_repository import SearchTaskRepository
from core.config import config
from core.logger import logger


class TaskLoader:
    """Task loader with caching."""
    
    def __init__(self, session: AsyncSession):
        """Initialize task loader."""
        self.session = session
        self.task_repo = SearchTaskRepository(session)
        self._cached_tasks: List = []
        self._last_update: datetime = None
        self._update_interval = config.TASK_LOADER_INTERVAL
    
    async def load_tasks(self) -> List:
        """Load tasks with caching (update every 10 seconds)."""
        now = datetime.utcnow()
        
        # Check if cache needs update
        if (
            self._last_update is None
            or (now - self._last_update).total_seconds() >= self._update_interval
        ):
            logger.debug("Updating task cache")
            self._cached_tasks = await self.task_repo.get_active()
            self._last_update = now
            logger.info(f"Loaded {len(self._cached_tasks)} active tasks")
        
        return self._cached_tasks.copy()
    
    async def force_reload(self) -> List:
        """Force reload tasks from database."""
        self._cached_tasks = await self.task_repo.get_active()
        self._last_update = datetime.utcnow()
        return self._cached_tasks.copy()
