"""Tests for KnowledgeStore"""
import pytest
from src.learn import KnowledgeStore, KnowledgeEntry


class TestKnowledgeEntry:
    """Tests for KnowledgeEntry dataclass"""

    def test_entry_creation(self):
        entry = KnowledgeEntry(key="test.key", value={"data": 1})
        assert entry.key == "test.key"
        assert entry.value == {"data": 1}
        assert entry.confidence == 1.0
        assert entry.source == "system"
        assert entry.access_count == 0

    def test_entry_invalid_confidence(self):
        with pytest.raises(ValueError):
            KnowledgeEntry(key="test", value=1, confidence=1.5)

    def test_entry_to_dict(self):
        entry = KnowledgeEntry(key="test", value="val", confidence=0.8)
        d = entry.to_dict()
        assert d["key"] == "test"
        assert d["value"] == "val"
        assert d["confidence"] == 0.8


class TestKnowledgeStore:
    """Tests for KnowledgeStore"""

    def test_initialization(self):
        store = KnowledgeStore()
        assert len(store) == 0

    def test_store_and_query(self):
        store = KnowledgeStore()
        entry = KnowledgeEntry(key="test", value=42)
        store.store(entry)

        result = store.query("test")
        assert result is not None
        assert result.value == 42
        assert result.access_count == 1

    def test_query_not_found(self):
        store = KnowledgeStore()
        result = store.query("nonexistent")
        assert result is None

    def test_update_existing(self):
        store = KnowledgeStore()
        store.store(KnowledgeEntry(key="test", value=1))
        store.store(KnowledgeEntry(key="test", value=2))

        result = store.query("test")
        assert result.value == 2
        assert len(store) == 1

    def test_search_pattern(self):
        store = KnowledgeStore()
        store.store(KnowledgeEntry(key="proxy.us.health", value=0.9))
        store.store(KnowledgeEntry(key="proxy.jp.health", value=0.8))
        store.store(KnowledgeEntry(key="other.data", value=1))

        results = store.search("proxy.*")
        assert len(results) == 2

    def test_search_wildcard(self):
        store = KnowledgeStore()
        store.store(KnowledgeEntry(key="a.b.c", value=1))
        store.store(KnowledgeEntry(key="a.x.c", value=2))
        store.store(KnowledgeEntry(key="x.b.c", value=3))

        results = store.search("a.*.c")
        assert len(results) == 2

    def test_get_by_source(self):
        store = KnowledgeStore()
        store.store(KnowledgeEntry(key="k1", value=1, source="analyzer"))
        store.store(KnowledgeEntry(key="k2", value=2, source="detector"))
        store.store(KnowledgeEntry(key="k3", value=3, source="analyzer"))

        results = store.get_by_source("analyzer")
        assert len(results) == 2

    def test_get_high_confidence(self):
        store = KnowledgeStore()
        store.store(KnowledgeEntry(key="k1", value=1, confidence=0.9))
        store.store(KnowledgeEntry(key="k2", value=2, confidence=0.5))
        store.store(KnowledgeEntry(key="k3", value=3, confidence=0.95))

        results = store.get_high_confidence(0.8)
        assert len(results) == 2

    def test_update_confidence(self):
        store = KnowledgeStore()
        store.store(KnowledgeEntry(key="test", value=1, confidence=0.5))

        result = store.update_confidence("test", 0.9)
        assert result is True

        entry = store.query("test")
        assert entry.confidence == 0.9

    def test_update_confidence_not_found(self):
        store = KnowledgeStore()
        result = store.update_confidence("nonexistent", 0.9)
        assert result is False

    def test_update_confidence_invalid(self):
        store = KnowledgeStore()
        store.store(KnowledgeEntry(key="test", value=1))

        with pytest.raises(ValueError):
            store.update_confidence("test", 1.5)

    def test_delete(self):
        store = KnowledgeStore()
        store.store(KnowledgeEntry(key="test", value=1))

        result = store.delete("test")
        assert result is True
        assert len(store) == 0

    def test_delete_not_found(self):
        store = KnowledgeStore()
        result = store.delete("nonexistent")
        assert result is False

    def test_clear(self):
        store = KnowledgeStore()
        store.store(KnowledgeEntry(key="k1", value=1))
        store.store(KnowledgeEntry(key="k2", value=2))
        store.clear()
        assert len(store) == 0

    def test_keys(self):
        store = KnowledgeStore()
        store.store(KnowledgeEntry(key="a", value=1))
        store.store(KnowledgeEntry(key="b", value=2))

        keys = store.keys()
        assert "a" in keys
        assert "b" in keys

    def test_contains(self):
        store = KnowledgeStore()
        store.store(KnowledgeEntry(key="exists", value=1))

        assert "exists" in store
        assert "not_exists" not in store

    def test_lru_eviction(self):
        store = KnowledgeStore(max_entries=3)
        store.store(KnowledgeEntry(key="a", value=1))
        store.store(KnowledgeEntry(key="b", value=2))
        store.store(KnowledgeEntry(key="c", value=3))
        store.store(KnowledgeEntry(key="d", value=4))

        assert len(store) == 3
        assert "a" not in store
        assert "d" in store

    def test_get_stats(self):
        store = KnowledgeStore()
        store.store(KnowledgeEntry(key="k1", value=1, confidence=0.8, source="s1"))
        store.store(KnowledgeEntry(key="k2", value=2, confidence=0.6, source="s2"))

        stats = store.get_stats()
        assert stats["entries"] == 2
        assert stats["avg_confidence"] == 0.7
        assert "s1" in stats["sources"]
        assert "s2" in stats["sources"]

    def test_get_stats_empty(self):
        store = KnowledgeStore()
        stats = store.get_stats()
        assert stats["entries"] == 0
        assert stats["avg_confidence"] == 0
