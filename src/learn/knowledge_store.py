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


class VectorKnowledgeStore(KnowledgeStore):
    """
    Knowledge store with vector similarity search.

    Extends KnowledgeStore with semantic search capabilities using
    vector embeddings. Falls back to key-based search if vector
    store is not available.

    Example:
        store = VectorKnowledgeStore(
            vector_backend="chroma",
            persist_directory="./knowledge_db",
        )

        # Store with automatic indexing
        store.store(KnowledgeEntry(
            key="proxy.residential.best_country",
            value="us",
            confidence=0.9,
            metadata={"description": "US residential proxies have highest success rate"}
        ))

        # Semantic search
        results = store.semantic_search("best proxy for web scraping")
        for entry, score in results:
            print(f"{entry.key}: {entry.value} (similarity: {score:.2f})")
    """

    def __init__(
        self,
        max_entries: int = 1000,
        vector_backend: str = "memory",
        collection_name: str = "ccp_knowledge",
        persist_directory: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(max_entries)

        self._vector_backend = vector_backend
        self._collection_name = collection_name
        self._persist_directory = persist_directory
        self._vector_store = None
        self._kwargs = kwargs

    def _get_vector_store(self):
        """Lazy initialization of vector store"""
        if self._vector_store is not None:
            return self._vector_store

        try:
            from .vector_store import create_vector_store

            kwargs = {"collection_name": self._collection_name}
            kwargs.update(self._kwargs)

            if self._vector_backend == "chroma" and self._persist_directory:
                kwargs["persist_directory"] = self._persist_directory

            self._vector_store = create_vector_store(self._vector_backend, **kwargs)
            logger.info(f"Vector store initialized: {self._vector_backend}")

        except Exception as e:
            logger.warning(f"Failed to initialize vector store: {e}")
            self._vector_store = None

        return self._vector_store

    def store(self, entry: KnowledgeEntry) -> None:
        """Store entry with vector indexing"""
        super().store(entry)

        # Index in vector store
        vector_store = self._get_vector_store()
        if vector_store:
            try:
                from .vector_store import VectorDocument

                # Build content for embedding
                content = self._entry_to_text(entry)

                doc = VectorDocument(
                    id=entry.key,
                    content=content,
                    metadata={
                        "confidence": entry.confidence,
                        "source": entry.source,
                        **entry.metadata,
                    },
                )

                vector_store.add(doc)

            except Exception as e:
                logger.warning(f"Failed to index entry in vector store: {e}")

    def semantic_search(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.3,
        filter: Optional[dict] = None,
    ) -> list[tuple[KnowledgeEntry, float]]:
        """
        Search entries by semantic similarity.

        Args:
            query: Search query
            limit: Max results
            min_score: Minimum similarity score
            filter: Metadata filter

        Returns:
            List of (KnowledgeEntry, score) tuples
        """
        vector_store = self._get_vector_store()
        if not vector_store:
            # Fallback to pattern search
            logger.warning("Vector store not available, falling back to pattern search")
            entries = self.search(f"*{query.split()[0]}*" if query else "*")
            return [(e, 0.5) for e in entries[:limit]]

        try:
            results = vector_store.search(query, limit=limit, filter=filter)

            matched = []
            for result in results:
                if result.score < min_score:
                    continue

                entry = self.query(result.document.id)
                if entry:
                    matched.append((entry, result.score))

            return matched

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def find_similar(
        self,
        key: str,
        limit: int = 5,
    ) -> list[tuple[KnowledgeEntry, float]]:
        """
        Find entries similar to a given entry.

        Args:
            key: Key of entry to find similar entries for
            limit: Max results

        Returns:
            List of (KnowledgeEntry, score) tuples
        """
        entry = self.query(key)
        if not entry:
            return []

        content = self._entry_to_text(entry)
        results = self.semantic_search(content, limit=limit + 1)

        # Exclude the original entry
        return [(e, s) for e, s in results if e.key != key][:limit]

    def get_related_knowledge(
        self,
        context: str,
        task_type: Optional[str] = None,
        limit: int = 5,
    ) -> str:
        """
        Get related knowledge as context string for LLM.

        Args:
            context: Task context or query
            task_type: Optional task type filter
            limit: Max entries to include

        Returns:
            Formatted context string
        """
        filter = {}
        if task_type:
            filter["task_type"] = task_type

        results = self.semantic_search(context, limit=limit, filter=filter if filter else None)

        if not results:
            return "No relevant knowledge found."

        lines = ["## Relevant Knowledge"]
        for entry, score in results:
            lines.append(
                f"- {entry.key}: {entry.value} "
                f"(confidence: {entry.confidence:.2f}, relevance: {score:.2f})"
            )

        return "\n".join(lines)

    def _entry_to_text(self, entry: KnowledgeEntry) -> str:
        """Convert entry to text for embedding"""
        parts = [
            f"Key: {entry.key}",
            f"Value: {entry.value}",
            f"Source: {entry.source}",
        ]

        if entry.metadata:
            for k, v in entry.metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    parts.append(f"{k}: {v}")

        return " | ".join(parts)

    def rebuild_index(self) -> int:
        """
        Rebuild vector index from all stored entries.

        Returns:
            Number of entries indexed
        """
        vector_store = self._get_vector_store()
        if not vector_store:
            return 0

        # Clear existing index
        try:
            vector_store.clear()
        except Exception:
            pass

        # Re-index all entries
        count = 0
        for key in self.keys():
            entry = self._store.get(key)
            if entry:
                try:
                    from .vector_store import VectorDocument

                    content = self._entry_to_text(entry)
                    doc = VectorDocument(
                        id=entry.key,
                        content=content,
                        metadata={
                            "confidence": entry.confidence,
                            "source": entry.source,
                            **entry.metadata,
                        },
                    )
                    vector_store.add(doc)
                    count += 1
                except Exception:
                    pass

        logger.info(f"Rebuilt vector index: {count} entries")
        return count

    def get_stats(self) -> dict:
        """Get store statistics including vector store"""
        stats = super().get_stats()

        vector_store = self._get_vector_store()
        if vector_store:
            stats["vector_backend"] = self._vector_backend
            stats["vector_indexed"] = vector_store.count()
        else:
            stats["vector_backend"] = None
            stats["vector_indexed"] = 0

        return stats
