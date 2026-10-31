#!/usr/bin/env python3
"""TST-0165 probe 2: live versioned migration vs lenient loader (rebuild).

Does not import probe1. Rails:
  (a) live: a v1 checkpoint migrates to v2 under the declared remaps
      (legacy_cursor->resume_cursor, legacy_artifact_cache_key ->
      artifact_cache_key, pinned_sha explicit default) with ZERO silent
      field drops; the current-version checkpoint resumes without
      migration; a future version refuses loudly;
  (b) live negative control: a lenient loader that stamps the version and
      ignores unknown keys must FAIL the field-set check (it silently
      drops the legacy fields);
  (c) receipt agreement: the live remap rows equal the receipt's recorded
      migration_table, and the receipt's lenient-control drops match.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "TST-0165.json"
UID = "TST-0165"
CURRENT_VERSION = 2
REMAMES = {
    "legacy_cursor": "resume_cursor",
    "legacy_artifact_cache_key": "artifact_cache_key",
}
DEFAULTS = {"pinned_sha": "unpinned-v1-migrated"}


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def load_strict(doc: dict) -> dict:
    """Versioned strict load: migrate up, refuse later versions loudly."""
    v = int(doc.get("schema_version") or 1)
    if v > CURRENT_VERSION:
        raise ValueError(f"checkpoint schema_version={v} is newer than this runner (v{CURRENT_VERSION}); refusing loudly")
    if v == CURRENT_VERSION:
        return dict(doc)
    migrated = {
        ("pinned_sha" if k == "pinned_sha" else REMAMES.get(k, k)): val
        for k, val in doc.items()
        if k != "schema_version"
    }
    migrated = {REMAMES.get(k, k): v_ for k, v_ in doc.items() if k != "schema_version"}
    for k, dv in DEFAULTS.items():
        if k not in migrated:
            migrated[k] = dv
    migrated["schema_version"] = CURRENT_VERSION
    migrated["migrated_from"] = v
    return migrated


def load_lenient(doc: dict) -> dict:
    """Mutant: stamps the version, silently ignores unknown keys."""
    out = {}
    for k, val in doc.items():
        if k in ("schema_version", "secret_operator_note"):
            continue
        if k in REMAMES:
            continue  # lenient loader does not know the remaps
        out[k] = val
    out["schema_version"] = CURRENT_VERSION
    return out


def fieldset(doc: dict) -> set:
    return {k for k in doc.keys()}


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="tst-0165-p2-") as td:
        root = Path(td)
        old_v1 = {
            "schema_version": 1,
            "legacy_cursor": {"node": "human-checkpoint.wait"},
            "legacy_artifact_cache_key": "cache-xyz",
            "completed_unit_ids": ["IMP-0145", "IMP-0146"],
            "open_nodes": ["human-checkpoint.wait"],
            "param_bindings": {"phase": "7", "workflow": "bp-resume"},
            "receipt_hashes": {"IMP-0145": "a" * 64, "IMP-0146": "b" * 64},
            "secret_operator_note": "note",
        }
        (root / "checkpoint.json").write_text(json.dumps(old_v1, indent=2))
        on_disk = json.loads((root / "checkpoint.json").read_text(encoding="utf-8"))

        # old-v1 migrates with zero silent drops
        migrated = load_strict(on_disk)
        src_fields = {k for k in on_disk if k not in ("schema_version",)}
        dst_fields = set(migrated)
        missing = {f for f in src_fields if f not in dst_fields and f not in REMAMES}
        if missing:
            return fail(f"migration silently dropped fields: {sorted(missing)}")
        if migrated.get("resume_cursor") != on_disk.get("legacy_cursor"):
            return fail("legacy_cursor value not preserved under remap")
        if migrated.get("artifact_cache_key") != on_disk.get("legacy_artifact_cache_key"):
            return fail("legacy_artifact_cache_key value not preserved under remap")
        if migrated.get("pinned_sha") != DEFAULTS["pinned_sha"]:
            return fail("pinned_sha explicit default missing")
        if migrated.get("schema_version") != CURRENT_VERSION:
            return fail("migrated version wrong")

        # current-v2 resumes without migration
        current = dict(migrated)
        current.pop("migrated_from", None)
        current["schema_version"] = 2
        current2 = load_strict(current)
        if current2.get("migrated_from") is not None:
            return fail("current-version checkpoint was migrated")

        # future version refuses loudly
        refused_clean = False
        try:
            load_strict({"schema_version": CURRENT_VERSION + 1})
        except ValueError as exc:
            refused_clean = "refusing loudly" in str(exc)
        if not refused_clean:
            return fail("future version did not refuse loudly")

        # lenient mutant must fail the field-set check
        lenient = load_lenient(on_disk)
        lenient_drops = sorted(
            (fieldset(on_disk) - fieldset(lenient)) - {"schema_version"}
        )
        must_drop = {"legacy_cursor", "legacy_artifact_cache_key", "secret_operator_note"}
        if not (must_drop <= set(lenient_drops)):
            return fail(f"lenient mutant did not drop the known keys: {lenient_drops}")

    # ---- receipt agreement --------------------------------------------
    table = doc.get("migration_table") or []
    live_remaps = {k: v for k, v in REMAMES.items()}
    for row in table:
        if row.get("rule", "").startswith("rename"):
            if live_remaps.get(row.get("from_field")) != row.get("to_field"):
                return fail(f"receipt migration row disagrees with live remap: {row}")
    if doc.get("current_schema_version") != CURRENT_VERSION:
        return fail("receipt current_schema_version drift")
    lc = doc.get("lenient_controls") or {}
    if lc.get("old-v1") is None and not lc:
        return fail("receipt lenient_controls empty")
    ans = doc.get("answer") or {}
    for key in ("old_schema_migrates_or_refuses", "current_version_resumes_without_migration", "lenient_loader_fails_fieldset"):
        if ans.get(key) is not True:
            return fail(f"receipt answer.{key} not true")

    out = {
        "probe": "probe2-migration-fieldset",
        "unit_id": UID,
        "migrated_fields": len(migrated),
        "zero_silent_drops": True,
        "current_no_migration": True,
        "future_refused_loudly": True,
        "lenient_drops": lenient_drops,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"SUCCESS:{UID}-probe2 strict migration zero-drop; lenient mutant red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
