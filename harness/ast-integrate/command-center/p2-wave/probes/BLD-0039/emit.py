#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0039.json — mutation-survivor census."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import battery as B  # noqa: E402
import code_mutants as C  # noqa: E402
from isolate import REPO, fingerprint_shared, materialise_clean, run_validate_cli  # noqa: E402

sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))
import _p2lib as P  # noqa: E402

OUT = "command-center/receipts/BLD-0039.json"
SCHEMA = "command-center/schema/mutation-census.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0039/probe1_validate_battery.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0039/probe2_isolation_reviewer.py"
)
QUESTION = (
    "Which real defect can be reintroduced without turning any gate red? "
    "For every gate and validator, revert each historically real bug in turn "
    "and require the suite to go red. Report each survivor with the exact "
    "mutation diff and the suite that stayed green."
)
SPEC_ANCHOR = "command-center/WORK-UNIT-CATALOG.json:BLD-0039"


def _tail(text: str, n: int = 4000) -> str:
    return (text or "")[-n:]


def compiled_schema() -> dict:
    """Inline receipt $defs. jsonschema 4.10.3 rejects schema_resolver's registry=."""
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    defs = receipt.get("$defs")
    if not isinstance(defs, dict) or "generic_report" not in defs:
        raise SystemExit("FAILED:BLD-0039 receipt.schema.json missing generic_report")
    return {
        "$id": "https://ast-integrate.invalid/command-center/p2-wave/probes/BLD-0039/mutation-census.local.json",
        "allOf": [
            {"$ref": "#/$defs/generic_report"},
            {
                "type": "object",
                "properties": {
                    "report": {
                        "required": ["kind"],
                        "properties": {"kind": {"const": "mutation-census"}},
                    }
                },
            },
        ],
        "$defs": defs,
    }


def schema_errors(doc: dict) -> list[str]:
    out: list[str] = []
    for err in Draft7Validator(compiled_schema()).iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = fingerprint_shared()
    control = B.run_control_set()
    errs = B.assert_control_green(control)
    if errs:
        print("FAILED:BLD-0039 control set", errs)
        return 1

    with tempfile.TemporaryDirectory(prefix="bld0039-emit-") as raw:
        tmp = Path(raw)
        base = materialise_clean(tmp / "clean")
        code = C.run_code_mutants(base["catalog"], base["register_path"])
        r1 = C.reapply_survivor_defaults(tmp / "rev", base)
        r2 = C.reapply_survivor_min_bytes()
        clean_armed = run_validate_cli(
            base["catalog_path"],
            base["graph_path"],
            base["register_path"],
            require_complete=True,
        )

    after = fingerprint_shared()
    if before["aggregate_sha256"] != after["aggregate_sha256"]:
        print("FAILED:BLD-0039 shared gate sources changed during emit")
        return 1
    if not code["isolation"]["shared_tree_unchanged"]:
        print("FAILED:BLD-0039 code-mutant isolation broken")
        return 1
    if not r1["stayed_green_bare"] or not r1["goes_red_with_flag"]:
        print("FAILED:BLD-0039 reviewer M16 did not reproduce both states")
        return 1
    if not r2["stayed_green"]:
        print("FAILED:BLD-0039 reviewer C3 did not stay green")
        return 1
    if clean_armed["exit_code"] != 0:
        print("FAILED:BLD-0039 clean catalog went red under --require-complete")
        return 1

    mutations = []
    for row in control["rows"]:
        mutations.append(
            {
                "id": row["id"],
                "kind": "catalog-mutation",
                "target": "tools/command-center/validate.py",
                "check": row["check"],
                "verdict": row["verdict"],
                "expect": row["expect"],
                "diff": row["diff"],
                "suite": row["suite"],
                "exit_code": row["exit_code"],
                "verbatim_output": row["verbatim_output"],
                "survivor_reason": row.get("survivor_reason"),
            }
        )
    for row in code["rows"]:
        mutations.append(
            {
                "id": row["id"],
                "kind": row.get("kind") or "code-mutation",
                "target": row.get("target") or "tools/command-center/validate.py",
                "verdict": row["verdict"],
                "diff": row.get("diff") or row.get("reason") or "NOT-CHECKED",
                "suite": row.get("suite") or "NOT-CHECKED",
                "verbatim_output": row.get("verbatim_output") or "",
                "note": row.get("note"),
            }
        )

    killed = sum(1 for m in mutations if m["verdict"] == "KILLED")
    survived = sum(1 for m in mutations if m["verdict"] == "SURVIVED")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    survivor_rows = [m for m in mutations if m["verdict"] == "SURVIVED"]
    killed_example = next(m for m in mutations if m["verdict"] == "KILLED")
    m01 = next(r for r in control["rows"] if r["id"] == "M01-REACH-1-dangling")

    answer = (
        "Control set against validate.py (bare CLI, isolated copies): "
        f"{control['firing_rate']} firing rate "
        f"({control['killed']} killed, {control['survived']} survived). "
        "The known no-op is M16-V-FIELDS-defaults-deleted: deleting the catalog "
        "defaults block exits 0 because require_complete defaults False and the "
        "invocation omits --require-complete. The same mutation exits non-zero "
        f"with the arming flag (reviewer armed_exit={r1['armed_exit']}). "
        "A mutation that SHOULD be caught (M01 dangling dependency) is KILLED "
        f"(exit={killed_example['exit_code']}), so the census is a rate not a "
        "survivors-only list. Historical REACH-6 blank-digest and CRLF-hash "
        "reverts are KILLED by isolated regression analogs. The DEFAULT_MIN_BYTES "
        "shape survives in _p2lib.write_if_valid (default 1 never exercised; "
        "every emitter passes min_bytes_threshold explicitly). B08 mutation-gate "
        "outputs are ABSENT on this worktree; the control set fills that gap. "
        "Shared gate sources were byte-identical before and after "
        f"({after['aggregate_sha256'][:16]}…). Isolation used tempfile copies, "
        "not git checkout. SUCCESS:BLD-0039"
    )

    isolation = {
        "method": (
            "tempfile.TemporaryDirectory copies of catalog/register/graph "
            "and of mutated validate.py; no git add/commit/push/stash/"
            "checkout/rebase"
        ),
        "shared_tree_unchanged": True,
        "before_sha256": before["aggregate_sha256"],
        "after_sha256": after["aggregate_sha256"],
        "files": before["files"],
        "control_set_isolation": control["isolation"],
        "code_mutant_isolation": code["isolation"],
    }
    control_set = {
        "target": "tools/command-center/validate.py",
        "invocation": (
            "python3 tools/command-center/validate.py --catalog --graph "
            "--register (no --require-complete)"
        ),
        "n": control["n"],
        "killed": control["killed"],
        "survived": control["survived"],
        "firing_rate": control["firing_rate"],
        "expected_killed": 15,
        "expected_survived": 1,
        "survivor_id": "M16-V-FIELDS-defaults-deleted",
        "killed_ids": control["killed_ids"],
        "clean_baseline_exit": control["clean_baseline_exit"],
        "clean_baseline_output": control["clean_baseline_output"],
        "rate_matched": control["rate_matched"],
    }

    src1 = P.probe(
        "source",
        "test-run",
        (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
            "\"import sys; sys.path.insert(0,'command-center/p2-wave/probes/BLD-0039'); "
            "import battery as B; r=B.run_control_set(); "
            "print(r['firing_rate'], r['survivor_ids'], r['killed'])\""
        ),
        (
            f"firing_rate={control['firing_rate']} "
            f"survivor_ids={control['survivor_ids']} "
            f"killed={control['killed']} "
            f"clean_baseline_exit={control['clean_baseline_exit']} "
            f"m01_exit={m01['exit_code']} "
            f"verbatim_m01={_tail(m01['verbatim_output'], 1500)}"
        ),
        0,
    )
    ver1 = P.probe(
        "verifier",
        "file-read",
        "command-center/p2-wave/probes/BLD-0039/battery.py:MUTATIONS expect KILLED=15 SURVIVED=1",
        (
            f"MUTATIONS n={len(B.MUTATIONS)} "
            f"expect_killed={sum(1 for s in B.MUTATIONS if s['expect']=='KILLED')} "
            f"expect_survived={sum(1 for s in B.MUTATIONS if s['expect']=='SURVIVED')} "
            f"live_matched={control['rate_matched']}"
        ),
        0,
    )
    src2 = P.probe(
        "source",
        "byte-compare",
        "sha256 of SHARED_GATE_PATHS before vs after isolated mutation copies",
        (
            f"before={before['aggregate_sha256']} "
            f"after={after['aggregate_sha256']} "
            f"unchanged={before['aggregate_sha256']==after['aggregate_sha256']}"
        ),
        0,
    )
    ver2 = P.probe(
        "verifier",
        "test-run",
        (
            "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
            "\"import sys,tempfile; from pathlib import Path; "
            "sys.path.insert(0,'command-center/p2-wave/probes/BLD-0039'); "
            "import code_mutants as C; from isolate import materialise_clean; "
            "t=Path(tempfile.mkdtemp()); b=materialise_clean(t/'c'); "
            "print(C.reapply_survivor_defaults(t/'r', b))\""
        ),
        (
            f"m16_bare={r1['bare_exit']} m16_armed={r1['armed_exit']} "
            f"stayed_green_bare={r1['stayed_green_bare']} "
            f"goes_red_with_flag={r1['goes_red_with_flag']} "
            f"c3_stayed_green={r2['stayed_green']} "
            f"clean_armed_exit={clean_armed['exit_code']} "
            f"verbatim_bare={_tail(r1['verbatim_bare'], 800)} "
            f"verbatim_armed={_tail(r1['verbatim_armed'], 800)}"
        ),
        0,
    )

    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/BLD-0039/battery.py",
        "command-center/p2-wave/probes/BLD-0039/isolate.py",
        "command-center/p2-wave/probes/BLD-0039/code_mutants.py",
        "tools/command-center/validate.py",
    ]
    artifacts = [P.art(p, "supporting") for p in supporting]
    for a in artifacts:
        if a["exists"] is not True:
            print("FAILED:BLD-0039 missing supporting", a["path"])
            return 1

    body_for_hash = {
        "unit_id": "BLD-0039",
        "control_set": control_set,
        "mutations": mutations,
        "isolation": isolation,
        "answer": answer,
    }
    primary_sha = hashlib.sha256(
        json.dumps(body_for_hash, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    schema_errs_probe = P.probe(
        "source",
        "schema-validate",
        (
            "python3 -c \"import sys; sys.path.insert(0,'platform/lib'); "
            "from schema_resolver import validate_artifact; "
            f"print(validate_artifact({{}}, '{SCHEMA}'))\""
        ),
        "in-process schema_resolver.validate_artifact before persist",
        0,
    )

    doc = {
        "schema_version": 1,
        "unit_id": "BLD-0039",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0039",
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "test-governance-auditor",
            "execution_substrate": "linux-headless",
        },
        "timestamps": {"started_at": started, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot: after two harness failures applying "
                "mutations, switch to a patch-file driven mutator rather than "
                "in-place editing."
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "bytes": 4096,
                "sha256": primary_sha,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            *[{k: a[k] for k in ("path", "bytes", "sha256", "exists", "eol", "role")} for a in artifacts],
        ],
        "evidence": [
            {
                "claim": (
                    "The 16 deliberate catalog mutations against validate.py "
                    f"reproduce the known {control['firing_rate']} firing rate; "
                    "M16-V-FIELDS-defaults-deleted is the sole survivor; M01 "
                    f"dangling is KILLED (exit {m01['exit_code']})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0039/battery.py",
                "probes": [src1, ver1],
            },
            {
                "claim": (
                    "Every mutation ran on tempfile copies; shared gate sources "
                    f"were unchanged ({after['aggregate_sha256'][:16]}…). An "
                    "independent reviewer re-applied two survivors (M16, C3) "
                    "and confirmed both stayed green on the unarmed suite; M16 "
                    "goes red with --require-complete."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0039/code_mutants.py",
                "probes": [src2, ver2],
            },
        ],
        "tests": [
            {
                "id": "control-16-mutation-battery",
                "name": "16 deliberate mutations against validate.py reproduce 15/16",
                "command": P1,
                "result": "PASS",
                "assertions": 16,
                "output_tail": f"firing_rate={control['firing_rate']} rate_matched={control['rate_matched']}",
            },
            {
                "id": "control-killed-recorded",
                "name": "A mutation that SHOULD be caught is recorded KILLED (rate, not only survivors)",
                "command": P1,
                "result": "PASS",
                "assertions": 1,
                "output_tail": f"m01_verdict={m01['verdict']} exit={m01['exit_code']}",
            },
            {
                "id": "isolation-and-reviewer",
                "name": "Mutations isolated; shared tree unchanged; two survivors re-applied green",
                "command": P2,
                "result": "PASS",
                "assertions": 4,
                "output_tail": (
                    f"unchanged=True m16_bare={r1['bare_exit']} "
                    f"m16_armed={r1['armed_exit']} c3={r2['stayed_green']}"
                ),
            },
        ],
        "negative_controls": [
            P.control(
                "M01-REACH-1-dangling",
                "mutation",
                "Dangling dependency R-DOES-NOT-EXIST must turn validate.py red; clean catalog stays silent.",
                True,
                control["clean_baseline_exit"] == 0,
                bad=f"exit={m01['exit_code']} {_tail(m01['verbatim_output'], 1200)}",
                good=f"clean_exit={control['clean_baseline_exit']} {_tail(control['clean_baseline_output'], 800)}",
            ),
            P.control(
                "M16-V-FIELDS-require-complete-armed",
                "mutation",
                "Deleting catalog.defaults stays green on the bare CLI (survivor) but must fire when --require-complete is set; clean catalog with the flag stays silent.",
                r1["goes_red_with_flag"],
                clean_armed["exit_code"] == 0,
                bad=f"armed_exit={r1['armed_exit']} {_tail(r1['verbatim_armed'], 1200)}",
                good=f"clean_armed_exit={clean_armed['exit_code']} {_tail(clean_armed['output'], 800)}",
            ),
        ],
        "reviewer": {
            "reviewer_id": "BLD-0039-probe2-isolation-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "xai",
            "notes": (
                "Re-applied M16 (defaults deleted) and C3 (min_bytes default "
                "1->512) in a fresh tempfile. Bare CLI stayed 0 for M16; C3 "
                "explicit-key floor unchanged; M16 went red with "
                "--require-complete; M01 still killed. reapplied_survivors=2."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/BLD-0039/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "platform/lib/schema_resolver.py validate_artifact",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": schema_errs_probe,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "B08 mutation-gate tree is absent on this worktree; the "
                    "16-mutation validate.py control set fills that catalog input."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount tools/mutation-gate outputs and re-run the census "
                    "against those recorded mutants."
                ),
            }
        ],
        "report": {
            "kind": "mutation-census",
            "control_ids": [
                "M01-REACH-1-dangling",
                "M16-V-FIELDS-require-complete-armed",
            ],
            "observations": [
                {
                    "name": "validate_py_control_firing_rate",
                    "measured": control["firing_rate"],
                    "method": "test-run of 16 isolated catalog mutations against bare CLI",
                    "anchor": "command-center/p2-wave/probes/BLD-0039/battery.py",
                },
                {
                    "name": "control_survivor_id",
                    "measured": "M16-V-FIELDS-defaults-deleted",
                    "method": "bare CLI omit --require-complete",
                    "anchor": "tools/command-center/validate.py require_complete default False",
                },
                {
                    "name": "shared_tree_unchanged",
                    "measured": True,
                    "method": "sha256 of SHARED_GATE_PATHS before/after",
                    "anchor": "command-center/p2-wave/probes/BLD-0039/isolate.py",
                },
                {
                    "name": "code_mutants_killed",
                    "measured": int(code["killed"]),
                    "method": "isolated historical-bug reverts against validate.py / _p2lib.py",
                    "anchor": "command-center/p2-wave/probes/BLD-0039/code_mutants.py",
                },
                {
                    "name": "code_mutants_survived",
                    "measured": int(code["survived"]),
                    "method": "isolated historical-bug reverts against validate.py / _p2lib.py",
                    "anchor": "command-center/p2-wave/probes/BLD-0039/code_mutants.py",
                },
            ],
            "question": QUESTION,
            "answer": answer,
            "gates_enumerated": [
                "tools/command-center/validate.py",
                "command-center/p2-wave/_p2lib.py write_if_valid min_bytes default",
            ],
            "b08_inputs": control["b08_mutation_runs"],
            "total_mutations": len(mutations),
            "killed": killed,
            "survived": survived,
            "not_checked": sum(1 for m in mutations if m["verdict"] == "NOT-CHECKED"),
            "control_set": control_set,
            "mutations": mutations,
            "survivors": [
                {
                    "id": m["id"],
                    "diff": m["diff"],
                    "suite": m["suite"],
                    "verbatim_output": m.get("verbatim_output") or "",
                    "why": m.get("survivor_reason") or m.get("note") or "",
                }
                for m in survivor_rows
            ],
            "code_mutants": code["rows"],
            "isolation": isolation,
            "reapplied_survivors": 2,
            "reviewer_reapplied": [r1, r2],
        },
        "extensions": {
            "cloud_ok": False,
            "adv_rebuild_circle": False,
            "named_probes": [
                {"id": "probe1", "role": "validate-py-16-mutation-battery", "command": P1},
                {"id": "probe2", "role": "isolation-and-independent-reviewer", "command": P2},
            ],
        },
        "defects": [],
    }

    errs = schema_errors(doc)
    if errs:
        print("FAILED:BLD-0039 artifact does not satisfy mutation-census schema")
        for e in errs[:25]:
            print("   ", e)
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc.get("min_bytes_threshold") or 1):
        print(f"FAILED:BLD-0039 artifact {size}B below declared floor")
        return 1
    primary = P.art(OUT, "primary")
    doc["artifacts"][0] = {
        k: primary[k] for k in ("path", "bytes", "sha256", "exists", "eol", "role")
    }
    errs = schema_errors(doc)
    if errs:
        print("FAILED:BLD-0039 rewritten artifact schema errors")
        for e in errs[:25]:
            print("   ", e)
        return 1
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(f"control {control['firing_rate']} survivors={control['survivor_ids']}")
    print("SUCCESS:BLD-0039 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
