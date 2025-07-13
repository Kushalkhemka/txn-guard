import json
from collections.abc import Iterable
from math import sqrt
from pathlib import Path
from typing import Any, Protocol

from fraud_detection.domain import StoredTransaction, TransactionEvidence


class VectorStore(Protocol):
    def upsert(self, transaction: StoredTransaction, embedding: list[float]) -> None:
        """Persist one embedded transaction."""

    def query(
        self,
        embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[TransactionEvidence]:
        """Return nearest transaction evidence."""

    def list_by_user(self, user_id: str, limit: int = 1000) -> list[StoredTransaction]:
        """Return stored transactions for a user."""


def serialize_metadata(transaction: StoredTransaction) -> dict[str, Any]:
    """Serialize metadata into Chroma-compatible primitive values."""

    data = transaction.model_dump(mode="json")
    custom_metadata = data.pop("metadata", {}) or {}
    data.pop("narrative", None)
    data["timestamp"] = transaction.timestamp.isoformat()
    data["metadata_json"] = json.dumps(custom_metadata, sort_keys=True)
    return {key: value for key, value in data.items() if value is not None}


def evidence_metadata(transaction: StoredTransaction) -> dict[str, Any]:
    data = transaction.model_dump(mode="json")
    data.pop("narrative", None)
    return data


def deserialize_metadata(metadata: dict[str, Any], narrative: str) -> StoredTransaction:
    data = dict(metadata)
    metadata_json = data.pop("metadata_json", "{}")
    try:
        data["metadata"] = json.loads(metadata_json) if metadata_json else {}
    except json.JSONDecodeError:
        data["metadata"] = {}
    return StoredTransaction(**data, narrative=narrative)


def deserialize_evidence_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    data = dict(metadata or {})
    metadata_json = data.pop("metadata_json", "{}")
    try:
        data["metadata"] = json.loads(metadata_json) if metadata_json else {}
    except json.JSONDecodeError:
        data["metadata"] = {}
    return data


class ChromaVectorStore:
    def __init__(self, persist_dir: Path, collection_name: str):
        import chromadb

        persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(name=collection_name)

    def upsert(self, transaction: StoredTransaction, embedding: list[float]) -> None:
        self._collection.upsert(
            ids=[transaction.transaction_id],
            documents=[transaction.narrative],
            metadatas=[serialize_metadata(transaction)],
            embeddings=[embedding],
        )

    def query(
        self,
        embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[TransactionEvidence]:
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=filters,
            include=["documents", "metadatas", "distances"],
        )
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        evidence: list[TransactionEvidence] = []
        for index, transaction_id in enumerate(ids):
            distance = distances[index] if index < len(distances) else None
            evidence.append(
                TransactionEvidence(
                    transaction_id=transaction_id,
                    document=documents[index],
                    metadata=deserialize_evidence_metadata(metadatas[index] or {}),
                    distance=distance,
                    similarity=_distance_to_similarity(distance),
                )
            )
        return evidence

    def list_by_user(self, user_id: str, limit: int = 1000) -> list[StoredTransaction]:
        results = self._collection.get(
            where={"user_id": user_id},
            limit=limit,
            include=["documents", "metadatas"],
        )
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        transactions: list[StoredTransaction] = []
        for index, metadata in enumerate(metadatas):
            if metadata:
                transactions.append(deserialize_metadata(metadata, documents[index]))
        return transactions


class InMemoryVectorStore:
    """Explicit test/development store; production wiring uses ChromaVectorStore."""

    def __init__(self):
        self._items: dict[str, tuple[StoredTransaction, list[float]]] = {}

    def upsert(self, transaction: StoredTransaction, embedding: list[float]) -> None:
        self._items[transaction.transaction_id] = (transaction, embedding)

    def query(
        self,
        embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[TransactionEvidence]:
        scored: list[tuple[float, StoredTransaction]] = []
        for transaction, stored_embedding in self._items.values():
            if _matches_filters(transaction, filters):
                scored.append((_cosine_similarity(embedding, stored_embedding), transaction))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            TransactionEvidence(
                transaction_id=transaction.transaction_id,
                document=transaction.narrative,
                metadata=evidence_metadata(transaction),
                distance=1 - similarity,
                similarity=similarity,
            )
            for similarity, transaction in scored[:top_k]
        ]

    def list_by_user(self, user_id: str, limit: int = 1000) -> list[StoredTransaction]:
        matches = [
            transaction
            for transaction, _embedding in self._items.values()
            if transaction.user_id == user_id
        ]
        matches.sort(key=lambda transaction: transaction.timestamp, reverse=True)
        return matches[:limit]


def _matches_filters(transaction: StoredTransaction, filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    data = transaction.model_dump(mode="json")
    return all(data.get(key) == value for key, value in filters.items())


def _cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = list(left)
    right_values = list(right)
    dot = sum(a * b for a, b in zip(left_values, right_values, strict=False))
    left_norm = sqrt(sum(a * a for a in left_values))
    right_norm = sqrt(sum(b * b for b in right_values))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _distance_to_similarity(distance: float | None) -> float | None:
    if distance is None:
        return None
    return 1 / (1 + max(distance, 0))
