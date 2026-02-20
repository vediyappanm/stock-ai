"""
Cache Layer - Redis with in-memory fallback.
Shared across all uvicorn workers via Redis.
Falls back to in-memory dict if Redis is unavailable.
"""
import json
import logging
from typing import Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CacheLayer:
    """
    Production cache with Redis primary and in-memory fallback.
    Redis ensures cache is shared across multiple uvicorn workers.
    """

    def __init__(self, ttl_minutes: int = 30, prefix: str = "research"):
        self._ttl = ttl_minutes * 60  # Redis uses seconds
        self._prefix = prefix
        self._redis = None
        self._memory: dict = {}  # Fallback
        self._connect_redis()

    def _connect_redis(self):
        """Try to connect to Redis. Silently fall back to memory if unavailable."""
        try:
            import redis
            r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
            r.ping()
            self._redis = r
            logger.info("Cache: Redis connected ✅")
        except Exception as e:
            logger.warning(f"Cache: Redis unavailable, using in-memory fallback ⚠️ ({e})")
            self._redis = None

    def _make_key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache. Returns None on miss."""
        full_key = self._make_key(key)

        if self._redis:
            try:
                raw = self._redis.get(full_key)
                if raw:
                    logger.debug(f"Cache HIT (Redis): {full_key}")
                    return json.loads(raw)
            except Exception as e:
                logger.warning(f"Redis get error: {e}")

        # In-memory fallback
        if full_key in self._memory:
            value, expires_at = self._memory[full_key]
            if datetime.now() < expires_at:
                logger.debug(f"Cache HIT (memory): {full_key}")
                return value
            else:
                del self._memory[full_key]

        logger.debug(f"Cache MISS: {full_key}")
        return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with TTL."""
        full_key = self._make_key(key)

        if self._redis:
            try:
                self._redis.setex(full_key, self._ttl, json.dumps(value, default=str))
                logger.debug(f"Cache SET (Redis): {full_key}")
                return
            except Exception as e:
                logger.warning(f"Redis set error: {e}")

        # In-memory fallback
        expires_at = datetime.now() + timedelta(seconds=self._ttl)
        self._memory[full_key] = (value, expires_at)
        logger.debug(f"Cache SET (memory): {full_key}")

    def invalidate(self, key: str) -> None:
        """Manually invalidate a cache entry."""
        full_key = self._make_key(key)
        if self._redis:
            try:
                self._redis.delete(full_key)
            except Exception:
                pass
        self._memory.pop(full_key, None)


# Global instance shared across modules
cache = CacheLayer(ttl_minutes=30, prefix="stk_research")
