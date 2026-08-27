"""Read-only inspection of the Ollama app settings DB (db.sqlite)."""
import sqlite3

DB = r"C:/Users/Prekzursil/AppData/Local/Ollama/db.sqlite"
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
print("tables:", tables)
for t in tables:
    cols = [r[1] for r in c.execute(f"pragma table_info({t})")]
    rows = c.execute(f"select * from {t} limit 25").fetchall()
    print(f"\n== {t} cols={cols} rows={len(rows)} ==")
    for row in rows:
        s = str(row)
        print(s[:300])
