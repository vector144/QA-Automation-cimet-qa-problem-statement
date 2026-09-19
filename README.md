# CIMET QA Automation Backend 🛡️

Automated, auditable Quality Assurance (QA) compliance scoring engine for sales and comparison calls (Broadband & Energy).

---

## 📌 Project Overview

CIMET operates multi-retailer comparison and switching platforms. Every sales call conducted by contact center agents must strictly comply with Australian consumer regulations (e.g., ACCC guidelines, Telecommunications Industry Ombudsman rules, and Energy Retail codes) alongside retailer-specific mandatory scripts.

This backend automates compliance verification by:
1. Ingesting call transcripts with automated PII redaction (masking credit card details, CVVs, etc.).
2. Mapping leads to retailer-specific compliance check libraries (Broadband, Energy, etc.) with version pinning.
3. Scoring compliance across three distinct verification types:
   - **Type A (Verbatim / Scripted)**: LLM semantic evaluation to confirm mandatory disclosures (e.g., cooling-off periods, cancellation fees, direct debit terms) were articulated accurately.
   - **Type B (Factual / CRM Reconciliation)**: Comparing values extracted from the conversation against CRM data (plan price, speed tier, contract term, billing address).
   - **Type C (Behavioural / Communication)**: Measuring customer interaction hygiene, dead-air gaps, and agent etiquette.
4. Gatekeeping sales dispatch: Blocking sales where critical compliance checks fail, and providing an auditable human-in-the-loop override workflow.

---

## 🏗️ Architecture & Technology Stack

- **Package & Dependency Manager**: [`uv`](https://github.com/astral-sh/uv) (ultra-fast Python package manager)
- **Runtime / Framework**: Python 3.12+ with [FastAPI](https://fastapi.tiangolo.com/) (asynchronous ASGI)
- **Database Layer**: SQLite via [`aiosqlite`](https://github.com/omnilib/aiosqlite) with pure async operations and connection management
- **Data Validation & Schemas**: [Pydantic v2](https://docs.pydantic.dev/)
- **Testing & TDD**: [pytest](https://docs.pytest.org/) and [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- **LLM Integration (Upcoming in Step 5b)**: OpenRouter API for multi-model flexibility (Claude Sonnet 3.5 / 4.5, GPT-4o)

---

## 📂 Current Directory Structure

```
backend/
├── data/
│   ├── check-library/
│   │   ├── broadband-v1.json      # Check library for broadband (NBN) compliance
│   │   └── energy-v1.json         # Check library for energy (Electricity/Gas) compliance
│   └── seed/
│       └── transcripts/           # Sample transcribed audio fixtures
├── database/
│   ├── connection.py              # Async connection pool & test_mode isolation
│   └── schema.sql                 # SQLite schema (5 tables + indexes)
├── models/
│   ├── lead.py                    # Lead Pydantic models & DTOs
│   └── transcript.py              # Transcript & utterance models
├── routers/
│   ├── ingest.py                  # POST /api/ingest (transcript storage & PII scrubbing)
│   └── leads.py                   # GET /api/leads & GET /api/leads/{id}
├── services/
│   ├── check_library.py           # Library loader, check filters, retailer resolution
│   ├── redact.py                  # Regex-based PII scrubber (credit cards, CVVs)
│   └── scoring/                   # Scoring engine modules (In progress)
├── tests/
│   ├── conftest.py                # Pytest fixtures and backend path configuration
│   ├── test_check_library.py      # Tests for check library definitions & resolution
│   ├── test_db.py                 # Tests for database tables & async queries
│   ├── test_health.py             # Tests for system health check endpoint
│   ├── test_ingest.py             # Tests for transcript ingestion & redaction
│   └── test_leads.py              # Tests for leads listing and detail retrieval
├── .env.example                   # Environment configuration template
├── cimet.db                       # Local development SQLite database
├── main.py                        # FastAPI application entrypoint & lifespan
├── pyproject.toml                 # uv project configuration and dependencies
└── README.md                      # This reference document
```

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
Ensure `uv` is installed on your system:
```bash
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Install Dependencies
In the `backend/` directory:
```bash
uv sync --dev
```

### 3. Environment Variables
Copy `.env.example` to `.env` and configure:
```env
OPENROUTER_API_KEY=sk-or-your-key-here
DATABASE_PATH=./cimet.db
DEFAULT_LLM_MODEL=anthropic/claude-sonnet-4-5
ENVIRONMENT=development
```

### 4. Running the Development Server
```bash
uv run uvicorn main:app --reload --port 8000
```
Interactive API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 🧪 Test-Driven Development (TDD) Status

All features are implemented strictly following Test-Driven Development: **Test first -> Confirm failure -> Implement code -> Confirm 100% green**.

### Current Test Suite: 79 / 79 Passing ✅

```bash
uv run pytest -v
```

| Test Suite | File | Tests | Coverage Scope |
|---|---|---|---|
| **Health** | `tests/test_health.py` | 4 | Server status, service identifier, API version |
| **Database** | `tests/test_db.py` | 6 | Table creation, seed execution, schema integrity, async CRUD |
| **Leads** | `tests/test_leads.py` | 11 | `GET /api/leads`, `GET /api/leads/{id}`, status filters, 404 handling |
| **Ingest & Redaction** | `tests/test_ingest.py` | 8 | `POST /api/ingest`, credit card masking, turn timestamps, upserts |
| **Check Library** | `tests/test_check_library.py` | 17 | Check validation, type filters (verbatim/factual/behaviour), version resolution |
| **OpenRouter Client** | `tests/test_openrouter.py` | 5 | Async LLM client, JSON cleaning/parsing, mock client isolation |
| **Type C Behavioural**| `tests/test_scoring_behaviour.py`| 4 | Dead-air silence gap detection, pause calculation |
| **Type A Verbatim**   | `tests/test_scoring_verbatim.py` | 3 | Script compliance classification, quote citation, confidence |
| **Type B Factual**    | `tests/test_scoring_factual.py`  | 5 | Entity extraction & deterministic comparison against CRM |
| **Orchestrator**      | `tests/test_scoring_orchestrator.py`| 4 | Parallel check execution, Gatekeeper blocking, repeat offences |
| **Scoring Router**    | `tests/test_scoring_router.py`   | 4 | `POST /api/scoring/run/{id}`, `GET /api/scoring/results/{id}` |
| **QA Reviews**        | `tests/test_reviews.py`          | 4 | `POST /api/reviews/{id}/override`, audit logs, sampled queue |
| **Export & Pack**     | `tests/test_export.py`           | 4 | `GET /api/export/csv`, `GET /api/export/compliance-pack/{id}` |
| **Total** | | **79** | **100% Green** |

---

## 🔍 Modules Built So Far

### 1. Database Layer (`database/`)
- **Schema (`schema.sql`)**:
  - `leads`: Customer contact details, plan details, sale gate status (`pending`, `passed`, `failed`, `needs_review`).
  - `transcripts`: Full raw and redacted conversation transcripts with turn-by-turn utterances.
  - `score_runs`: Scoring execution sessions with composite score, timestamps, model metadata.
  - `check_results`: Granular per-check verification outcomes (status, confidence, evidence quote, explanation).
  - `qa_overrides`: Human QA supervisor overrides with audit logs and rationale notes.
- **Connection (`connection.py`)**:
  - Async context manager via `aiosqlite`.
  - Built-in `test_mode` providing zero-pollution temporary test databases for test suites.

### 2. Leads Management (`models/lead.py`, `routers/leads.py`)
- Endpoints:
  - `GET /api/leads`: Query leads with optional filtering by `gate_status` and `retailer_id`.
  - `GET /api/leads/{id}`: Detailed lead profile including plan configuration and CRM attributes.
- Auto-seeds initial realistic test leads representing Broadband and Energy sales.

### 3. Transcript Ingestion & PII Redaction (`services/redact.py`, `routers/ingest.py`)
- Endpoint:
  - `POST /api/ingest`: Accepts full transcript payloads or audio diarization segments.
- Automatically strips payment card numbers (Visa, Mastercard, Amex, 13-19 digit strings) replacing them with `[REDACTED_PAYMENT_CARD]`.
- Enriches utterances with calculated sequential timeline timestamps if missing.

### 4. Compliance Check Library (`services/check_library.py`, `data/check-library/`)
- Declarative JSON compliance rules with schema validation:
  - **`broadband-v1.json`**:
    - Mandatory speed tier explanation (Type A / Critical)
    - Medical alarm / back-to-base compatibility disclosure (Type A / Critical)
    - Monthly plan pricing confirmation matching CRM (Type B / Factual)
    - Cooling-off period rights explanation (Type A / Critical)
    - Dead-air & hold time etiquette (Type C / Behavioural)
  - **`energy-v1.json`**:
    - Concession card & rebate eligibility checks
    - Tariff structure disclosure (Peak/Off-peak)
    - Explicit informed consent (EIC) verification (Critical)
- Dynamic version resolver selecting the exact regulatory rulebook applicable at call date.

---

## 🗺️ Roadmap: What We Are Building Next

### Phase 5b: LLM Evaluation Engine (In Progress)
- **OpenRouter Async Client (`services/openrouter.py`)**: Robust async calls to OpenRouter with automatic backoff, retry, and token tracking.
- **Type A (Verbatim) Evaluator (`services/scoring/verbatim.py`)**: Windowed transcript search + LLM prompt returning structured JSON:
  ```json
  {
    "status": "PASS",
    "confidence": 0.95,
    "quote": "Agent: You have a 10-business-day cooling-off period...",
    "explanation": "Agent clearly stated cooling-off rights without ambiguity."
  }
  ```
- **Type B (Factual) Evaluator (`services/scoring/factual.py`)**: Extraction of spoken plan details (monthly charge, term, address) and mathematical/string comparison against CRM truth.
- **Type C (Behavioural) Evaluator (`services/scoring/behaviour.py`)**: Deterministic timeline analysis detecting customer dead air > 5 seconds, over-talking, and sentiment flags.

### Phase 6: Score Orchestrator & Compliance Gatekeeper
- Orchestrates concurrent evaluation of all checks for a call.
- Aggregates overall compliance score (0-100%).
- Automatically sets `gate_status = "failed"` if any **Critical** check fails.
- Prevents submission of non-compliant sales to retailer APIs.

### Phase 7: QA Reviewer Dashboard & Human-In-The-Loop Overrides
- Endpoint `POST /api/reviews/{lead_id}/override`: Allows certified QA managers to override false-positive checks with mandatory explanation notes.
- Historical audit trail logging reviewer ID, timestamp, and previous status.

### Phase 8: Export & Retailer Integration
- Export compliant sales via CSV / JSON webhook formats tailored to retailer partner specifications.
- Automated compliance pack generation with timestamped quotes as evidence for regulatory audits.
