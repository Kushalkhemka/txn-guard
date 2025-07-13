from dataclasses import dataclass
from statistics import mean, pstdev

from fraud_detection.domain import StoredTransaction


@dataclass(frozen=True)
class UserTransactionProfile:
    user_id: str
    transactions: list[StoredTransaction]

    @property
    def amounts(self) -> list[float]:
        return [transaction.amount for transaction in self.transactions]

    @property
    def mean_amount(self) -> float | None:
        if not self.amounts:
            return None
        return mean(self.amounts)

    @property
    def amount_stddev(self) -> float:
        if len(self.amounts) < 2:
            return 0.0
        return pstdev(self.amounts)

    @property
    def merchants(self) -> set[str]:
        return {transaction.merchant for transaction in self.transactions}

    @property
    def devices(self) -> set[str]:
        return {transaction.device_id for transaction in self.transactions}

    @property
    def locations(self) -> set[str]:
        return {transaction.location for transaction in self.transactions}
