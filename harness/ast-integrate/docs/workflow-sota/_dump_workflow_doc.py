"""Dump the Workflow-tool documentation block embedded in claude.exe (read-only).
Writes the decoded text to docs/workflow-sota/RUNTIME-API-DUMP.txt."""

from pathlib import Path

BIN = Path(r"C:/Users/Prekzursil/.local/bin/claude.exe")
OUT = Path(
    r"C:/Users/Prekzursil/source/ast-integrate/docs/workflow-sota/RUNTIME-API-DUMP.txt"
)

START = 269_016_000
LENGTH = 26_000

with BIN.open("rb") as fh:
    fh.seek(START)
    raw = fh.read(LENGTH)

text = raw.decode("utf-8", "replace")
OUT.write_text(text, encoding="utf-8")
print(f"wrote {OUT} ({len(text)} chars) from offset {START}")
print(text[:1500])
