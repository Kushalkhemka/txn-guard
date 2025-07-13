from datetime import UTC, datetime, timedelta

from fraud_detection.core.config import ComplianceSettings
from fraud_detection.domain import RiskBand, StoredTransaction
from fraud_detection.services.compliance import AMLComplianceService
from fraud_detection.services.profile import UserTransactionProfile


def tx(
    transaction_id: str,
    amount: float,
    timestamp: datetime,
    metadata=None,
) -> StoredTransaction:
    return StoredTransaction(
        transaction_id=transaction_id,
        user_id="user-1",
        amount=amount,
        currency="USD",
        merchant="Counterparty",
        timestamp=timestamp,
        location="New York",
        device_id="device-a",
        narrative=transaction_id,
        metadata=metadata or {},
    )


def test_aml_compliance_detects_screening_and_structuring_findings():
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    service = AMLComplianceService(
        ComplianceSettings(
            near_threshold_amount=10000,
            structuring_min_transactions=2,
            structuring_window_minutes=1440,
            sanctions_match_fields=["provider_sanctions_hit"],
            kyc_risk_level_fields=["customer_risk_tier"],
            high_kyc_risk_levels=["elevated"],
        )
    )
    history = [
        tx("history-1", 3000, now - timedelta(hours=2)),
        tx("history-2", 3500, now - timedelta(hours=1)),
    ]
    current = tx(
        "current",
        4000,
        now,
        metadata={"provider_sanctions_hit": True, "customer_risk_tier": "elevated"},
    )

    findings = service.evaluate(
        current,
        UserTransactionProfile(user_id="user-1", transactions=history),
    )

    names = {finding.name for finding in findings}
    assert "sanctions_screening_match" in names
    assert "high_risk_customer" in names
    assert "possible_structuring_pattern" in names
    assert any(finding.severity == RiskBand.escalate for finding in findings)
