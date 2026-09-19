# CIMET QA Automation Platform — Technical Reference

> Developer documentation covering architecture, API, setup, and all implementation details.

---

## Tech Stack

### Backend
| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12 | Core language |
| FastAPI | >=0.115 | Async REST API |
| uvicorn | >=0.30 | ASGI server |
| aiosqlite | >=0.20 | Async SQLite driver |
| Pydantic v2 | >=2.7 | Request/response validation |
| Groq SDK | >=0.9 | Whisper large-v3 transcription |
| httpx | >=0.27 | Async HTTP for OpenRouter |
| reportlab | >=5.0 | PDF generation |
| uv | latest | Dependency management |
| pytest + pytest-asyncio | >=8.0 | Test suite (79 tests) |

### Frontend
| Tool | Version | Purpose |
|------|---------|---------|
| React | 19 | UI framework |
| Vite | 8 | Dev server & bundler |
| lucide-react | latest | Icons |
| Vanilla CSS | - | Styling |

### AI / LLM
| Model | Provider | Usage |
|-------|----------|-------|
| `whisper-large-v3` | Groq | Transcription + diarization |
| `openai/gpt-oss-120b` | OpenRouter | Speaker diarization labels |
| `anthropic/claude-sonnet-4-5` | OpenRouter | Verbatim + factual checks |

---

## Project Structure

```
cimet-hackthon/
+-- backend/
|   +-- audio/                       # Call recording files (.mp3)
|   +-- data/
|   |   +-- check-library/
|   |   |   +-- broadband-v1.json    # 12 compliance checks
|   |   |   +-- energy-v1.json
|   |   +-- transcript_3613793.json  # Fallback pre-generated transcript
|   |   +-- transcript_3613794.json
|   +-- database/
|   |   +-- connection.py            # Async DB init + connection
|   |   +-- schema.sql               # 6-table SQLite schema
|   |   +-- seed.py                  # Lead seeding
|   +-- models/
|   |   +-- lead.py
|   |   +-- scoring.py
|   +-- routers/
|   |   +-- audio.py                 # Transcription endpoints
|   |   +-- export.py                # CSV + PDF export
|   |   +-- ingest.py                # Ingest + PII redaction
|   |   +-- leads.py                 # Lead CRUD
|   |   +-- reviews.py               # Human override
|   |   +-- scoring.py               # Run scoring + results
|   +-- services/
|   |   +-- check_library.py         # Library loader + resolver
|   |   +-- openrouter.py            # Async LLM client
|   |   +-- redact.py                # PCI/PII regex sanitizer
|   |   +-- transcribe.py            # Groq Whisper + diarization
|   |   +-- scoring/
|   |       +-- orchestrator.py      # Full pipeline
|   |       +-- verbatim.py          # Type A checks (LLM)
|   |       +-- factual.py           # Type B checks (LLM + deterministic)
|   |       +-- behaviour.py         # Type C checks (heuristic)
|   +-- tests/                       # 79 pytest tests
|   +-- cimet.db                     # SQLite production DB
|   +-- main.py
|   +-- pyproject.toml
|   +-- .env
+-- frontend/
|   +-- src/
|   |   +-- App.jsx                  # Full React SPA (~1200 lines)
|   |   +-- index.css                # Design system
|   +-- package.json
|   +-- vite.config.js
+-- docs/
|   +-- SYSTEM_ARCHITECTURE.md
+-- README.md                        # Non-technical overview
+-- README_TECHNICAL.md              # This file
```

---

## Setup

### Backend

```bash
cd backend
cp .env.example .env        # Add your API keys
uv sync                     # Install dependencies
uv run uvicorn main:app --reload
# http://localhost:8000
# http://localhost:8000/docs  (Swagger UI)
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

### Tests

```bash
cd backend
uv run pytest -v
# 79 tests, all green
```

---

## Environment Variables (`backend/.env`)

```env
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=anthropic/claude-sonnet-4-5
ENVIRONMENT=development
```

---

## API Reference

### Audio & Transcription
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/audio/seed-leads` | Seed test leads into DB |
| `POST` | `/api/audio/transcribe/{lead_id}` | Transcribe via Groq Whisper |
| `GET`  | `/api/audio/status/{lead_id}` | Transcript exists? |
| `GET`  | `/api/audio/files` | List audio files |

### Scoring
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/scoring/run/{lead_id}` | Run all 12 checks (concurrent) |
| `GET`  | `/api/scoring/results/{lead_id}` | Fetch score run + check results |
| `POST` | `/api/scoring/reset/{lead_id}` | Reset lead to PENDING |
| `GET`  | `/api/scoring/repeat-offences` | Repeat failures by agent |

### Leads
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/leads` | List leads (filterable) |
| `GET`  | `/api/leads/{lead_id}` | Lead detail + CRM fields |

### Reviews
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/reviews/{lead_id}/override` | Auditor override + justification |
| `GET`  | `/api/reviews/{lead_id}/history` | Override audit log |
| `GET`  | `/api/reviews/sampled` | 5% sampled calls |

### Export
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/export/csv` | Bulk CSV export |
| `GET`  | `/api/export/compliance-pack/{lead_id}` | PDF compliance certificate |
| `GET`  | `/api/export/transcript-pdf` | Timestamped transcript PDF |

### Ingest
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/ingest` | Ingest transcript + auto-redact PCI/PII |

---

## Database Schema (SQLite)

| Table | Key Columns |
|-------|------------|
| `leads` | id, retailer_id, agent_id, crm_fields (JSON), gate_status, recording_url |
| `transcripts` | lead_id, turns (JSON), full_text, source |
| `score_runs` | id, lead_id, score, overall_status, gate_decision, run_at |
| `check_results` | run_id, check_id, status, confidence, agent_said, expected_value, timestamp_ms, reason |
| `repeat_offences` | agent_id, check_id, fail_date, lead_id |
| `qa_overrides` | lead_id, check_id, old_status, new_status, justification, reviewer_name |

---

## Compliance Check Library Format

```json
{
  "id": "broadband-v1",
  "checks": [
    {
      "id": "BB-004",
      "name": "Introductory Price Stated Correctly",
      "type": "FACTUAL",
      "is_critical": true,
      "blocks_sale": true,
      "crm_field": "plan_price_intro"
    }
  ]
}
```

---

## Gate Logic

```
All criticals PASS + score >= 85%  ->  PASSED       (auto-submit)
Any critical FAILS                 ->  FAILED        (held, TL queue)
Score < 85% / low confidence       ->  NEEDS_REVIEW  (QA human)
```

---

## Full Processing Flow

```bash
POST /api/audio/seed-leads
POST /api/audio/transcribe/lead-audio-3613793
POST /api/audio/transcribe/lead-audio-3613794
POST /api/scoring/run/lead-audio-3613793
POST /api/scoring/run/lead-audio-3613794
GET  /api/scoring/results/lead-audio-3613793
```

---

## Real Results

| Call | Turns | Score | Gate | Critical Fails |
|------|-------|-------|------|----------------|
| `lead-audio-3613793` | 154 | 75/100 | FAILED | 3 |
| `lead-audio-3613794` | 154 | 75/100 | FAILED | 3 |

Top failure — **BB-004**: Agent said `$35.90`, CRM expected `$42.90`.
