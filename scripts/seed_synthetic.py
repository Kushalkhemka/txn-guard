from argparse import ArgumentParser
from datetime import UTC
from random import Random

from faker import Faker

from fraud_detection.agents import FraudTriageOrchestrator
from fraud_detection.api.dependencies import get_embedder, get_vector_store
from fraud_detection.core.config import get_settings
from fraud_detection.domain import TransactionInput


def parse_args():
    parser = ArgumentParser(description="Seed synthetic transactions for local development.")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--user-count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--merchant",
        action="append",
        dest="merchants",
        help="Merchant name. Repeat to provide multiple merchants.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fake = Faker()
    fake.seed_instance(args.seed)
    random = Random(args.seed)
    merchants = args.merchants or [f"Merchant-{index}" for index in range(1, 8)]
    settings = get_settings()
    orchestrator = FraudTriageOrchestrator(
        settings=settings,
        embedder=get_embedder(),
        vector_store=get_vector_store(),
    )

    for _ in range(args.count):
        transaction = TransactionInput(
            user_id=str(random.randint(1, args.user_count)),
            amount=round(random.uniform(10, 10000), 2),
            currency=settings.default_currency,
            merchant=random.choice(merchants),
            timestamp=fake.date_time_between(start_date="-30d", end_date="now", tzinfo=UTC),
            location=fake.city(),
            device_id=fake.mac_address(),
        )
        orchestrator.ingest(transaction)
    print(f"Seeded {args.count} synthetic transactions.")


if __name__ == "__main__":
    main()
