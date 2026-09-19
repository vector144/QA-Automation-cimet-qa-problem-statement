# CIMET QA Automation System — Technical Architecture & Reference Guide

**Project**: CIMET QA Automation Platform (Hackathon Edition)  
**Target Domain**: Automated Compliance & Quality Assurance for Sales Comparison Calls (Broadband & Energy)  
**Stack**: Python 3.12, FastAPI, SQLite (`aiosqlite`), Pydantic v2, `uv`, OpenRouter (Claude Sonnet 3.5/4.5)  

---

## 1. Executive Summary & Problem Context

In retail utility and telecommunications brokering (such as CIMET's comparison platforms), sales are conducted over phone calls by contact center agents. These calls are subject to stringent regulatory frameworks enforced by:
- **ACCC** (Australian Competition and Consumer Commission)
- **TIO** (Telecommunications Industry Ombudsman)
- **AER** (Australian Energy Regulator) — specifically Explicit Informed Consent (EIC) guidelines
- **Retailer-Specific Compliance Guidelines** (Optus, Telstra, AGL, Origin, etc.)

Traditional QA audits only 1% to 3% of recorded calls manually. Non-compliant sales that slip through risk heavy fines, customer clawbacks, churn, and cancellation of retailer affiliate agreements.

### Objective of this Platform
Deliver a **100% automated call QA system** that:
1. Ingests sales call transcripts or audio.
2. Strips PII / PCI data before processing or storage.
3. Automatically evaluates every single call against a version-controlled regulatory rulebook.
4. Determines if the sale is compliant to be passed to the retailer or must be gated / blocked.
5. Provides a QA dashboard where human auditors can inspect evidence citations and override edge cases.

---

## 2. High-Level System Architecture

```
                                  +---------------------------------------+
                                  |         Raw Audio / Transcript        |
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |      Ingest & PII Redaction API       |
                                  |     (POST /api/ingest - Regex PCI)    |
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |             SQLite Database           |
                                  |  - leads         - transcripts        |
                                  |  - score_runs    - check_results      |
                                  +---------------------------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |        Compliance Check Library       |
                                  |  - broadband-v1.json  - energy-v1.json|
                                  +---------------------------------------+
                                                      |
                                  +-------------------+-------------------+
                                  |                   |                   |
                                  v                   v                   v
                        +-------------------+ +---------------+ +------------------+
                        |  Type A: Verbatim | |Type B: Factual| |Type C: Behaviour |
                        |   Mandatory LLM   | |CRM Cross-check| | Dead Air & Hold  |
                        |    Disclosures    | |  Extraction   | |   Calculations   |
                        +-------------------+ +---------------+ +------------------+
                                  |                   |                   |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |          Scoring Orchestrator         |
                                  |      - Score Aggregation (0-100)      |
                                  |      - Gatekeeper: Critical Fail?     |
                                  |        PASSED / FAILED / REVIEW       |
                                  +---------------------------------------+
                                                      |
                                  +-------------------+-------------------+
                                  |                                       |
                                  v                                       v
                     +---------------------------+           +--------------------------+
                     |  QA Reviewer UI Override  |           |     Retailer Dispatch    |
                     | (Human-in-the-loop audit) |           |   (Webhooks & CSV Export)|
                     +---------------------------+           +--------------------------+
```

---

## 3. Compliance Check Taxonomy

Compliance rules are structured into 3 distinct operational types:

| Type | Name | Purpose | Evaluation Method | Failure Impact |
|---|---|---|---|---|
| **Type A** | **Verbatim / Scripted Disclosures** | Mandatory legal statements that must be spoken with semantic fidelity (e.g. cooling off period, medical alarm disclaimers). | LLM classification with semantic similarity check against defined script templates. | **CRITICAL** — Blocks sale dispatch immediately if missing. |
| **Type B** | **Factual Reconciliation** | Spoken terms must strictly match the agreed CRM sales data (e.g. quoted monthly price, speed tier, contract tenure). | LLM entity extraction + deterministic comparison with lead record in DB. | **CRITICAL / MAJOR** — Blocks sale if price or term differs. |
| **Type C** | **Communication & Behavioural** | Professional conduct, polite greetings, proper wrap-up, and dead-air gaps. | Rule-based timestamp heuristics (pause duration > 5s) & sentiment analysis. | **MINOR** — Deducts points from overall QA score, does not block sale. |

---

## 4. Current Implementation Status (Step-by-Step)

### Completed Milestones (79 / 79 Passing TDD Tests)

#### 1. Foundation & Health (`main.py`, `tests/test_health.py`) — 4 Tests
- Fast, asynchronous ASGI server configuration with CORS support.
- Central health check endpoint (`GET /health`) returning version and status.

#### 2. Database Schema & Async Engine (`database/`) — 6 Tests
- Relational schema defined in `schema.sql` covering 6 core tables:
  - `leads`: Lead profile, customer info, retailer ID, CRM metadata, sales gate status (`pending`, `passed`, `failed`, `needs_review`).
  - `transcripts`: Full text, redacted transcript, turn-by-turn utterances with participant tags (`agent`, `customer`).
  - `score_runs`: Scoring session records, aggregate score (0-100), overall status, run duration.
  - `check_results`: Individual check results linked to `score_runs`, citing direct transcript quotes and rationale.
  - `repeat_offences`: Repeat check failures tagged by agent for management coaching.
  - `qa_overrides`: Audit log storing reviewer identity, previous status, updated status, and mandatory justification note.

#### 3. Leads Management Router (`routers/leads.py`, `models/lead.py`) — 11 Tests
- `GET /api/leads`: Query leads with optional filtering by `gate_status` and `retailer_id`.
- `GET /api/leads/{id}`: Detailed lead retrieval with full CRM configuration.

#### 4. Ingest & PCI / PII Sanitizer (`routers/ingest.py`, `services/redact.py`) — 8 Tests
- `POST /api/ingest`: Accepts call transcript payloads.
- Automated sanitization of credit card numbers (Visa, Mastercard, Amex) using regex patterns, replacing numbers with `[REDACTED_PAYMENT_CARD]`.
- Automatic timeline calculation: Enriches conversational turns with estimated timestamps if audio diarization lacks them.

#### 5a. Compliance Check Library System (`services/check_library.py`) — 17 Tests
- Declarative JSON format with versioning (`broadband-v1.json`, `energy-v1.json`).
- Schema validation ensuring every check specifies `type`, `severity`, and evaluation parameters.
- Dynamic library resolver mapping incoming lead product type to the correct versioned compliance library.

#### 5b. LLM Evaluation Engine (`services/openrouter.py`, `services/scoring/`) — 17 Tests
- **OpenRouter Client**: Async client with JSON cleaner/parser and deterministic offline mock support (5 tests).
- **Type C Behavioural Evaluator**: Dead-air silence gap detector and pause calculator (4 tests).
- **Type A Verbatim Evaluator**: Script compliance classifier, citations, confidence score (3 tests).
- **Type B Factual Evaluator**: Entity extraction and deterministic comparison against CRM (5 tests).

#### 6. Scoring Orchestrator & Compliance Gatekeeper (`services/scoring/orchestrator.py`, `routers/scoring.py`) — 8 Tests
- Runs all checks concurrently with `asyncio.gather`.
- Enforces strict regulatory gatekeeper logic: Any critical check failure forces `gate_decision = "FAILED"`, blocking sale dispatch.
- Endpoints: `POST /api/scoring/run/{lead_id}`, `GET /api/scoring/results/{lead_id}`, `GET /api/scoring/repeat-offences`.

#### 7. QA Reviewer Workflow & Overrides (`routers/reviews.py`) — 4 Tests
- Certified human auditor override workflow requiring mandatory justification notes.
- Endpoints: `POST /api/reviews/{lead_id}/override`, `GET /api/reviews/{lead_id}/history`, `GET /api/reviews/sampled`.

#### 8. Export & Compliance Pack Bundles (`routers/export.py`) — 4 Tests
- `GET /api/export/csv`: Export sales with gate status filters.
- `GET /api/export/compliance-pack/{lead_id}`: Generates an auditable compliance certificate bundle for retailer partners.

---

## 5. Next Steps: Roadmap to Completion

### Step 5b: LLM Evaluation Core
- **`services/openrouter.py`**: Async OpenRouter HTTP client with API key configuration, retries, and rate-limit backoff.
- **`services/scoring/verbatim.py`**: Type A evaluator prompt engine.
- **`services/scoring/factual.py`**: Type B factual extractor & CRM comparator.
- **`services/scoring/behaviour.py`**: Type C dead-air heuristic calculator.

### Step 6: Full Scoring Orchestrator
- Connects transcript, lead CRM record, and check library.
- Executes checks asynchronously in parallel.
- Aggregates final score and sets `gate_status`:
  - `PASSED`: All critical checks passed and score >= 85%.
  - `NEEDS_REVIEW`: Non-critical failures or borderline confidence (< 75%).
  - `FAILED`: Any critical check failed.

### Step 7: Reviewer Interface & Overrides API
- `POST /api/reviews/{lead_id}/override`: Secure endpoint for QA team to mark false positives with audit logs.
- Evidence browser: Returns highlighted transcript citations for every check.

### Step 8: CRM / Retailer Export
- Automated CSV/Webhook exporter formatted for retailer intake.

---

## 6. How to Run & Verify

```bash
# In backend/
uv run pytest -v
```
All 46 tests currently pass with 100% green status.
