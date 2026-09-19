"""
scratch/reset_for_audio.py
Resets the DB so both audio leads can be fully re-processed:
  - Clears transcripts (so /api/audio/transcribe will re-run Groq Whisper)
  - Clears score_runs + check_results + qa_overrides + repeat_offences
  - Resets gate_status -> PENDING on both leads
  - Keeps the lead rows and recording_url intact
"""
import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent.parent / "cimet.db"
con = sqlite3.connect(db_path)
cur = con.cursor()

print("--- BEFORE RESET ---")
for t in ["leads", "transcripts", "score_runs", "check_results", "qa_overrides", "repeat_offences"]:
    cnt = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"  {t:<20} {cnt} rows")

# 1. Wipe scoring data
cur.execute("DELETE FROM check_results")
cur.execute("DELETE FROM score_runs")
cur.execute("DELETE FROM qa_overrides")
cur.execute("DELETE FROM repeat_offences")

# 2. Wipe transcripts (so audio can be re-transcribed)
cur.execute("DELETE FROM transcripts")

# 3. Reset lead gate_status back to PENDING
cur.execute("UPDATE leads SET gate_status = 'PENDING'")

con.commit()

print("\n--- AFTER RESET ---")
for t in ["leads", "transcripts", "score_runs", "check_results", "qa_overrides", "repeat_offences"]:
    cnt = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"  {t:<20} {cnt} rows")

print("\n--- LEADS (ready to process) ---")
for r in cur.execute("SELECT id, gate_status, recording_url FROM leads").fetchall():
    print(f"  {r[0]}  gate={r[1]}  recording={r[2]}")

print("\nReset complete!")
print("\nNext steps:")
print("  1. POST http://localhost:8000/api/audio/transcribe/lead-audio-3613793")
print("  2. POST http://localhost:8000/api/audio/transcribe/lead-audio-3613794")
print("  3. POST http://localhost:8000/api/scoring/run/lead-audio-3613793")
print("  4. POST http://localhost:8000/api/scoring/run/lead-audio-3613794")
