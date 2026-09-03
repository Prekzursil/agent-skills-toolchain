#!/usr/bin/env python3
"""Read-only CyberStrike session lookup. No secret dumps."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path(r"C:\Users\Prekzursil\.local\share\cyberstrike\cyberstrike.db")
SID = "ses_f9c9ab90cffetNo68ohzF6RZAq"


def main() -> int:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")]
    print("TABLES", ",".join(tables))
    for t in tables:
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})")]
        print(f"COLS {t}: {cols}")
        joined = " ".join(cols).lower()
        if any(k in joined for k in ("session", "id", "title", "slug")):
            idcols = [c for c in cols if c.lower() in ("id", "session_id", "sessionid", "slug")]
            if not idcols:
                continue
            q = " OR ".join(f"{c}=?" for c in idcols)
            rows = list(cur.execute(f"SELECT * FROM {t} WHERE {q} LIMIT 3", [SID] * len(idcols)))
            print(f"HIT {t} n={len(rows)}")
            for row in rows:
                keys = [k for k in row.keys() if k.lower() not in ("prompt", "messages", "data", "blob", "content")]
                summary = {k: row[k] if not isinstance(row[k], (bytes, memoryview)) else f"bytes:{len(row[k])}" for k in keys}
                # truncate long strings
                for k, v in list(summary.items()):
                    if isinstance(v, str) and len(v) > 180:
                        summary[k] = v[:180] + "…"
                print(" ", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
