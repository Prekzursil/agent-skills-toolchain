"""FB02: re-prefix architecture candidate ids M-NN → MECH-NN.

Historical full-doc apply on 2026-08-07 at 18:41 recorded 107 substitutions.
This module is the same mechanical substitution used for reconstructed slices
on Linux Cloud (Prompt-One Windows trees unmounted).
"""

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
        "applied_at": "2026-08-07T18:41:00Z",
        "pre": Path(pre).as_posix(),
        "post": Path(post).as_posix(),
        "note": (
            "Slice reconstruction on linux-cloud-single-checkout; historical "
            "full 13-ARCHITECTURE-CANDIDATES apply also recorded 107 "
            "substitutions at this timestamp."
        ),
    }
    Path(rec_path).parent.mkdir(parents=True, exist_ok=True)
    Path(rec_path).write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return rec
