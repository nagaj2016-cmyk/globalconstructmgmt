"""
One-shot DB migration — run this once to add missing columns.
    cd /Users/nagavenkateshwarraoj/Claude/Projects/Construction/backend
    python ../migrate_db.py
"""
import sqlite3, os, sys

# Find the DB — try common locations
CANDIDATES = [
    "./construction.db",
    "./nagaforge.db",
    "./app.db",
    "../construction.db",
    "./backend/construction.db",
]
db_path = None
for c in CANDIDATES:
    p = os.path.abspath(c)
    if os.path.exists(p):
        db_path = p
        break

if not db_path:
    print("ERROR: Could not find construction.db")
    print("Run this script from inside the backend/ folder:")
    print("  cd .../Construction/backend && python ../migrate_db.py")
    sys.exit(1)

print(f"Found DB: {db_path}")
conn = sqlite3.connect(db_path)
cur  = conn.cursor()

# ── companies table ──────────────────────────────────────────────────────────
cur.execute("PRAGMA table_info(companies)")
existing = {r[1] for r in cur.fetchall()}
print(f"Existing columns: {sorted(existing)}")

MIGRATIONS = [
    ("companies", "gst_no",   "TEXT"),
    ("companies", "timezone", "TEXT DEFAULT 'Asia/Kolkata'"),
    ("companies", "city",     "TEXT"),
]

for tbl, col, defn in MIGRATIONS:
    if col not in existing:
        cur.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {defn}")
        print(f"  ✅ Added  : {tbl}.{col}")
    else:
        print(f"  ✓  Exists : {tbl}.{col}")

conn.commit()
conn.close()

print("\nMigration complete. Restart your FastAPI server now.")
