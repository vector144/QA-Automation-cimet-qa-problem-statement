import sqlite3

con = sqlite3.connect("cimet.db")
con.row_factory = sqlite3.Row
cur = con.cursor()

cur.execute("UPDATE leads SET gate_status = 'PENDING'")
con.commit()

print(f"Reset {cur.rowcount} lead(s) to PENDING")
for row in cur.execute("SELECT id, gate_status FROM leads").fetchall():
    print(" ", dict(row))
