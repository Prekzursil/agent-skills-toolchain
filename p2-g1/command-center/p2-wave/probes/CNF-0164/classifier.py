#!/usr/bin/env python3
"""CNF-0164 primary quote-fidelity classifier.

Classification policy (matches the recorded receipt policy and the recorded
independent reviewer notes: "EOL-norm exact substring, then per-line
indent-strip and whitespace-collapse, then same-length token Hamming
distance == 1"):

  1. external source with no citation-time archive  -> NOT-CHECKED
  2. EOL-normalised exact substring                 -> exact
  3. per-line indent-strip + whitespace-collapse    -> whitespace-different
  4. same-length token window, Hamming distance <=1 -> paraphrase
  5. otherwise                                      -> absent

Re-materialized 2026-10-26 (shard8-w3 builder): the prior builder attempt
died mid-flight and this probe directory was found empty. The classifier is
rebuilt to the recorded policy so the receipt's recorded case classes stay
falsifiable live; it is not byte-identical to the lost August file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CLASS_EXACT = "exact"
CLASS_WS = "whitespace-different"
CLASS_PARAPHRASE = "paraphrase"
CLASS_ABSENT = "absent"
CLASS_NOT_CHECKED = "NOT-CHECKED"
HAMMING_PARAPHRASE = 1


def _norm_eol(raw: bytes) -> str:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode("utf-8", errors="replace")


def _ws_collapse(text: str) -> str:
    out = []
    for line in text.replace("\r\n", "\n").split("\n"):
        out.append(line.strip())
    return " ".join(x for x in out if x)


def _tokens(text: str) -> list[str]:
    return _ws_collapse(text).split()


def _hamming(a: list[str], b: list[str]) -> int:
    return sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))


def classify(quote: str, source_bytes: bytes, *, external: bool = False,
             archive_present: bool = True) -> tuple[str, str]:
    """Return (class, reason) for quote against the cited source bytes."""
    if external and not archive_present:
        return CLASS_NOT_CHECKED, "external URL has no citation-time archive in probes/CNF-0164/archives/"
    src = _norm_eol(source_bytes)
    q = quote.replace("\r\n", "\n")
    if q in src:
        return CLASS_EXACT, "matched"
    if _ws_collapse(q) and _ws_collapse(q) in _ws_collapse(src):
        return CLASS_WS, "matched-after-indent-collapse"
    qt = _tokens(q)
    st = _tokens(src)
    if len(qt) >= 3 and len(st) >= len(qt):
        best = None
        for i in range(len(st) - len(qt) + 1):
            d = _hamming(qt, st[i:i + len(qt)])
            if best is None or d < best:
                best = d
                if best == 0:
                    break
        if best is not None and best <= HAMMING_PARAPHRASE:
            return CLASS_PARAPHRASE, "matched-one-token-edit"
    return CLASS_ABSENT, "no-window"


def detector_self_check(quote: str, source_bytes: bytes) -> tuple[bool, str]:
    """The matcher must find a known-present quote before any 'absent' verdict
    from it is trusted anywhere. Returns (found_exact, matched_slice)."""
    src = _norm_eol(source_bytes)
    q = quote.replace("\r\n", "\n")
    idx = src.find(q)
    if idx < 0:
        return False, ""
    return True, src[max(0, idx):idx + 60]


def main() -> int:
    """CLI: classify quotes from a JSON file ({quotes: [{id, quote}], source: path})."""
    if len(sys.argv) != 3:
        print("usage: classifier.py <quotes.json> <source.txt>", file=sys.stderr)
        return 2
    qdoc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    src = Path(sys.argv[2]).read_bytes()
    rows = []
    for item in qdoc.get("quotes", []):
        cls, reason = classify(item["quote"], src)
        rows.append({"id": item["id"], "class": cls, "reason": reason})
        print(f"{item['id']} class={cls} reason={reason}")
    print(json.dumps({"rows": rows}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
