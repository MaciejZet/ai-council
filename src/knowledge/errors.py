"""Knowledge base errors and filter validation."""


class KnowledgeBaseError(Exception):
    """Base class for knowledge retrieval failures."""


class KnowledgeConfigError(KnowledgeBaseError):
    """Missing API keys or index configuration."""


class KnowledgeEmbeddingError(KnowledgeBaseError):
    """Embedding provider failure."""


class KnowledgeVectorError(KnowledgeBaseError):
    """Pinecone query or connectivity failure."""


class KnowledgeFilterError(KnowledgeBaseError):
    """Invalid metadata filter values."""
