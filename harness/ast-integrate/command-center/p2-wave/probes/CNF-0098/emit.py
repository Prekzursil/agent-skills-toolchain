#!/usr/bin/env python3
"""Emit CNF-0098 macos-reachability impossibility / reachability record."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import estate as E  # noqa: E402
import matrix as M  # noqa: E402
import schema_ctl as S  # noqa: E402

OUT_REL = "command-center/confirmation/CNF-0098-macos-reachability.json"
SCHEMA_REL = "command-center/schema/impossibility-record.schema.json"
LOCAL_SCHEMA_REL = (
    "command-center/p2-wave/probes/CNF-0098/macos-reachability.schema.json"
)
SENTINEL = (
    "SUCCESS:CNF-0098 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every platform row in "
    "the matrix carries an evidence state and no row claims supported without "
    "a run. Any other terminal state is FAILED:CNF-0098 <classification> with "
    "the diagnostic tail attached."
)
QUESTION = (
    "Can the macOS support claim be tested at all on this estate? Determine "
    "whether any macOS runner is reachable, and if so run the install and "
    "health check there; if not, produce a proof-of-impossibility naming the "
    "exact missing prerequisite and downgrade every macOS row in the "
    "compatibility matrix from supported to untested. Do not let an untested "
    "platform read as supported."
)


def _signal_block(raw: dict) -> dict:
    return {
        "id": raw["id"],
        "method": raw["method"],
        "observation": raw["observation"],
        "fingerprint": raw["fingerprint"],
        "this_host_darwin": raw.get("this_host_darwin"),
        "macos_provisioned": raw.get("macos_provisioned"),
        "macos_runner_present": raw.get("macos_runner_present"),
        "observations": raw.get("observations"),
    }


def build() -> dict:
    live = E.macos_reachable(REPO)
    s1 = live["signal_command"]
    s2 = live["signal_catalogue"]
    if s1["method"] == s2["method"]:
        raise SystemExit("FAILED:CNF-0098 signals share a method (not independent)")

    macos_run = None
    if live["reachable"]:
        macos_run = {
            "ran": False,
            "health_ok": False,
            "reason": "reachable-but-no-published-install-artifact",
        }
    rows = M.amend(live["reachable"], macos_run)
    M.assert_honest(rows)

    missing = (
        "a reachable macOS execution substrate (this-host Darwin, or a named "
        "macOS CI runner / tart-or-ssh hop that can actually exec sw_vers)"
    )
    classification = "platform-unreachable"
    if live["reachable"]:
        classification = "untested-claimed-supported"
        missing = (
            "a published installable artifact plus a completed Darwin "
            "install+health run"
        )

    tests = [
        {
            "id": "T1-two-independent-runner-absence-or-presence-probes",
            "result": "PASS",
            "detail": (
                f"methods={s1['method']}+{s2['method']} "
                f"this_host_darwin={live['this_host_darwin']} "
                f"catalogue_macos={live['catalogue_macos']} "
                f"hop={live['hop_available']}"
            ),
        },
        {
            "id": "T2-every-macos-row-tested-pass-tested-fail-or-untested",
            "result": "PASS",
            "detail": [
                {
                    "id": r["id"],
                    "evidence_state": r["evidence_state"],
                    "amended_tier": r["amended_tier"],
                }
                for r in rows
                if r["os"] == "macos"
            ],
        },
        {
            "id": "T3-same-treatment-for-never-exercised-platforms",
            "result": "PASS",
            "detail": [
                {
                    "id": r["id"],
                    "os": r["os"],
                    "declared_tier": r["declared_tier"],
                    "amended_tier": r["amended_tier"],
                    "evidence_state": r["evidence_state"],
                }
                for r in rows
            ],
        },
    ]

    doc = {
        "unit_id": "CNF-0098",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "schema_rel": SCHEMA_REL,
        "executable_schema": LOCAL_SCHEMA_REL,
        "output_schema_declared_note": (
            "catalog output_schema is a generated shim with an unresolvable "
            "$ref; the probe-local schema is the executable contract"
        ),
        "output_rel": OUT_REL,
        "question": QUESTION,
        "macos_reachable": live["reachable"],
        "this_host_darwin": live["this_host_darwin"],
        "catalogue_macos": live["catalogue_macos"],
        "hop_available": live["hop_available"],
        "missing_prerequisite": missing,
        "classification": classification,
        "two_signal_proof": [_signal_block(s1), _signal_block(s2)],
        "settling_experiment": {
            "name": "provision-or-attach-a-darwin-runner-and-re-probe",
            "procedure": (
                "Attach a macOS GitHub Actions runner or a tart VM, confirm "
                "sw_vers exits 0 from that substrate, run the published "
                "installable artifact and the same health check used for a "
                "clean Linux install, then rewrite every macos matrix row to "
                "tested-pass or tested-fail from that run. A second uname "
                "from this Linux host must not be accepted as the second signal."
            ),
        },
        "falsifier": (
            "Any live Darwin substrate on this estate where /usr/bin/sw_vers "
            "exits 0, or a hop (tart list nonempty / ssh Host named macos*) "
            "that can exec the same binary."
        ),
        "expiry": "2026-11-24",
        "matrix_source": (
            "reconstructed-from-catalog-CNF-0096-0097-0098-and-IMP-0013-0014-0015; "
            "no on-disk compatibility-matrix artifact present"
        ),
        "matrix_rows": rows,
        "macos_run": macos_run,
        "tests": tests,
        "reviewers": [
            {
                "id": "CNF-0098-probe1-command-signal",
                "independent": True,
                "sees_other_verdict_before_filing": False,
                "role": "re-run Darwin identity + failed provision commands",
            },
            {
                "id": "CNF-0098-probe2-catalogue-schema",
                "independent": True,
                "sees_other_verdict_before_filing": False,
                "role": "re-run runner catalogue + schema both-states + matrix honesty",
            },
        ],
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record "
                "(spec 11039), never an error to retry away"
            ),
        },
        "produced_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    S.assert_valid(doc)
    S.both_states(doc)
    return doc


def main() -> int:
    doc = build()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:CNF-0098 sentinel absent from serialized artifact")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    macos_states = [
        r["evidence_state"] for r in doc["matrix_rows"] if r["os"] == "macos"
    ]
    print(
        f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))} "
        f"reachable={doc['macos_reachable']} macos_rows={macos_states}"
    )
    print("SUCCESS:CNF-0098 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
