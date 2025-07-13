from functools import lru_cache

from fraud_detection.agents import FraudTriageOrchestrator
from fraud_detection.core.config import Settings, get_settings
from fraud_detection.services.embeddings import SentenceTransformerEmbeddingProvider
from fraud_detection.storage import ChromaVectorStore


@lru_cache
def get_embedder() -> SentenceTransformerEmbeddingProvider:
    settings = get_settings()
    return SentenceTransformerEmbeddingProvider(settings.embedding_model_name)


@lru_cache
def get_vector_store() -> ChromaVectorStore:
    settings = get_settings()
    return ChromaVectorStore(settings.vector_persist_dir, settings.vector_collection_name)


def get_orchestrator() -> FraudTriageOrchestrator:
    settings: Settings = get_settings()
    return FraudTriageOrchestrator(
        settings=settings,
        embedder=get_embedder(),
        vector_store=get_vector_store(),
    )
