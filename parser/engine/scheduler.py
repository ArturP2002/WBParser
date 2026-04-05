"""Task scheduler for managing task execution."""
from typing import List
from datetime import datetime, timedelta
from parser.services.task_loader import TaskLoader
from database.models.search_task import SearchTask
from core.config import config
from core.logger import logger


class TaskScheduler:
    """Task scheduler for managing execution timing."""
    
    def __init__(self, task_loader: TaskLoader):
        """Initialize scheduler."""
        self.task_loader = task_loader
        self.scheduler_interval = config.SCHEDULER_INTERVAL
    
    def get_ready_tasks(self, tasks: List[SearchTask]) -> List[SearchTask]:
        """Get tasks ready for execution.
        
        Tasks are ready if last_check was more than scheduler_interval seconds ago.
        """
        now = datetime.utcnow()
        ready_tasks = []
        
        for task in tasks:
            if task.last_check is None:
                # Never checked, ready to go
                ready_tasks.append(task)
            else:
                # Check if enough time has passed
                time_since_check = (now - task.last_check).total_seconds()
                if time_since_check >= self.scheduler_interval:
                    ready_tasks.append(task)
        
        return ready_tasks
    
    def create_batches(
        self, 
        tasks: List[SearchTask], 
        batch_size: int = 20
    ) -> List[List[SearchTask]]:
        """Split tasks into batches.
        
        Example: 100 tasks → 5 batches of 20 tasks each.
        """
        batches = []
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batches.append(batch)
        
        return batches
