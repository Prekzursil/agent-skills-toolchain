#!/usr/bin/env python3
"""Probe 2: semantic configuration diff, independent of migrate() exit codes.

Mechanically different from probe 1: this probe never classifies on exception
type. It canonicalizes the user-authored payload (extra keys + out-of-enum
layout + live key path) before and after the same engine, plus a planted
wipe that must fire and a planted preserve that must stay quiet.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from fixture_matrix import (  # noqa: E402
    USER_KEY,
    USER_MARK,
    lost_user_keys,
    run_one,
    seed_variant,
    user_surface,
)
from plugin.migration import demo_engine, dump_json  # noqa: E402

UNIT = "ADV-0121"
ART = REPO / "command-center/adversarial/ADV-0121-upgrade-from-handedited-config.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def canonical(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="adv0121-p2-") as tmp:
        parent = Path(tmp)
        live = {vid: run_one(parent / "live", vid) for vid in (
            "pristine",
            "unknown-key",
            "reordered",
            "comments",
            "crlf",
            "enum-out-of-range",
        )}

        # Planted wipe: migrate unknown-key, then delete the user key from the
        # post config. The semantic diff must name USER_KEY. This is the
        # both-states detector (quiet on real unknown-key preserve, loud on wipe).
        plant_root = seed_variant(parent / "plant-wipe", "unknown-key")
        demo_engine().migrate(
            plant_root, "3", journal=parent / "plant-wipe.journal.json"
        )
        post_path = plant_root / "config.json"
        post_doc = json.loads(post_path.read_text(encoding="utf-8"))
        before_wipe = user_surface(post_doc)
        post_doc.pop(USER_KEY, None)
        post_path.write_text(dump_json(post_doc), encoding="utf-8")
        after_wipe = user_surface(
            json.loads(post_path.read_text(encoding="utf-8"))
        )
        planted_lost = lost_user_keys(before_wipe, after_wipe)

        preserve = live["unknown-key"]
        preserve_lost = [
            k for k in (preserve["lost_user_keys"] or []) if k != "$unparseable-pre"
        ]
        enum_lost = live["enum-out-of-range"]["lost_user_keys"] or []
        pristine_lost = [
            k
            for k in (live["pristine"]["lost_user_keys"] or [])
            if k != "$unparseable-pre"
        ]
        comments_pre = live["comments"]["pre_user"]

    plant_fired = USER_KEY in planted_lost
    preserve_quiet = USER_KEY not in preserve_lost and preserve["migrated"]
    enum_named = "$layout_user_enum" in enum_lost
    pristine_quiet = pristine_lost == []
    comments_unparseable = comments_pre is None

    diffs = {
        vid: {
            "pre_user": row["pre_user"],
            "post_user": row["post_user"],
            "lost_user_keys": row["lost_user_keys"],
            "pre_canonical": canonical(row["pre_user"]) if row["pre_user"] is not None else None,
            "post_canonical": canonical(row["post_user"]) if row["post_user"] is not None else None,
            "byte_identical_user": (
                canonical(row["pre_user"]) == canonical(row["post_user"])
                if row["pre_user"] is not None and row["post_user"] is not None
                else False
            ),
        }
        for vid, row in live.items()
    }

    payload = {
        "probe": "probe2-semantic-diff",
        "unit_id": UNIT,
        "method": "canonical-json-user-surface-not-exit-code",
        "planted_wipe_lost": planted_lost,
        "planted_wipe_fired": plant_fired,
        "unknown_key_preserved": preserve_quiet,
        "enum_user_layout_lost": enum_named,
        "pristine_no_user_loss": pristine_quiet,
        "comments_pre_unparseable": comments_unparseable,
        "diffs": diffs,
        "ok": bool(
            plant_fired
            and preserve_quiet
            and enum_named
            and pristine_quiet
            and comments_unparseable
        ),
    }
    print(json.dumps(payload, sort_keys=True, default=str))

    if not plant_fired:
        return fail(f"planted wipe did not name {USER_KEY}: {planted_lost}")
    if not preserve_quiet:
        return fail(f"unknown-key extra value {USER_MARK} was not preserved: {preserve_lost}")
    if not enum_named:
        return fail(f"enum silent loss not visible in semantic diff: {enum_lost}")
    if not pristine_quiet:
        return fail(f"pristine control showed user-key loss: {pristine_lost}")
    if not comments_unparseable:
        return fail("comments fixture parsed; probe 2 cannot see JSONC as unparseable")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"artifact self-declared {st}")

    print(
        "SUCCESS:ADV-0121-probe2 semantic-diff "
        f"plant_fired={plant_fired} preserve={preserve_quiet} "
        f"enum_lost={enum_named}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
