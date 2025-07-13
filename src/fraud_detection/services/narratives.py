from fraud_detection.domain import StoredTransaction, TransactionInput


class TransactionNarrativeBuilder:
    """Builds stable semantic text for embedding and retrieval."""

    def build_from_input(self, transaction: TransactionInput, default_currency: str) -> str:
        currency = (transaction.currency or default_currency).upper()
        parts = [
            f"user={transaction.user_id}",
            f"amount={transaction.amount:.2f}",
            f"currency={currency}",
            f"merchant={transaction.merchant}",
            f"timestamp={transaction.timestamp.isoformat()}",
            f"location={transaction.location}",
            f"device={transaction.device_id}",
        ]
        if transaction.channel:
            parts.append(f"channel={transaction.channel}")
        if transaction.merchant_category:
            parts.append(f"merchant_category={transaction.merchant_category}")
        for key, value in sorted(transaction.metadata.items()):
            if value is not None:
                parts.append(f"{key}={value}")
        return " | ".join(parts)

    def build_from_stored(self, transaction: StoredTransaction) -> str:
        return transaction.narrative
