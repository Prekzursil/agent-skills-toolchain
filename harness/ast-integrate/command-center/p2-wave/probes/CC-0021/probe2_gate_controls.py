#!/usr/bin/env python3
"""Probe 2: planted gate fire, use-vs-mention silence, independent regex.

Known-broken: a planted bare M-<harness> in a scratch file must make the gate fire.
Use-vs-mention: a document quoting the collision to describe it must not be
flagged as carrying an unresolved id.
Reviewer: a different regex construction must agree on the estate counts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import estate_silent, mention_silent, planted_fires, regex_agree  # noqa: E402

ART = REPO / "command-center/receipts/CC-0021.json"
SENTINEL = "SUCCESS:CC-0021"


def main() -> int:
    planted = planted_fires()
    mention = mention_silent()
    estate = estate_silent()
    agree = regex_agree()
    print(
        json.dumps(
            {
                "planted_fires": {
                    k: planted[k] for k in ("fired", "ambiguous_use_count", "ok")
                },
                "mention_silent": {
                    k: mention[k] for k in ("fired", "m_hits", "mentions", "ok")
                },
                "estate_silent": {
                    k: estate[k] for k in ("fired", "ambiguous_use_count", "ok")
                },
                "regex_agree": {
                    k: agree[k]
                    for k in ("primary", "reviewer", "ok", "only_primary", "only_reviewer")
                },
            },
            sort_keys=True,
        )
    )
    if not planted["ok"]:
        print(f"FAILED:CC-0021-probe2 planted did not fire {planted}")
        return 1
    if not mention["ok"]:
        print(f"FAILED:CC-0021-probe2 mention not silent {mention}")
        return 1
    if not estate["ok"]:
        print(f"FAILED:CC-0021-probe2 declared estate not silent {estate}")
        return 1
    if not agree["ok"]:
        print(f"FAILED:CC-0021-probe2 regex disagreement {agree}")
        return 1
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CC-0021-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CC-0021-probe2 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:CC-0021-probe2 sentinel absent")
        return 1
    print(
        f"planted_fired={planted['fired']} mention_fired={mention['fired']} "
        f"estate_fired={estate['fired']} regex_n={agree['primary']}"
    )
    print("SUCCESS:CC-0021-probe2 gate controls and reviewer regex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
