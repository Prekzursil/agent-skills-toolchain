#!/usr/bin/env python3
"""Probe 1: migrate each hostile N-2 variant and classify the live outcome.

Classification is from migrate() status / exception type (crashed vs refused
vs complete). Strict-parser refusal is recorded as a separate column so a
SUCCESS migrate of a document the frozen schema rejects is visible.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from fixture_matrix import VARIANT_IDS, run_one  # noqa: E402

UNIT = "ADV-0121"
ART = (
    HERE.parents[3]
    / "command-center/adversarial/ADV-0121-upgrade-from-handedited-config.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="adv0121-p1-") as tmp:
        parent = Path(tmp)
        for vid in VARIANT_IDS:
            rows.append(run_one(parent, vid))

    by_id = {r["variant"]: r for r in rows}
    control = by_id["pristine"]
    comments = by_id["comments"]
    unknown = by_id["unknown-key"]
    enum_row = by_id["enum-out-of-range"]
    reordered = by_id["reordered"]
    crlf = by_id["crlf"]

    control_ok = (
        control["migrated"] is True
        and control["current_version"] == "3"
        and control["outcome"] == "migrated_ok"
        and not control["silent_loss"]
        and control["pre_strict"]["schema_ok"]
    )
    comments_crashed = comments["outcome"] == "crashed"
    comments_clear = comments["outcome"] == "refused_clear"
    unknown_migrated = unknown["migrated"] is True
    unknown_strict_pre_red = unknown["pre_strict"]["schema_ok"] is False
    unknown_strict_post_red = unknown["post_strict"]["schema_ok"] is False
    enum_silent = enum_row["silent_loss"] is True and "$layout_user_enum" in (
        enum_row["lost_user_keys"] or []
    )
    reordered_ok = reordered["migrated"] is True and not reordered["silent_loss"]
    crlf_ok = crlf["migrated"] is True and not crlf["silent_loss"] and crlf["pre_crlf"]

    # Three documents the strict parser refuses: unknown-key (pre and post),
    # comments (unparseable), enum-out-of-range (pre enum). Migration still
    # reports complete for unknown-key and enum.
    strict_refused_ids = [
        r["variant"]
        for r in rows
        if (not r["pre_strict"]["parse_ok"]) or (not r["pre_strict"]["schema_ok"])
    ]
    success_despite_strict = [
        r["variant"]
        for r in rows
        if r["migrated"] and not r["pre_strict"]["schema_ok"]
    ]

    payload = {
        "probe": "probe1-migration-matrix",
        "unit_id": UNIT,
        "control_pristine_migrates": control_ok,
        "comments_crashed": comments_crashed,
        "comments_refused_clearly": comments_clear,
        "unknown_key_migrated": unknown_migrated,
        "unknown_key_strict_pre_red": unknown_strict_pre_red,
        "unknown_key_strict_post_red": unknown_strict_post_red,
        "enum_silent_loss": enum_silent,
        "reordered_semantic_ok": reordered_ok,
        "crlf_semantic_ok": crlf_ok,
        "engine_validates_config": False,
        "strict_parser_refused_pre": strict_refused_ids,
        "migrate_complete_despite_strict_red": success_despite_strict,
        "rows": rows,
        "ok": bool(
            control_ok
            and comments_crashed
            and unknown_migrated
            and unknown_strict_pre_red
            and enum_silent
            and reordered_ok
            and crlf_ok
        ),
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    if not control_ok:
        return fail("pristine N-2 control did not migrate cleanly")
    if not comments_crashed and not comments_clear:
        return fail("comments variant neither crashed nor refused")
    if not unknown_strict_pre_red:
        return fail("unknown-key control: strict parser accepted extra key")
    if not enum_silent:
        return fail("enum-out-of-range did not silently lose $layout_user_enum")
    if not reordered_ok:
        return fail("reordered sections lost user content or failed to migrate")
    if not crlf_ok:
        return fail("crlf variant not a CRLF file or lost user content")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"artifact self-declared {st}")

    print(
        "SUCCESS:ADV-0121-probe1 matrix "
        f"control={control_ok} comments={comments['outcome']} "
        f"strict_red_pre={strict_refused_ids} "
        f"success_despite_strict={success_despite_strict}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
