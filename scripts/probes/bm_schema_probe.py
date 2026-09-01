"""Read-only probe of the basic-memory index: schema + shape stats.

Design input for the HippoRAG-over-basic-memory lane. Opens the SQLite index in
read-only URI mode so it can never mutate the vault's derived state.
"""

import os
import sqlite3

DB = os.path.expanduser("~/.basic-memory/memory.db")


def main() -> None:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = conn.cursor()

    print("### TABLES / VIEWS / INDEXES")
    for name, typ, sql in cur.execute(
        "SELECT name, type, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ):
        print(f"\n-- [{typ}] {name}")
        print(sql)

    print("\n### ROW COUNTS")
    tables = [
        r[0]
        for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    for t in tables:
        try:
            (n,) = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()
            print(f"{t:32s} {n}")
        except sqlite3.Error as exc:  # virtual/fts tables can refuse plain counts
            print(f"{t:32s} ERR {exc}")

    conn.close()


if __name__ == "__main__":
    main()
