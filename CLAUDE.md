# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run application locally (requires .env file)
python main.py

# Run with Docker Compose
docker-compose up -d

# Run tests
python -m unittest tests/test_wb_parsing_and_prices.py

# Database migrations
python -m alembic upgrade head
python -m alembic revision --autogenerate -m "description"
```

## Architecture Overview

This is a **Wildberries price monitoring Telegram bot** split into 4 concurrent services, all launched from [main.py](main.py):

- **Bot** — handles Telegram user interactions (aiogram 3.x). Runs as an async task in the main event loop.
- **Parser** — queries Wildberries API, filters/deduplicates products, emits price events. Runs in a **separate thread** with its own event loop (to isolate blocking ML inference). Uses NullPool for DB connections.
- **Event Detector** (`event_detector/`) — detects price changes (new product, price drop, price entering target range) and writes events to Redis Streams.
- **Notifier** — reads from Redis Streams, applies rate limiting and deduplication, sends Telegram messages.

### Data Flow

```
User → Bot → SearchTask (PostgreSQL)
                          ↓
Parser: TaskLoader → TaskScheduler → WorkerPool → WB API
                                                    ↓
                              Filter → Deduplicator → ProductNormalizer
                                                    ↓
                                            PriceDetector → Redis Streams
                                                                  ↓
                                                   Notifier → TelegramClient → User
```

### Key Directories

- [bot/handlers/](bot/handlers/) — FSM-driven Telegram handlers; states in [bot/states.py](bot/states.py)
- [parser/engine/](parser/engine/) — orchestrates task scheduling, worker pool (semaphore-limited), and WB API calls
- [parser/wb/](parser/wb/) — Wildberries API client supporting v4/v5/v18 search + card price endpoints
- [parser/processing/](parser/processing/) — product filtering (price range, exclude words), deduplication (rapidfuzz), normalization (sentence-transformers)
- [notifier/worker/](notifier/worker/) — Redis Streams consumer with rate limiting (20/min/user) and 12-hour notification dedup
- [infrastructure/redis/](infrastructure/redis/) — Redis cache, streams, and event queue abstractions
- [database/models/](database/models/) — SQLAlchemy models: Users, SearchTasks, Products, ProductPrices, ProductSellers, Notifications
- [database/repositories/](database/repositories/) — repository pattern for all DB access
- [core/config.py](core/config.py) — all configuration via env vars (40+ settings)

### Threading Model

The parser runs in a separate thread with its own asyncio event loop. The main thread runs Bot + Notifier sharing one event loop. Redis client is shared across threads; DB connections use NullPool in the parser thread to avoid cross-loop issues.

### Configuration

All settings come from environment variables (see [core/config.py](core/config.py)). Required:
- `TELEGRAM_BOT_TOKEN`
- `DATABASE_URL` (default: `postgresql+asyncpg://...`)
- `REDIS_URL` (default: `redis://localhost:6379/0`)

Key tunable values: `PARSER_SEMAPHORE_LIMIT` (default 50), `MIN_PRICE_CHANGE` (default 200 RUB), event dedup TTL (5 min), notification dedup (12 hours).

### Test Mode

Set `PARSER_TEST_MODE=true` to run a single parse cycle and exit (used in integration tests and local debugging without real Telegram traffic). WB stub mode is also available for testing without real API calls.
