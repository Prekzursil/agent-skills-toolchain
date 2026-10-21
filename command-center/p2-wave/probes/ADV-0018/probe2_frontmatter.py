"""ADV-0018 Probe 2 (mechanically different): frontmatter audit for superseded_by /
valid_as_of on every contradicted note, computed from the FILE rather than from the
search snippet.

Mechanical independence from Probe 1: probe 1 compares note TEXT against live repo
measurements; this probe never measures the repo — it parses the contradicted note's
own YAML head from disk and asks the temporal-validity question the estate convention
defines (superseded_by on the old note, valid_as_of dating).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from shared import parse_frontmatter, write_raw


def detector(note_path: Path) -> dict:
    """The single frontmatter detector used by BOTH probe 2 and the negative control,
    so the control exercises the instrument actually shipping (not a twin)."""
    text = note_path.read_text(encoding="utf-8", errors="replace")
    fm = parse_frontmatter(text)
    superseded_by = fm.get("superseded_by", "").strip()
    valid_as_of = fm.get("valid_as_of", "").strip()
    # body-level valid_as_of (the estate also writes it as a body bullet)
    body_vao = ""
    for line in text.splitlines():
        if line.strip().startswith("- valid_as_of:"):
            body_vao = line.split(":", 1)[1].strip()
            break
    return {
        "note": str(note_path),
        "frontmatter_keys": sorted(fm.keys()),
        "superseded_by": superseded_by or None,
        "valid_as_of": valid_as_of or body_vao or None,
        "fires": not superseded_by,  # RED: contradicted note still recallable as truth
    }


def main() -> int:
    probe1 = Path(__file__).resolve().parent / "probe1-topic-retrieval.json"
    if not probe1.is_file():
        print("FAILED: probe1 raw output missing; run probe1_topic_diff.py first")
        return 2
    contradicted = json.loads(probe1.read_text(encoding="utf-8"))["contradicted_notes"]
    rows = [detector(Path(n)) for n in contradicted]
    unpointed = [r for r in rows if r["fires"]]
    payload = {
        "probe": "probe2-frontmatter-audit",
        "contradicted_note_count": len(contradicted),
        "pointer_present": [r["note"] for r in rows if not r["fires"]],
        "pointer_absent": [r["note"] for r in unpointed],
        "rows": rows,
    }
    out = [f"SUCCESS:adv0018-probe2 {len(contradicted)} contradicted notes audited from file; "
           f"{len(unpointed)} lack superseded_by"]
    for r in rows:
        out.append(f"  {Path(r['note']).name}: superseded_by={r['superseded_by']} "
                   f"valid_as_of={r['valid_as_of']} fires={r['fires']}")
    text_out = "\n".join(out) + "\n"
    print(text_out, end="")
    write_raw("probe2-frontmatter-audit", payload, text_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
