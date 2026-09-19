import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parent.parent / "cimet.db"
con = sqlite3.connect(db_path)
cur = con.cursor()

TARGET_LEADS = ("lead-audio-3613793", "lead-audio-3613794")
placeholders = ",".join("?" for _ in TARGET_LEADS)

print("--- BEFORE CLEANUP ---")
for t in ["leads", "transcripts", "score_runs", "check_results", "qa_overrides", "repeat_offences"]:
    try:
        cnt = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {cnt} rows")
    except Exception as e:
        print(f"  {t}: {e}")

# 1. Delete qa_overrides for other leads
cur.execute(f"DELETE FROM qa_overrides WHERE lead_id NOT IN ({placeholders})", TARGET_LEADS)

# 2. Delete repeat_offences for other leads
cur.execute(f"DELETE FROM repeat_offences WHERE lead_id NOT IN ({placeholders})", TARGET_LEADS)

# 3. Delete check_results for other score_runs
cur.execute(f"""
    DELETE FROM check_results
    WHERE run_id NOT IN (
        SELECT id FROM score_runs WHERE lead_id IN ({placeholders})
    )
""", TARGET_LEADS)

# 4. Delete score_runs for other leads
cur.execute(f"DELETE FROM score_runs WHERE lead_id NOT IN ({placeholders})", TARGET_LEADS)

# 5. Delete transcripts for other leads
cur.execute(f"DELETE FROM transcripts WHERE lead_id NOT IN ({placeholders})", TARGET_LEADS)

# 6. Delete other leads
cur.execute(f"DELETE FROM leads WHERE id NOT IN ({placeholders})", TARGET_LEADS)

con.commit()
cur.execute("VACUUM")
con.commit()

print("\n--- AFTER CLEANUP ---")
for t in ["leads", "transcripts", "score_runs", "check_results", "qa_overrides", "repeat_offences"]:
    cnt = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {cnt} rows")

print("\nRemaining Leads in Database:")
for r in cur.execute("SELECT id, retailer_name, agent_name, recording_url FROM leads").fetchall():
    print(f"  ID: {r[0]} | Retailer: {r[1]} | Agent: {r[2]} | Recording: {r[3]}")

print("\nRemaining Transcripts in Database:")
for r in cur.execute("SELECT lead_id, source FROM transcripts").fetchall():
    print(f"  Lead: {r[0]} | Source: {r[1]}")
