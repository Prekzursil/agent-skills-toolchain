#!/usr/bin/env python3
"""Probe 2: independent re-derivation of scope inertness and unknown-key refusal.

Reads schemas and fixtures first. Reads the unit conclusion only after the
controls have already fired.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import reader as R  # noqa: E402

OUT = "command-center/confirmation/CNF-0057-config-key-diff.json"
UNIT = "CNF-0057"


def main() -> int:
    before = R.load_schema("before")
    after = R.load_schema("after")
    fixtures = R.load_fixtures()
    delta = R.diff_schemas(before, after)
    loads = R.load_all(after, fixtures, permissive=False)
    permissive = R.load_all(after, fixtures, permissive=True)

    unknown_strict = next(row for row in loads if row["control"] == "unknown-key")
    unknown_perm = next(row for row in permissive if row["control"] == "unknown-key")
    wrong = next(row for row in loads if row["control"] == "wrong-scope")
    realistic = next(row for row in loads if row["control"] == "realistic")
    legacy = next(row for row in loads if row["control"] == "legacy-wrong-file")

    unknown_fired = R.UNKNOWN_CONTROL_KEY in {u["key"] for u in unknown_strict["unknown"]}
    permissive_silent = (
        R.UNKNOWN_CONTROL_KEY not in {u["key"] for u in unknown_perm["unknown"]}
        and any(
            h["key"] == R.UNKNOWN_CONTROL_KEY for h in unknown_perm["honoured"]
        )
    )
    wrong_inert = any(
        i["key"] == "disabledMcpServers" and i["written_scope"] == "root"
        for i in wrong["inert"]
    )
    realistic_ok = realistic["verbatim_honour"] and not realistic["inert"]
    legacy_not_verbatim = not legacy["verbatim_honour"] and bool(legacy["inert"])

    dropped_mutant = copy.deepcopy(after)
    del dropped_mutant["keys"]["model"]
    drop_delta = R.diff_schemas(before, dropped_mutant)
    drop_detected = "model" in drop_delta["keys_dropped"]

    default_mutant = copy.deepcopy(after)
    default_mutant["keys"]["model"]["default"] = "haiku"
    def_delta = R.diff_schemas(before, default_mutant)
    default_detected = any(row["key"] == "model" for row in def_delta["defaults_moved"])

    live_no_drop = delta["keys_dropped"] == []
    live_no_default_move = delta["defaults_moved"] == []

    print(f"unknown_fired={unknown_fired} permissive_silent={permissive_silent}")
    print(f"wrong_inert={wrong_inert} realistic_ok={realistic_ok} legacy_inert={legacy_not_verbatim}")
    print(f"mutant_drop_detected={drop_detected} mutant_default_detected={default_detected}")
    print(f"live_keys_dropped={delta['keys_dropped']} live_defaults_moved={len(delta['defaults_moved'])}")
    print(f"scopes_changed={[row['key'] for row in delta['scopes_changed']]}")

    independent_ok = (
        unknown_fired
        and permissive_silent
        and wrong_inert
        and realistic_ok
        and legacy_not_verbatim
        and drop_detected
        and default_detected
        and live_no_drop
        and live_no_default_move
    )
    if not independent_ok:
        print(f"FAILED:{UNIT}-probe2 independent controls did not all fire")
        return 1

    artifact = json.loads((REPO / OUT).read_text(encoding="utf-8"))
    rec_unknown = None
    rec_wrong = None
    for row in artifact.get("fixture_loads") or []:
        if row.get("fixture_id") == "unknown-key":
            rec_unknown = row
        if row.get("fixture_id") == "wrong-scope-inert":
            rec_wrong = row
    if rec_unknown is None or R.UNKNOWN_CONTROL_KEY not in (rec_unknown.get("unknown_keys") or []):
        print(f"FAILED:{UNIT}-probe2 artifact omitted unknown-key control")
        return 1
    if rec_wrong is None or "disabledMcpServers" not in (rec_wrong.get("inert_keys") or []):
        print(f"FAILED:{UNIT}-probe2 artifact omitted wrong-scope inert key")
        return 1
    if artifact.get("delta", {}).get("keys_dropped") != []:
        print(f"FAILED:{UNIT}-probe2 artifact keys_dropped disagrees with independent diff")
        return 1
    print(f"SUCCESS:{UNIT}-probe2 overclaim anchors reviewer-added-mode")
    print(f"SUCCESS:{UNIT}-probe2 independent unknown-key and wrong-scope controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
