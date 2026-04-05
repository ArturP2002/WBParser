"""Redis streams for event queue."""
import json
from typing import Optional, Dict, Any
from infrastructure.redis.redis_client import redis_client
from core.logger import logger


class RedisStreams:
    """Redis streams for event queue."""
    
    STREAM_NAME = "notification_queue"
    CONSUMER_GROUP = "notification_group"
    CONSUMER_NAME = "notifier_worker"
    
    @staticmethod
    async def _ensure_consumer_group():
        """Ensure consumer group exists."""
        if not redis_client._client:
            await redis_client.connect()
        
        try:
            # Try to create consumer group (will fail if it already exists, which is fine)
            await redis_client._client.xgroup_create(
                name=RedisStreams.STREAM_NAME,
                groupname=RedisStreams.CONSUMER_GROUP,
                id="0",  # Start from beginning
                mkstream=True  # Create stream if it doesn't exist
            )
            logger.info(f"Created consumer group '{RedisStreams.CONSUMER_GROUP}' for stream '{RedisStreams.STREAM_NAME}'")
        except Exception as e:
            # Group already exists or other error - that's okay
            if "BUSYGROUP" not in str(e) and "already exists" not in str(e).lower():
                logger.warning(f"Error creating consumer group: {e}")
    
    @staticmethod
    async def ensure_consumer_group():
        """Ensure consumer group exists (public method for initialization)."""
        await RedisStreams._ensure_consumer_group()
    
    @staticmethod
    async def add_event(event: Dict[str, Any]) -> str:
        """Add event to stream."""
        if not redis_client._client:
            await redis_client.connect()
        
        # Convert event to JSON string
        event_data = json.dumps(event)
        
        # Add to stream
        message_id = await redis_client._client.xadd(
            RedisStreams.STREAM_NAME,
            {"data": event_data}
        )
        return message_id
    
    @staticmethod
    async def read_events(
        count: int = 10,
        block: Optional[int] = None
    ) -> list[tuple[str, Dict[str, Any]]]:
        """Read events from stream using consumer group."""
        if not redis_client._client:
            await redis_client.connect()
        
        # Ensure consumer group exists
        await RedisStreams._ensure_consumer_group()
        
        # Read from stream using consumer group (reads only unprocessed messages)
        try:
            messages = await redis_client._client.xreadgroup(
                groupname=RedisStreams.CONSUMER_GROUP,
                consumername=RedisStreams.CONSUMER_NAME,
                streams={RedisStreams.STREAM_NAME: ">"},  # ">" means "read only new messages"
                count=count,
                block=block,
            )
        except Exception as e:
            # If consumer group doesn't exist, create it and retry
            if "NOGROUP" in str(e):
                await RedisStreams._ensure_consumer_group()
                messages = await redis_client._client.xreadgroup(
                    groupname=RedisStreams.CONSUMER_GROUP,
                    consumername=RedisStreams.CONSUMER_NAME,
                    streams={RedisStreams.STREAM_NAME: ">"},
                    count=count,
                    block=block,
                )
            else:
                raise
        
        events = []
        for stream_name, stream_messages in messages:
            for message_id, message_data in stream_messages:
                event_data = json.loads(message_data.get("data", "{}"))
                events.append((message_id, event_data))
        
        return events
    
    @staticmethod
    async def acknowledge_event(message_id: str) -> None:
        """Acknowledge event processing."""
        if not redis_client._client:
            await redis_client.connect()
        
        await redis_client._client.xack(
            RedisStreams.STREAM_NAME,
            RedisStreams.CONSUMER_GROUP,
            message_id
        )
