"""Redis client for basic operations."""
import redis.asyncio as redis
from typing import Optional, Any
from core.config import config


class RedisClient:
    """Redis client wrapper."""
    
    def __init__(self):
        """Initialize Redis client."""
        self._client: Optional[redis.Redis] = None
    
    async def connect(self) -> None:
        """Connect to Redis."""
        if self._client is None:
            self._client = await redis.from_url(
                config.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
            )
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        if not self._client:
            await self.connect()
        return await self._client.get(key)
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ex: Optional[int] = None
    ) -> bool:
        """Set value with optional expiration."""
        if not self._client:
            await self.connect()
        return await self._client.set(key, str(value), ex=ex)
    
    async def delete(self, key: str) -> int:
        """Delete key."""
        if not self._client:
            await self.connect()
        return await self._client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        if not self._client:
            await self.connect()
        return await self._client.exists(key) > 0
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment key value."""
        if not self._client:
            await self.connect()
        return await self._client.incrby(key, amount)
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for key."""
        if not self._client:
            await self.connect()
        return await self._client.expire(key, seconds)


# Global Redis client instance
redis_client = RedisClient()
