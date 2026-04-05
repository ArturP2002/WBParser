"""Worker pool for parallel parsing."""
import asyncio
from typing import List, Callable, Any
from core.config import config
from core.logger import logger


class WorkerPool:
    """Worker pool with semaphore for limiting parallelism."""
    
    def __init__(self, max_workers: int = None):
        """Initialize worker pool."""
        if max_workers is None:
            max_workers = config.PARSER_SEMAPHORE_LIMIT
        self.semaphore = asyncio.Semaphore(max_workers)
        self.max_workers = max_workers
    
    async def execute(
        self,
        tasks: List[Any],
        worker_func: Callable,
    ) -> List[Any]:
        """Execute tasks in parallel with semaphore limit.
        
        Args:
            tasks: List of tasks to process
            worker_func: Async function to process each task
        
        Returns:
            List of results
        """
        async def worker_with_semaphore(task):
            """Worker with semaphore."""
            async with self.semaphore:
                return await worker_func(task)
        
        # Create coroutines for all tasks
        coroutines = [worker_with_semaphore(task) for task in tasks]
        
        # Execute in parallel
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # Filter out exceptions
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing task {i}: {result}")
            else:
                successful_results.append(result)
        
        return successful_results
