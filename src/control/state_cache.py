"""
State Cache - Redis-backed state persistence for crash recovery

Features:
- Task state persistence in Redis
- Automatic recovery after crash/restart
- Distributed state sharing across workers
- TTL-based cleanup
"""
from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from loguru import logger


class TaskState(str, Enum):
    """Task execution states"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECOVERING = "recovering"


@dataclass
class CachedTaskState:
    """Cached task state with metadata"""
    task_id: str
    state: TaskState
    target: str
    task_type: str
    retry_count: int = 0
    max_retries: int = 3
    error: Optional[str] = None
    result: Optional[dict] = None
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    worker_id: Optional[str] = None
    checkpoint: Optional[dict] = None  # For resumable tasks

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "state": self.state.value,
            "target": self.target,
            "task_type": self.task_type,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error": self.error,
            "result": self.result,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "worker_id": self.worker_id,
            "checkpoint": self.checkpoint,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CachedTaskState":
        return cls(
            task_id=data["task_id"],
            state=TaskState(data["state"]),
            target=data["target"],
            task_type=data["task_type"],
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            error=data.get("error"),
            result=data.get("result"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            worker_id=data.get("worker_id"),
            checkpoint=data.get("checkpoint"),
        )


class StateCache(ABC):
    """Abstract base class for state caches"""

    @abstractmethod
    async def save(self, state: CachedTaskState) -> bool:
        """Save task state"""
        pass

    @abstractmethod
    async def get(self, task_id: str) -> Optional[CachedTaskState]:
        """Get task state"""
        pass

    @abstractmethod
    async def delete(self, task_id: str) -> bool:
        """Delete task state"""
        pass

    @abstractmethod
    async def list_by_state(self, state: TaskState) -> list[CachedTaskState]:
        """List tasks by state"""
        pass

    @abstractmethod
    async def list_all(self) -> list[CachedTaskState]:
        """List all tasks"""
        pass


class InMemoryStateCache(StateCache):
    """In-memory state cache for development/testing"""

    def __init__(self, max_size: int = 10000):
        self._cache: dict[str, CachedTaskState] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def save(self, state: CachedTaskState) -> bool:
        async with self._lock:
            state.updated_at = time.time()
            self._cache[state.task_id] = state

            # Enforce max size (remove oldest completed/failed)
            if len(self._cache) > self._max_size:
                to_remove = []
                for tid, s in self._cache.items():
                    if s.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
                        to_remove.append(tid)
                        if len(self._cache) - len(to_remove) <= self._max_size:
                            break

                for tid in to_remove:
                    del self._cache[tid]

            return True

    async def get(self, task_id: str) -> Optional[CachedTaskState]:
        return self._cache.get(task_id)

    async def delete(self, task_id: str) -> bool:
        if task_id in self._cache:
            del self._cache[task_id]
            return True
        return False

    async def list_by_state(self, state: TaskState) -> list[CachedTaskState]:
        return [s for s in self._cache.values() if s.state == state]

    async def list_all(self) -> list[CachedTaskState]:
        return list(self._cache.values())

    def get_stats(self) -> dict:
        states = {}
        for s in self._cache.values():
            states[s.state.value] = states.get(s.state.value, 0) + 1
        return {
            "total": len(self._cache),
            "max_size": self._max_size,
            "by_state": states,
        }


class RedisStateCache(StateCache):
    """
    Redis-backed state cache for distributed systems.

    Features:
    - Persistent task state storage
    - TTL-based automatic cleanup
    - Crash recovery support
    - Distributed locking for state updates

    Example:
        cache = RedisStateCache(redis_url="redis://localhost:6379")

        # Save task state
        state = CachedTaskState(
            task_id="task_001",
            state=TaskState.RUNNING,
            target="https://example.com",
            task_type="navigate",
        )
        await cache.save(state)

        # Recover after crash
        running_tasks = await cache.list_by_state(TaskState.RUNNING)
        for task in running_tasks:
            task.state = TaskState.RECOVERING
            await cache.save(task)
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "ccp:tasks:",
        default_ttl: int = 86400,  # 24 hours
        completed_ttl: int = 3600,  # 1 hour for completed tasks
    ):
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        self._default_ttl = default_ttl
        self._completed_ttl = completed_ttl
        self._redis = None

    async def _get_redis(self):
        """Lazy Redis connection"""
        if self._redis is not None:
            return self._redis

        try:
            import redis.asyncio as redis
            self._redis = redis.from_url(self._redis_url)
            await self._redis.ping()
            logger.info(f"State cache connected to Redis: {self._redis_url}")
            return self._redis
        except ImportError:
            logger.error("redis package not installed: pip install redis")
            raise
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise

    def _task_key(self, task_id: str) -> str:
        return f"{self._key_prefix}{task_id}"

    def _index_key(self, state: TaskState) -> str:
        return f"{self._key_prefix}index:{state.value}"

    async def save(self, state: CachedTaskState) -> bool:
        """Save task state to Redis"""
        redis_client = await self._get_redis()

        state.updated_at = time.time()
        task_key = self._task_key(state.task_id)
        data = json.dumps(state.to_dict())

        # Determine TTL
        if state.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
            ttl = self._completed_ttl
        else:
            ttl = self._default_ttl

        try:
            # Use pipeline for atomic operation
            async with redis_client.pipeline() as pipe:
                # Save task data
                await pipe.setex(task_key, ttl, data)

                # Update state index
                await pipe.sadd(self._index_key(state.state), state.task_id)

                # Remove from other state indexes
                for s in TaskState:
                    if s != state.state:
                        await pipe.srem(self._index_key(s), state.task_id)

                await pipe.execute()

            logger.debug(f"Saved task state: {state.task_id} -> {state.state.value}")
            return True

        except Exception as e:
            logger.error(f"Failed to save task state: {e}")
            return False

    async def get(self, task_id: str) -> Optional[CachedTaskState]:
        """Get task state from Redis"""
        redis_client = await self._get_redis()

        try:
            data = await redis_client.get(self._task_key(task_id))
            if data:
                return CachedTaskState.from_dict(json.loads(data))
            return None
        except Exception as e:
            logger.error(f"Failed to get task state: {e}")
            return None

    async def delete(self, task_id: str) -> bool:
        """Delete task state from Redis"""
        redis_client = await self._get_redis()

        try:
            task_key = self._task_key(task_id)

            # Get current state to remove from index
            data = await redis_client.get(task_key)
            if data:
                state_data = json.loads(data)
                state = TaskState(state_data["state"])
                await redis_client.srem(self._index_key(state), task_id)

            await redis_client.delete(task_key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete task state: {e}")
            return False

    async def list_by_state(self, state: TaskState) -> list[CachedTaskState]:
        """List tasks by state"""
        redis_client = await self._get_redis()

        try:
            task_ids = await redis_client.smembers(self._index_key(state))
            tasks = []

            for task_id in task_ids:
                task = await self.get(task_id.decode() if isinstance(task_id, bytes) else task_id)
                if task and task.state == state:
                    tasks.append(task)

            return tasks
        except Exception as e:
            logger.error(f"Failed to list tasks by state: {e}")
            return []

    async def list_all(self) -> list[CachedTaskState]:
        """List all tasks"""
        redis_client = await self._get_redis()

        try:
            # Get all task keys
            pattern = f"{self._key_prefix}[^:]*"
            keys = []
            async for key in redis_client.scan_iter(match=pattern):
                if b":index:" not in key and ":index:" not in str(key):
                    keys.append(key)

            tasks = []
            for key in keys:
                data = await redis_client.get(key)
                if data:
                    tasks.append(CachedTaskState.from_dict(json.loads(data)))

            return tasks
        except Exception as e:
            logger.error(f"Failed to list all tasks: {e}")
            return []

    async def recover_running_tasks(self, worker_id: Optional[str] = None) -> list[CachedTaskState]:
        """
        Recover tasks that were running when system crashed.

        Args:
            worker_id: Optional filter by worker

        Returns:
            List of tasks marked for recovery
        """
        running_tasks = await self.list_by_state(TaskState.RUNNING)

        recovered = []
        for task in running_tasks:
            if worker_id and task.worker_id != worker_id:
                continue

            task.state = TaskState.RECOVERING
            task.retry_count += 1
            await self.save(task)
            recovered.append(task)

        logger.info(f"Recovered {len(recovered)} running tasks")
        return recovered

    async def cleanup_old_tasks(self, max_age_seconds: int = 86400) -> int:
        """
        Cleanup old completed/failed tasks.

        Args:
            max_age_seconds: Maximum age of tasks to keep

        Returns:
            Number of tasks cleaned up
        """
        cutoff = time.time() - max_age_seconds
        cleaned = 0

        for state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED):
            tasks = await self.list_by_state(state)
            for task in tasks:
                if task.updated_at < cutoff:
                    await self.delete(task.task_id)
                    cleaned += 1

        logger.info(f"Cleaned up {cleaned} old tasks")
        return cleaned

    async def acquire_lock(self, task_id: str, worker_id: str, ttl: int = 60) -> bool:
        """
        Acquire distributed lock for task.

        Args:
            task_id: Task to lock
            worker_id: Worker acquiring lock
            ttl: Lock TTL in seconds

        Returns:
            True if lock acquired
        """
        redis_client = await self._get_redis()
        lock_key = f"{self._key_prefix}lock:{task_id}"

        try:
            result = await redis_client.set(lock_key, worker_id, nx=True, ex=ttl)
            return result is not None
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            return False

    async def release_lock(self, task_id: str, worker_id: str) -> bool:
        """Release distributed lock for task"""
        redis_client = await self._get_redis()
        lock_key = f"{self._key_prefix}lock:{task_id}"

        try:
            # Only release if we own the lock
            current = await redis_client.get(lock_key)
            if current and current.decode() == worker_id:
                await redis_client.delete(lock_key)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to release lock: {e}")
            return False

    async def save_checkpoint(self, task_id: str, checkpoint: dict) -> bool:
        """
        Save checkpoint for resumable task.

        Args:
            task_id: Task ID
            checkpoint: Checkpoint data

        Returns:
            True if saved
        """
        task = await self.get(task_id)
        if task:
            task.checkpoint = checkpoint
            return await self.save(task)
        return False

    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def get_stats(self) -> dict:
        """Get cache statistics"""
        redis_client = await self._get_redis()

        stats = {
            "backend": "redis",
            "connected": True,
            "by_state": {},
        }

        try:
            for state in TaskState:
                count = await redis_client.scard(self._index_key(state))
                stats["by_state"][state.value] = count

            stats["total"] = sum(stats["by_state"].values())
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            stats["error"] = str(e)

        return stats


def create_state_cache(
    backend: str = "memory",
    **kwargs,
) -> StateCache:
    """
    Factory function to create state cache.

    Args:
        backend: "memory" or "redis"
        **kwargs: Backend-specific options

    Returns:
        StateCache instance
    """
    if backend == "memory":
        return InMemoryStateCache(**kwargs)
    elif backend == "redis":
        return RedisStateCache(**kwargs)
    else:
        raise ValueError(f"Unknown backend: {backend}")