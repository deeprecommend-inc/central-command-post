"""
Knowledge Store - In-memory knowledge base
"""
import time
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from collections import OrderedDict
from loguru import logger


@dataclass
class KnowledgeEntry:
    """Single knowledge entry"""
    key: str
    value: Any
    confidence: float = 1.0
    source: str = "system"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
            "metadata": self.metadata,
        }


class KnowledgeStore:
    """
    In-memory knowledge store with LRU eviction.

    Example:
        store = KnowledgeStore()
        store.store(KnowledgeEntry(
            key="proxy.us.success_rate",
            value=0.95,
            confidence=0.9,
            source="performance_analyzer"
        ))

        entry = store.query("proxy.us.success_rate")
        print(f"Value: {entry.value}, Confidence: {entry.confidence}")
    """

    def __init__(self, max_entries: int = 1000):
        self._store: OrderedDict[str, KnowledgeEntry] = OrderedDict()
        self._max_entries = max_entries

    def store(self, entry: KnowledgeEntry) -> None:
        """
        Store a knowledge entry.

        Args:
            entry: Knowledge entry to store
        """
        if entry.key in self._store:
            existing = self._store[entry.key]
            entry.created_at = existing.created_at
            entry.access_count = existing.access_count
            entry.updated_at = time.time()
            self._store.move_to_end(entry.key)
        else:
            if len(self._store) >= self._max_entries:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]
                logger.debug(f"Evicted oldest entry: {oldest_key}")

        self._store[entry.key] = entry
        logger.debug(f"Stored knowledge: {entry.key}")

    def query(self, key: str) -> Optional[KnowledgeEntry]:
        """
        Query a knowledge entry by key.

        Args:
            key: Entry key

        Returns:
            KnowledgeEntry or None
        """
        if key not in self._store:
            return None

        entry = self._store[key]
        entry.access_count += 1
        self._store.move_to_end(key)
        return entry

    def search(self, pattern: str) -> list[KnowledgeEntry]:
        """
        Search entries by key pattern.

        Args:
            pattern: Regex pattern or glob-like pattern

        Returns:
            Matching entries
        """
        pattern = pattern.replace("*", ".*").replace("?", ".")
        try:
            regex = re.compile(pattern)
        except re.error:
            return []

        results = []
        for key, entry in self._store.items():
            if regex.search(key):
                results.append(entry)
        return results

    def get_by_source(self, source: str) -> list[KnowledgeEntry]:
        """Get all entries from a specific source"""
        return [e for e in self._store.values() if e.source == source]

    def get_high_confidence(self, threshold: float = 0.8) -> list[KnowledgeEntry]:
        """Get entries with confidence above threshold"""
        return [e for e in self._store.values() if e.confidence >= threshold]

    def update_confidence(self, key: str, confidence: float) -> bool:
        """
        Update confidence for an entry.

        Returns:
            True if entry was found and updated
        """
        if key not in self._store:
            return False

        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")

        self._store[key].confidence = confidence
        self._store[key].updated_at = time.time()
        return True

    def delete(self, key: str) -> bool:
        """
        Delete an entry.

        Returns:
            True if entry was found and deleted
        """
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all entries"""
        self._store.clear()

    def keys(self) -> list[str]:
        """Get all keys"""
        return list(self._store.keys())

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def get_stats(self) -> dict:
        """Get store statistics"""
        if not self._store:
            return {
                "entries": 0,
                "max_entries": self._max_entries,
                "avg_confidence": 0,
                "sources": [],
            }

        confidences = [e.confidence for e in self._store.values()]
        sources = list(set(e.source for e in self._store.values()))

        return {
            "entries": len(self._store),
            "max_entries": self._max_entries,
            "avg_confidence": sum(confidences) / len(confidences),
            "sources": sources,
        }
