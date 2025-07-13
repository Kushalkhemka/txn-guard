# Txn Guard: Agentic Transaction Surveillance Backend

Txn Guard is a FastAPI backend for fraud and AML-oriented transaction surveillance. It converts normalized transaction records into semantic narratives, embeds them into a persistent vector evidence corpus, retrieves similar activity, evaluates behavioral and compliance signals, and returns an auditable triage response.

## Project Overview

The system is designed around a modular surveillance pipeline:

1. Standardize incoming transaction data.
2. Generate a searchable transaction narrative.
3. Embed the narrative using SentenceTransformers.
4. Store and retrieve evidence through ChromaDB.
5. Build a user-level transaction profile.
6. Evaluate fraud, AML, and contextual risk signals.
7. Aggregate the result into a triage decision with traceable agent outputs.

The backend is intentionally separated from any dashboard or frontend so it can be used as the service layer behind analyst tools, monitoring workflows, or internal investigation systems.

## Key Features

- Semantic evidence retrieval over transaction narratives.
- Persistent vector storage with ChromaDB.
- Behavioral profiling by user, merchant, device, location, spend, and velocity.
- Fraud signal generation for spend shifts, new device usage, geo changes, merchant novelty, and rapid repeat activity.
- AML-oriented compliance checks from configurable screening and customer-risk metadata.
- Agent-style orchestration with traceable standardization, signal, retrieval, compliance, and risk aggregation steps.
- FastAPI endpoints for ingestion, search, triage, and user transaction history.
- Configurable scoring thresholds, evidence fields, AML metadata mappings, and embedding model.
- Focused test suite for scoring, compliance findings, and orchestration behavior.

## Architecture

```text
Client / Ingestion Job
        |
        v
FastAPI Routes
        |
        v
FraudTriageOrchestrator
        |
        +-- TransactionNarrativeBuilder
        +-- SentenceTransformerEmbeddingProvider
        +-- ChromaVectorStore
        +-- ContextSignalService
        +-- AMLComplianceService
        +-- UserTransactionProfile
```

### Core Components

- **API Layer**: FastAPI routes for transaction ingestion, evidence search, triage, and user history.
- **Domain Layer**: Pydantic models for transaction input, stored evidence, signals, compliance findings, and triage responses.
- **Embedding Layer**: SentenceTransformer-backed vectorization for transaction narratives.
- **Storage Layer**: ChromaDB persistence behind a vector-store interface.
- **Signal Layer**: Contextual fraud and behavioral signal generation.
- **Compliance Layer**: AML-oriented findings driven by configurable screening metadata.
- **Orchestration Layer**: Coordinates standardization, retrieval, signal evaluation, compliance checks, and final risk aggregation.

## Project Structure

```text
txn-guard/
├── scripts/
│   └── seed_synthetic.py
├── src/
│   └── fraud_detection/
│       ├── agents/
│       ├── api/
│       ├── core/
│       ├── domain/
│       ├── services/
│       └── storage/
├── tests/
├── .env.example
├── pyproject.toml
├── LICENSE
└── README.md
```

## Getting Started

### Installation

```bash
git clone https://github.com/Kushalkhemka/txn-guard.git
cd txn-guard

python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

### Run the API

```bash
uvicorn fraud_detection.api.main:app --reload
```

OpenAPI docs:

```text
http://127.0.0.1:8000/docs
```

### Seed Synthetic Transactions

```bash
python scripts/seed_synthetic.py --count 1000 --user-count 80
```

## API Usage

### Health Check

```bash
curl http://127.0.0.1:8000/health
```

### Ingest Transaction

```bash
curl -X POST http://127.0.0.1:8000/transactions \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn_001",
    "user_id": "user_123",
    "amount": 1250.75,
    "currency": "USD",
    "merchant": "Example Electronics",
    "timestamp": "2026-06-13T10:30:00Z",
    "location": "New York",
    "device_id": "device_a",
    "channel": "card_not_present",
    "merchant_category": "electronics",
    "metadata": {
      "source_system": "processor",
      "provider_screening_status": "clear",
      "customer_risk_tier": "standard"
    }
  }'
```

### Search Evidence

```bash
curl -X POST http://127.0.0.1:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "high value electronics transaction from a new device",
    "top_k": 5,
    "filters": {
      "user_id": "user_123"
    }
  }'
```

### Triage Transaction

```bash
curl -X POST http://127.0.0.1:8000/triage \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn_review_001",
    "user_id": "user_123",
    "amount": 5000.00,
    "currency": "USD",
    "merchant": "Unknown Merchant",
    "timestamp": "2026-06-13T12:15:00Z",
    "location": "Los Angeles",
    "device_id": "new_device"
  }'
```

## Triage Response

The triage endpoint returns:

- `risk_score`: normalized risk score from `0` to `1`.
- `risk_band`: `low`, `review`, or `escalate`.
- `signals`: behavioral and contextual fraud signals.
- `compliance_findings`: AML-oriented screening and customer-risk findings.
- `evidence`: nearest matching transactions from the vector corpus.
- `typologies`: detected risk patterns.
- `agent_trace`: step-by-step orchestration output.

## Scoring Pipeline

Txn Guard combines multiple signal families:

- **Amount shift**: detects transaction values outside the user's historical spend profile.
- **Novelty**: detects new merchant, device, and location patterns.
- **Velocity**: detects repeat activity inside a configurable time window.
- **Evidence risk**: incorporates retrieved evidence when prior transactions include configured risk labels or scores.
- **AML compliance**: evaluates screening metadata, customer risk, jurisdiction risk, and possible structuring.

## Configuration

Runtime behavior is configured through `.env` or environment variables. The main configurable areas are:

- Vector persistence path and collection name.
- Embedding model.
- Similarity result count.
- Risk thresholds and signal weights.
- Evidence score and label field mappings.
- AML screening and customer-risk metadata field mappings.

## Testing

```bash
pytest
```

Current coverage includes:

- Context signal generation.
- AML compliance findings.
- Orchestrator scoring and evidence aggregation.
- Configurable metadata mappings.

## Tech Stack

- FastAPI
- Pydantic
- SentenceTransformers
- ChromaDB
- Pandas
- Faker
- Pytest

## License

MIT License.
