"""
models/transcript.py
Pydantic schemas for transcript ingest request/response.
"""

from pydantic import BaseModel
from typing import Optional


class TranscriptTurnIn(BaseModel):
    """A single speaker turn as received from the caller."""
    speaker: str          # e.g. "Speaker 1", "Speaker 2"
    text: str             # Raw spoken text


class TranscriptTurnStored(BaseModel):
    """A speaker turn as stored in the DB — includes estimated timestamps."""
    turn_index: int
    speaker: str
    text: str
    start_ms: int         # Estimated audio position (milliseconds)
    end_ms: int


class IngestRequest(BaseModel):
    lead_id: str
    turns: list[TranscriptTurnIn]
    recording_url: Optional[str] = None   # Optional audio file URL


class IngestResponse(BaseModel):
    lead_id: str
    transcript_stored: bool
    turns_count: int
    redacted: bool        # True if any PII was found and redacted
    recording_url: Optional[str] = None
