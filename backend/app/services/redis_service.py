import redis.asyncio as redis
from typing import Optional
import json
import time
from datetime import datetime, timedelta

from ..core.config import settings


class RedisService:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None

    async def connect(self):
        """Connect to Redis"""
        self.redis_client = await redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )

    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()

    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int
    ) -> tuple[bool, int]:
        """
        Token bucket rate limiting
        Returns: (allowed, remaining_requests)
        """
        now = time.time()
        window_key = f"rate:{key}:{int(now / window_seconds)}"

        current = await self.redis_client.get(window_key)

        if current is None:
            await self.redis_client.setex(
                window_key,
                window_seconds,
                1
            )
            return True, max_requests - 1

        current_count = int(current)

        if current_count >= max_requests:
            return False, 0

        await self.redis_client.incr(window_key)
        return True, max_requests - current_count - 1

    async def acquire_lock(
        self,
        lock_key: str,
        timeout: int = 10
    ) -> bool:
        """
        Acquire distributed lock
        """
        acquired = await self.redis_client.set(
            f"lock:{lock_key}",
            "1",
            nx=True,
            ex=timeout
        )
        return bool(acquired)

    async def release_lock(self, lock_key: str):
        """Release distributed lock"""
        await self.redis_client.delete(f"lock:{lock_key}")

    async def enqueue_job(self, queue_name: str, job_data: dict):
        """Add job to queue"""
        await self.redis_client.rpush(
            f"queue:{queue_name}",
            json.dumps(job_data)
        )

    async def dequeue_job(self, queue_name: str) -> Optional[dict]:
        """Get job from queue (blocking)"""
        result = await self.redis_client.blpop(
            f"queue:{queue_name}",
            timeout=5
        )
        if result:
            _, job_json = result
            return json.loads(job_json)
        return None

    async def get_queue_length(self, queue_name: str) -> int:
        """Get queue length"""
        return await self.redis_client.llen(f"queue:{queue_name}")

    async def check_platform_rate(
        self,
        platform: str,
        account_id: int,
        action: str,
        hourly_limit: int,
        daily_limit: int
    ) -> tuple[bool, str]:
        """
        Check platform-specific rate limits
        Returns: (allowed, reason)
        """
        # Check hourly limit
        hourly_allowed, _ = await self.check_rate_limit(
            f"{platform}:{account_id}:{action}:hourly",
            hourly_limit,
            3600
        )

        if not hourly_allowed:
            return False, "Hourly rate limit exceeded"

        # Check daily limit
        daily_allowed, _ = await self.check_rate_limit(
            f"{platform}:{account_id}:{action}:daily",
            daily_limit,
            86400
        )

        if not daily_allowed:
            return False, "Daily rate limit exceeded"

        return True, "OK"

    async def increment_metric(self, key: str, value: float = 1.0):
        """Increment a metric counter"""
        await self.redis_client.incrbyfloat(f"metric:{key}", value)

    async def get_metric(self, key: str) -> float:
        """Get metric value"""
        value = await self.redis_client.get(f"metric:{key}")
        return float(value) if value else 0.0

    async def set_cache(self, key: str, value: str, ttl: int = 300):
        """Set cache with TTL"""
        await self.redis_client.setex(f"cache:{key}", ttl, value)

    async def get_cache(self, key: str) -> Optional[str]:
        """Get cached value"""
        return await self.redis_client.get(f"cache:{key}")


redis_service = RedisService()
