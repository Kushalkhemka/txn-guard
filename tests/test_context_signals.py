from datetime import UTC, datetime, timedelta

from fraud_detection.core.config import RiskSettings
from fraud_detection.domain import StoredTransaction
from fraud_detection.services.context_signals import ContextSignalService
from fraud_detection.services.profile import UserTransactionProfile


def tx(
    transaction_id: str,
    amount: float,
    merchant: str = "Known Merchant",
    device_id: str = "known-device",
    location: str = "Known City",
    timestamp: datetime | None = None,
) -> StoredTransaction:
    timestamp = timestamp or datetime(2026, 1, 1, 12, tzinfo=UTC)
    return StoredTransaction(
        transaction_id=transaction_id,
        user_id="user-1",
        amount=amount,
        currency="USD",
        merchant=merchant,
        timestamp=timestamp,
        location=location,
        device_id=device_id,
        narrative=f"{transaction_id}:{amount}",
    )


def test_context_signals_detect_amount_novelty_and_velocity():
    settings = RiskSettings(min_history_for_amount_profile=3, velocity_count_threshold=2)
    service = ContextSignalService(settings)
    now = datetime(2026, 1, 1, 12, tzinfo=UTC)
    history = [
        tx("1", 100, timestamp=now - timedelta(minutes=10)),
        tx("2", 110, timestamp=now - timedelta(minutes=5)),
        tx("3", 95, timestamp=now - timedelta(days=1)),
        tx("4", 105, timestamp=now - timedelta(days=2)),
        tx("5", 115, timestamp=now - timedelta(days=3)),
    ]
    current = tx(
        "current",
        1000,
        merchant="New Merchant",
        device_id="new-device",
        location="New City",
        timestamp=now,
    )

    signals = service.evaluate(
        current,
        UserTransactionProfile(user_id="user-1", transactions=history),
    )

    names = {signal.name for signal in signals}
    assert "amount_shift" in names
    assert "merchant_novelty" in names
    assert "device_novelty" in names
    assert "geo_novelty" in names
    assert "spend_velocity" in names
