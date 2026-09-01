"""Set Ollama app 'expose' setting to 0 (loopback-only). Backup-first, read then write."""

import sqlite3

DB = r"C:/Users/Prekzursil/AppData/Local/Ollama/db.sqlite"
c = sqlite3.connect(DB)
before = c.execute("select id, expose from settings").fetchall()
print("before:", before)
c.execute("update settings set expose=0 where expose<>0")
c.commit()
after = c.execute("select id, expose from settings").fetchall()
print("after:", after)
c.close()
