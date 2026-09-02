#!/usr/bin/env python3
"""Probe 1: scripted vN→vN+1 upgrade in a throwaway HOME; the user edit survives.

Catalog evidence (1): a user-edited file is present across the version boundary.
Existence alone is not enough — the unique override bytes must still be in the
file, and vN+1's new setting must land in the same document.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import update as upd  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0024.json"
UNIT = "IMP-0024"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0024-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:IMP-0024" not in text:
        print("FAILED:IMP-0024-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0024-probe1 self-declared", doc.get("state"))
        return 1

    v1, v2, v3 = upd.payload_v1(), upd.payload_v2(), upd.payload_v3()
    with tempfile.TemporaryDirectory(prefix="imp0024-p1-") as td:
        root = Path(td) / "home"
        upd.seed_live_tree(root, v1, version="1.0.0")
        ours = upd.apply_user_override(root)
        pre_notes = ours["notes.md"]
        pre_settings = json.loads(ours["settings.json"].decode("utf-8"))
        if pre_settings.get("accent") != upd.USER_ACCENT_VALUE:
            print("FAILED:IMP-0024-probe1 user edit did not plant")
            return 1
        if upd.USER_NOTE_LINE.encode("ascii") not in pre_notes:
            print("FAILED:IMP-0024-probe1 unique notes line did not plant")
            return 1

        r12 = upd.update(
            root,
            base_payload=v1,
            theirs_payload=v2,
            from_version="1.0.0",
            to_version="1.1.0",
        )
        if not r12.proceeded or r12.wrote is False:
            print("FAILED:IMP-0024-probe1 v1->v2 did not apply")
            print(json.dumps(r12.as_dict(), default=str)[:2000])
            return 1
        notes_after_v2 = (root / "notes.md").read_bytes()
        settings_v2 = upd.parsed_settings(root)
        exists_only_would_pass = (root / "notes.md").is_file()
        content_survived = (
            upd.USER_NOTE_LINE.encode("ascii") in notes_after_v2
            and settings_v2.get("accent") == upd.USER_ACCENT_VALUE
        )
        if not content_survived:
            print("FAILED:IMP-0024-probe1 user edit missing after v2 (truncation/overwrite)")
            print(json.dumps({"notes": notes_after_v2.decode("utf-8"), "settings": settings_v2}))
            return 1
        if settings_v2.get("telemetry") is not False:
            print("FAILED:IMP-0024-probe1 v2 telemetry did not land")
            return 1

        r23 = upd.update(
            root,
            base_payload=v2,
            theirs_payload=v3,
            from_version="1.1.0",
            to_version="1.2.0",
        )
        if not r23.proceeded:
            print("FAILED:IMP-0024-probe1 v2->v3 did not apply")
            print(json.dumps(r23.as_dict(), default=str)[:2000])
            return 1
        notes_after_v3 = (root / "notes.md").read_bytes()
        settings_v3 = upd.parsed_settings(root)
        chain_ok = (
            upd.USER_NOTE_LINE.encode("ascii") in notes_after_v3
            and settings_v3.get("accent") == upd.USER_ACCENT_VALUE
            and settings_v3.get("keymap") == "vim"
            and b"shipped-v3" in notes_after_v3
        )
        if not chain_ok:
            print("FAILED:IMP-0024-probe1 chain lost the edit")
            print(json.dumps({"notes": notes_after_v3.decode("utf-8"), "settings": settings_v3}))
            return 1

        unchanged_root = Path(td) / "unchanged"
        upd.seed_live_tree(unchanged_root, v1, version="1.0.0")
        r_un = upd.update(
            unchanged_root,
            base_payload=v1,
            theirs_payload=v2,
            from_version="1.0.0",
            to_version="1.1.0",
        )
        un_plan = next(p for p in r_un.files if p.relpath == "notes.md")
        if un_plan.classification != upd.UNCHANGED_BY_USER:
            print("FAILED:IMP-0024-probe1 untouched tree not classified unchanged-by-user")
            return 1

    out = {
        "probe": "probe1-upgrade-edit-survives",
        "unit_id": UNIT,
        "pass": True,
        "exists_only_would_pass": exists_only_would_pass,
        "content_survived_v2": True,
        "content_survived_v3_chain": True,
        "accent": settings_v3["accent"],
        "telemetry": settings_v3["telemetry"],
        "keymap": settings_v3["keymap"],
        "notes_contains_user_line": True,
        "unchanged_classification": un_plan.classification,
        "v1_to_v2_reason": r12.reason,
        "v2_to_v3_reason": r23.reason,
        "two_independent_signals": "pair-with-probe2-unique-line-differ",
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print("SUCCESS:IMP-0024-probe1 throwaway HOME upgrade; unique edit bytes survived v1->v2->v3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
