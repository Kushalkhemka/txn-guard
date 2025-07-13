from fastapi import APIRouter, Depends

from fraud_detection.agents import FraudTriageOrchestrator
from fraud_detection.api.dependencies import get_orchestrator
from fraud_detection.domain import (
    BulkIngestRequest,
    BulkIngestResult,
    IngestResult,
    SearchRequest,
    SearchResult,
    StoredTransaction,
    TransactionInput,
    TriageResult,
)

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/transactions", response_model=IngestResult)
def ingest_transaction(
    transaction: TransactionInput,
    orchestrator: FraudTriageOrchestrator = Depends(get_orchestrator),
) -> IngestResult:
    stored = orchestrator.ingest(transaction)
    return IngestResult(transaction_id=stored.transaction_id, stored=True)


@router.post("/transactions/bulk", response_model=BulkIngestResult)
def ingest_transactions(
    request: BulkIngestRequest,
    orchestrator: FraudTriageOrchestrator = Depends(get_orchestrator),
) -> BulkIngestResult:
    transaction_ids = [
        orchestrator.ingest(transaction).transaction_id for transaction in request.transactions
    ]
    return BulkIngestResult(inserted=len(transaction_ids), transaction_ids=transaction_ids)


@router.post("/search", response_model=SearchResult)
def search_evidence(
    request: SearchRequest,
    orchestrator: FraudTriageOrchestrator = Depends(get_orchestrator),
) -> SearchResult:
    evidence = orchestrator.search(
        query=request.query,
        top_k=request.top_k,
        filters=request.filters,
    )
    return SearchResult(query=request.query, evidence=evidence)


@router.post("/triage", response_model=TriageResult)
def triage_transaction(
    transaction: TransactionInput,
    orchestrator: FraudTriageOrchestrator = Depends(get_orchestrator),
) -> TriageResult:
    return orchestrator.triage(transaction)


@router.get("/users/{user_id}/transactions", response_model=list[StoredTransaction])
def user_transactions(
    user_id: str,
    limit: int = 1000,
    orchestrator: FraudTriageOrchestrator = Depends(get_orchestrator),
) -> list[StoredTransaction]:
    return orchestrator.user_transactions(user_id=user_id, limit=limit)
