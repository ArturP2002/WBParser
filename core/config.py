"""Модуль для загрузки переменных окружения"""
import os
from typing import Optional, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Конфигурация приложения"""
    
    # База данных
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:password@localhost:5432/wb_parser_bot"
    )
    
    # Redis (для кеширования)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Telegram Bot (токен для бота)
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_API_ID: Optional[str] = os.getenv("TELEGRAM_API_ID")  # ID для API Telegram
    TELEGRAM_API_HASH: Optional[str] = os.getenv("TELEGRAM_API_HASH")  # Хеш для API Telegram
    
    # Настройки парсера
    MIN_PRICE_CHANGE: int = int(os.getenv("MIN_PRICE_CHANGE", "200"))
    PARSER_SEMAPHORE_LIMIT: int = int(os.getenv("PARSER_SEMAPHORE_LIMIT", "50"))
    # Parser loop controls
    # By default parser runs continuously; set PARSER_TEST_MODE=true for local debugging.
    PARSER_TEST_MODE: bool = os.getenv("PARSER_TEST_MODE", "false").lower() in {"1", "true", "yes"}
    PARSER_TEST_MAX_TASKS: int = int(os.getenv("PARSER_TEST_MAX_TASKS", "1"))
    PARSER_TEST_MAX_PRODUCTS: int = int(os.getenv("PARSER_TEST_MAX_PRODUCTS", "5"))
    PARSER_CYCLE_SLEEP: float = float(os.getenv("PARSER_CYCLE_SLEEP", "1.0"))
    TASK_LOADER_INTERVAL: int = int(os.getenv("TASK_LOADER_INTERVAL", "10"))
    SCHEDULER_INTERVAL: int = int(os.getenv("SCHEDULER_INTERVAL", "3"))
    
    # Логирование
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # WB API settings
    # Используем u-search.wb.ru для v18+ (новый endpoint с лучшими данными о цене)
    # Если нет v18, используем search.wb.ru
    # Используем u-search.wb.ru для v18+ (новый endpoint с лучшими данными о цене)
    # Если нет v18, используем search.wb.ru
    WB_API_BASE_URL: str = os.getenv("WB_API_BASE_URL", "https://search.wb.ru")
    WB_API_VERSION: str = os.getenv("WB_API_VERSION", "v5")  # v4, v5, or v18
    WB_API_TIMEOUT: int = int(os.getenv("WB_API_TIMEOUT", "20"))
    WB_API_RETRIES: int = int(os.getenv("WB_API_RETRIES", "5"))
    WB_API_MAX_PAGES: int = int(os.getenv("WB_API_MAX_PAGES", "1"))  # Max pages to fetch (1-10, 100 products per page)
    
    # WB Cards API settings (для получения цен)
    WB_CARDS_API_BASE_URL: str = "https://card.wb.ru"
    WB_CARDS_API_ENDPOINT: str = "/cards/v4/detail"
    WB_CARDS_API_BATCH_SIZE: int = int(os.getenv("WB_CARDS_API_BATCH_SIZE", "30"))
    
    # WB API additional parameters
    WB_API_DEST: str = os.getenv("WB_API_DEST", "-1257786")  # Москва по умолчанию
    WB_API_REGIONS: str = os.getenv(
        "WB_API_REGIONS", 
        "80,64,38,4,115,83,33,68,70,30,86,75,69,1,66,110,22,48,71,31,54,114"
    )  # Основные регионы России
    WB_API_APPTYPE: str = os.getenv("WB_API_APPTYPE", "1")  # 1 = веб
    WB_API_CURR: str = os.getenv("WB_API_CURR", "rub")
    WB_API_LANG: str = os.getenv("WB_API_LANG", "ru")
    WB_API_LOCALE: str = os.getenv("WB_API_LOCALE", "ru")
    WB_API_SPP: int = int(os.getenv("WB_API_SPP", "30"))  # Discount percentage used by WB frontend
    # Test / stub mode for WB API (do not call real WB, return fake data)
    WB_STUB_MODE: bool = os.getenv("WB_STUB_MODE", "false").lower() in {"1", "true", "yes"}
    
    @property
    def WB_API_SEARCH_ENDPOINT(self) -> str:
        """Get search endpoint based on API version."""
        # For v18+, use the newer endpoint structure
        if self.WB_API_VERSION in ("v18", "18"):
            return "/exactmatch/ru/common/v18/search"
        return f"/exactmatch/ru/common/{self.WB_API_VERSION}/search"
    
    # HTTP client settings
    HTTP_MAX_CONNECTIONS: int = 100
    HTTP_MAX_KEEPALIVE_CONNECTIONS: int = 50
    HTTP_CONNECT_TIMEOUT: int = int(os.getenv("HTTP_CONNECT_TIMEOUT", "20"))
    
    # Request throttling (seconds) — target ~3 req/sec
    WB_REQUEST_DELAY_MIN: float = float(os.getenv("WB_REQUEST_DELAY_MIN", "0.3"))
    WB_REQUEST_DELAY_MAX: float = float(os.getenv("WB_REQUEST_DELAY_MAX", "0.5"))
    
    # Notification settings
    NOTIFICATION_LIMIT_PER_MINUTE: int = 20
    NOTIFICATION_DEDUP_TTL: int = 43200  # 12 hours in seconds
    EVENT_DEDUP_TTL: int = 300  # 5 minutes in seconds
    
    # Proxy settings
    PROXY_LIST: List[str] = (
        [p.strip() for p in os.getenv("PROXY_LIST", "").split(",") if p.strip()]
        if os.getenv("PROXY_LIST")
        else []
    )
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration values."""
        if not cls.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL is required")
        if not cls.REDIS_URL:
            raise ValueError("REDIS_URL is required")


# Global config instance
config = Config()
