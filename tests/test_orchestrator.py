from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from fraud_detection.agents import FraudTriageOrchestrator
from fraud_detection.core.config import Settings
from fraud_detection.domain import RiskBand, TransactionInput
from fraud_detection.storage import InMemoryVectorStore


class StaticEmbedder:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(len(text) % 10), 1.0, 0.5] for text in texts]


def transaction(
    amount: float,
    merchant: str,
    device_id: str,
    location: str,
    timestamp,
    transaction_id: str | None = None,
) -> TransactionInput:
    return TransactionInput(
        transaction_id=transaction_id,
        user_id="user-1",
        amount=amount,
        currency="USD",
        merchant=merchant,
        timestamp=timestamp,
        location=location,
        device_id=device_id,
    )


def test_orchestrator_triages_contextual_risk():
    settings = Settings()
    settings.risk.min_history_for_amount_profile = 3
    settings.risk.velocity_count_threshold = 2
    store = InMemoryVectorStore()
    orchestrator = FraudTriageOrchestrator(settings, StaticEmbedder(), store)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)

    for index, amount in enumerate([90, 100, 105, 110, 95]):
        orchestrator.ingest(
            transaction(
                amount=amount,
                merchant="Known Merchant",
                device_id="known-device",
                location="Known City",
                timestamp=now - timedelta(minutes=index + 1),
                transaction_id=f"history-{index}",
            )
        )

    result = orchestrator.triage(
        transaction(
            amount=1500,
            merchant="New Merchant",
            device_id="new-device",
            location="New City",
            timestamp=now,
            transaction_id="current",
        )
    )

    assert result.risk_band in {RiskBand.review, RiskBand.escalate}
    assert result.risk_score > 0
    assert "high_value_new_device" in result.typologies


def test_orchestrator_uses_configured_evidence_risk_field():
    settings = Settings()
    settings.risk.evidence_score_fields = ["provider_risk_score"]
    settings.risk.amount_weight = 0
    settings.risk.novelty_weight = 0
    settings.risk.velocity_weight = 0
    settings.risk.evidence_weight = 1
    store = InMemoryVectorStore()
    orchestrator = FraudTriageOrchestrator(settings, StaticEmbedder(), store)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)

    orchestrator.ingest(
        TransactionInput(
            transaction_id="evidence-1",
            user_id="user-1",
            amount=100,
            currency="USD",
            merchant="Known Merchant",
            timestamp=now - timedelta(days=1),
            location="Known City",
            device_id="known-device",
            metadata={"provider_risk_score": 0.9},
        )
    )

    result = orchestrator.triage(
        transaction(
            amount=100,
            merchant="Known Merchant",
            device_id="known-device",
            location="Known City",
            timestamp=now,
            transaction_id="current",
        )
    )

    assert result.risk_score > 0
    assert "similar_labeled_risky_evidence" in result.typologies
