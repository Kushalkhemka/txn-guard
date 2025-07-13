from datetime import timedelta

from fraud_detection.core.config import RiskSettings
from fraud_detection.domain import ContextSignal, StoredTransaction
from fraud_detection.services.profile import UserTransactionProfile


class ContextSignalService:
    def __init__(self, settings: RiskSettings):
        self._settings = settings

    def evaluate(
        self,
        transaction: StoredTransaction,
        profile: UserTransactionProfile,
    ) -> list[ContextSignal]:
        signals: list[ContextSignal] = []
        signals.extend(self._amount_signals(transaction, profile))
        signals.extend(self._novelty_signals(transaction, profile))
        signals.extend(self._velocity_signals(transaction, profile))
        return signals

    def _amount_signals(
        self,
        transaction: StoredTransaction,
        profile: UserTransactionProfile,
    ) -> list[ContextSignal]:
        if len(profile.amounts) < self._settings.min_history_for_amount_profile:
            return []
        mean_amount = profile.mean_amount
        if mean_amount is None:
            return []
        stddev = profile.amount_stddev
        if stddev <= 0:
            return []
        zscore = (transaction.amount - mean_amount) / stddev
        if zscore <= 0:
            return []
        score = min(zscore / self._settings.amount_zscore_high, 1.0)
        return [
            ContextSignal(
                name="amount_shift",
                score=score,
                reason="Amount is above this user's historical spend profile.",
                details={
                    "amount": transaction.amount,
                    "mean_amount": round(mean_amount, 2),
                    "stddev": round(stddev, 2),
                    "zscore": round(zscore, 2),
                    "history_size": len(profile.amounts),
                },
            )
        ]

    def _novelty_signals(
        self,
        transaction: StoredTransaction,
        profile: UserTransactionProfile,
    ) -> list[ContextSignal]:
        if not profile.transactions:
            return []
        candidates = [
            ("merchant_novelty", transaction.merchant, profile.merchants, "Merchant is new for user."),
            ("device_novelty", transaction.device_id, profile.devices, "Device is new for user."),
            ("geo_novelty", transaction.location, profile.locations, "Location is new for user."),
        ]
        signals = []
        for name, value, historical_values, reason in candidates:
            if value not in historical_values:
                signals.append(
                    ContextSignal(
                        name=name,
                        score=self._settings.novelty_signal_score,
                        reason=reason,
                        details={"value": value, "known_values": len(historical_values)},
                    )
                )
        return signals

    def _velocity_signals(
        self,
        transaction: StoredTransaction,
        profile: UserTransactionProfile,
    ) -> list[ContextSignal]:
        window_start = transaction.timestamp - timedelta(
            minutes=self._settings.velocity_window_minutes
        )
        recent = [
            historical
            for historical in profile.transactions
            if window_start <= historical.timestamp <= transaction.timestamp
            and historical.transaction_id != transaction.transaction_id
        ]
        if len(recent) < self._settings.velocity_count_threshold:
            return []
        score = min(len(recent) / self._settings.velocity_count_threshold, 1.0)
        return [
            ContextSignal(
                name="spend_velocity",
                score=score,
                reason="Multiple transactions occurred inside the configured velocity window.",
                details={
                    "recent_transaction_count": len(recent),
                    "window_minutes": self._settings.velocity_window_minutes,
                    "threshold": self._settings.velocity_count_threshold,
                },
            )
        ]
