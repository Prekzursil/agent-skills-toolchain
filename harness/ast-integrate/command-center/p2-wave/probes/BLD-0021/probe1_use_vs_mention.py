#!/usr/bin/env python3
"""Probe 1: use-vs-mention. Fenced/quoted/inline must be MENTION, not USE.

Both-states: the same spans classify as USE (or other non-MENTION) when
mention detection is disabled. A detector that is silent in both states
measures nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import resolver as R  # noqa: E402
import scenario as S  # noqa: E402
from schema_offline import payload  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0021.json"


def main() -> int:
    S.ensure_fixtures()
    decls = R.load_registries(S.registry_paths())
    on = R.sweep_files(S.corpus_files(), decls, detect_mentions=True)
    off = R.sweep_files(S.corpus_files(), decls, detect_mentions=False)

    mentions = [r for r in on if r.classification == "MENTION"]
    reasons = {r.mention_reason for r in mentions}
    print(
        json.dumps(
            {
                "mention_count": len(mentions),
                "reasons": sorted(x for x in reasons if x),
                "tokens": sorted({r.token for r in mentions}),
            },
            sort_keys=True,
        )
    )
    if "fenced-code" not in reasons:
        print("FAILED:BLD-0021-probe1 no fenced-code MENTION")
        return 1
    if "quoted-example" not in reasons:
        print("FAILED:BLD-0021-probe1 no quoted-example MENTION")
        return 1
    if "inline-code" not in reasons:
        print("FAILED:BLD-0021-probe1 no inline-code MENTION")
        return 1
    if any(r.classification != "MENTION" for r in mentions):
        print("FAILED:BLD-0021-probe1 mention list mixed")
        return 1

    keys = {(r.path, r.line, r.start, r.token) for r in mentions}
    off_map = {(r.path, r.line, r.start, r.token): r for r in off}
    flipped = 0
    for key in keys:
        other = off_map.get(key)
        if other is None:
            print(f"FAILED:BLD-0021-probe1 span missing with detection off {key}")
            return 1
        if other.classification == "MENTION":
            print(f"FAILED:BLD-0021-probe1 still MENTION with detection off {key}")
            return 1
        flipped += 1
    if flipped < 3:
        print(f"FAILED:BLD-0021-probe1 both-states flipped={flipped}")
        return 1

    ones = [
        r
        for r in on
        if r.token == "M-8" and r.classification == "RESOLVES-ONE"
    ]
    if not ones:
        print("FAILED:BLD-0021-probe1 discriminated option M-8 not RESOLVES-ONE")
        return 1
    if ones[0].candidates[0]["namespace_id"] != "option-universe":
        print("FAILED:BLD-0021-probe1 M-8 resolved to the wrong namespace")
        return 1

    if not ART.is_file():
        print("FAILED:BLD-0021-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = payload(doc)
    if body.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:BLD-0021-probe1 self-declared {body.get('state')}")
        return 1
    if body.get("mention_not_use_proven") is not True:
        print("FAILED:BLD-0021-probe1 artifact mention_not_use_proven is not true")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:BLD-0021" not in text:
        print("FAILED:BLD-0021-probe1 sentinel absent")
        return 1
    art_mentions = [
        row
        for row in body.get("references") or []
        if row.get("classification") == "MENTION"
    ]
    if len(art_mentions) != len(mentions):
        print(
            f"FAILED:BLD-0021-probe1 artifact mentions {len(art_mentions)} "
            f"!= live {len(mentions)}"
        )
        return 1
    print(f"both_states_flipped={flipped}")
    print("SUCCESS:BLD-0021-probe1 use-vs-mention")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
