#!/usr/bin/env python3
"""Probe 2: restore into scratch, byte-compare vs source, damaged restore turns RED."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import KEEP_ME_REL, artifact_both_states, artifact_restore, run_rehearsal  # noqa: E402

ART = REPO / "command-center/audit/AUD-0092-rollback-backup-rehearsal.json"
SENTINEL = (
    "SUCCESS:AUD-0092 emitted only when the artifact at output_path exists, is non-empty, "
    "parses against output_schema, and both named probes are recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0092-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    both = artifact_both_states(doc)
    if both.get("discriminates") is not True:
        return fail("artifact both_states.discriminates is not true")

    live = run_rehearsal()
    if not live.get("ok"):
        return fail("live rehearsal not ok")
    good = live["known_good"]
    broken = live["known_broken"]
    if good.get("equal") is not True or int(good.get("exit_code")) != 0:
        return fail(f"intact restore did not compare equal {good}")
    if broken.get("equal") is not False or int(broken.get("exit_code")) == 0:
        return fail(f"damaged restore did not turn RED {broken}")
    if KEEP_ME_REL not in (broken.get("missing_head") or []) and broken.get("missing_n", 0) < 1:
        return fail("damaged restore did not report keep-me missing")
    if not live.get("discriminates"):
        return fail("honest comparator does not discriminate")
    if not live.get("mutant_fails_to_discriminate"):
        return fail("always-green mutant did not stay green on damaged restore")
    if not live.get("restore_outside_corpus"):
        return fail("restore scratch is not outside corpus")
    if live.get("damaged_rel") != KEEP_ME_REL:
        return fail("damaged_rel is not keep-me")

    art_restore = artifact_restore(doc)
    if art_restore.get("intact_equal") is not True:
        return fail("artifact restore.intact_equal is not true")
    if art_restore.get("damaged_equal") is not False:
        return fail("artifact restore.damaged_equal is not false")

    print(
        json.dumps(
            {
                "intact_equal": True,
                "intact_exit_code": good["exit_code"],
                "damaged_equal": False,
                "damaged_exit_code": broken["exit_code"],
                "damaged_missing_n": broken["missing_n"],
                "mutant_always_green_on_damaged": True,
                "discriminates": True,
                "restore_scratch": live["restore_scratch"],
                "computed_not_asserted": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"intact rc={good['exit_code']} damaged rc={broken['exit_code']} "
        f"missing_n={broken['missing_n']} mutant_green=True"
    )
    print("SUCCESS:AUD-0092-probe2 restore byte-compare and damaged-restore control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
