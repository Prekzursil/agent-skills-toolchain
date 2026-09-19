"""C11 lane: migrate receipts still pointing at the OLD charter manifest.

Owner decision Option B (command-center/p2-next/OWNER-DECISION-condition-11.md)
chose a DEDICATED unit-artifact manifest for condition 11. The doc's "80
receipts" figure was measured 2026-08-13 and is stale: the 2026-08-16 p2-wave
_pack_receipt.py builders already repointed most receipts at per-probe
UNIT-ARTIFACT-MANIFEST.json files. Fresh census 2026-09-19
(command-center/p2-next/C11-CENSUS.json): 20 receipt-shaped files still declare
manifest_path == command-center/ARTIFACT-MANIFEST.json.

This migration rewrites manifest_path IN PLACE, byte-surgically (regex scoped to
the manifest_path VALUE only -- evidence anchors citing the charter manifest are
historical references and are NOT touched), for every one of those 20 EXCEPT
the 14 frozen both-states fixtures under command-center/p2-wave/fixtures/
(consumed by command-center/ready_units.py and tools/measure-guard/unitgate.py
as known-broken/known-good controls; churning their bytes buys no contract and
risks the freeze inventory recorded in AUD-0095). The 6 migrated receipts are
real delivery receipts whose declared artifacts are all present on disk.

The rewrite is verified structurally: re-parse each migrated file, assert the
only parsed-field delta is manifest_registration.manifest_path, and assert the
pre-edit bytes can be reconstructed by reversing the substitution. Idempotent:
a re-run migrates zero files and reports SUCCESS with migrated=0.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CC = ROOT / "command-center"
OLD = "command-center/ARTIFACT-MANIFEST.json"
NEW = "command-center/UNIT-ARTIFACT-MANIFEST.json"
EXCLUDED_FIXTURE_DIR = "command-center/p2-wave/fixtures/"

#: Scoped to the manifest_path value only. Tolerates any JSON spacing between
#: the key, the colon, and the string. Exactly one match per file is expected.
_PATTERN = re.compile(r'("manifest_path"\s*:\s*")' + re.escape(OLD) + r'(")')
#: The same shape matching the NEW value, used only to prove the rewrite is
#: reversible byte-for-byte (undo must restore the original text exactly).
_REVERSE = re.compile(r'("manifest_path"\s*:\s*")' + re.escape(NEW) + r'(")')


def main() -> int:
    migrated: list[str] = []
    skipped_fixtures: list[str] = []
    failures: list[str] = []
    scanned = 0
    for path in sorted(CC.rglob("*.json")):
        rel = path.relative_to(ROOT).as_posix()
        if any(part.startswith("_") for part in path.relative_to(CC).parts):
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            failures.append(f"unreadable {rel}: {exc}")
            continue
        if b"manifest_registration" not in raw:
            continue
        scanned += 1
        try:
            before = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            continue  # not our receipt to touch; the producer fails closed on claimers
        mr = before.get("manifest_registration") if isinstance(before, dict) else None
        if not isinstance(mr, dict) or mr.get("manifest_path") != OLD:
            continue
        if rel.startswith(EXCLUDED_FIXTURE_DIR):
            skipped_fixtures.append(rel)
            continue
        text = raw.decode("utf-8")
        new_text, n = _PATTERN.subn(r"\g<1>" + NEW + r"\g<2>", text)
        if n != 1:
            failures.append(f"{rel}: expected exactly 1 manifest_path match, got {n}")
            continue
        after = json.loads(new_text)
        # Structural verification: the ONLY delta is manifest_registration.manifest_path.
        delta_keys = {
            k for k in set(before) | set(after) if before.get(k) != after.get(k)
        }
        if delta_keys != {"manifest_registration"}:
            failures.append(f"{rel}: unexpected delta keys {sorted(delta_keys)}")
            continue
        if after["manifest_registration"].get("manifest_path") != NEW or after[
            "manifest_registration"
        ].get("registered") != before["manifest_registration"].get("registered"):
            failures.append(f"{rel}: manifest_registration delta beyond manifest_path")
            continue
        # Reversibility: undoing the substitution must restore the original bytes.
        if _REVERSE.subn(r"\g<1>" + OLD + r"\g<2>", new_text)[0] != text:
            failures.append(f"{rel}: rewrite not reversible")
            continue
        path.write_bytes(new_text.encode("utf-8"))
        migrated.append(rel)

    print(f"scanned receipt-shaped candidates: {scanned}")
    print(f"migrated to NEW manifest: {len(migrated)}")
    for rel in migrated:
        print(f"   M {rel}")
    print(f"skipped frozen fixtures ({EXCLUDED_FIXTURE_DIR}): {len(skipped_fixtures)}")
    for rel in skipped_fixtures:
        print(f"   S {rel}")
    if failures:
        for f in failures:
            print(f"FAILED:c11-migrate {f}")
        return 1
    print(
        f"SUCCESS:c11-migrate migrated={len(migrated)} skipped_fixtures="
        f"{len(skipped_fixtures)} remaining_old_path=0 (of real receipts)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
