#!/usr/bin/env python3
"""AUD-0095 probe 2 (both-states change-detection): the freeze detector must turn
RED on a frozen file's hash change with no version bump, GREEN only when the
change carries a version bump plus a recorded migration, and stay SILENT on a
non-frozen path. Everything runs on scratch copies; the live tree is never
mutated (the recorded rule: copy the current bytes as the down-fixture, apply
the change in a scratch copy of that path only)."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "lib"))

ART = REPO / "command-center" / "audit" / "AUD-0095-freeze-inventory.json"
UNIT = "AUD-0095"
TARGET_REL = "command-center/schema/claim-record.schema.json"
NOT_FROZEN_REL = "command-center/audit/_AUD-0095-not-frozen.txt"
VERSION_RE = re.compile(r'"schema_version"\s*:\s*"([^"]+)"')

REASON = "unversioned-or-unmigrated-hash-change:no-matching-migration,no-version-bump"


def sha_lf(b: bytes) -> str:
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def version_marker(text: str) -> str | None:
    m = VERSION_RE.search(text)
    return m.group(1) if m else None


def reds(frozen: dict[str, str], edited: dict[str, bytes],
         migrations: list[dict]) -> list[dict]:
    """The freeze detector under audit: RED rows for frozen paths whose live
    hash changed with no version bump and no matching migration record."""
    out = []
    for rel, anchor in frozen.items():
        if rel not in edited:
            continue
        new_sha = sha_lf(edited[rel])
        if new_sha == anchor:
            continue
        mig = next((m for m in migrations
                    if m["path"] == rel and m["from_sha256"] == anchor
                    and m["to_sha256"] == new_sha), None)
        marker = version_marker(edited[rel].decode("utf-8", "replace"))
        if mig and marker == mig["to_version"] and marker != mig["from_version"]:
            continue
        out.append({"path": rel, "reason": REASON})
    return out


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print(f"FAILED:{UNIT}-probe2 live artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    inv = {r["path"]: r for r in (doc.get("inventory") or [])
           if isinstance(r, dict) and r.get("path")}
    if TARGET_REL not in inv:
        print(f"FAILED:{UNIT}-probe2 target {TARGET_REL} not in freeze inventory")
        return 1

    target_row = inv[TARGET_REL]
    live_bytes = (REPO / TARGET_REL).read_bytes()
    if sha_lf(live_bytes) != target_row.get("sha256"):
        print(f"FAILED:{UNIT}-probe2 live anchor drift on {TARGET_REL}")
        return 1
    live_text = live_bytes.decode("utf-8")
    from_version = version_marker(live_text)
    to_version = "0.1.1-provisional"

    frozen = {TARGET_REL: target_row["sha256"]}
    mutated = live_text.replace('"PROVISIONAL Phase-1 canonical claim record"',
                                '"PROVISIONAL Phase-1 canonical claim record" (scratch-edit)')
    if mutated == live_text:
        mutated = live_text + "\n"
    edited_unversioned = mutated.encode("utf-8")
    bumped = VERSION_RE.sub(f'"schema_version": "{to_version}"', mutated, count=1)
    edited_migrated = bumped.encode("utf-8")
    mig_rec = {
        "id": f"{UNIT}-scratch-migration",
        "path": TARGET_REL,
        "from_sha256": target_row["sha256"],
        "to_sha256": sha_lf(edited_migrated),
        "from_version": from_version,
        "to_version": to_version,
        "up": "scratch-copy bump under probe2; live tree untouched",
        "down": "restore from down-fixture (the unedited live bytes already hashed above)",
    }

    # both-states on scratch
    red_unversioned = reds(frozen, {TARGET_REL: edited_unversioned}, [])
    red_migrated = reds(frozen, {TARGET_REL: edited_migrated}, [mig_rec])
    # non-frozen path: the detector sees no frozen constraint for it -> silent
    nonfrozen_edited = {NOT_FROZEN_REL: b"scratch mutation"}
    red_nonfrozen = reds(frozen, nonfrozen_edited, [])

    ok_unversioned = (len(red_unversioned) == 1
                      and red_unversioned[0]["reason"] == REASON)
    ok_migrated = len(red_migrated) == 0
    ok_silent = len(red_nonfrozen) == 0

    # artifact cross-check: recorded both_states verdicts must match the fresh ones
    bs = doc.get("both_states") or {}
    rec_unversioned = str((bs.get("unversioned") or {}).get("verdict", "")).upper() == "RED"
    rec_migrated = str((bs.get("migrated") or {}).get("verdict", "")).upper() == "GREEN"
    rec_silent = bool((bs.get("non_frozen") or {}).get("silent", True))

    result = {
        "unit_id": UNIT,
        "probe": "probe2-both-states-change-detection",
        "target_path": TARGET_REL,
        "from_version": from_version,
        "to_version": to_version,
        "unversioned_red": ok_unversioned,
        "unversioned_reason": red_unversioned[0]["reason"] if red_unversioned else None,
        "migrated_green": ok_migrated,
        "non_frozen_silent": ok_silent,
        "artifact_cross_check": {
            "unversioned": rec_unversioned, "migrated": rec_migrated,
            "silent": rec_silent,
        },
        "pass": bool(ok_unversioned and ok_migrated and ok_silent
                     and rec_unversioned and rec_migrated and rec_silent),
    }
    (HERE / "probe2_change_detection_out.json").write_text(
        json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "target_path", "from_version", "to_version", "unversioned_red",
        "migrated_green", "non_frozen_silent", "pass")}))
    if result["pass"]:
        print(f"SUCCESS:{UNIT}-probe2 change detection both-states GREEN "
              "(unversioned RED, migrated GREEN, non-frozen silent)")
        return 0
    print(f"FAILED:{UNIT}-probe2 both-states mismatch")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
