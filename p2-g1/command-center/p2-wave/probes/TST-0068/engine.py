#!/usr/bin/env python3
"""TST-0068 engine: interpreter-declaration census and classification.

classify_entries() splits manifest/plugin entries into
declares_interpreter (script with interpreter field, or command argv
form whose argv[0] is an interpreter) vs relies_on_shebang (script by
bare path). census_file() audits a manifest.json or plugin.json."""
from __future__ import annotations

import json
from pathlib import Path

INTERPRETERS = {"bash", "sh", "python", "python3", "pwsh", "powershell", "node", "python.exe", "bash.exe"}


def _classify(row: dict) -> dict:
    cmd = row.get("command")
    script = row.get("script") or ""
    interp = row.get("interpreter")
    if isinstance(cmd, list) and cmd:
        head = str(cmd[0])
        declares = head.casefold() in INTERPRETERS
        return {"id": row.get("id"), "script": " ".join(str(x) for x in cmd[1:2]) or script,
                "interpreter": head if declares else None, "declares_interpreter": declares,
                "relies_on_shebang": not declares, "runtime": "argv", "kind": row.get("kind", "hook")}
    if isinstance(cmd, str) and cmd:
        head = cmd.strip().split()[0].strip(chr(34)) if cmd.strip() else ""
        declares = head.casefold() in INTERPRETERS or bool(interp)
        return {"id": row.get("id"), "script": cmd, "interpreter": head if declares else None,
                "declares_interpreter": declares, "relies_on_shebang": not declares,
                "runtime": "argv-or-interpreter-field", "kind": row.get("kind", "hook")}
    declares = bool(interp)
    return {"id": row.get("id"), "script": script, "interpreter": interp,
            "declares_interpreter": declares, "relies_on_shebang": (bool(script) and not declares),
            "runtime": "argv-or-interpreter-field", "kind": row.get("kind", "hook")}


def census_document(doc: dict, source: str) -> dict:
    rows = []
    for h in doc.get("hooks") or []:
        if isinstance(h, str):
            r = {"id": h, "script": h, "interpreter": None, "declares_interpreter": False,
                 "relies_on_shebang": True, "runtime": "bare-path", "kind": "hook"}
        else:
            r = _classify({**h, "kind": "hook"})
        r["source"] = source
        rows.append(r)
    for c in doc.get("commands") or []:
        r = _classify({**c, "kind": "plugin-command"})
        r["source"] = source
        rows.append(r)
    for ev, block in (doc.get("events") or {}).items():
        for chk in block.get("checks") or []:
            r = _classify({**chk, "kind": "dispatch-check", "event": ev})
            r["source"] = source
            rows.append(r)
    reliant = [r for r in rows if r["relies_on_shebang"]]
    return {"count": len(rows), "entries": rows,
            "declares_interpreter_count": sum(1 for r in rows if r["declares_interpreter"]),
            "shebang_reliant_count": len(reliant),
            "shebang_reliant_ids": [r["id"] for r in reliant],
            "all_declare_interpreter": bool(rows) and not reliant}


def census_file(path: Path, source: str) -> dict | None:
    if not path.is_file():
        return None
    return census_document(json.loads(path.read_text(encoding="utf-8")), source)
