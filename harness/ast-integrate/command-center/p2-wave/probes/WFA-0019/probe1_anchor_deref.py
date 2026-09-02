#!/usr/bin/env python3
"""Probe 1: every cited file:line is dereferenced and compared to content.

Exists-only is the known-bad control: the fabricated 08/10 anchors point at
real files whose cited lines do not contain the claimed token. Content mode
must reject them; exists-only would wrongly accept them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sweep as S  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0019-sweep-prior-artifacts.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0019-probe1 {msg}")
    return 1


def main() -> int:
    if not OUT.is_file():
        return fail("artifact-missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    fixture_root = Path(doc["fixture_corpus_root"])
    if not fixture_root.is_dir():
        return fail("fixture-root-missing")

    anchors = []
    for row in doc.get("extracted_constructs") or []:
        anchors.append(
            (
                "extracted",
                row["anchor"],
                row["id"],
                True,
                row.get("snippet") or row["id"],
            )
        )
    for row in doc.get("dropped_mechanisms") or []:
        loc = row["defined_at"]
        anchors.append(
            ("dropped", loc["anchor"], row["id"], True, loc.get("snippet") or row["id"])
        )
    for row in doc.get("confirmed_anchors") or []:
        anchors.append(
            ("confirmed", row["src"], row["claimed"], True, row["claimed"])
        )
    for row in doc.get("fabricated_anchors") or []:
        anchors.append(
            ("fabricated", row["src"], row["claimed"], False, row["claimed"])
        )

    if len(anchors) < 6:
        return fail(f"too-few-anchors n={len(anchors)}")

    content_ok = 0
    content_bad_correctly = 0
    exists_wrongly_ok = 0
    for kind, src, claimed, want_ok, token in anchors:
        if not src:
            return fail(f"{kind} missing src")
        content = S.verify_anchor(fixture_root, src, token, mode="content")
        exists = S.verify_anchor(fixture_root, src, token, mode="exists-only")
        print(
            f"anchor kind={kind} src={src} claimed={claimed!r} "
            f"content_ok={content['ok']} exists_ok={exists['ok']} "
            f"line={content.get('line_content')!r}"
        )
        if want_ok:
            if not content["ok"]:
                return fail(f"good-anchor-content-miss {kind} {src}")
            content_ok += 1
        else:
            if content["ok"]:
                return fail(f"fabricated-accepted-by-content {kind} {src}")
            content_bad_correctly += 1
            if exists["ok"]:
                exists_wrongly_ok += 1

    if content_ok < 3:
        return fail(f"too-few-good-content-hits {content_ok}")
    if content_bad_correctly < 2:
        return fail(f"too-few-fabricated-rejects {content_bad_correctly}")
    if exists_wrongly_ok < 2:
        return fail(
            "exists-only-control-did-not-fire "
            f"wrongly_ok={exists_wrongly_ok} (need fabricated files that exist)"
        )

    # Both-states: mutating a good snippet must flip content mode.
    good = next(a for a in anchors if a[0] == "extracted" and a[3])
    mutated = S.verify_anchor(fixture_root, good[1], "THIS-SNIPPET-IS-NOT-ON-THE-LINE", mode="content")
    if mutated["ok"]:
        return fail("mutated-snippet-still-matched")
    print(
        f"both-states good_content={content_ok} fabricated_content_reject={content_bad_correctly} "
        f"exists_only_false_accept={exists_wrongly_ok} mutant_rejected=True"
    )
    print("SUCCESS:WFA-0019-probe1 anchor-deref content-compare")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
