import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent.parent / "cimet.db"
con = sqlite3.connect(db_path)
cur = con.cursor()

cur.execute("DELETE FROM check_results")
cur.execute("DELETE FROM score_runs")
cur.execute("DELETE FROM qa_overrides")
cur.execute("UPDATE leads SET gate_status = 'PENDING'")
con.commit()

print("Reset complete.")
print("Leads in DB:")
for r in cur.execute("SELECT id, retailer_name, agent_name, gate_status, recording_url FROM leads").fetchall():
    print(" ", r)
print("Transcripts in DB:")
for r in cur.execute("SELECT lead_id, source FROM transcripts").fetchall():
    print(" ", r)
print("Score runs in DB:", cur.execute("SELECT count(*) FROM score_runs").fetchone()[0])
