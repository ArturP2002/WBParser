"""Search task repository."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database.models.search_task import SearchTask
from database.models.task_exclude_word import TaskExcludeWord


class SearchTaskRepository:
    """Repository for SearchTask model."""
    
    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        self.session = session
    
    async def get_by_user(self, user_id: int) -> List[SearchTask]:
        """Get all tasks for user."""
        result = await self.session.execute(
            select(SearchTask)
            .where(SearchTask.user_id == user_id)
            .order_by(SearchTask.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_active(self) -> List[SearchTask]:
        """Get all active tasks."""
        result = await self.session.execute(
            select(SearchTask)
            .where(SearchTask.is_active == True)
            .options(selectinload(SearchTask.exclude_words))
        )
        return list(result.scalars().all())
    
    async def create(
        self,
        user_id: int,
        query: str,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        exclude_words: Optional[List[str]] = None,
    ) -> SearchTask:
        """Create new search task."""
        task = SearchTask(
            user_id=user_id,
            query=query,
            price_min=price_min,
            price_max=price_max,
        )
        self.session.add(task)
        await self.session.flush()
        
        if exclude_words:
            for word in exclude_words:
                exclude_word = TaskExcludeWord(task_id=task.id, word=word.strip())
                self.session.add(exclude_word)
        
        await self.session.commit()
        await self.session.refresh(task)
        return task
    
    async def update(
        self,
        task_id: int,
        query: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        exclude_words: Optional[List[str]] = None,
    ) -> Optional[SearchTask]:
        """Update search task."""
        result = await self.session.execute(
            select(SearchTask).where(SearchTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return None
        
        if query is not None:
            task.query = query
        if price_min is not None:
            task.price_min = price_min
        if price_max is not None:
            task.price_max = price_max
        
        if exclude_words is not None:
            # Delete old exclude words
            from sqlalchemy import delete
            await self.session.execute(
                delete(TaskExcludeWord).where(TaskExcludeWord.task_id == task_id)
            )
            # Add new exclude words (only if list is not empty)
            for word in exclude_words:
                if word.strip():  # Only add non-empty words
                    exclude_word = TaskExcludeWord(task_id=task.id, word=word.strip())
                    self.session.add(exclude_word)
            # Flush to ensure changes are applied before commit
            await self.session.flush()
        
        await self.session.commit()
        await self.session.refresh(task)
        return task
    
    async def delete(self, task_id: int) -> bool:
        """Delete search task."""
        result = await self.session.execute(
            select(SearchTask).where(SearchTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return False
        
        await self.session.delete(task)
        await self.session.commit()
        return True
    
    async def get_with_exclude_words(self, task_id: int) -> Optional[SearchTask]:
        """Get task with exclude words."""
        result = await self.session.execute(
            select(SearchTask)
            .where(SearchTask.id == task_id)
            .options(selectinload(SearchTask.exclude_words))
        )
        return result.scalar_one_or_none()
