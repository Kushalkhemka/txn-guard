from collections.abc import Sequence
from typing import Any

from fraud_detection.core.config import Settings
from fraud_detection.domain import (
    AgentTrace,
    ComplianceFinding,
    ContextSignal,
    RiskBand,
    StoredTransaction,
    TransactionEvidence,
    TransactionInput,
    TriageResult,
)
from fraud_detection.services.compliance import AMLComplianceService
from fraud_detection.services.context_signals import ContextSignalService
from fraud_detection.services.embeddings import EmbeddingProvider
from fraud_detection.services.narratives import TransactionNarrativeBuilder
from fraud_detection.services.profile import UserTransactionProfile
from fraud_detection.storage import VectorStore


class FraudTriageOrchestrator:
    def __init__(
        self,
        settings: Settings,
        embedder: EmbeddingProvider,
        vector_store: VectorStore,
        narrative_builder: TransactionNarrativeBuilder | None = None,
        signal_service: ContextSignalService | None = None,
        compliance_service: AMLComplianceService | None = None,
    ):
        self._settings = settings
        self._embedder = embedder
        self._vector_store = vector_store
        self._narratives = narrative_builder or TransactionNarrativeBuilder()
        self._signals = signal_service or ContextSignalService(settings.risk)
        self._compliance = compliance_service or AMLComplianceService(settings.compliance)

    def ingest(self, transaction: TransactionInput) -> StoredTransaction:
        stored = self._standardize(transaction)
        embedding = self._embedder.embed([stored.narrative])[0]
        self._vector_store.upsert(stored, embedding)
        return stored

    def search(
        self,
        query: str,
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[TransactionEvidence]:
        embedding = self._embedder.embed([query])[0]
        return self._vector_store.query(
            embedding=embedding,
            top_k=top_k or self._settings.similarity_top_k,
            filters=filters,
        )

    def user_transactions(self, user_id: str, limit: int = 1000) -> list[StoredTransaction]:
        return self._vector_store.list_by_user(user_id=user_id, limit=limit)

    def triage(self, transaction: TransactionInput) -> TriageResult:
        trace: list[AgentTrace] = []

        stored = self._standardize(transaction)
        trace.append(
            AgentTrace(
                agent="standardization_agent",
                output={
                    "transaction_id": stored.transaction_id,
                    "narrative": stored.narrative,
                },
            )
        )

        profile_transactions = self._vector_store.list_by_user(stored.user_id)
        profile = UserTransactionProfile(user_id=stored.user_id, transactions=profile_transactions)
        signals = self._signals.evaluate(stored, profile)
        compliance_findings = self._compliance.evaluate(stored, profile)
        trace.append(
            AgentTrace(
                agent="context_signal_agent",
                output={
                    "history_size": len(profile_transactions),
                    "signals": [signal.model_dump() for signal in signals],
                },
            )
        )
        trace.append(
            AgentTrace(
                agent="aml_compliance_agent",
                output={
                    "findings": [finding.model_dump() for finding in compliance_findings],
                },
            )
        )

        evidence = self.search(stored.narrative, self._settings.similarity_top_k)
        evidence = [
            item for item in evidence if item.transaction_id != stored.transaction_id
        ]
        trace.append(
            AgentTrace(
                agent="retrieval_agent",
                output={
                    "evidence_count": len(evidence),
                    "transaction_ids": [item.transaction_id for item in evidence],
                },
            )
        )

        risk_score = self._score(signals, evidence, compliance_findings)
        risk_band = self._risk_band(risk_score)
        typologies = self._typologies(signals, evidence, compliance_findings)
        recommendation = self._recommendation(risk_band)
        trace.append(
            AgentTrace(
                agent="risk_orchestrator",
                output={
                    "risk_score": risk_score,
                    "risk_band": risk_band,
                    "typologies": typologies,
                    "recommendation": recommendation,
                },
            )
        )

        return TriageResult(
            transaction=stored,
            risk_score=risk_score,
            risk_band=risk_band,
            recommendation=recommendation,
            typologies=typologies,
            signals=signals,
            compliance_findings=compliance_findings,
            evidence=evidence,
            agent_trace=trace,
        )

    def _standardize(self, transaction: TransactionInput) -> StoredTransaction:
        narrative = self._narratives.build_from_input(transaction, self._settings.default_currency)
        return StoredTransaction.from_input(
            transaction=transaction,
            narrative=narrative,
            default_currency=self._settings.default_currency,
        )

    def _score(
        self,
        signals: Sequence[ContextSignal],
        evidence: Sequence[TransactionEvidence],
        compliance_findings: Sequence[ComplianceFinding],
    ) -> float:
        weights = self._settings.risk.normalized_weights
        amount_score = max((signal.score for signal in signals if signal.name == "amount_shift"), default=0)
        novelty_score = max(
            (
                signal.score
                for signal in signals
                if signal.name in {"merchant_novelty", "device_novelty", "geo_novelty"}
            ),
            default=0,
        )
        velocity_score = max(
            (signal.score for signal in signals if signal.name == "spend_velocity"),
            default=0,
        )
        evidence_score = self._evidence_risk_score(evidence)
        compliance_score = max((finding.score for finding in compliance_findings), default=0)
        score = (
            amount_score * weights["amount"]
            + novelty_score * weights["novelty"]
            + velocity_score * weights["velocity"]
            + evidence_score * weights["evidence"]
        )
        score = max(score, compliance_score)
        return round(min(max(score, 0.0), 1.0), 4)

    def _evidence_risk_score(self, evidence: Sequence[TransactionEvidence]) -> float:
        scored_items: list[tuple[float, float]] = []
        for item in evidence:
            metadata_score = self._metadata_risk_score(item.metadata)
            if metadata_score is None:
                continue
            similarity = item.similarity if item.similarity is not None else 1.0
            scored_items.append((metadata_score, max(similarity, 0.0)))
        if not scored_items:
            return 0.0
        weighted_sum = sum(score * weight for score, weight in scored_items)
        weight_total = sum(weight for _score, weight in scored_items)
        if weight_total <= 0:
            return 0.0
        return min(weighted_sum / weight_total, 1.0)

    def _risk_band(self, risk_score: float) -> RiskBand:
        if risk_score >= self._settings.risk.escalate_threshold:
            return RiskBand.escalate
        if risk_score >= self._settings.risk.review_threshold:
            return RiskBand.review
        return RiskBand.low

    def _typologies(
        self,
        signals: Sequence[ContextSignal],
        evidence: Sequence[TransactionEvidence],
        compliance_findings: Sequence[ComplianceFinding],
    ) -> list[str]:
        typologies = []
        signal_names = {signal.name for signal in signals}
        finding_names = {finding.name for finding in compliance_findings}
        if {"amount_shift", "device_novelty"} <= signal_names:
            typologies.append("high_value_new_device")
        if {"amount_shift", "geo_novelty"} <= signal_names:
            typologies.append("high_value_geo_shift")
        if "spend_velocity" in signal_names:
            typologies.append("rapid_repeat_spend")
        if any(self._metadata_risk_score(item.metadata) for item in evidence):
            typologies.append("similar_labeled_risky_evidence")
        if "possible_structuring_pattern" in finding_names:
            typologies.append("possible_structuring")
        if finding_names & {
            "sanctions_screening_match",
            "pep_screening_match",
            "adverse_media_match",
        }:
            typologies.append("screening_alert")
        if finding_names & {"high_risk_jurisdiction", "high_risk_customer"}:
            typologies.append("enhanced_due_diligence")
        return typologies

    def _recommendation(self, risk_band: RiskBand) -> str:
        if risk_band == RiskBand.escalate:
            return "Escalate for investigation and consider temporary transaction hold."
        if risk_band == RiskBand.review:
            return "Queue for analyst review with retrieved evidence and context signals."
        return "Allow automated monitoring unless downstream controls require review."

    def _metadata_risk_score(self, metadata: dict[str, Any]) -> float | None:
        custom_metadata = metadata.get("metadata")
        merged_metadata = dict(metadata)
        if isinstance(custom_metadata, dict):
            merged_metadata.update(custom_metadata)

        for field in self._settings.risk.evidence_score_fields:
            if field not in merged_metadata:
                continue
            try:
                return min(max(float(merged_metadata[field]), 0.0), 1.0)
            except (TypeError, ValueError):
                return None

        for field in self._settings.risk.fraud_boolean_fields:
            if merged_metadata.get(field) is True:
                return 1.0

        high_risk_labels = {_normalize(value) for value in self._settings.risk.high_risk_labels}
        medium_risk_labels = {_normalize(value) for value in self._settings.risk.medium_risk_labels}
        for field in self._settings.risk.risk_label_fields:
            risk_label = _normalize(merged_metadata.get(field))
            if risk_label in high_risk_labels:
                return 1.0
            if risk_label in medium_risk_labels:
                return 0.5
        return None


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()
