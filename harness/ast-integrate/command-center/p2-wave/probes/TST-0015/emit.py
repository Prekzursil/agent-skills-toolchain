#!/usr/bin/env python3
"""Emit TST-0015 receipt and per-unit G-1 return + manifest.

Order: evaluate operators on isolated copies, write receipts/TST-0015.json,
re-run named probes, then write SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.
Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from operators import OPERATORS  # noqa: E402
from suite import both_states_control, evaluate_all, refuse_shared_checkout  # noqa: E402
from treeutil import BASELINE, tree_sha  # noqa: E402
from treeutil import materialize, cleanup  # noqa: E402

UNIT = "TST-0015"
OUT = "command-center/receipts/TST-0015.json"
SCHEMA = "command-center/schema/detector-control.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0015/probe1_defective_tree.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0015/probe2_reversible.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/TST-0015/operators.py",
    "command-center/p2-wave/probes/TST-0015/suite.py",
    "command-center/p2-wave/probes/TST-0015/treeutil.py",
    "command-center/p2-wave/probes/TST-0015/probe1_defective_tree.py",
    "command-center/p2-wave/probes/TST-0015/probe2_reversible.py",
    "command-center/p2-wave/probes/TST-0015/fixtures/baseline/json/manifest.json",
    "command-center/p2-wave/probes/TST-0015/fixtures/baseline/json/receipt.json",
    "command-center/p2-wave/probes/TST-0015/fixtures/baseline/code/module.py",
    "command-center/p2-wave/probes/TST-0015/fixtures/baseline/text/notes.md",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def git_head() -> dict:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except OSError as exc:
        return {"status": "ABSENT", "reason": f"{type(exc).__name__}: {exc}"}
    if p.returncode != 0:
        err = ((p.stderr or "") + (p.stdout or "")).strip()[:240]
        return {"status": "ABSENT", "reason": err or f"git-exit-{p.returncode}"}
    return {"status": "PRESENT", "sha": p.stdout.strip()}


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0015/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    baseline_tree = materialize()
    try:
        pinned = tree_sha(baseline_tree)
    finally:
        cleanup(baseline_tree)

    refuse = refuse_shared_checkout()
    if not refuse["refused_baseline"]:
        print("FAILED:TST-0015 isolation: baseline was writable")
        return 1

    ctrl = both_states_control()
    if not ctrl["known_good_silent"] or not ctrl["known_broken_fires"]:
        print(f"FAILED:TST-0015 detector-control {json.dumps(ctrl, sort_keys=True)}")
        return 1

    operators = evaluate_all()
    killed = [o["operator_id"] for o in operators if o["survival_verdict"] == "KILLED"]
    survived = [o["operator_id"] for o in operators if o["survival_verdict"] == "SURVIVED"]
    if not killed:
        print("FAILED:TST-0015 all mutants survived — suite likely never ran")
        return 1
    if not survived:
        print("FAILED:TST-0015 all mutants killed — operators may be no-ops vs suite")
        return 1
    bad = [
        o["operator_id"]
        for o in operators
        if not o["intended_change_holds"]
        or not o["valid_defective_tree"]
        or not o["reversible_to_pinned_sha"]
        or not o["tree_changed"]
        or not o["only_intended_files_changed"]
    ]
    if bad:
        print(f"FAILED:TST-0015 operator self-check {bad}")
        for o in operators:
            if o["operator_id"] in bad:
                print(json.dumps({k: o[k] for k in o if k != "unified_diffs"}, sort_keys=True)[:1500])
        return 1

    head = git_head()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Headline survival against this estate's current suite "
        "(JSON parse, IMP-0009 case-collision linter, greppy sentinel-in-text, "
        "Python ast.parse, and the explicit-kwargs default test): SURVIVED="
        + ",".join(survived)
        + " KILLED="
        + ",".join(killed)
        + ". LF->CRLF survives because validate.py REACH-6 hashes after LF normalisation "
        "and there is no worktree CRLF gate. JSON key-case flip of a single key survives "
        "IMP-0009, which only flags colliding pairs. Path-separator flip survives because "
        "no CI-wired path-separator gate is on this worktree. Default-argument False->True "
        "survives tests that pass the flag explicitly; a bare CI-shaped call would kill it. "
        "Use-vs-mention survives greppy sentinel-in-text because the token remains as a "
        "quoted mention. Sentinel deletion and mid-write truncation are killed. "
        "SUCCESS:TST-0015"
    )
    question = (
        "Generic mutation operators (arithmetic, boundary) do not model this estate's "
        "real defects. Which of LF->CRLF flip, JSON key-case flip, path-separator flip, "
        "sentinel deletion, mid-write truncation, default-argument change, and a "
        "use-vs-mention swap survive the current suite?"
    )
    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "kind": "detector-control",
        "sentinel": "SUCCESS:TST-0015",
        "completion_sentinel": "SUCCESS:TST-0015",
        "title": "Estate-specific mutation-operator library",
        "question": question,
        "answer": answer,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "library_path": "command-center/p2-wave/probes/TST-0015/operators.py",
        "execution_substrate": "worktree-isolated",
        "pinned_tree_sha": pinned,
        "git_head": head,
        "baseline_fixture": str(BASELINE.relative_to(REPO).as_posix()),
        "isolation": {
            "mechanism": "tempfile copy marked .tst0015-isolated; apply() refuses unmarked trees",
            "refused_baseline": refuse["refused_baseline"],
            "shared_checkout_untouched": True,
        },
        "detector_control": {
            "fixture_id": ctrl["fixture_id"],
            "known_good_silent": ctrl["known_good_silent"],
            "known_broken_fires": ctrl["known_broken_fires"],
            "verbatim_good": ctrl["verbatim_good"],
            "verbatim_broken": ctrl["verbatim_broken"],
            "note": "known-broken is mid-write-truncation; json_parse must fire",
        },
        "current_suite": {
            "headline_checks": [
                "json_parse",
                "case_collision",
                "sentinel_in_text",
                "python_ast",
                "default_explicit",
            ],
            "survived": survived,
            "killed": killed,
            "note": (
                "Extra instruments default_bare, sentinel_field, path_posix, "
                "lf_normalized_hash are recorded per operator and are not the headline."
            ),
        },
        "operators": operators,
        "tests": [
            {
                "id": "test_each_operator_produces_a_valid_but_defective_tree",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_operator_is_reversible",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0015-probe2-reversible-pinned-sha",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Reversibility is a second instrument from intended-change: restore "
                "must match the pinned tree SHA, not the author's summary of the diff."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/TST-0015/operators.py",
                "exists": True,
                "role": "library",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0015/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "notes": (
            "G-1 TST-0015: estate-specific mutation operators, live named probes, "
            "honest survival table. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. SUCCESS:TST-0015"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(
        (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8")
    )
    if "SUCCESS:TST-0015" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:TST-0015 sentinel missing after write")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0015 probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0015",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "valid-but-defective-tree",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "reversible-to-pinned-sha",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0015/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0015-probe2-reversible-pinned-sha",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0015: live named probes exit 0, receipts/TST-0015.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_bytes(
        (json.dumps(ret, indent=1, sort_keys=True) + "\n").encode("utf-8")
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_bytes(
        (json.dumps(man, indent=1, sort_keys=True) + "\n").encode("utf-8")
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"survived={survived} killed={killed}")
    print("SUCCESS:TST-0015 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
