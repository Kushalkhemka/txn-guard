# Txn Guard

Backend service for semantic transaction surveillance and fraud triage. The service turns normalized transaction records into embedded narratives, stores them in a Chroma-backed evidence corpus, retrieves similar historical transactions, computes contextual risk signals, and returns an auditable triage decision.

This repository is the backend foundation for a larger market/financial intelligence platform. It intentionally keeps API, domain, storage, embedding, and orchestration code separated so the fraud pipeline can evolve without coupling it to a future dashboard or frontend.

## Current Scope

The service supports:

- Transaction ingestion into a persistent vector evidence store.
- Semantic similarity search over transaction narratives.
- User-level behavioral profiling using historical transactions.
- Context signals for spend shift, merchant/device/location novelty, and transaction velocity.
- AML-oriented compliance findings for screening hits, high-risk customer/jurisdiction metadata, and possible structuring patterns.
- Agent-style orchestration that standardizes input, retrieves evidence, evaluates signals, assigns a risk band, and returns an analyst-readable trace.
- Local synthetic data generation for development only.

The service does not replace a regulated AML screening provider. Sanctions, PEP, adverse media, jurisdiction, and KYC risk results should come from upstream compliance systems and be passed through transaction metadata. This backend uses those inputs alongside behavioral signals to produce a triage response.

## Architecture

```text
client / ingestion job
        |
        v
FastAPI routes
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

Package layout:

```text
src/fraud_detection/
  api/          FastAPI app, routes, dependency wiring
  agents/       Backend-safe orchestration layer
  core/         Runtime configuration
  domain/       Pydantic request/response and domain models
  services/     Embeddings, narratives, profile, signal and compliance logic
  storage/      Vector store abstraction and Chroma implementation
scripts/        Development utilities
tests/          Focused unit tests
```

## Running Locally

- Python 3.11 or newer.
- ChromaDB for local vector persistence.
- SentenceTransformers for embedding generation.

Create a local environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Start the API:

```bash
uvicorn fraud_detection.api.main:app --reload
```

OpenAPI documentation is available at:

```text
http://127.0.0.1:8000/docs
```

The default local settings are in `.env.example`. Risk weights, thresholds, vector-store path, and embedding model can be changed from environment variables without touching the pipeline code.

## API

### Health Check

```bash
curl http://127.0.0.1:8000/health
```

### Ingest One Transaction

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

### Bulk Ingest

```bash
curl -X POST http://127.0.0.1:8000/transactions/bulk \
  -H "Content-Type: application/json" \
  -d '{
    "transactions": [
      {
        "transaction_id": "txn_002",
        "user_id": "user_123",
        "amount": 48.10,
        "currency": "USD",
        "merchant": "Local Grocery",
        "timestamp": "2026-06-13T11:00:00Z",
        "location": "New York",
        "device_id": "device_a"
      }
    ]
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

### Triage A Transaction

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

The triage response includes:

- `risk_score`: normalized score between `0` and `1`.
- `risk_band`: `low`, `review`, or `escalate`.
- `signals`: contextual findings with scores and details.
- `compliance_findings`: AML/compliance findings with severity and supporting details.
- `evidence`: nearest transaction records from the vector corpus.
- `agent_trace`: step-by-step orchestration output for audit/debugging.

## Development Data

Seed synthetic transactions for local testing:

```bash
python scripts/seed_synthetic.py --count 1000 --user-count 80
```

Synthetic data is not used by the service automatically. Production ingestion should provide normalized transaction records from the source payment, banking, ledger, or event pipeline.

## Testing

Run the focused test suite:

```bash
pytest
```

The current tests cover:

- Context signal generation for spend shift, novelty, and velocity.
- AML compliance findings from screening metadata and structuring patterns.
- End-to-end orchestrator scoring using an explicit in-memory vector store.

## Scoring Model

The current score is a transparent weighted aggregation:

- Amount shift against the user's historical spend profile.
- Novel merchant, device, or location for the user.
- Transaction velocity inside a configurable time window.
- Retrieved evidence risk when historical records include configured risk score, boolean, or label fields.
- AML compliance findings from configured screening fields, customer/jurisdiction risk fields, and possible structuring patterns.

Similarity alone does not increase risk unless the retrieved evidence contains risk labels. This avoids treating "similar" as automatically suspicious.

## Production Hardening Checklist

Before deploying this as a production fraud service, add:

- Authentication and authorization for all API routes.
- Request IDs, structured logs, metrics, and tracing.
- Durable source-of-truth storage for raw transactions and triage decisions.
- Database migrations and environment-specific Chroma or vector database provisioning.
- Rate limits and payload size limits.
- Model/version metadata in every triage response.
- Offline evaluation against labeled fraud, chargeback, dispute, and false-positive data.
- Monitoring for embedding drift, retrieval quality, and score calibration.
- PII handling policy, retention controls, and encryption requirements.
- Case management or queue integration for `review` and `escalate` decisions.

## Assumptions

- Input transactions are already normalized before reaching this service.
- Timestamps should include timezone information when available.
- `user_id`, `merchant`, `location`, and `device_id` are stable enough to support behavioral profiling.
- Evidence labels and AML screening truth are supplied by upstream systems through configurable transaction metadata fields.
- The current orchestrator is deterministic and backend-safe. CrewAI or another LLM-driven agent layer can be integrated later behind the same orchestration boundary if there is a clear production need.
