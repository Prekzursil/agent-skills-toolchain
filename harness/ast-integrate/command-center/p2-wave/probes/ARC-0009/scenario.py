"""Executable silent-capability-loss scenario for ARC-0009.

Estate fixture (mirrors DESIGN.json file set + unlisted_file rule):
  MANIFEST.json lists capabilities/skills/listed.skill.json only.
  capabilities/skills/ also contains orphan.skill.json (NOT listed).

A1 loader: loads listed, silently omits orphan, errors=[].
A2 completeness: FAIL-CLOSED, names the orphan.

Repair state: add orphan to MANIFEST; A1 loads both; A2 passes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "estate"

LISTED_REL = "capabilities/skills/listed.skill.json"
ORPHAN_REL = "capabilities/skills/orphan.skill.json"
LISTED_ID = "skill.listed"
ORPHAN_ID = "skill.orphan"


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_estate(root: Path, include_orphan_in_manifest: bool) -> Path:
    if root.exists():
        for p in sorted(root.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                try:
                    p.rmdir()
                except OSError:
                    pass
    root.mkdir(parents=True, exist_ok=True)
    _write(
        root / LISTED_REL,
        {
            "id": LISTED_ID,
            "kind": "skill",
            "enabled": True,
            "instructions": "Listed skill. Must remain loaded under A1.",
        },
    )
    _write(
        root / ORPHAN_REL,
        {
            "id": ORPHAN_ID,
            "kind": "skill",
            "enabled": True,
            "instructions": "On-disk but unlisted. A1 must omit this silently.",
        },
    )
    files = [LISTED_REL]
    if include_orphan_in_manifest:
        files.append(ORPHAN_REL)
    _write(
        root / "MANIFEST.json",
        {
            "architecture_id": "A1",
            "files": files,
            "notes": "Files not listed are not loaded (DESIGN precedence.unlisted_file).",
        },
    )
    return root


def run_scenario() -> dict[str, Any]:
    from a1_loader import load_a1
    from a2_completeness import check_a2_completeness

    bad_root = FIX / "unlisted-orphan"
    good_root = FIX / "orphan-listed"
    write_estate(bad_root, include_orphan_in_manifest=False)
    write_estate(good_root, include_orphan_in_manifest=True)
    a1_bad = load_a1(bad_root)
    a2_bad = check_a2_completeness(bad_root)
    a1_good = load_a1(good_root)
    a2_good = check_a2_completeness(good_root)
    silent_loss = (
        a1_bad.get("ok") is True
        and a1_bad.get("errors") == []
        and a1_bad.get("warnings") == []
        and LISTED_ID in (a1_bad.get("loaded_ids") or [])
        and ORPHAN_ID not in (a1_bad.get("loaded_ids") or [])
        and ORPHAN_REL in (a1_bad.get("unlisted_on_disk") or [])
        and ORPHAN_ID in (a1_bad.get("silent_omission_ids") or [])
    )
    a2_catches = (
        a2_bad.get("ok") is False
        and ORPHAN_REL in (a2_bad.get("orphans_on_disk") or [])
        and ORPHAN_ID in (a2_bad.get("caught_ids") or [])
    )
    repaired = (
        a1_good.get("ok") is True
        and LISTED_ID in (a1_good.get("loaded_ids") or [])
        and ORPHAN_ID in (a1_good.get("loaded_ids") or [])
        and a2_good.get("ok") is True
        and not (a2_good.get("orphans_on_disk") or [])
    )
    return {
        "silent_loss_under_a1": silent_loss,
        "a2_generated_ssot_catches": a2_catches,
        "repaired_both_load": repaired,
        "a1_unlisted": {
            "ok": a1_bad.get("ok"),
            "errors": a1_bad.get("errors"),
            "warnings": a1_bad.get("warnings"),
            "loaded_ids": a1_bad.get("loaded_ids"),
            "unlisted_on_disk": a1_bad.get("unlisted_on_disk"),
            "silent_omission_ids": a1_bad.get("silent_omission_ids"),
        },
        "a2_unlisted": {
            "ok": a2_bad.get("ok"),
            "errors": a2_bad.get("errors"),
            "caught_ids": a2_bad.get("caught_ids"),
            "orphans_on_disk": a2_bad.get("orphans_on_disk"),
        },
        "a1_listed": {
            "ok": a1_good.get("ok"),
            "loaded_ids": a1_good.get("loaded_ids"),
        },
        "a2_listed": {
            "ok": a2_good.get("ok"),
            "orphans_on_disk": a2_good.get("orphans_on_disk"),
        },
        "pass": bool(silent_loss and a2_catches and repaired),
        "silent_loss_under_a1": silent_loss,
        "a2_generated_ssot_catches": a2_catches,
        "repaired_both_load": repaired,
    }


if __name__ == "__main__":
    import json as _json
    import sys as _sys

    _out = run_scenario()
    print(_json.dumps(_out, indent=2, sort_keys=True))
    _sys.exit(0 if _out.get("pass") else 1)
