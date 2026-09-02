#!/usr/bin/env python3
"""Named probe 2: field-set diff + both-states + lenient-loader control.

Mechanically different from probe 1: does not use exit_code or message text
as a pass criterion. Accounts every old key against the loaded/migrated
document. A lenient loader that ignores unknown fields must go red.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

ART = REPO / "command-center/receipts/TST-0165.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0165-probe2 {msg}")
    return 1


def keyset(doc: dict) -> set[str]:
    return set(E.flatten(doc))


def main() -> int:
    paths = E.materialize_fixtures()
    strict = E.evaluate_strict(paths)
    lenient = E.evaluate_lenient(paths)

    old = strict["old-v1"]
    diff = old["fieldset"]
    if not diff or not diff["zero_silent_drops"]:
        return fail(
            f"old-v1 strict migrate silent_drops={diff.get('silent_drops') if diff else None} "
            f"meaning_changed={diff.get('meaning_changed') if diff else None}"
        )
    mapped_from = {m["from"] for m in diff["mapped"]}
    if "legacy_cursor" not in mapped_from:
        return fail(f"legacy_cursor not mapped {diff['mapped']}")
    if "legacy_artifact_cache_key" not in mapped_from:
        return fail(f"legacy_artifact_cache_key not mapped {diff['mapped']}")
    ckpt = old["resume"]["checkpoint"]
    if ckpt is None:
        return fail("old-v1 produced no checkpoint")
    if ckpt.get("resume_cursor") != "phase-7-mid":
        return fail(f"resume_cursor {ckpt.get('resume_cursor')}")
    if ckpt.get("artifact_cache_key") != "cache-xyz":
        return fail(f"artifact_cache_key {ckpt.get('artifact_cache_key')}")
    if "legacy_cursor" in ckpt or "legacy_artifact_cache_key" in ckpt:
        return fail("v1 names survived into v2 checkpoint")
    if "pinned_sha" not in diff["added"]:
        return fail(f"pinned_sha not in added {diff['added']}")

    # both-states: current-version field set is identity (no migration keys).
    cur = strict["current-v2"]
    before = json.loads(paths["current-v2"].read_text(encoding="utf-8"))
    after = cur["resume"]["checkpoint"]
    if after is None:
        return fail("current-v2 produced no checkpoint")
    if keyset(before) != keyset(after):
        return fail(
            f"current-v2 keyset changed before={sorted(keyset(before))} "
            f"after={sorted(keyset(after))}"
        )
    if E.flatten(before) != E.flatten(after):
        return fail("current-v2 values changed; migration ran on current schema")
    cdiff = cur["fieldset"]
    if not cdiff or cdiff["mapped"] or cdiff["added"] or cdiff["silent_drops"]:
        return fail(f"current-v2 fieldset is not identity {cdiff}")
    if cur["resume"].get("migrated"):
        return fail("current-v2 migrated=True (both-states red)")

    # negative control: lenient loader must drop or mis-meaning v1-only keys.
    lv1 = lenient["old-v1"]
    ld = lv1["fieldset"]
    if ld["zero_silent_drops"]:
        return fail(
            "lenient old-v1 field-set detector silent; negative control vacuous"
        )
    dropped = set(ld["silent_drops"]) | set(ld["meaning_changed"])
    if "legacy_cursor" not in dropped:
        return fail(f"lenient did not drop/mis-meaning legacy_cursor {ld}")
    if "legacy_artifact_cache_key" not in dropped:
        return fail(f"lenient did not drop/mis-meaning cache key {ld}")
    lckpt = lv1["resume"]["checkpoint"]
    if lckpt and lckpt.get("resume_cursor") == "phase-7-mid":
        return fail("lenient remapped cursor; mutant is not the silent-drop bug")

    lextra = lenient["old-v1-unknown-extra"]
    xd = lextra["fieldset"]
    if "secret_operator_note" not in xd["silent_drops"]:
        return fail(
            f"lenient extra-field silent_drops missing secret_operator_note {xd['silent_drops']}"
        )
    if xd["zero_silent_drops"]:
        return fail("lenient extra-field detector silent")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        ev = doc.get("evidence_b") or {}
        if ev.get("old_v1_zero_silent_drops") is not True:
            return fail("artifact evidence_b old_v1_zero_silent_drops")
        claimed = ev.get("lenient_silent_drops") or []
        live_drops = sorted(set(ld["silent_drops"]) | set(ld["meaning_changed"]))
        if not claimed:
            return fail("artifact evidence_b lenient_silent_drops empty")
        if set(claimed) != set(live_drops):
            return fail(
                f"artifact lenient_silent_drops {claimed} vs live {live_drops}"
            )
        tests = {t.get("id"): t.get("result") for t in (doc.get("tests") or [])}
        for tid in (
            "TST-0165-BOTH-STATES",
            "TST-0165-NEGATIVE-LENIENT",
            "TST-0165-FIELDSET-ZERO-DROPS",
        ):
            if tests.get(tid) != "PASS":
                return fail(f"artifact test {tid}={tests.get(tid)}")

    payload = {
        "probe": "probe2-fieldset-diff",
        "unit_id": "TST-0165",
        "pass": True,
        "old_v1_zero_silent_drops": True,
        "old_v1_mapped": diff["mapped"],
        "current_v2_identity": True,
        "lenient_old_v1_drops": sorted(dropped),
        "lenient_extra_drops": xd["silent_drops"],
        "negative_control_fired": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "zero_silent_drops=True current_identity=True "
        f"lenient_drops={sorted(dropped)} extra_drops={xd['silent_drops']}"
    )
    print("SUCCESS:TST-0165-probe2 field-set diff and lenient-loader control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
