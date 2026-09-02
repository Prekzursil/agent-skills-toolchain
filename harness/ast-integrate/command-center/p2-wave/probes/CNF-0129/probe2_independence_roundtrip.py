#!/usr/bin/env python3
"""Probe 2: same-probe-rerun, round-trip, and smuggle attempt (reviewer).

Mechanically different from probe 1:
  probe 1 is schema Draft7Validator on the absent-source mutant plus gate exit.
  probe 2 is fingerprint byte-identity (same-probe-rerun) plus confirmer
  serialize/parse equality, and an independent smuggle of unsourced CONFIRMED.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "confirmation"))

from fixtures import same_probe_record, write_fixtures  # noqa: E402
from record_gate import fingerprint_bytes, validate_record  # noqa: E402
from reference_confirmer import emit, round_trip  # noqa: E402

LIVE_GATE = REPO / ".agents/skills/claim-verify-gate/scripts/claim_gate.py"
VALIDATOR = REPO / "command-center/confirmation/validate_confirmation_record.py"


def run_py(script: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, "-B", str(script), *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0129-probe2 {msg}")
    return 1


def main() -> int:
    fx = HERE / "fixtures"
    write_fixtures(fx)

    rec = same_probe_record()
    src_b = fingerprint_bytes(rec["source_probe"])
    ver_b = fingerprint_bytes(rec["verifier_probe"])
    if src_b != ver_b:
        return fail("fixture source/verifier fingerprints were not byte-identical")

    extra = validate_record(rec)
    rules = [v.get("rule") for v in extra.get("violations") or []]
    if "same-probe-rerun" not in rules:
        return fail(f"same-probe record missed same-probe-rerun {extra}")

    rc_gate, gate_out = run_py(LIVE_GATE, str(fx / "claim-same-probe.json"))
    try:
        start, end = gate_out.find("{"), gate_out.rfind("}")
        gate_doc = json.loads(gate_out[start : end + 1])
    except json.JSONDecodeError:
        return fail(f"gate output unparseable {gate_out[-800:]}")
    fired = []
    for claim in gate_doc.get("claims") or []:
        fired.extend(v.get("rule") for v in claim.get("violations") or [])
    if rc_gate == 0 or "same-probe-rerun" not in fired:
        return fail(f"gate same-probe rc={rc_gate} rules={fired}")

    rc_val, val_out = run_py(VALIDATOR, str(fx / "record-same-probe.json"))
    try:
        val_doc = json.loads(val_out[val_out.find("{") : val_out.rfind("}") + 1])
    except json.JSONDecodeError:
        return fail(f"validator unparseable {val_out[-800:]}")
    val_rules = [v.get("rule") for v in val_doc.get("violations") or []]
    if rc_val == 0 or "same-probe-rerun" not in val_rules:
        return fail(f"validator same-probe rc={rc_val} {val_doc}")

    rc_ok, ok_out = run_py(LIVE_GATE, str(fx / "claim-well-formed.json"))
    if rc_ok != 0:
        return fail(f"well-formed claim gate rc={rc_ok} {ok_out[-400:]}")

    rec_ok = emit()
    rt = round_trip(rec_ok)
    if not rt["byte_identical"] or not rt["object_equal"]:
        return fail(f"round-trip loss {rt}")
    required = [
        "kind",
        "claim_id",
        "confirmer",
        "blinding_attestation_hash",
        "baseline_repro",
        "corrected_repro",
        "rollback_repro",
        "regression_diff",
        "discrepancies",
        "verdict",
        "source_probe",
        "verifier_probe",
        "residual_caveat",
    ]
    missing = [f for f in required if f not in rec_ok]
    if missing:
        return fail(f"reference confirmer omitted {missing}")

    # Independent smuggle attempt (reviewer requirement): try to pass unsourced CONFIRMED.
    rc_smuggle, smuggle_out = run_py(LIVE_GATE, str(fx / "record-unsourced-confirmed.json"))
    smuggle_accepted = rc_smuggle == 0
    if smuggle_accepted:
        return fail("smuggle of unsourced CONFIRMED succeeded")

    identity = rec_ok["source_probe"] != rec_ok["verifier_probe"]
    if not identity:
        return fail("reference confirmer used identical probes")

    out = {
        "probe": "probe2-independence-roundtrip",
        "same_probe_fingerprints_byte_identical": True,
        "same_probe_rerun_gate_exit": rc_gate,
        "same_probe_rerun_fired": True,
        "validator_same_probe_exit": rc_val,
        "well_formed_gate_exit": rc_ok,
        "round_trip": rt,
        "reference_confirmer_fields": required,
        "smuggle_unsourced_confirmed": {
            "attempted": True,
            "accepted": smuggle_accepted,
            "gate_exit": rc_smuggle,
        },
        "pass": True,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print(
        "same_probe_rerun=True round_trip=True smuggle_rejected=True "
        f"fields={len(required)}"
    )
    print("SUCCESS:CNF-0129-probe2 independence round-trip smuggle-rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
