"""Parse UNKNOWNS-REGISTER.md into structured rows. Missing file => empty."""
from __future__ import annotations

import re
from pathlib import Path

_H2 = re.compile(r"^##\s+(\S+)\s*$")


def parse_text(text: str) -> list[dict]:
    rows: list[dict] = []
    current: dict | None = None
    buf_key = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        h2 = _H2.match(line)
        if h2:
            if current:
                rows.append(_finalise(current))
            current = {
                "id": h2.group(1),
                "unknown": "",
                "experiment": "",
                "impact": "",
                "source": "",
            }
            buf_key = ""
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            stripped = stripped[2:]
        m = re.match(
            r"^(unknown|experiment|impact|source)\s*:\s*(.*)$",
            stripped,
            re.IGNORECASE,
        )
        if m:
            buf_key = m.group(1).lower()
            current[buf_key if buf_key != "unknown" else "unknown"] = m.group(2)
            continue
        if buf_key and stripped:
            current[buf_key] = (current.get(buf_key) or "") + "\n" + stripped
    if current:
        rows.append(_finalise(current))
    return rows


def _finalise(row: dict) -> dict:
    exp = (row.get("experiment") or "").strip()
    command = _line(exp, "command")
    input_ = _line(exp, "input")
    observation = _line(exp, "observation")
    experiment: dict | str
    if command or input_ or observation:
        experiment = {
            "command": command,
            "input": input_,
            "observation": observation,
            "raw": exp,
        }
    else:
        experiment = exp
    return {
        "id": row["id"],
        "unknown": (row.get("unknown") or "").strip(),
        "experiment": experiment,
        "impact": (row.get("impact") or "").strip(),
        "source": (row.get("source") or "").strip(),
    }


def _line(text: str, label: str) -> str:
    m = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+)$", text)
    return m.group(1).strip().strip("`") if m else ""


def parse_file(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return parse_text(path.read_text(encoding="utf-8"))


parse_file = parse_file
