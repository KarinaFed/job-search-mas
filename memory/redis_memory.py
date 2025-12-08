"""Redis-based short-term and shared memory."""
import redis
import json
from typing import Optional, Dict, Any
from datetime import datetime
from config import settings
from loguru import logger


class RedisMemory:
    """Redis memory manager for short-term and shared memory."""
    
    def __init__(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory fallback.")
            self.redis_client = None
            self._fallback_storage = {}
    
    def set_session_context(self, session_id: str, context: Dict[str, Any], ttl: int = 3600):
        """Store session context (short-term memory)."""
        key = f"session:{session_id}"
        if self.redis_client:
            self.redis_client.setex(key, ttl, json.dumps(context, default=str))
        else:
            self._fallback_storage[key] = context
        logger.debug(f"Stored session context for {session_id}")
    
    def get_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session context."""
        key = f"session:{session_id}"
        if self.redis_client:
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
        else:
            return self._fallback_storage.get(key)
        return None
    
    def update_session_context(self, session_id: str, updates: Dict[str, Any]):
        """Update session context with new data."""
        context = self.get_session_context(session_id) or {}
        context.update(updates)
        self.set_session_context(session_id, context)
    
    def publish_to_shared_memory(self, channel: str, message: Dict[str, Any]):
        """Publish message to shared memory (pub/sub)."""
        if self.redis_client:
            self.redis_client.publish(channel, json.dumps(message, default=str))
        logger.debug(f"Published message to channel {channel}")
    
    def set_shared_data(self, key: str, value: Dict[str, Any], ttl: Optional[int] = None):
        """Store data in shared memory."""
        if self.redis_client:
            if ttl:
                self.redis_client.setex(key, ttl, json.dumps(value, default=str))
            else:
                self.redis_client.set(key, json.dumps(value, default=str))
        else:
            self._fallback_storage[key] = value
    
    def get_shared_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from shared memory."""
        if self.redis_client:
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
        else:
            return self._fallback_storage.get(key)
        return None
    
    def append_agent_output(self, session_id: str, agent_name: str, output: Dict[str, Any]):
        """Append agent output to shared workspace."""
        key = f"workspace:{session_id}"
        workspace = self.get_shared_data(key) or {}
        if "agent_outputs" not in workspace:
            workspace["agent_outputs"] = {}
        workspace["agent_outputs"][agent_name] = output
        workspace["last_updated"] = str(datetime.now())
        self.set_shared_data(key, workspace, ttl=7200)
    
    def get_workspace(self, session_id: str) -> Dict[str, Any]:
        """Get collaborative workspace for session."""
        key = f"workspace:{session_id}"
        return self.get_shared_data(key) or {}
    
    def clear_session(self, session_id: str):
        """Clear session data."""
        keys = [f"session:{session_id}", f"workspace:{session_id}"]
        if self.redis_client:
            for key in keys:
                self.redis_client.delete(key)
        else:
            for key in keys:
                self._fallback_storage.pop(key, None)
        logger.info(f"Cleared session {session_id}")


redis_memory = RedisMemory()
