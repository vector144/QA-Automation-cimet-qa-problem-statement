"""
routers/audio.py
POST /api/audio/transcribe/{lead_id}  -- transcribes audio file via Groq Whisper
GET  /api/audio/files                 -- lists available audio files with metadata
GET  /api/audio/status/{lead_id}      -- returns transcription status for a lead
"""

import json
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
import aiosqlite

from database.connection import get_db_connection
from services.transcribe import transcribe_audio_file

router = APIRouter()

# Audio directory relative to this file
AUDIO_DIR = Path(__file__).resolve().parent.parent / "audio"

# Mapping: audio file stem ? lead_id assignment
AUDIO_LEAD_MAP = {
    "3613793": "lead-audio-3613793",
    "3613794": "lead-audio-3613794",
}


def _find_audio_file(stem: str) -> Path | None:
    """Find an audio file by its numeric stem (handles any extension)."""
    for f in AUDIO_DIR.iterdir():
        if f.stem == stem or f.name.startswith(stem + "."):
            return f
    return None


@router.get("/files")
async def list_audio_files():
    """Return available audio files with sizes and assigned lead IDs."""
    files = []
    for f in sorted(AUDIO_DIR.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            stem = f.stem.split(".")[0]
            files.append({
                "filename": f.name,
                "stem": stem,
                "size_mb": round(f.stat().st_size / 1_048_576, 2),
                "lead_id": AUDIO_LEAD_MAP.get(stem),
                "audio_url": f"/audio/{f.name}",
            })
    return files


@router.get("/status/{lead_id}")
async def transcription_status(
    lead_id: str,
    db: aiosqlite.Connection = Depends(get_db_connection),
):
    """Return whether a transcript exists for the given lead."""
    cursor = await db.execute(
        "SELECT lead_id, source, created_at FROM transcripts WHERE lead_id = ?",
        (lead_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return {"lead_id": lead_id, "has_transcript": False}
    return {
        "lead_id": lead_id,
        "has_transcript": True,
        "source": row["source"],
        "created_at": row["created_at"],
    }


@router.post("/transcribe/{lead_id}", status_code=status.HTTP_202_ACCEPTED)
async def transcribe_lead_audio(
    lead_id: str,
    background_tasks: BackgroundTasks,
    db: aiosqlite.Connection = Depends(get_db_connection),
):
    """
    Trigger Groq Whisper transcription for the audio file associated with lead_id.
    The job runs synchronously (audio files are ~14 MB; Groq is fast).
    Returns turn count and duration on success.
    """
    # Find the audio file stem for this lead
    stem = None
    for s, lid in AUDIO_LEAD_MAP.items():
        if lid == lead_id:
            stem = s
            break

    if stem is None:
        raise HTTPException(
            status_code=404,
            detail=f"No audio file mapped to lead '{lead_id}'. Known leads: {list(AUDIO_LEAD_MAP.values())}",
        )

    audio_file = _find_audio_file(stem)
    if audio_file is None:
        raise HTTPException(
            status_code=404,
            detail=f"Audio file for stem '{stem}' not found in audio directory.",
        )

    # Verify lead exists (auto-create if not)
    cursor = await db.execute("SELECT id FROM leads WHERE id = ?", (lead_id,))
    lead_row = await cursor.fetchone()
    if lead_row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Lead '{lead_id}' not found. Please seed the leads first via /api/audio/seed-leads.",
        )

    # Run transcription (this blocks until Groq responds, usually 30-90s for 14MB)
    try:
        result = await transcribe_audio_file(audio_file)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

    turns = result["turns"]
    full_text = result["full_text"]
    duration_sec = result["duration_sec"]

    # Store transcript
    await db.execute(
        """INSERT OR REPLACE INTO transcripts (lead_id, turns, full_text, redacted, source)
           VALUES (?, ?, ?, ?, ?)""",
        (lead_id, json.dumps(turns), full_text, 0, f"groq-whisper:{audio_file.name}"),
    )

    # Update lead recording_url and call duration
    audio_url = f"/audio/{audio_file.name}"
    await db.execute(
        "UPDATE leads SET recording_url = ? WHERE id = ?",
        (audio_url, lead_id),
    )

    await db.commit()

    return {
        "lead_id": lead_id,
        "audio_file": audio_file.name,
        "audio_url": audio_url,
        "turns_count": len(turns),
        "duration_sec": duration_sec,
        "language": result["language"],
        "transcript_stored": True,
    }


@router.post("/seed-leads", status_code=status.HTTP_201_CREATED)
async def seed_audio_leads(
    db: aiosqlite.Connection = Depends(get_db_connection),
):
    """
    Insert the two real audio call leads into the DB if they don't exist yet.
    Call this once before running /api/audio/transcribe/{lead_id}.
    """
    created = []

    leads_to_seed = [
        {
            "id": "lead-audio-3613793",
            "retailer_id": "retailer-broadband",
            "retailer_name": "Dodo NBN",
            "agent_id": "agent-marco-01",
            "agent_name": "Marco Santos",
            "call_date": "2024-06-15",
            "crm_fields": json.dumps({
                "customer_full_name": "Helen (Call 3613793)",
                "audio_file": "3613793.mp3.mpeg",
                "phone": "0412 345 678",
                "email": "helen.customer@example.com",
                "service_address": "14 Harbour Street, Parramatta NSW 2150",
                "plan_price_intro": 42.90,
                "plan_price_standard": 72.90,
                "modem_upfront_cost": 0.00,
                "delivery_days": "3 to 5 business days",
            }),
            "gate_status": "PENDING",
            "recording_url": "/audio/3613793.mp3.mpeg",
        },
        {
            "id": "lead-audio-3613794",
            "retailer_id": "retailer-broadband",
            "retailer_name": "Dodo NBN",
            "agent_id": "agent-marco-02",
            "agent_name": "Marco Santos",
            "call_date": "2024-06-16",
            "crm_fields": json.dumps({
                "customer_full_name": "Helen (Call 3613794)",
                "audio_file": "3613794.mp3.mpeg",
                "phone": "0412 345 678",
                "email": "helen.customer@example.com",
                "service_address": "14 Harbour Street, Parramatta NSW 2150",
                "plan_price_intro": 42.90,
                "plan_price_standard": 72.90,
                "modem_upfront_cost": 0.00,
                "delivery_days": "3 to 5 business days",
            }),
            "gate_status": "PENDING",
            "recording_url": "/audio/3613794.mp3.mpeg",
        },
    ]

    # Also link recording_url to lead-cimet-real-01 if present
    await db.execute(
        "UPDATE leads SET recording_url = '/audio/3613793.mp3.mpeg' WHERE id = 'lead-cimet-real-01' AND recording_url IS NULL"
    )

    data_dir = Path(__file__).resolve().parent.parent / "data"

    for lead in leads_to_seed:
        cursor = await db.execute("SELECT id FROM leads WHERE id = ?", (lead["id"],))
        if await cursor.fetchone() is None:
            await db.execute(
                """INSERT INTO leads (id, retailer_id, retailer_name, agent_id, agent_name,
                                     call_date, crm_fields, gate_status, recording_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    lead["id"], lead["retailer_id"], lead["retailer_name"],
                    lead["agent_id"], lead["agent_name"], lead["call_date"],
                    lead["crm_fields"], lead["gate_status"], lead["recording_url"],
                ),
            )
            created.append(lead["id"])
        else:
            # Update existing lead with updated crm_fields and recording_url
            await db.execute(
                """UPDATE leads SET retailer_name = ?, agent_name = ?, crm_fields = ?, recording_url = ?
                   WHERE id = ?""",
                (lead["retailer_name"], lead["agent_name"], lead["crm_fields"], lead["recording_url"], lead["id"]),
            )

        # Check if pre-generated transcript exists and seed into DB if not present
        stem = lead["id"].split("-")[-1]
        json_file = data_dir / f"transcript_{stem}.json"
        if json_file.exists():
            tr_cur = await db.execute("SELECT lead_id FROM transcripts WHERE lead_id = ?", (lead["id"],))
            if await tr_cur.fetchone() is None:
                with open(json_file, "r", encoding="utf-8") as jf:
                    tr_data = json.load(jf)
                await db.execute(
                    """INSERT OR REPLACE INTO transcripts (lead_id, turns, full_text, redacted, source)
                       VALUES (?, ?, ?, ?, ?)""",
                    (lead["id"], json.dumps(tr_data["turns"]), tr_data["full_text"], 0, f"pregenerated:{stem}"),
                )

    await db.commit()
    return {"created": created, "message": f"Seeded {len(created)} lead(s) and synchronized transcripts."}

