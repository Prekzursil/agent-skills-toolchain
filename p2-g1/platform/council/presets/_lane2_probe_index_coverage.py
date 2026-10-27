"""Which of doc 12's 72 preset cards actually have a file on disk?

Mechanical: parse the card ids out of the design doc's own headings, then match
each against the *.councilspec.json filenames present. No judgement.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOC = Path(
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
)

CARD_RE = re.compile(r"^#### (C-[A-Z]\d+) `([a-z0-9-]+)`", re.M)


def main() -> int:
    text = DOC.read_text(encoding="utf-8", errors="replace")
    cards = CARD_RE.findall(text)
    names = [p.name for p in HERE.glob("*.councilspec.json")]
    lower = [n.lower() for n in names]

    rows = []
    for card_id, slug in cards:
        # index is the digits in the card id; C-M01 -> 1, C-H72 -> 72
        idx = int(re.search(r"\d+", card_id).group())
        token = card_id.lower() + "-"
        hit = next((n for n, low in zip(names, lower) if low.startswith(token)), None)
        if hit is None:
            # some lanes named files after the slug rather than the card id
            hit = next((n for n, low in zip(names, lower) if slug in low), None)
        rows.append({"index": idx, "card": card_id, "slug": slug, "file": hit})

    present = [r for r in rows if r["file"]]
    absent = [r for r in rows if not r["file"]]
    print(f"cards in doc 12            : {len(rows)}")
    print(f"cards WITH a file on disk  : {len(present)}")
    print(f"cards WITHOUT a file       : {len(absent)}")
    print("absent card indices        : " + str([r["index"] for r in absent]))
    for r in absent:
        print(f"   MISSING idx={r['index']:>2} {r['card']} `{r['slug']}`")
    extra = len(names) - len(present)
    print(f"files not matched to a card: {extra} (gap-fills + naming variants)")

    (HERE / "_lane2_probe_index_coverage_out.json").write_text(
        json.dumps(
            {
                "cards_total": len(rows),
                "cards_with_file": len(present),
                "cards_without_file": [
                    {"index": r["index"], "card": r["card"], "slug": r["slug"]}
                    for r in absent
                ],
                "files_total": len(names),
                "files_unmatched": extra,
                "rows": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        "SUCCESS:index-coverage measured"
        if rows
        else "FAILED:index-coverage no cards parsed - the detector is broken"
    )
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
