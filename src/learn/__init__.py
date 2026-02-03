"""
Learn Layer - Learning and Knowledge Management

v3 Features:
- Vector Store for semantic search
- RAG Retriever for experience-based learning
- VectorKnowledgeStore with semantic search
"""
from .knowledge_store import KnowledgeStore, KnowledgeEntry, VectorKnowledgeStore
from .pattern_detector import PatternDetector, Pattern, Anomaly
from .performance_analyzer import PerformanceAnalyzer, PerformanceReport
from .experience_store import (
    ExperienceStore,
    Experience,
    StateSnapshot,
    Action,
    Outcome,
    OutcomeStatus,
    RewardModel,
    DefaultRewardModel,
)
from .replay_engine import (
    ReplayEngine,
    ReplayConfig,
    SimulatedEnvironment,
    EpisodeResult,
    StepTrace,
)
# v3 Vector Store
from .vector_store import (
    VectorStore,
    VectorDocument,
    SearchResult,
    InMemoryVectorStore,
    ChromaVectorStore,
    QdrantVectorStore,
    create_vector_store,
    SimpleHashEmbedding,
    OpenAIEmbedding,
)
# v3 RAG Retriever
from .rag_retriever import (
    RAGRetriever,
    RAGConfig,
    RetrievalResult,
    inject_rag_context,
)

__all__ = [
    # v1 Knowledge Store
    "KnowledgeStore",
    "KnowledgeEntry",
    "PatternDetector",
    "Pattern",
    "Anomaly",
    "PerformanceAnalyzer",
    "PerformanceReport",
    # v2 Experience Store
    "ExperienceStore",
    "Experience",
    "StateSnapshot",
    "Action",
    "Outcome",
    "OutcomeStatus",
    "RewardModel",
    "DefaultRewardModel",
    # v2 Replay Engine
    "ReplayEngine",
    "ReplayConfig",
    "SimulatedEnvironment",
    "EpisodeResult",
    "StepTrace",
    # v3 Vector Store
    "VectorStore",
    "VectorDocument",
    "SearchResult",
    "InMemoryVectorStore",
    "ChromaVectorStore",
    "QdrantVectorStore",
    "create_vector_store",
    "SimpleHashEmbedding",
    "OpenAIEmbedding",
    # v3 RAG Retriever
    "RAGRetriever",
    "RAGConfig",
    "RetrievalResult",
    "inject_rag_context",
    # v3 Vector Knowledge Store
    "VectorKnowledgeStore",
]
