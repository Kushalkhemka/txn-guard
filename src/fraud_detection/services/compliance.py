from datetime import timedelta
from typing import Any

from fraud_detection.core.config import ComplianceSettings
from fraud_detection.domain import ComplianceFinding, RiskBand, StoredTransaction
from fraud_detection.services.profile import UserTransactionProfile


class AMLComplianceService:
    """Evaluates AML-oriented findings from screening metadata and behavior."""

    def __init__(self, settings: ComplianceSettings):
        self._settings = settings

    def evaluate(
        self,
        transaction: StoredTransaction,
        profile: UserTransactionProfile,
    ) -> list[ComplianceFinding]:
        metadata = transaction.metadata or {}
        findings: list[ComplianceFinding] = []
        findings.extend(self._screening_findings(metadata))
        findings.extend(self._risk_attribute_findings(metadata))
        findings.extend(self._structuring_findings(transaction, profile))
        return findings

    def _screening_findings(self, metadata: dict[str, Any]) -> list[ComplianceFinding]:
        checks = [
            (
                "sanctions_screening_match",
                self._settings.sanctions_match_fields,
                self._settings.screening_match_score,
                RiskBand.escalate,
                "Transaction has a sanctions or watchlist screening match from upstream screening metadata.",
            ),
            (
                "pep_screening_match",
                self._settings.pep_match_fields,
                self._settings.pep_match_score,
                RiskBand.review,
                "Transaction involves a PEP match from upstream screening metadata.",
            ),
            (
                "adverse_media_match",
                self._settings.adverse_media_match_fields,
                self._settings.adverse_media_score,
                RiskBand.review,
                "Transaction has adverse media screening metadata.",
            ),
        ]
        findings = []
        for name, keys, score, severity, reason in checks:
            matched_keys = [
                key for key in keys if _is_truthy(metadata.get(key), self._settings.truthy_values)
            ]
            if matched_keys:
                findings.append(
                    ComplianceFinding(
                        name=name,
                        score=score,
                        severity=severity,
                        reason=reason,
                        details={"matched_metadata_keys": matched_keys},
                    )
                )
        return findings

    def _risk_attribute_findings(self, metadata: dict[str, Any]) -> list[ComplianceFinding]:
        findings = []
        jurisdiction_level = _first_metadata_value(
            metadata,
            self._settings.jurisdiction_risk_level_fields,
        )
        normalized_jurisdiction_level = _normalize(jurisdiction_level)
        has_jurisdiction_flag = any(
            _is_truthy(metadata.get(key), self._settings.truthy_values)
            for key in self._settings.high_risk_jurisdiction_fields
        )
        if (
            has_jurisdiction_flag
            or normalized_jurisdiction_level
            in {_normalize(value) for value in self._settings.high_jurisdiction_risk_levels}
        ):
            findings.append(
                ComplianceFinding(
                    name="high_risk_jurisdiction",
                    score=self._settings.high_risk_jurisdiction_score,
                    severity=RiskBand.review,
                    reason="Transaction metadata indicates exposure to a high-risk jurisdiction.",
                    details={"jurisdiction_risk_level": normalized_jurisdiction_level or None},
                )
            )

        kyc_level = _first_metadata_value(metadata, self._settings.kyc_risk_level_fields)
        normalized_kyc_level = _normalize(kyc_level)
        if normalized_kyc_level in {_normalize(value) for value in self._settings.high_kyc_risk_levels}:
            findings.append(
                ComplianceFinding(
                    name="high_risk_customer",
                    score=self._settings.kyc_high_risk_score,
                    severity=RiskBand.review,
                    reason="Customer KYC metadata is marked high risk.",
                    details={"kyc_risk_level": normalized_kyc_level},
                )
            )
        return findings

    def _structuring_findings(
        self,
        transaction: StoredTransaction,
        profile: UserTransactionProfile,
    ) -> list[ComplianceFinding]:
        findings = []
        floor = self._settings.near_threshold_amount * self._settings.near_threshold_ratio
        if floor <= transaction.amount < self._settings.near_threshold_amount:
            findings.append(
                ComplianceFinding(
                    name="near_threshold_transaction",
                    score=self._settings.near_threshold_score,
                    severity=RiskBand.review,
                    reason="Transaction amount is close to the configured AML reporting threshold.",
                    details={
                        "amount": transaction.amount,
                        "threshold": self._settings.near_threshold_amount,
                        "ratio": self._settings.near_threshold_ratio,
                    },
                )
            )

        window_start = transaction.timestamp - timedelta(
            minutes=self._settings.structuring_window_minutes
        )
        recent = [
            historical
            for historical in profile.transactions
            if window_start <= historical.timestamp <= transaction.timestamp
            and historical.transaction_id != transaction.transaction_id
            and historical.amount < self._settings.near_threshold_amount
        ]
        combined_amount = transaction.amount + sum(item.amount for item in recent)
        if (
            transaction.amount < self._settings.near_threshold_amount
            and len(recent) >= self._settings.structuring_min_transactions
            and combined_amount >= self._settings.near_threshold_amount
        ):
            findings.append(
                ComplianceFinding(
                    name="possible_structuring_pattern",
                    score=self._settings.structuring_score,
                    severity=RiskBand.review,
                    reason="Multiple below-threshold transactions combine above the configured AML threshold inside the configured window.",
                    details={
                        "transaction_count": len(recent) + 1,
                        "combined_amount": round(combined_amount, 2),
                        "threshold": self._settings.near_threshold_amount,
                        "window_minutes": self._settings.structuring_window_minutes,
                    },
                )
            )
        return findings


def _is_truthy(value: Any, truthy_values: list[str]) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _normalize(value) in {_normalize(item) for item in truthy_values}
    return bool(value)


def _first_metadata_value(metadata: dict[str, Any], fields: list[str]) -> Any:
    for field in fields:
        if field in metadata:
            return metadata[field]
    return None


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()
