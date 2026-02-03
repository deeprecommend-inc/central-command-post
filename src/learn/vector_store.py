"""
Vector Store - Vector database abstraction layer for semantic search

Supports:
- ChromaDB (local/embedded)
- Qdrant (local/cloud)
- In-memory fallback
"""
from __future__ import annotations

import json
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol
from pathlib import Path
from loguru import logger


@dataclass
class VectorDocument:
    """A document with vector embedding"""
    id: str
    content: str
    embedding: Optional[list[float]] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VectorDocument":
        return cls(
            id=data["id"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
        )


@dataclass
class SearchResult:
    """Result from vector similarity search"""
    document: VectorDocument
    score: float  # Similarity score (higher = more similar)
    distance: float = 0.0  # Distance (lower = more similar)

    def to_dict(self) -> dict:
        return {
            "document": self.document.to_dict(),
            "score": self.score,
            "distance": self.distance,
        }


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers"""
    def embed(self, text: str) -> list[float]:
        """Generate embedding for text"""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        ...

    @property
    def dimension(self) -> int:
        """Embedding dimension"""
        ...


class SimpleHashEmbedding:
    """
    Simple hash-based embedding for testing/fallback.
    NOT suitable for production semantic search.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    def embed(self, text: str) -> list[float]:
        """Generate pseudo-embedding from text hash"""
        # Create deterministic hash
        h = hashlib.sha256(text.encode()).hexdigest()

        # Convert to float vector
        embedding = []
        for i in range(0, min(len(h), self._dimension * 2), 2):
            val = int(h[i:i+2], 16) / 255.0 - 0.5
            embedding.append(val)

        # Pad if needed
        while len(embedding) < self._dimension:
            embedding.append(0.0)

        return embedding[:self._dimension]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    @property
    def dimension(self) -> int:
        return self._dimension


class OpenAIEmbedding:
    """OpenAI embedding provider"""

    def __init__(self, model: str = "text-embedding-3-small"):
        self.model = model
        self._client = None
        self._dimension = 1536 if "large" in model else 1536

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI()
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client

    def embed(self, text: str) -> list[float]:
        client = self._get_client()
        response = client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        response = client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [d.embedding for d in response.data]

    @property
    def dimension(self) -> int:
        return self._dimension


class VectorStore(ABC):
    """Abstract base class for vector stores"""

    @abstractmethod
    def add(self, document: VectorDocument) -> str:
        """Add a document to the store"""
        pass

    @abstractmethod
    def add_batch(self, documents: list[VectorDocument]) -> list[str]:
        """Add multiple documents"""
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int = 10,
        filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search for similar documents"""
        pass

    @abstractmethod
    def get(self, doc_id: str) -> Optional[VectorDocument]:
        """Get document by ID"""
        pass

    @abstractmethod
    def delete(self, doc_id: str) -> bool:
        """Delete document by ID"""
        pass

    @abstractmethod
    def count(self) -> int:
        """Get total document count"""
        pass

    def clear(self) -> int:
        """Clear all documents (override for efficiency)"""
        raise NotImplementedError


class InMemoryVectorStore(VectorStore):
    """
    In-memory vector store for development/testing.

    Uses simple cosine similarity for search.
    """

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        max_size: int = 10000,
    ):
        self.embedding = embedding_provider or SimpleHashEmbedding()
        self.max_size = max_size
        self._documents: dict[str, VectorDocument] = {}
        self._embeddings: dict[str, list[float]] = {}

    def add(self, document: VectorDocument) -> str:
        # Generate embedding if not provided
        if document.embedding is None:
            document.embedding = self.embedding.embed(document.content)

        self._documents[document.id] = document
        self._embeddings[document.id] = document.embedding

        # Enforce max size
        if len(self._documents) > self.max_size:
            oldest_id = next(iter(self._documents))
            del self._documents[oldest_id]
            del self._embeddings[oldest_id]

        return document.id

    def add_batch(self, documents: list[VectorDocument]) -> list[str]:
        # Batch embed documents without embeddings
        texts_to_embed = []
        indices_to_embed = []

        for i, doc in enumerate(documents):
            if doc.embedding is None:
                texts_to_embed.append(doc.content)
                indices_to_embed.append(i)

        if texts_to_embed:
            embeddings = self.embedding.embed_batch(texts_to_embed)
            for idx, emb in zip(indices_to_embed, embeddings):
                documents[idx].embedding = emb

        ids = []
        for doc in documents:
            ids.append(self.add(doc))

        return ids

    def search(
        self,
        query: str,
        limit: int = 10,
        filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        if not self._documents:
            return []

        # Get query embedding
        query_embedding = self.embedding.embed(query)

        # Calculate similarities
        results = []
        for doc_id, doc in self._documents.items():
            # Apply filter
            if filter:
                match = all(
                    doc.metadata.get(k) == v
                    for k, v in filter.items()
                )
                if not match:
                    continue

            doc_embedding = self._embeddings[doc_id]
            score = self._cosine_similarity(query_embedding, doc_embedding)

            results.append(SearchResult(
                document=doc,
                score=score,
                distance=1.0 - score,
            ))

        # Sort by score (descending)
        results.sort(key=lambda r: r.score, reverse=True)

        return results[:limit]

    def get(self, doc_id: str) -> Optional[VectorDocument]:
        return self._documents.get(doc_id)

    def delete(self, doc_id: str) -> bool:
        if doc_id in self._documents:
            del self._documents[doc_id]
            del self._embeddings[doc_id]
            return True
        return False

    def count(self) -> int:
        return len(self._documents)

    def clear(self) -> int:
        count = len(self._documents)
        self._documents.clear()
        self._embeddings.clear()
        return count

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


class ChromaVectorStore(VectorStore):
    """
    ChromaDB-backed vector store.

    Requires: pip install chromadb
    """

    def __init__(
        self,
        collection_name: str = "ccp_knowledge",
        persist_directory: Optional[str] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self._embedding = embedding_provider or SimpleHashEmbedding()
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is not None:
            return self._collection

        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            raise ImportError("chromadb package required: pip install chromadb")

        if self.persist_directory:
            self._client = chromadb.PersistentClient(path=self.persist_directory)
        else:
            self._client = chromadb.Client()

        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(f"ChromaDB collection '{self.collection_name}' initialized")
        return self._collection

    def add(self, document: VectorDocument) -> str:
        collection = self._get_collection()

        if document.embedding is None:
            document.embedding = self._embedding.embed(document.content)

        collection.add(
            ids=[document.id],
            embeddings=[document.embedding],
            documents=[document.content],
            metadatas=[{**document.metadata, "timestamp": document.timestamp.isoformat()}],
        )

        return document.id

    def add_batch(self, documents: list[VectorDocument]) -> list[str]:
        collection = self._get_collection()

        # Generate embeddings
        for doc in documents:
            if doc.embedding is None:
                doc.embedding = self._embedding.embed(doc.content)

        collection.add(
            ids=[d.id for d in documents],
            embeddings=[d.embedding for d in documents],
            documents=[d.content for d in documents],
            metadatas=[{**d.metadata, "timestamp": d.timestamp.isoformat()} for d in documents],
        )

        return [d.id for d in documents]

    def search(
        self,
        query: str,
        limit: int = 10,
        filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        collection = self._get_collection()

        query_embedding = self._embedding.embed(query)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=filter if filter else None,
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                timestamp_str = metadata.pop("timestamp", None)

                doc = VectorDocument(
                    id=doc_id,
                    content=results["documents"][0][i] if results["documents"] else "",
                    metadata=metadata,
                    timestamp=datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(),
                )

                distance = results["distances"][0][i] if results["distances"] else 0.0
                score = 1.0 - distance  # Convert distance to similarity

                search_results.append(SearchResult(
                    document=doc,
                    score=score,
                    distance=distance,
                ))

        return search_results

    def get(self, doc_id: str) -> Optional[VectorDocument]:
        collection = self._get_collection()

        result = collection.get(ids=[doc_id])

        if not result["ids"]:
            return None

        metadata = result["metadatas"][0] if result["metadatas"] else {}
        timestamp_str = metadata.pop("timestamp", None)

        return VectorDocument(
            id=doc_id,
            content=result["documents"][0] if result["documents"] else "",
            metadata=metadata,
            timestamp=datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(),
        )

    def delete(self, doc_id: str) -> bool:
        collection = self._get_collection()
        try:
            collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def count(self) -> int:
        collection = self._get_collection()
        return collection.count()

    def clear(self) -> int:
        collection = self._get_collection()
        count = collection.count()
        self._client.delete_collection(self.collection_name)
        self._collection = None
        return count


class QdrantVectorStore(VectorStore):
    """
    Qdrant-backed vector store.

    Requires: pip install qdrant-client
    """

    def __init__(
        self,
        collection_name: str = "ccp_knowledge",
        host: str = "localhost",
        port: int = 6333,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self.collection_name = collection_name
        self.host = host
        self.port = port
        self._embedding = embedding_provider or SimpleHashEmbedding()
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
        except ImportError:
            raise ImportError("qdrant-client package required: pip install qdrant-client")

        self._client = QdrantClient(host=self.host, port=self.port)

        # Create collection if not exists
        collections = self._client.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self._embedding.dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Qdrant collection '{self.collection_name}' created")

        return self._client

    def add(self, document: VectorDocument) -> str:
        from qdrant_client.models import PointStruct

        client = self._get_client()

        if document.embedding is None:
            document.embedding = self._embedding.embed(document.content)

        point = PointStruct(
            id=hash(document.id) % (2**63),  # Qdrant needs int IDs
            vector=document.embedding,
            payload={
                "doc_id": document.id,
                "content": document.content,
                "metadata": document.metadata,
                "timestamp": document.timestamp.isoformat(),
            },
        )

        client.upsert(
            collection_name=self.collection_name,
            points=[point],
        )

        return document.id

    def add_batch(self, documents: list[VectorDocument]) -> list[str]:
        from qdrant_client.models import PointStruct

        client = self._get_client()

        for doc in documents:
            if doc.embedding is None:
                doc.embedding = self._embedding.embed(doc.content)

        points = [
            PointStruct(
                id=hash(doc.id) % (2**63),
                vector=doc.embedding,
                payload={
                    "doc_id": doc.id,
                    "content": doc.content,
                    "metadata": doc.metadata,
                    "timestamp": doc.timestamp.isoformat(),
                },
            )
            for doc in documents
        ]

        client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

        return [d.id for d in documents]

    def search(
        self,
        query: str,
        limit: int = 10,
        filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = self._get_client()
        query_embedding = self._embedding.embed(query)

        # Build filter
        qdrant_filter = None
        if filter:
            conditions = [
                FieldCondition(key=f"metadata.{k}", match=MatchValue(value=v))
                for k, v in filter.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results = client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            query_filter=qdrant_filter,
        )

        search_results = []
        for hit in results:
            payload = hit.payload or {}
            doc = VectorDocument(
                id=payload.get("doc_id", str(hit.id)),
                content=payload.get("content", ""),
                metadata=payload.get("metadata", {}),
                timestamp=datetime.fromisoformat(payload["timestamp"]) if "timestamp" in payload else datetime.now(),
            )

            search_results.append(SearchResult(
                document=doc,
                score=hit.score,
                distance=1.0 - hit.score,
            ))

        return search_results

    def get(self, doc_id: str) -> Optional[VectorDocument]:
        client = self._get_client()

        result = client.retrieve(
            collection_name=self.collection_name,
            ids=[hash(doc_id) % (2**63)],
        )

        if not result:
            return None

        payload = result[0].payload or {}
        return VectorDocument(
            id=payload.get("doc_id", doc_id),
            content=payload.get("content", ""),
            metadata=payload.get("metadata", {}),
            timestamp=datetime.fromisoformat(payload["timestamp"]) if "timestamp" in payload else datetime.now(),
        )

    def delete(self, doc_id: str) -> bool:
        from qdrant_client.models import PointIdsList

        client = self._get_client()
        try:
            client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=[hash(doc_id) % (2**63)]),
            )
            return True
        except Exception:
            return False

    def count(self) -> int:
        client = self._get_client()
        info = client.get_collection(self.collection_name)
        return info.points_count

    def clear(self) -> int:
        client = self._get_client()
        count = self.count()
        client.delete_collection(self.collection_name)
        self._client = None
        return count


def create_vector_store(
    backend: str = "memory",
    **kwargs,
) -> VectorStore:
    """
    Factory function to create vector stores.

    Args:
        backend: "memory", "chroma", or "qdrant"
        **kwargs: Backend-specific options

    Returns:
        VectorStore instance
    """
    if backend == "memory":
        return InMemoryVectorStore(**kwargs)
    elif backend == "chroma":
        return ChromaVectorStore(**kwargs)
    elif backend == "qdrant":
        return QdrantVectorStore(**kwargs)
    else:
        raise ValueError(f"Unknown backend: {backend}. Use 'memory', 'chroma', or 'qdrant'")
