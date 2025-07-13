from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RiskBand(StrEnum):
    low = "low"
    review = "review"
    escalate = "escalate"


class TransactionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str | None = None
    user_id: str
    amount: float = Field(gt=0)
    currency: str | None = None
    merchant: str
    timestamp: datetime
    location: str
    device_id: str
    channel: str | None = None
    merchant_category: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_id", "merchant", "location", "device_id")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class StoredTransaction(TransactionInput):
    transaction_id: str
    currency: str
    narrative: str

    @classmethod
    def from_input(
        cls,
        transaction: TransactionInput,
        narrative: str,
        default_currency: str,
    ) -> "StoredTransaction":
        data = transaction.model_dump()
        data["transaction_id"] = transaction.transaction_id or str(uuid4())
        data["currency"] = (transaction.currency or default_currency).upper()
        data["narrative"] = narrative
        return cls(**data)


class TransactionEvidence(BaseModel):
    transaction_id: str
    document: str
    metadata: dict[str, Any]
    distance: float | None = None
    similarity: float | None = None


class ContextSignal(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)


class ComplianceFinding(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    severity: RiskBand
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)


class AgentTrace(BaseModel):
    agent: str
    output: dict[str, Any]


class SearchRequest(BaseModel):
    query: str
    top_k: int | None = Field(default=None, gt=0, le=100)
    filters: dict[str, Any] | None = None


class SearchResult(BaseModel):
    query: str
    evidence: list[TransactionEvidence]


class IngestResult(BaseModel):
    transaction_id: str
    stored: bool


class BulkIngestRequest(BaseModel):
    transactions: list[TransactionInput] = Field(min_length=1)


class BulkIngestResult(BaseModel):
    inserted: int
    transaction_ids: list[str]


class TriageResult(BaseModel):
    transaction: StoredTransaction
    risk_score: float = Field(ge=0, le=1)
    risk_band: RiskBand
    recommendation: str
    typologies: list[str]
    signals: list[ContextSignal]
    compliance_findings: list[ComplianceFinding]
    evidence: list[TransactionEvidence]
    agent_trace: list[AgentTrace]
