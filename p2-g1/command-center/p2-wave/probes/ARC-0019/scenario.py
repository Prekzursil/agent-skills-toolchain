"""Both-states fixtures, detector-control, and the planted-orphan negative control.

Live-tree measurement is separate. These trees prove the detector fires and
goes silent. A live zero in direction B is trusted only after the planted
unregistered package is found on a fixture.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reconcile import PACKAGE_NAME, canonical_blob, load_registry, reconcile

LISTED_PLUGIN = {
    "id": "plugin.listed",
    "kind": "plugin_manifest",
    "name": "listed",
    "version": "1.0.0",
    "description": "Paired registry row.",
}
LISTED_SKILL = {
    "id": "skill.listed",
    "kind": "skill",
    "name": "listed",
    "version": "1.0.0",
    "description": "Paired skill row.",
}
ORPHAN_REG = {
    "id": "skill.orphan-registry",
    "kind": "skill",
    "name": "orphan-registry",
    "version": "0.0.1",
    "description": "Known Direction A orphan.",
}
PLANTED_ID = "capability.planted-orphan"


def _write_registry(root: Path, entries: list[dict[str, Any]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "registry.json").write_text(
        json.dumps({"schema_version": 1, "entries": entries}, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _write_package(root: Path, entry: dict[str, Any], blob: bytes | None = None) -> Path:
    install = root / "installed" / str(entry["id"])
    install.mkdir(parents=True, exist_ok=True)
    path = install / PACKAGE_NAME
    path.write_bytes(blob if blob is not None else canonical_blob(entry))
    return path


def write_complete(root: Path) -> Path:
    entries = [LISTED_PLUGIN, LISTED_SKILL]
    _write_registry(root, entries)
    for e in entries:
        _write_package(root, e)
    return root


def write_registry_not_deployed(root: Path) -> Path:
    """Delete skill.listed install; plugin remains. Direction A must fire."""
    write_complete(root)
    pkg = root / "installed" / LISTED_SKILL["id"] / PACKAGE_NAME
    pkg.unlink()
    pkg.parent.rmdir()
    return root


def write_deployed_not_registered(root: Path) -> Path:
    """Plant an unregistered installed capability. Direction B must fire."""
    write_complete(root)
    planted = {
        "id": PLANTED_ID,
        "kind": "skill",
        "name": "planted-orphan",
        "version": "9.9.9",
        "description": "Deployed capability with no registry entry.",
    }
    _write_package(root, planted)
    return root


def write_restored(root: Path) -> Path:
    return write_complete(root)


def write_empty_package(root: Path) -> Path:
    write_complete(root)
    path = root / "installed" / LISTED_SKILL["id"] / PACKAGE_NAME
    path.write_bytes(b"")
    return root


def write_known_a(root: Path) -> Path:
    _write_registry(root, [LISTED_PLUGIN, ORPHAN_REG])
    _write_package(root, LISTED_PLUGIN)
    return root


def write_known_b(root: Path) -> Path:
    return write_deployed_not_registered(root)


def write_hash_mismatch(root: Path) -> Path:
    write_complete(root)
    path = root / "installed" / LISTED_SKILL["id"] / PACKAGE_NAME
    path.write_text('{"id":"skill.listed","stale":true}\n', encoding="utf-8")
    return root


def run_on(root: Path) -> dict[str, Any]:
    registry = load_registry(root / "registry.json")
    return reconcile(registry, root / "installed", registry_path=str(root / "registry.json"))


def both_states() -> dict[str, Any]:
    here = Path(__file__).resolve().parent / "fixtures"
    complete = write_complete(here / "complete")
    a_bad = write_registry_not_deployed(here / "a-missing")
    b_bad = write_deployed_not_registered(here / "b-planted")
    restored_a = write_restored(here / "a-restored")
    restored_b = write_restored(here / "b-restored")
    empty = write_empty_package(here / "empty-package")
    known_a = write_known_a(here / "known-a")
    known_b = write_known_b(here / "known-b")
    hashed = write_hash_mismatch(here / "hash-mismatch")

    c = run_on(complete)
    a = run_on(a_bad)
    b = run_on(b_bad)
    ra = run_on(restored_a)
    rb = run_on(restored_b)
    em = run_on(empty)
    ka = run_on(known_a)
    kb = run_on(known_b)
    hm = run_on(hashed)

    a_fires = a["registry_not_deployed_count"] >= 1 and any(
        x["id"] == LISTED_SKILL["id"] for x in a["registry_not_deployed"]
    )
    a_silent_good = c["registry_not_deployed_count"] == 0
    a_silent_restored = ra["registry_not_deployed_count"] == 0
    b_fires = b["deployed_not_in_registry_count"] >= 1 and any(
        x["id"] == PLANTED_ID for x in b["deployed_not_in_registry"]
    )
    b_silent_good = c["deployed_not_in_registry_count"] == 0
    b_silent_restored = rb["deployed_not_in_registry_count"] == 0
    empty_is_a = any(
        x["id"] == LISTED_SKILL["id"] and x.get("reason") == "empty"
        for x in em["registry_not_deployed"]
    )
    known_a_hit = any(x["id"] == ORPHAN_REG["id"] for x in ka["registry_not_deployed"])
    known_b_hit = any(x["id"] == PLANTED_ID for x in kb["deployed_not_in_registry"])
    hash_fires = hm["hash_mismatch_count"] >= 1 and any(
        x["id"] == LISTED_SKILL["id"] for x in hm["hash_mismatches"]
    )
    hash_silent_complete = c["hash_mismatch_count"] == 0
    planted_negative = b_fires and known_b_hit
    return {
        "complete": c,
        "a_fires_on_missing_install": a_fires,
        "a_silent_on_complete": a_silent_good,
        "a_silent_on_restore": a_silent_restored,
        "b_fires_on_planted_orphan": b_fires,
        "b_silent_on_complete": b_silent_good,
        "b_silent_on_restore": b_silent_restored,
        "empty_package_is_registry_not_deployed": empty_is_a,
        "detector_control_a_found_known_orphan": known_a_hit,
        "detector_control_b_found_planted_orphan": known_b_hit,
        "hash_fires_on_stale_bytes": hash_fires,
        "hash_silent_on_complete": hash_silent_complete,
        "planted_negative_control": planted_negative,
        "complete_disagreement_count": c["disagreement_count"],
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
                hash_fires,
                hash_silent_complete,
                planted_negative,
                c["both_sides_clean"],
            ]
        ),
    }


if __name__ == "__main__":
    out = both_states()
    keep = {k: v for k, v in out.items() if k != "complete"}
    print(json.dumps(keep, indent=2, sort_keys=True, default=str))
    raise SystemExit(0 if out["pass"] else 1)
