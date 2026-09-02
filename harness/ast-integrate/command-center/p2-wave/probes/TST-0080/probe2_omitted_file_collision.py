#!/usr/bin/env python3
"""Probe 2 / detector control: a hash that omits a shipped file collides.

Two packages that differ only in pkg/extra.dat share the omitted-file key and
the name+version key, but not the sound key. A name+version client also keeps
serving BROKEN after a same-version fix — the stale-cache class itself.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0080.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SENTINEL = "SUCCESS:TST-0080"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0080-probe2 {msg}")
    return 1


def main() -> int:
    collision = S.omitted_file_collision()
    masked = S.name_version_masks_fix()
    printable = {
        "collision": {k: collision[k] for k in sorted(collision) if k != "pass"},
        "name_version": {k: masked[k] for k in sorted(masked) if k != "pass"},
    }
    print(json.dumps(printable, sort_keys=True, default=str)[:4000])
    if not collision.get("pass") or collision.get("omitted_hash_collided") is not True:
        return fail("omitted-file hash did not collide")
    if collision.get("sound_keys_differ") is not True:
        return fail("sound keys collided — shipped hash omitted a file")
    if collision.get("two_materially_different_packages_share_one_sound_key") is True:
        return fail("sound key shared by materially different packages")
    if not masked.get("pass") or masked.get("masked_by_stale_cache") is not True:
        return fail("name+version mutant did not mask the fix")
    print(
        f"omit_collided={collision['omitted_hash_collided']} "
        f"sound_differ={collision['sound_keys_differ']} "
        f"nv_masked={masked['masked_by_stale_cache']} "
        f"nv_behavior={masked['second']['behavior']}"
    )
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            return fail(f"self-declared {doc.get('state')}")
        if SENTINEL not in text:
            return fail("catalog sentinel absent from artifact")
        ctrl = doc.get("detector_control") or {}
        if ctrl.get("fired") is not True:
            return fail("artifact detector_control.fired is not true")
        attempt = doc.get("collision_attempt") or {}
        if attempt.get("omitted_hash_collided") is not True:
            return fail("artifact collision_attempt did not record a collision")
        if attempt.get("sound_keys_differ") is not True:
            return fail("artifact collision_attempt sound keys did not differ")
        if attempt.get("two_materially_different_packages_share_one_sound_key") is True:
            return fail("artifact claims sound-key collision")
        if (doc.get("name_version_mutant") or {}).get("masked_by_stale_cache") is not True:
            return fail("artifact name+version mutant did not mask the fix")
    print("SUCCESS:TST-0080-probe2 omitted-file collision and name+version mask fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
