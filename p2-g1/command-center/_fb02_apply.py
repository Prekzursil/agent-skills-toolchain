"""FB02: re-prefix architecture candidate ids M-NN → MECH-NN."""
from __future__ import annotations

import json
import re
from pathlib import Path

_ID = re.compile(r"\bM-(\d{2})\b")


def apply(pre: Path, post: Path, rec_path: Path) -> dict:
    text = Path(pre).read_text(encoding="utf-8")
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f"MECH-{match.group(1)}"

    out = _ID.sub(repl, text)
    Path(post).parent.mkdir(parents=True, exist_ok=True)
    Path(post).write_text(out, encoding="utf-8")
    rec = {
        "id": "FB02",
        "from_prefix": "M-",
        "to_prefix": "MECH-",
        "substitutions": count,
        "pre": Path(pre).as_posix(),
        "post": Path(post).as_posix(),
    }
    Path(rec_path).parent.mkdir(parents=True, exist_ok=True)
    Path(rec_path).write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return rec
