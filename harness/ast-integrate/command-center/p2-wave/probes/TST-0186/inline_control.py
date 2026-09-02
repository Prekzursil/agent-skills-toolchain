#!/usr/bin/env python3
"""Both-states control: deliberately inline prose, expect unmatched-quote EOF.

Naive wrap: git commit -m '<payload>' written as a shell script and handed
to bash. A payload with an odd number of apostrophes leaves bash with:

  unexpected EOF while looking for matching `''

which is the catalog's `unexpected EOF while looking for matching quote`
failure class. The file route in runner.py is the supported state.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

# Live GNU bash 5.x: "... unexpected EOF while looking for matching `''"
EOF_PHRASE = "unexpected EOF while looking for matching"
# Catalog paraphrases the closing token as "quote".
CATALOG_EOF_CLASS = "unexpected EOF while looking for matching quote"


def naive_commit_script(payload: str) -> str:
    return "git commit -m '" + payload + "'\n"


def run_inline_script(payload: str, workdir: Path) -> dict:
    script = naive_commit_script(payload)
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / "inline-commit.sh"
    path.write_text(script, encoding="utf-8")
    proc = subprocess.run(
        ["bash", str(path)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    stderr = proc.stderr or ""
    stdout = proc.stdout or ""
    combined = stderr + stdout
    return {
        "payload": payload,
        "script": script,
        "script_path": str(path),
        "returncode": proc.returncode,
        "stdout": stdout[:400],
        "stderr": stderr[:800],
        "stderr_head": stderr[:240],
        "eof_phrase_live": EOF_PHRASE in combined,
        "catalog_class": CATALOG_EOF_CLASS,
        "payload_in_stdout": payload in stdout,
        "control_holds": (
            proc.returncode != 0
            and EOF_PHRASE in combined
            and payload not in stdout
        ),
    }
