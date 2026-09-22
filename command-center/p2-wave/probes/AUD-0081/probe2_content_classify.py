#!/usr/bin/env python3
"""AUD-0081 named probe 2: content-classify every probe 1 hit as inert
documentation vs an active hook or MCP registration.

Catalog evidence_requirement (verbatim, probe 2 half): "a content read of
each hit classifying it as inert documentation versus an active hook or
MCP registration - the presence of a file named CLAUDE.md is not by
itself a risk finding." This probe reads probe 1's real hit list off disk
(never re-derives it) and runs _autoload_classifier.classify_hit on the
REAL bytes of each hit -- the same function exercised by the
tests_required control, so this is not a hand-waved "looks fine" pass.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _autoload_classifier as C  # noqa: E402

REPO = Path(__file__).resolve().parents[4]
PROBE1_JSON = Path(__file__).resolve().parent / "probe1-filename-search.json"
OUT_JSON = Path(__file__).resolve().parent / "probe2-content-classification.json"
OUT_RAW = Path(__file__).resolve().parent / "probe2-content-classification.raw.txt"


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not PROBE1_JSON.is_file():
        print(f"FAILED:AUD-0081-probe2 probe1 output missing at {PROBE1_JSON}")
        return 1
    p1 = json.loads(PROBE1_JSON.read_text(encoding="utf-8"))
    hits = p1.get("hits", [])

    classified: list[dict] = []
    for h in hits:
        abs_path = REPO / h["path"]
        result = C.classify_hit(abs_path, h["matched_name"], h["kind"])
        classified.append(
            {
                "path": h["path"],
                "vendored_root": h["vendored_root"],
                "kind": h["kind"],
                "matched_name": h["matched_name"],
                "classification": result["classification"],
                "reason": result["reason"],
            }
        )

    active = [c for c in classified if c["classification"] == "active"]
    mention_only = [c for c in classified if c["classification"] == "mention-only"]
    inert = [c for c in classified if c["classification"] == "inert"]

    doc = {
        "ok": True,
        "started_at": started,
        "probe1_source": "probe1-filename-search.json",
        "probe1_hits_count": len(hits),
        "classified": classified,
        "classified_count": len(classified),
        "active_count": len(active),
        "mention_only_count": len(mention_only),
        "inert_count": len(inert),
        "active_hits": active,
        "mention_only_hits": mention_only,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    lines = [
        "SUCCESS:AUD-0081-probe2",
        f"unit=AUD-0081 probe=2 classified_count={len(classified)} "
        f"active_count={len(active)} mention_only_count={len(mention_only)} "
        f"inert_count={len(inert)}",
        "--- per-hit classification ---",
    ]
    for c in classified:
        lines.append(f"{c['classification']:12s} {c['path']} :: {c['reason']}")
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
