"""Parser engine - main parsing loop."""
import asyncio
from datetime import datetime
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from parser.services.task_loader import TaskLoader
from parser.engine.scheduler import TaskScheduler
from parser.engine.worker_pool import WorkerPool
from parser.wb.wb_api import wb_api
from parser.processing.filters import filter_products
from parser.processing.deduplicator import Deduplicator
from parser.processing.seller_grouper import SellerGrouper
from parser.processing.product_normalizer import ProductNormalizer
from database.repositories.product_repository import ProductRepository
from database.repositories.task_repository import SearchTaskRepository
from infrastructure.redis.redis_streams import RedisStreams
from event_detector.detector.price_detector import PriceDetector
from core.logger import logger
from core.config import config


class ParserEngine:
    """Main parser engine."""
    
    def __init__(self, session: AsyncSession):
        """Initialize parser engine."""
        self.session = session
        self.task_loader = TaskLoader(session)
        self.scheduler = TaskScheduler(self.task_loader)
        self.worker_pool = WorkerPool()
        self.deduplicator = Deduplicator(session)
        self.seller_grouper = SellerGrouper(session)
        self.normalizer = ProductNormalizer()
        self.product_repo = ProductRepository(session)
        self.task_repo = SearchTaskRepository(session)
        self.price_detector = PriceDetector(session)
    
    async def parse_task(self, task) -> List[dict]:
        """Parse single task and return events."""
        try:
            logger.info(
                f"Parsing task {task.id}: query='{task.query}', "
                f"price_range={task.price_min}-{task.price_max}"
            )
            
            # Search products (multi-page: up to WB_API_MAX_PAGES pages, ~100 products each)
            wb_products = await wb_api.search_all_pages(task.query)
            logger.info(
                f"Task {task.id}: API returned {len(wb_products)} products"
            )
            no_price_count = sum(1 for product in wb_products if product.price is None)
            if no_price_count:
                logger.debug(
                    "Task %s: %s products have no price before filtering",
                    task.id,
                    no_price_count,
                )
            
            # Yield control after HTTP request to allow bot to process messages
            await asyncio.sleep(0.01)  # Small delay to ensure bot gets priority
            
            # Filter products
            filtered = filter_products(wb_products, task)
            logger.info(
                f"Task {task.id}: {len(filtered)} products passed filters "
                f"(relevance, price range, exclude words) from {len(wb_products)} total"
            )

            # TEST MODE: limit number of products processed per task
            if config.PARSER_TEST_MODE:
                max_test_products = 5
                if len(filtered) > max_test_products:
                    filtered = filtered[:max_test_products]
                    logger.info(
                        f"[TEST MODE] Limiting products to first {len(filtered)} items "
                        f"from {len(wb_products)} total"
                    )

            events = []
            new_products_count = 0
            existing_products_count = 0
            
            for idx, wb_product in enumerate(filtered):
                # Yield control to event loop every 3 products to allow bot to process messages
                if idx > 0 and idx % 3 == 0:
                    await asyncio.sleep(0.002)  # Small delay to ensure bot gets priority
                
                # Deduplicate
                existing_product, is_new = await self.deduplicator.deduplicate(
                    wb_product,
                    task.user_id,
                )
                
                # Yield after DB operation to allow bot to process messages
                if idx % 3 == 0:
                    await asyncio.sleep(0.001)
                
                if is_new:
                    new_products_count += 1
                    # Create new product
                    # Run normalization in thread to avoid blocking event loop
                    normalized_name = await asyncio.to_thread(
                        self.normalizer.normalize, wb_product.name
                    )
                    product = await self.product_repo.create_or_update(
                        wb_id=wb_product.id,
                        user_id=task.user_id,
                        name=wb_product.name,
                        root_id=wb_product.root,
                        normalized_name=normalized_name,
                        brand=wb_product.brand,
                        seller=wb_product.supplier,
                        rating=wb_product.rating,
                        url=wb_product.url,
                    )
                    
                    logger.debug(
                        f"Task {task.id}: New product created: {product.name[:50]}... "
                        f"(wb_id={wb_product.id}, price={wb_product.price})"
                    )
                    
                    # Add seller if root_id exists
                    if wb_product.root and wb_product.supplier:
                        await self.seller_grouper.seller_repo.create_or_update(
                            product_id=product.id,
                            seller_name=wb_product.supplier,
                            price=wb_product.price,
                            rating=wb_product.supplier_rating,
                        )
                else:
                    existing_products_count += 1
                    # Use existing product; if по каким-то причинам его нет — пропускаем элемент
                    product = existing_product
                    if product is None:
                        logger.warning(
                            "Task %s: deduplicator returned is_new=False but existing_product is None "
                            "(wb_id=%s, name=%s)",
                            task.id,
                            wb_product.id,
                            wb_product.name[:50],
                        )
                        continue

                    # Update existing product's sellers (если есть поставщик)
                    if wb_product.supplier:
                        await self.seller_grouper.seller_repo.create_or_update(
                            product_id=product.id,
                            seller_name=wb_product.supplier,
                            price=wb_product.price,
                            rating=wb_product.supplier_rating,
                        )
                
                # Get best price (from sellers or product itself)
                best_price = await self.seller_grouper.get_best_price(product.id)
                if best_price is None:
                    best_price = wb_product.price
                
                # Log price info for debugging
                if is_new:
                    logger.info(
                        f"Task {task.id}: New product {product.id} ({product.name[:50]}...): "
                        f"wb_price={wb_product.price}, best_price={best_price}, "
                        f"price_range=[{task.price_min}, {task.price_max}]"
                    )
                
                # Yield after price lookup
                if idx % 3 == 0:
                    await asyncio.sleep(0.001)
                
                # Detect events
                event = await self.price_detector.detect_event(
                    product=product,
                    task=task,
                    current_price=best_price,
                )
                
                if event:
                    events.append(event)
                    logger.info(
                        f"Task {task.id}: Event detected for product {product.name[:50]}... "
                        f"(event_type={event.get('event_type')}, price={best_price})"
                    )
            
            # Update last_check
            await self.task_repo.update(
                task_id=task.id,
                price_min=task.price_min,  # Keep existing values
                price_max=task.price_max,
            )
            # Update last_check manually
            from sqlalchemy import update
            from database.models.search_task import SearchTask
            await self.session.execute(
                update(SearchTask)
                .where(SearchTask.id == task.id)
                .values(last_check=datetime.utcnow())
            )
            await self.session.commit()
            
            logger.info(
                f"Task {task.id} completed: "
                f"{len(wb_products)} found → {len(filtered)} filtered → "
                f"{new_products_count} new, {existing_products_count} existing → "
                f"{len(events)} events"
            )
            
            return events
            
        except Exception as e:
            logger.error(f"Error parsing task {task.id}: {e}")
            # Reset failed transaction state before any further DB operations.
            try:
                await self.session.rollback()
            except Exception:
                logger.error(
                    "Failed to rollback session after parse_task error",
                    exc_info=True,
                )
            # Ensure the scheduler doesn't repeatedly re-run the same task immediately
            # after transient HTTP/network issues.
            try:
                from sqlalchemy import update
                from database.models.search_task import SearchTask
                await self.session.execute(
                    update(SearchTask)
                    .where(SearchTask.id == task.id)
                    .values(last_check=datetime.utcnow())
                )
                await self.session.commit()
            except Exception:
                logger.error(
                    "Failed to update last_check after parse error",
                    exc_info=True,
                )
            return []
    
    async def run(self, tasks: List) -> List[dict]:
        """Run parser for list of tasks."""
        if not tasks:
            return []

        # NOTE:
        # parse_task performs many DB operations through a shared AsyncSession.
        # Running parse_task concurrently leads to SQLAlchemy async context errors
        # like "greenlet_spawn has not been called". Process tasks sequentially
        # to keep DB session usage safe and predictable.
        all_events = []
        for task in tasks:
            events = await self.parse_task(task)
            if events:
                all_events.extend(events)

        return all_events
    
    async def run_cycle(self) -> None:
        """Run one parsing cycle."""
        start_time = datetime.utcnow()
        
        try:
            # Load tasks
            tasks = await self.task_loader.load_tasks()
            
            # Get ready tasks
            ready_tasks = self.scheduler.get_ready_tasks(tasks)
            
            if not ready_tasks:
                logger.debug("No ready tasks")
                return

            # TEST MODE: process only a small number of tasks
            if config.PARSER_TEST_MODE:
                max_test_tasks = 1
                if len(ready_tasks) > max_test_tasks:
                    ready_tasks = ready_tasks[:max_test_tasks]
                    logger.info(
                        f"[TEST MODE] Limiting ready tasks to first {len(ready_tasks)} "
                        f"from {len(tasks)} loaded"
                    )

            logger.info(f"Processing {len(ready_tasks)} ready tasks")

            # Run parser
            events = await self.run(ready_tasks)
            
            # Send events to queue (with yield points for bot responsiveness)
            for idx, event in enumerate(events):
                await RedisStreams.add_event(event)
                # Yield control every 3 events to allow bot to process messages
                if idx > 0 and (idx + 1) % 3 == 0:
                    await asyncio.sleep(0.001)
            
            # Log performance
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            if events:
                logger.info(
                    f"✅ Parsed {len(ready_tasks)} tasks in {duration:.2f}s, "
                    f"found {len(events)} events → sending to notification queue"
                )
            else:
                logger.info(
                    f"Parsed {len(ready_tasks)} tasks in {duration:.2f}s, "
                    f"found {len(events)} events (no new events to notify)"
                )
            
        except Exception as e:
            logger.error(f"Error in parser cycle: {e}", exc_info=True)
            # Important: recover from failed transaction state (e.g. asyncpg
            # InFailedSQLTransactionError) so the next cycle can continue.
            try:
                await self.session.rollback()
            except Exception:
                logger.error(
                    "Failed to rollback session after parser cycle error",
                    exc_info=True,
                )
