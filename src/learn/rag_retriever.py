"""
RAG Retriever - Retrieval Augmented Generation for CCP

Uses vector similarity search to find relevant past experiences
and inject them as context into decision-making prompts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from loguru import logger

from .vector_store import (
    VectorStore,
    VectorDocument,
    SearchResult,
    InMemoryVectorStore,
    create_vector_store,
)
from .experience_store import Experience, ExperienceStore


@dataclass
class RetrievalResult:
    """Result of RAG retrieval"""
    experiences: list[Experience]
    context_text: str
    scores: list[float]
    query: str
    retrieval_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "experience_count": len(self.experiences),
            "context_length": len(self.context_text),
            "scores": self.scores,
            "query": self.query,
            "retrieval_time_ms": self.retrieval_time_ms,
        }


@dataclass
class RAGConfig:
    """Configuration for RAG retriever"""
    vector_backend: str = "memory"  # memory, chroma, qdrant
    collection_name: str = "ccp_experiences"
    top_k: int = 5  # Number of similar experiences to retrieve
    min_score: float = 0.3  # Minimum similarity score
    include_failed: bool = True  # Include failed experiences
    context_template: str = "default"
    persist_directory: Optional[str] = None  # For ChromaDB
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333


# Context templates for different use cases
CONTEXT_TEMPLATES = {
    "default": """## Similar Past Experiences

The following are similar tasks from the past that may be relevant:

{experiences}

Use these experiences to inform your decision. Consider:
- What actions succeeded/failed in similar situations
- What patterns emerge from past outcomes
- How to avoid past mistakes
""",

    "decision": """## Historical Context for Decision

Based on similar past situations:

{experiences}

Success patterns:
{success_patterns}

Failure patterns:
{failure_patterns}

Recommended approach based on history: {recommendation}
""",

    "minimal": """Past similar experiences:
{experiences}
""",
}


class RAGRetriever:
    """
    RAG Retriever for CCP experience-based learning.

    Indexes experiences in a vector store and retrieves similar ones
    to provide context for decision-making.

    Example:
        retriever = RAGRetriever()

        # Index experiences from store
        retriever.index_experiences(experience_store)

        # Retrieve similar experiences for a query
        result = retriever.retrieve(
            query="Navigate to https://example.com",
            filter={"task_type": "navigate"},
        )

        # Get context for LLM prompt
        context = result.context_text
    """

    def __init__(
        self,
        config: Optional[RAGConfig] = None,
        vector_store: Optional[VectorStore] = None,
    ):
        self.config = config or RAGConfig()
        self._experience_cache: dict[str, Experience] = {}

        # Initialize vector store
        if vector_store:
            self._vector_store = vector_store
        else:
            self._vector_store = self._create_vector_store()

    def _create_vector_store(self) -> VectorStore:
        """Create vector store based on config"""
        kwargs = {"collection_name": self.config.collection_name}

        if self.config.vector_backend == "chroma":
            kwargs["persist_directory"] = self.config.persist_directory
        elif self.config.vector_backend == "qdrant":
            kwargs["host"] = self.config.qdrant_host
            kwargs["port"] = self.config.qdrant_port

        return create_vector_store(self.config.vector_backend, **kwargs)

    def index_experience(self, experience: Experience) -> str:
        """
        Index a single experience.

        Args:
            experience: Experience to index

        Returns:
            Document ID
        """
        # Build content for embedding
        content = self._experience_to_text(experience)

        # Build metadata
        metadata = {
            "task_type": experience.action.action_type,
            "success": experience.outcome.status.value == "success",
            "reward": experience.reward,
            "duration_ms": experience.outcome.duration_ms,
        }

        # Add state features to metadata
        for key, value in experience.state.features.items():
            if isinstance(value, (str, int, float, bool)):
                metadata[f"state_{key}"] = value

        doc = VectorDocument(
            id=experience.id,
            content=content,
            metadata=metadata,
            timestamp=experience.state.timestamp,
        )

        self._experience_cache[experience.id] = experience
        return self._vector_store.add(doc)

    def index_experiences(self, experience_store: ExperienceStore) -> int:
        """
        Index all experiences from a store.

        Args:
            experience_store: ExperienceStore to index

        Returns:
            Number of experiences indexed
        """
        count = 0
        for experience in experience_store:
            self.index_experience(experience)
            count += 1

        logger.info(f"Indexed {count} experiences")
        return count

    def retrieve(
        self,
        query: str,
        limit: Optional[int] = None,
        filter: Optional[dict] = None,
        template: Optional[str] = None,
    ) -> RetrievalResult:
        """
        Retrieve similar experiences for a query.

        Args:
            query: Search query (task description, URL, etc.)
            limit: Max results (default: config.top_k)
            filter: Metadata filter
            template: Context template name

        Returns:
            RetrievalResult with experiences and context
        """
        start_time = datetime.now()
        limit = limit or self.config.top_k

        # Search vector store
        results = self._vector_store.search(
            query=query,
            limit=limit * 2,  # Get extra for filtering
            filter=filter,
        )

        # Filter by minimum score
        filtered_results = [
            r for r in results
            if r.score >= self.config.min_score
        ]

        # Filter out failed experiences if configured
        if not self.config.include_failed:
            filtered_results = [
                r for r in filtered_results
                if r.document.metadata.get("success", True)
            ]

        # Limit results
        filtered_results = filtered_results[:limit]

        # Get experiences from cache or rebuild
        experiences = []
        scores = []
        for result in filtered_results:
            exp = self._experience_cache.get(result.document.id)
            if exp:
                experiences.append(exp)
                scores.append(result.score)

        # Build context text
        context_text = self._build_context(
            experiences=experiences,
            scores=scores,
            template=template or self.config.context_template,
        )

        retrieval_time = (datetime.now() - start_time).total_seconds() * 1000

        return RetrievalResult(
            experiences=experiences,
            context_text=context_text,
            scores=scores,
            query=query,
            retrieval_time_ms=retrieval_time,
        )

    def retrieve_for_decision(
        self,
        task_type: str,
        target: str,
        current_state: dict,
    ) -> RetrievalResult:
        """
        Retrieve experiences for decision-making.

        Specialized retrieval that considers task type and current state.

        Args:
            task_type: Type of task (navigate, scrape, etc.)
            target: Target URL or identifier
            current_state: Current system state

        Returns:
            RetrievalResult with decision-focused context
        """
        # Build query from task info
        query = f"Task: {task_type} Target: {target}"

        # Add state context
        if current_state:
            state_summary = " ".join(
                f"{k}={v}" for k, v in current_state.items()
                if isinstance(v, (str, int, float, bool))
            )
            query += f" State: {state_summary}"

        # Filter by task type
        filter = {"task_type": task_type}

        return self.retrieve(
            query=query,
            filter=filter,
            template="decision",
        )

    def get_success_patterns(
        self,
        task_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get patterns from successful experiences.

        Args:
            task_type: Filter by task type
            limit: Max patterns to return

        Returns:
            List of success patterns
        """
        filter = {"success": True}
        if task_type:
            filter["task_type"] = task_type

        results = self._vector_store.search(
            query="successful task execution",
            limit=limit,
            filter=filter,
        )

        patterns = []
        for result in results:
            exp = self._experience_cache.get(result.document.id)
            if exp:
                patterns.append({
                    "action": exp.action.action_type,
                    "params": exp.action.params,
                    "duration_ms": exp.outcome.duration_ms,
                    "reward": exp.reward,
                })

        return patterns

    def get_failure_patterns(
        self,
        task_type: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get patterns from failed experiences.

        Args:
            task_type: Filter by task type
            limit: Max patterns to return

        Returns:
            List of failure patterns with error info
        """
        filter = {"success": False}
        if task_type:
            filter["task_type"] = task_type

        results = self._vector_store.search(
            query="failed task execution error",
            limit=limit,
            filter=filter,
        )

        patterns = []
        for result in results:
            exp = self._experience_cache.get(result.document.id)
            if exp:
                patterns.append({
                    "action": exp.action.action_type,
                    "params": exp.action.params,
                    "error": exp.outcome.error,
                    "reward": exp.reward,
                })

        return patterns

    def _experience_to_text(self, experience: Experience) -> str:
        """Convert experience to text for embedding"""
        parts = [
            f"Action: {experience.action.action_type}",
            f"Params: {json.dumps(experience.action.params)}",
            f"Outcome: {experience.outcome.status.value}",
            f"Reward: {experience.reward}",
        ]

        if experience.outcome.error:
            parts.append(f"Error: {experience.outcome.error}")

        if experience.outcome.result:
            result_str = json.dumps(experience.outcome.result)[:200]
            parts.append(f"Result: {result_str}")

        # Add state features
        for key, value in experience.state.features.items():
            parts.append(f"{key}: {value}")

        return " | ".join(parts)

    def _build_context(
        self,
        experiences: list[Experience],
        scores: list[float],
        template: str,
    ) -> str:
        """Build context text from experiences"""
        if not experiences:
            return "No similar past experiences found."

        template_str = CONTEXT_TEMPLATES.get(template, CONTEXT_TEMPLATES["default"])

        # Format experiences
        exp_texts = []
        for i, (exp, score) in enumerate(zip(experiences, scores), 1):
            status = "SUCCESS" if exp.outcome.status.value == "success" else "FAILED"
            text = (
                f"{i}. [{status}] {exp.action.action_type} "
                f"(similarity: {score:.2f}, reward: {exp.reward:.2f})"
            )
            if exp.outcome.error:
                text += f"\n   Error: {exp.outcome.error}"
            exp_texts.append(text)

        experiences_str = "\n".join(exp_texts)

        # Build success/failure patterns for decision template
        success_patterns = "\n".join(
            f"- {exp.action.action_type}: reward={exp.reward:.2f}"
            for exp in experiences
            if exp.outcome.status.value == "success"
        ) or "None found"

        failure_patterns = "\n".join(
            f"- {exp.action.action_type}: {exp.outcome.error or 'Unknown error'}"
            for exp in experiences
            if exp.outcome.status.value != "success"
        ) or "None found"

        # Recommendation based on history
        successful = [e for e in experiences if e.outcome.status.value == "success"]
        if successful:
            best = max(successful, key=lambda e: e.reward)
            recommendation = f"Consider action '{best.action.action_type}' which achieved reward {best.reward:.2f}"
        else:
            recommendation = "No successful similar experiences. Proceed with caution."

        return template_str.format(
            experiences=experiences_str,
            success_patterns=success_patterns,
            failure_patterns=failure_patterns,
            recommendation=recommendation,
        )

    def clear(self) -> int:
        """Clear all indexed experiences"""
        count = self._vector_store.clear()
        self._experience_cache.clear()
        return count

    def get_stats(self) -> dict:
        """Get retriever statistics"""
        return {
            "indexed_count": self._vector_store.count(),
            "cached_count": len(self._experience_cache),
            "backend": self.config.vector_backend,
            "collection": self.config.collection_name,
        }


def inject_rag_context(
    prompt: str,
    retriever: RAGRetriever,
    query: str,
    **kwargs,
) -> str:
    """
    Inject RAG context into a prompt.

    Args:
        prompt: Original prompt
        retriever: RAGRetriever instance
        query: Search query
        **kwargs: Additional retrieve() arguments

    Returns:
        Prompt with RAG context injected
    """
    result = retriever.retrieve(query, **kwargs)

    if not result.experiences:
        return prompt

    # Insert context before the main prompt
    return f"{result.context_text}\n\n{prompt}"
