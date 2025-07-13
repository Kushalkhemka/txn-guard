from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RiskSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="RISK_", extra="ignore")

    amount_zscore_high: float = 3.0
    min_history_for_amount_profile: int = 5
    novelty_signal_score: float = 0.65
    velocity_window_minutes: int = 30
    velocity_count_threshold: int = 3
    review_threshold: float = 0.45
    escalate_threshold: float = 0.70
    amount_weight: float = 0.30
    novelty_weight: float = 0.25
    velocity_weight: float = 0.20
    evidence_weight: float = 0.25
    evidence_score_fields: list[str] = Field(default_factory=lambda: ["risk_score"])
    fraud_boolean_fields: list[str] = Field(default_factory=lambda: ["is_fraud"])
    high_risk_labels: list[str] = Field(
        default_factory=lambda: ["fraud", "fraudulent", "suspicious", "confirmed_fraud"]
    )
    medium_risk_labels: list[str] = Field(
        default_factory=lambda: ["review", "chargeback", "disputed"]
    )
    risk_label_fields: list[str] = Field(default_factory=lambda: ["risk_label"])

    @property
    def normalized_weights(self) -> dict[str, float]:
        weights = {
            "amount": self.amount_weight,
            "novelty": self.novelty_weight,
            "velocity": self.velocity_weight,
            "evidence": self.evidence_weight,
        }
        total = sum(value for value in weights.values() if value > 0)
        if total <= 0:
            return {key: 0.0 for key in weights}
        return {key: max(value, 0.0) / total for key, value in weights.items()}


class ComplianceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AML_", extra="ignore")

    near_threshold_amount: float = 10000.0
    near_threshold_ratio: float = 0.90
    structuring_window_minutes: int = 1440
    structuring_min_transactions: int = 2
    screening_match_score: float = 1.0
    pep_match_score: float = 0.75
    adverse_media_score: float = 0.70
    high_risk_jurisdiction_score: float = 0.80
    kyc_high_risk_score: float = 0.75
    near_threshold_score: float = 0.65
    structuring_score: float = 0.80
    sanctions_match_fields: list[str] = Field(
        default_factory=lambda: ["sanctions_match", "watchlist_match"]
    )
    pep_match_fields: list[str] = Field(
        default_factory=lambda: ["pep_match", "politically_exposed_person_match"]
    )
    adverse_media_match_fields: list[str] = Field(default_factory=lambda: ["adverse_media_match"])
    high_risk_jurisdiction_fields: list[str] = Field(
        default_factory=lambda: ["high_risk_jurisdiction"]
    )
    jurisdiction_risk_level_fields: list[str] = Field(
        default_factory=lambda: ["jurisdiction_risk_level"]
    )
    high_jurisdiction_risk_levels: list[str] = Field(
        default_factory=lambda: ["high", "very_high", "sanctioned"]
    )
    kyc_risk_level_fields: list[str] = Field(default_factory=lambda: ["kyc_risk_level"])
    high_kyc_risk_levels: list[str] = Field(default_factory=lambda: ["high", "very_high"])
    truthy_values: list[str] = Field(
        default_factory=lambda: ["true", "yes", "y", "1", "match", "matched"]
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Fraud Detection Agentic Backend"
    environment: str = "local"
    vector_persist_dir: Path = Field(default=Path("data/chroma"))
    vector_collection_name: str = "transaction_evidence"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    similarity_top_k: int = 8
    default_currency: str = "USD"
    risk: RiskSettings = Field(default_factory=RiskSettings)
    compliance: ComplianceSettings = Field(default_factory=ComplianceSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()
