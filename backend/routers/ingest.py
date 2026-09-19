"""
routers/ingest.py
POST /api/ingest — accepts transcript turns for a lead, estimates timestamps,
                   redacts card numbers, stores in DB.
"""

import json
from fastapi import APIRouter, Depends, HTTPException, status
import aiosqlite

from database.connection import get_db_connection
from models.transcript import IngestRequest, IngestResponse, TranscriptTurnStored
from services.redact import redact_turns

router = APIRouter()

# Average speaking rate used for timestamp estimation
_WORDS_PER_MINUTE = 130
_MS_PER_WORD = 60_000 / _WORDS_PER_MINUTE   # ≈ 461.5 ms per word
_PAUSE_BETWEEN_TURNS_MS = 500               # Brief gap between speaker turns


def _estimate_timestamps(turns: list[dict]) -> list[TranscriptTurnStored]:
    """
    Assign start_ms / end_ms to each turn based on word count.
    Adds a short inter-turn pause for realism.
    """
    cursor_ms = 0
    result = []

    for i, turn in enumerate(turns):
        word_count = max(1, len(turn["text"].split()))
        duration_ms = int(word_count * _MS_PER_WORD)

        result.append(
            TranscriptTurnStored(
                turn_index=i,
                speaker=turn["speaker"],
                text=turn["text"],
                start_ms=cursor_ms,
                end_ms=cursor_ms + duration_ms,
            )
        )
        cursor_ms += duration_ms + _PAUSE_BETWEEN_TURNS_MS

    return result


@router.post("", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_transcript(
    payload: IngestRequest,
    db: aiosqlite.Connection = Depends(get_db_connection),
):
    """
    Accept a transcript (list of speaker turns) for an existing lead.

    Steps:
    1. Verify lead exists.
    2. Redact any card numbers from turn texts.
    3. Estimate audio timestamps for each turn.
    4. Upsert transcript into the transcripts table.
    5. Update lead recording_url if provided.
    """
    # 1. Verify lead exists
    cursor = await db.execute("SELECT id FROM leads WHERE id = ?", (payload.lead_id,))
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead '{payload.lead_id}' not found",
        )

    # 2. Redact PII from turns
    raw_turns = [t.model_dump() for t in payload.turns]
    clean_turns, any_redacted = redact_turns(raw_turns)

    # 3. Estimate timestamps
    timed_turns = _estimate_timestamps(clean_turns)
    turns_json = json.dumps([t.model_dump() for t in timed_turns])

    # Full flat text for quick searching
    full_text = " ".join(t.text for t in timed_turns)

    # 4. Upsert transcript (INSERT OR REPLACE)
    await db.execute(
        """INSERT OR REPLACE INTO transcripts
           (lead_id, turns, full_text, redacted, source)
           VALUES (?, ?, ?, ?, ?)""",
        (
            payload.lead_id,
            turns_json,
            full_text,
            1 if any_redacted else 0,
            "provided",
        ),
    )

    # 5. Update recording_url on lead if provided
    if payload.recording_url:
        await db.execute(
            "UPDATE leads SET recording_url = ? WHERE id = ?",
            (payload.recording_url, payload.lead_id),
        )

    await db.commit()

    return IngestResponse(
        lead_id=payload.lead_id,
        transcript_stored=True,
        turns_count=len(timed_turns),
        redacted=any_redacted,
        recording_url=payload.recording_url,
    )
