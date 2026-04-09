"""Главный файл для всех сервисов"""
import asyncio
import signal
import threading
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from core.config import config
from core.logger import logger
from bot.middlewares_all import DatabaseMiddleware, ThrottlingMiddleware
from bot.routers_all import start_router, menu_router, product_router
from bot.handlers.add_product import router as add_product_router
from bot.handlers.edit_product import router as edit_product_router
from database.db import init_db, AsyncSessionLocal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from core.config import config
from parser.engine.parser_engine import ParserEngine
from notifier.worker.notification_worker import NotificationWorker
from infrastructure.redis.redis_client import redis_client, RedisClient
from infrastructure.redis.redis_streams import RedisStreams
from infrastructure.http.http_client import http_client
from infrastructure.telegram.telegram_client import telegram_client


# Глобальный флаг для условного завершения (соблюдение потокобезопасности)
shutdown_event = threading.Event()
parser_thread = None
# Separate Redis client for parser thread (используется только в production режиме; в test режиме мы используем глобальный redis_client)
parser_redis_client = None


async def run_bot():
    """Запуск Telegram бота"""
    bot = None
    dp = None
    try:
        logger.info("Bot service starting...")
        
        # Initialize bot and dispatcher
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        dp = Dispatcher(storage=MemoryStorage())
        
        # Register middleware
        dp.message.middleware(DatabaseMiddleware())
        dp.callback_query.middleware(DatabaseMiddleware())
        dp.message.middleware(ThrottlingMiddleware())
        dp.callback_query.middleware(ThrottlingMiddleware())
        
        # Register routers
        dp.include_router(start_router)
        dp.include_router(menu_router)
        dp.include_router(product_router)
        dp.include_router(add_product_router)
        dp.include_router(edit_product_router)
        
        logger.info("Bot service started")
        
        # Start polling (this blocks until shutdown)
        await dp.start_polling(bot, stop_signals=[])
        
    except asyncio.CancelledError:
        logger.info("Bot service cancelled")
        raise
    except Exception as e:
        logger.error(f"Error in bot service: {e}", exc_info=True)
        # Fail fast: let main/systemd restart the whole service if bot crashes.
        raise
    finally:
        # Stop polling and close bot
        if dp:
            try:
                await dp.stop_polling()
            except Exception:
                # Dispatcher might not be fully started yet.
                pass
        if bot:
            await bot.session.close()
        logger.info("Bot service stopped")


async def run_parser():
    """Запуск парсера в отдельном потоке"""
    try:
        logger.info("Parser service starting in separate thread...")

        async with AsyncSessionLocal() as session:
            parser_engine = ParserEngine(session)

            if config.PARSER_TEST_MODE:
                # TEST MODE: run a single parser cycle and stop
                await parser_engine.run_cycle()
                logger.info("[TEST MODE] Parser ran single cycle and will now stop")
                return

            # Production mode: run parser continuously
            while True:
                await parser_engine.run_cycle()
                await asyncio.sleep(config.PARSER_CYCLE_SLEEP)
        
    except asyncio.CancelledError:
        logger.info("Parser service cancelled")
    except Exception as e:
        logger.error(f"Error in parser service: {e}", exc_info=True)
    finally:
        logger.info("Parser service stopped")


def run_parser_in_thread():
    """Запуск парсера в отдельном потоке с его собственным циклом событий"""
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Create separate database engine for this thread
    # This ensures the engine is bound to this thread's event loop
    parser_engine = create_async_engine(
        config.DATABASE_URL,
        echo=False,
        poolclass=NullPool,  # Use NullPool to avoid connection pool issues across threads
        pool_pre_ping=True,
        future=True,
    )
    ParserSessionLocal = async_sessionmaker(
        parser_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async def init_parser_resources():
        """Initialize resources for parser thread."""
        # In TEST MODE we reuse global redis_client, so no separate connection here.
        logger.info("Parser thread: Database engine created (separate connection)")
    
    async def run_parser_with_separate_resources():
        """Run parser with separate Redis client, DB session and HTTP client."""
        # TEST MODE: do not replace global redis_client, reuse the same client as main loop.
        # This avoids cross-event-loop issues for Redis.
        # Replace AsyncSessionLocal with parser's session factory
        import database.db as db_module
        original_session_local = db_module.AsyncSessionLocal
        original_main_session_local = AsyncSessionLocal
        db_module.AsyncSessionLocal = ParserSessionLocal
        globals()["AsyncSessionLocal"] = ParserSessionLocal

        try:
            await run_parser()
            # Cleanup parser's DB engine within the same event loop
            try:
                await parser_engine.dispose()
            except Exception as e:
                logger.error(f"Error cleaning up parser DB engine: {e}")
        finally:
            # Restore original session factory
            db_module.AsyncSessionLocal = original_session_local
            globals()["AsyncSessionLocal"] = original_main_session_local
    
    try:
        # Initialize resources
        loop.run_until_complete(init_parser_resources())
        
        # Run parser with separate Redis client and DB engine
        loop.run_until_complete(run_parser_with_separate_resources())
    except Exception as e:
        logger.error(f"Error in parser thread: {e}", exc_info=True)
    finally:
        # Close event loop for parser thread
        loop.close()
        logger.info("Parser thread: Event loop closed")


async def run_notifier():
    """Запуск нотификатора"""
    try:
        logger.info("Notifier service starting...")
        
        # Run worker loop with shutdown check
        # Create session per event batch to avoid long-lived connections
        while not shutdown_event.is_set():  # threading.Event works in async context
            try:
                # Read events from stream (with timeout to check shutdown)
                events = await RedisStreams.read_events(count=10, block=1000)
                
                if events:
                    logger.info(f"Processing {len(events)} events")
                    # Create new session for processing events
                    async with AsyncSessionLocal() as session:
                        worker = NotificationWorker(session)
                        for message_id, event_data in events:
                            if shutdown_event.is_set():
                                break
                            await worker.process_event(event_data)
                            # Acknowledge event
                            await RedisStreams.acknowledge_event(message_id)
                else:
                    # Small sleep if no events to allow shutdown check
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                if not shutdown_event.is_set():
                    logger.error(f"Error in notifier cycle: {e}", exc_info=True)
                await asyncio.sleep(1)
        
    except asyncio.CancelledError:
        logger.info("Notifier service cancelled")
    except Exception as e:
        logger.error(f"Error in notifier service: {e}", exc_info=True)
    finally:
        logger.info("Notifier service stopped")


async def main():
    """Главная функция - запуск всех сервисов"""
    # Validate config
    config.validate()
    
    # Initialize database tables
    await init_db()
    logger.info("Database initialized")
    
    # Connect to Redis (shared by parser and notifier)
    await redis_client.connect()
    logger.info("Redis connected")
    
    # Initialize Redis Stream consumer group
    await RedisStreams.ensure_consumer_group()
    logger.info("Redis Stream consumer group initialized")
    
    try:
        # Start parser in separate thread with its own event loop
        global parser_thread
        parser_thread = threading.Thread(
            target=run_parser_in_thread,
            daemon=True,
            name="ParserThread"
        )
        parser_thread.start()
        logger.info("Parser service started in separate thread")
        
        # Create tasks for bot and notifier (they share the main event loop)
        bot_task = asyncio.create_task(run_bot())
        notifier_task = asyncio.create_task(run_notifier())
        
        logger.info("All services started")
        
        # Wait for bot and notifier (parser runs in separate thread).
        # Any task failure should fail the process so systemd can restart it.
        await asyncio.gather(bot_task, notifier_task)
        
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
    finally:
        # Set shutdown event
        shutdown_event.set()
        
        # Close all connections
        logger.info("Closing connections...")
        await redis_client.disconnect()
        await http_client.close()
        await telegram_client.close()
        logger.info("All services stopped")


def signal_handler():
    """Обработка сигналов завершения"""
    logger.info("Received shutdown signal")
    shutdown_event.set()


if __name__ == "__main__":
    # Setup signal handlers for graceful shutdown
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
