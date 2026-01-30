"""Tests for EventBus"""
import pytest
from src.sense import Event, EventBus


class TestEvent:
    """Tests for Event dataclass"""

    def test_event_creation(self):
        event = Event(
            event_type="test.event",
            source="test",
            data={"key": "value"},
        )
        assert event.event_type == "test.event"
        assert event.source == "test"
        assert event.data == {"key": "value"}
        assert event.timestamp > 0

    def test_event_requires_type(self):
        with pytest.raises(ValueError):
            Event(event_type="", source="test")

    def test_event_requires_source(self):
        with pytest.raises(ValueError):
            Event(event_type="test", source="")

    def test_event_default_data(self):
        event = Event(event_type="test", source="test")
        assert event.data == {}


class TestEventBus:
    """Tests for EventBus"""

    def test_initialization(self):
        bus = EventBus()
        assert bus.get_subscriber_count() == 0

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []

        async def handler(event: Event):
            received.append(event)

        bus.subscribe("test.event", handler)
        await bus.publish(Event("test.event", "test", {"x": 1}))

        assert len(received) == 1
        assert received[0].data == {"x": 1}

    @pytest.mark.asyncio
    async def test_wildcard_subscriber(self):
        bus = EventBus()
        received = []

        async def handler(event: Event):
            received.append(event)

        bus.subscribe("*", handler)
        await bus.publish(Event("event1", "test"))
        await bus.publish(Event("event2", "test"))

        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_no_subscribers(self):
        bus = EventBus()
        count = await bus.publish(Event("unsubscribed", "test"))
        assert count == 0

    def test_unsubscribe(self):
        bus = EventBus()

        async def handler(event: Event):
            pass

        bus.subscribe("test", handler)
        assert bus.get_subscriber_count("test") == 1

        result = bus.unsubscribe("test", handler)
        assert result is True
        assert bus.get_subscriber_count("test") == 0

    def test_unsubscribe_not_found(self):
        bus = EventBus()

        async def handler(event: Event):
            pass

        result = bus.unsubscribe("test", handler)
        assert result is False

    @pytest.mark.asyncio
    async def test_event_history(self):
        bus = EventBus()
        await bus.publish(Event("e1", "test"))
        await bus.publish(Event("e2", "test"))
        await bus.publish(Event("e3", "test"))

        history = bus.get_history()
        assert len(history) == 3

        filtered = bus.get_history(event_type="e2")
        assert len(filtered) == 1
        assert filtered[0].event_type == "e2"

    @pytest.mark.asyncio
    async def test_history_limit(self):
        bus = EventBus(max_history=5)
        for i in range(10):
            await bus.publish(Event(f"e{i}", "test"))

        history = bus.get_history()
        assert len(history) == 5

    def test_clear_history(self):
        bus = EventBus()
        bus._history.append(Event("test", "test"))
        bus.clear_history()
        assert len(bus.get_history()) == 0

    @pytest.mark.asyncio
    async def test_handler_error_does_not_crash(self):
        bus = EventBus()

        async def bad_handler(event: Event):
            raise ValueError("Handler error")

        bus.subscribe("test", bad_handler)
        count = await bus.publish(Event("test", "test"))
        assert count == 1
