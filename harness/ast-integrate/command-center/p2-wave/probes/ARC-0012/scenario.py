"""Both-states fixtures and detector-control (known-orphan) fixtures.

Live-tree measurement is separate: these trees prove the detector can fire
and go silent. They are not a substitute for running against the repo.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from completeness import completeness
from mapping import expected_rel

LISTED_SKILL = {
    "id": "skill.listed",
    "kind": "skill",
    "name": "listed",
    "description": "Paired registry row.",
    "instructions": "Must have a generated output.",
    "roles": ["tester"],
}
LISTED_HOOK = {
    "id": "hook.listed",
    "kind": "hook",
    "event": "Stop",
    "script": "hooks/listed.py",
    "enabled": True,
}
ORPHAN_SKILL = {
    "id": "skill.orphan-registry",
    "kind": "skill",
    "name": "orphan-registry",
    "description": "Known Direction A orphan.",
    "instructions": "No generated file.",
    "roles": ["tester"],
}


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_output(root: Path, entry: dict[str, Any], body: str = "generated\n") -> Path:
    rel = expected_rel(entry, "generated")
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def write_complete(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    entries = [LISTED_SKILL, LISTED_HOOK]
    _write_json(root / "registry.json", {"schema_version": 1, "entries": entries})
    for e in entries:
        _write_output(root, e)
    return root


def write_direction_a_bad(root: Path) -> Path:
    """Delete skill.listed output; hook remains. Direction A must fire."""
    write_complete(root)
    rel = expected_rel(LISTED_SKILL, "generated")
    (root / rel).unlink()
    return root


def write_direction_b_bad(root: Path) -> Path:
    """Add an unregistered generated file. Direction B must fire."""
    write_complete(root)
    extra = root / "generated" / "skills" / "skill.unregistered.json"
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_text("leftover\n", encoding="utf-8")
    return root


def write_empty_output(root: Path) -> Path:
    """Zero-byte generated file is Direction A (empty), not complete."""
    write_complete(root)
    rel = expected_rel(LISTED_SKILL, "generated")
    (root / rel).write_bytes(b"")
    return root


def write_known_a_orphan(root: Path) -> Path:
    """Detector-control for A: a KNOWN-present orphan registry row."""
    root.mkdir(parents=True, exist_ok=True)
    entries = [LISTED_HOOK, ORPHAN_SKILL]
    _write_json(root / "registry.json", {"schema_version": 1, "entries": entries})
    _write_output(root, LISTED_HOOK)
    return root


def write_known_b_orphan(root: Path) -> Path:
    """Detector-control for B: a KNOWN-present unregistered file."""
    write_complete(root)
    extra = root / "generated" / "docs" / "doc.known-orphan.md"
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_text("known B orphan\n", encoding="utf-8")
    return root


def run_on(root: Path) -> dict[str, Any]:
    import json as _json

    reg = _json.loads((root / "registry.json").read_text(encoding="utf-8"))
    return completeness(root, reg, "generated")


def both_states() -> dict[str, Any]:
    here = Path(__file__).resolve().parent / "fixtures"
    complete = write_complete(here / "complete")
    a_bad = write_direction_a_bad(here / "a-missing")
    b_bad = write_direction_b_bad(here / "b-extra")
    restored_a = write_complete(here / "a-restored")
    restored_b = write_complete(here / "b-restored")
    empty = write_empty_output(here / "empty-file")
    known_a = write_known_a_orphan(here / "known-a")
    known_b = write_known_b_orphan(here / "known-b")

    c = run_on(complete)
    a = run_on(a_bad)
    b = run_on(b_bad)
    ra = run_on(restored_a)
    rb = run_on(restored_b)
    em = run_on(empty)
    ka = run_on(known_a)
    kb = run_on(known_b)

    a_fires = a["direction_a_orphan_registry_count"] >= 1 and any(
        x["id"] == "skill.listed" for x in a["direction_a_orphans"]
    )
    a_silent_good = c["direction_a_orphan_registry_count"] == 0
    a_silent_restored = ra["direction_a_orphan_registry_count"] == 0
    b_fires = b["direction_b_orphan_output_count"] >= 1 and any(
        x["path"].endswith("skill.unregistered.json") for x in b["direction_b_orphans"]
    )
    b_silent_good = c["direction_b_orphan_output_count"] == 0
    b_silent_restored = rb["direction_b_orphan_output_count"] == 0
    empty_is_a = any(x.get("reason") == "empty" for x in em["direction_a_orphans"])
    known_a_hit = any(
        x["id"] == "skill.orphan-registry" for x in ka["direction_a_orphans"]
    )
    known_b_hit = any(
        x["path"].endswith("doc.known-orphan.md") for x in kb["direction_b_orphans"]
    )
    return {
        "complete": c,
        "direction_a_bad": a,
        "direction_b_bad": b,
        "restored_a": ra,
        "restored_b": rb,
        "empty": em,
        "known_a": ka,
        "known_b": kb,
        "a_fires_on_delete": a_fires,
        "a_silent_on_complete": a_silent_good,
        "a_silent_on_restore": a_silent_restored,
        "b_fires_on_unregistered": b_fires,
        "b_silent_on_complete": b_silent_good,
        "b_silent_on_restore": b_silent_restored,
        "empty_file_is_direction_a": empty_is_a,
        "detector_control_a_found_known_orphan": known_a_hit,
        "detector_control_b_found_known_orphan": known_b_hit,
        "pass": all(
            [
                a_fires,
                a_silent_good,
                a_silent_restored,
                b_fires,
                b_silent_good,
                b_silent_restored,
                empty_is_a,
                known_a_hit,
                known_b_hit,
                c["both_directions_clean"],
            ]
        ),
    }


if __name__ == "__main__":
    out = both_states()
    print(json.dumps({k: out[k] for k in sorted(out) if k != "complete"}, default=str))
    raise SystemExit(0 if out["pass"] else 1)
