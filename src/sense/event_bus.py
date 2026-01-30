"""
Event Bus - Pub/Sub event system
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional
from collections import defaultdict
from loguru import logger


@dataclass
class Event:
    """Immutable event data"""
    event_type: str
    source: str
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.source:
            raise ValueError("source is required")


EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    Async event bus for publish/subscribe pattern.

    Example:
        bus = EventBus()

        async def on_failure(event: Event):
            print(f"Failure: {event.data}")

        bus.subscribe("proxy.failure", on_failure)
        await bus.publish(Event("proxy.failure", "proxy_manager", {"reason": "timeout"}))
    """

    def __init__(self, max_history: int = 1000):
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_subscribers: list[EventHandler] = []
        self._history: list[Event] = []
        self._max_history = max_history
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: Event type pattern (use "*" for all events)
            handler: Async function to handle events
        """
        if event_type == "*":
            self._wildcard_subscribers.append(handler)
        else:
            self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed to '{event_type}'")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """
        Unsubscribe from events.

        Returns:
            True if handler was found and removed
        """
        if event_type == "*":
            if handler in self._wildcard_subscribers:
                self._wildcard_subscribers.remove(handler)
                return True
        else:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                return True
        return False

    async def publish(self, event: Event) -> int:
        """
        Publish an event to all subscribers.

        Args:
            event: Event to publish

        Returns:
            Number of handlers that received the event
        """
        async with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        handlers = list(self._subscribers.get(event.event_type, []))
        handlers.extend(self._wildcard_subscribers)

        if not handlers:
            logger.debug(f"No subscribers for '{event.event_type}'")
            return 0

        tasks = []
        for handler in handlers:
            tasks.append(self._safe_call(handler, event))

        await asyncio.gather(*tasks)
        logger.debug(f"Published '{event.event_type}' to {len(handlers)} handlers")
        return len(handlers)

    async def _safe_call(self, handler: EventHandler, event: Event) -> None:
        """Call handler with error handling"""
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Handler error for '{event.event_type}': {e}")

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[Event]:
        """
        Get event history.

        Args:
            event_type: Filter by event type (None for all)
            limit: Maximum events to return
        """
        events = self._history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    def clear_history(self) -> None:
        """Clear event history"""
        self._history = []

    def get_subscriber_count(self, event_type: Optional[str] = None) -> int:
        """Get number of subscribers"""
        if event_type is None:
            total = sum(len(h) for h in self._subscribers.values())
            return total + len(self._wildcard_subscribers)
        if event_type == "*":
            return len(self._wildcard_subscribers)
        return len(self._subscribers.get(event_type, []))
