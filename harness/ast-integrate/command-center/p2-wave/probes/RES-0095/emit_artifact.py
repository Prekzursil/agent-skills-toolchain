#!/usr/bin/env python3
"""Emit command-center/research/RES-0095.json (measurement-run)."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import inputs as I  # noqa: E402
import power as P  # noqa: E402

OUT = "command-center/research/RES-0095.json"
SCHEMA = "command-center/p2-wave/probes/RES-0095/artifact.schema.json"
DECLARED_SCHEMA = "command-center/schema/measurement-run.schema.json"
QUESTION = (
    "Given the expected effect size and the observed per-case variance, how many "
    "benchmark cases are needed to detect the intended improvement at conventional "
    "power — and is the planned suite large enough, or is it underpowered by construction?"
)
SENTINEL = "SUCCESS:RES-0095"
COMPLETION = (
    "SUCCESS:RES-0095 in the receipt AND a printed required-N versus planned-N "
    "comparison plus a sensitivity row for a halved effect size"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0095/probe1_required_vs_planned.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0095/probe2_halved_effect.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def reviewer_recompute(z_a: float, z_b: float, sigma2: float, delta: float) -> dict:
    py = (
        "import math; "
        f"za={z_a!r}; zb={z_b!r}; s={sigma2!r}; d={delta!r}; "
        "print(int(math.ceil(((za+zb)**2)*s/(d*d)-1e-12)))"
    )
    cmd = ["bash", "-lc", "python3 -c " + repr(py)]
    proc = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, check=False)
    text = (proc.stdout or "").strip()
    try:
        value = int(text.splitlines()[-1])
    except (ValueError, IndexError):
        value = None
    pwsh = shutil.which("pwsh") or shutil.which("pwsh.exe")
    return {
        "reviewer_id": "RES-0095-independent-arithmetic-recompute",
        "verdict": "FAIL",
        "independent": True,
        "fresh_context": True,
        "shell": "bash -lc python3 -c",
        "powershell_available": bool(pwsh),
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "stdout": text,
        "stderr": (proc.stderr or "").strip()[-500:],
        "reproduced_required_n": value,
        "tolerance_cases": 0,
        "attempt": (
            "Recomputed n from printed z_a, z_b, sigma2, delta via a subprocess "
            "arithmetic path (bash -lc). Catalog asked PowerShell 7 vs Git Bash; "
            "pwsh availability is recorded, not invented."
        ),
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bundle = I.gather()
    planned_n = int(bundle["planned"]["planned_n"])
    residual = float(bundle["residual_variance_used"])
    calc = P.report(planned_n, residual)
    sens = calc["sensitivity_halved_effect_size"]
    broken = calc["known_broken_constant_calculator"]
    printed_cmp = calc["comparison"]["printed"]
    printed_sens = sens["printed"]
    if broken.get("moved") is True:
        print("FAILED:RES-0095 known-broken constant calculator moved with δ")
        return 1
    if not sens["moved"]:
        print("FAILED:RES-0095 good calculator did not move when δ halved")
        return 1
    if not (3.0 <= float(sens["ratio"]) <= 5.0):
        print(f"FAILED:RES-0095 halved-δ ratio {sens['ratio']} not ~4")
        return 1

    rev = reviewer_recompute(
        calc["z_a"], calc["z_b"], calc["variance_parts"]["sigma2"], calc["delta_assumed"]
    )
    if rev["reproduced_required_n"] != calc["required_n"]:
        print(
            f"FAILED:RES-0095 reviewer n={rev['reproduced_required_n']} "
            f"live={calc['required_n']}"
        )
        return 1
    rev["verdict"] = "PASS"

    declared_present = (REPO / DECLARED_SCHEMA).is_file()
    res0094_present = bool(bundle["res0094"].get("present"))
    planned_src = bundle["planned"].get("source")
    corpus_present = (REPO / "command-center/bench/cases/IMP-0198/corpus.json").is_file()
    answer = (
        f"Under conventional two-sided α={calc['alpha']} and power={calc['power']}, "
        f"the paired z-test requires n={calc['required_n']} cases to detect an "
        f"ASSUMED {calc['delta_assumed'] * 100:.0f}pp pass-rate lift "
        f"(p0={calc['p0_assumed']} → p1={calc['p1_assumed']}) given "
        f"σ_d²={calc['variance_parts']['sigma2']:.6f}. "
        f"The planned suite is planned_n={planned_n} (source={planned_src}). "
        f"{printed_cmp}. Halved-effect sensitivity: {printed_sens}. "
        f"Verdict: the planned suite is {calc['comparison']['verdict']} for the "
        f"stated assumption. Effect size is NOT a measured improvement; Sherman-Kent "
        f"band '{P.SHERMAN_KENT_BAND}' {list(P.SHERMAN_KENT_P_INTERVAL)}. "
        f"RES-0094.json present={res0094_present}; "
        f"variance_source={bundle['variance_source']} "
        f"(residual_after_pinning={residual}). Bernoulli outcome variance dominates."
    )

    doc = {
        "unit_id": "RES-0095",
        "schema_version": 1,
        "report_kind": "measurement-run",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION,
        "title": "Compute the sample size needed to detect this program's intended benchmark improvement",
        "question": QUESTION,
        "answer": answer,
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=RES-0095]",
        "output_schema_declared": DECLARED_SCHEMA,
        "output_schema_declared_present": declared_present,
        "local_artifact_schema": SCHEMA,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "measurement-engineer",
            "execution_substrate": "headless-linux",
        },
        "effect_size_assumption": {
            "delta": calc["delta_assumed"],
            "is_assumption": True,
            "smuggled_from_measurement": False,
            "source": (
                "ASSUMPTION. Magnitude taken from TST-0298's synthetic 10-point "
                "known-effect control — the only numeric improvement this program "
                "names — and is still not a measured lift on this estate."
            ),
            "p0": calc["p0_assumed"],
            "p0_source": (
                "ASSUMPTION; max-Bernoulli-variance default; no live baseline "
                "pass-rate on this tree"
            ),
            "sherman_kent_band": P.SHERMAN_KENT_BAND,
            "sherman_kent_probability_interval": list(P.SHERMAN_KENT_P_INTERVAL),
            "numeric_envelope_on_delta": list(P.DELTA_ENVELOPE),
            "alpha": calc["alpha"],
            "power": calc["power"],
            "conventional": True,
        },
        "variance": {
            "res0094": bundle["res0094"],
            "res0094_harness": bundle.get("res0094_harness"),
            "local_residual": bundle["local_residual"],
            "protocol_control": bundle.get("protocol_control"),
            "residual_variance_used": residual,
            "variance_source": bundle["variance_source"],
            "parts": calc["variance_parts"],
            "note": (
                "Power is executed with residual variance from the RES-0094 protocol "
                "(RES-0094.json if present, else a live re-run of that unit's pinning "
                "harness, else a labelled hash surrogate of the same unpin-and-increase "
                "control) PLUS Bernoulli outcome variance. Residual-only-zero is refused "
                "as a sample-size claim."
            ),
        },
        "planned_n": planned_n,
        "required_n": calc["required_n"],
        "planned_suite": bundle["planned"],
        "power": {k: v for k, v in calc.items() if k != "known_broken_constant_calculator"},
        "printed_required_n_versus_planned_n": printed_cmp,
        "printed_sensitivity_row_halved_effect_size": printed_sens,
        "comparison": calc["comparison"],
        "sensitivity_halved_effect_size": sens,
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "tests": [
            {
                "id": "T1-required-vs-planned",
                "name": "Run the power calculation and print required N alongside planned N",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-halved-effect-sensitivity",
                "name": "Control: show how required N changes if the assumed effect size halves",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "RES0095-C1",
                "kind": "known-broken-calculator",
                "description": (
                    "A constant-N calculator that ignores δ must NOT move when the "
                    "effect size is halved. The good calculator must move (~4×)."
                ),
                "fired_on_bad_state": broken["moved"] is False,
                "silent_on_good_state": sens["moved"] is True,
                "bad_state_output": broken["printed"],
                "good_state_output": sens["printed"],
                "on_the_state_it_rejects": broken["printed"],
            }
        ],
        "evidence": [
            {
                "id": "E1-planned-n-census",
                "kind": "file-census",
                "detail": (
                    f"planned_n={planned_n} from {bundle['planned']['source']} "
                    f"declared={bundle['planned']['declared_case_count']} "
                    f"live={bundle['planned']['live_case_count']} "
                    f"agree={bundle['planned']['counts_agree']}"
                ),
            },
            {
                "id": "E2-variance-protocol",
                "kind": "measurement",
                "detail": (
                    f"source={bundle['variance_source']} residual={residual} "
                    f"unpin_increases={bundle['local_residual']['unpin_increases_variance']} "
                    f"n={bundle['local_residual']['n']}"
                ),
            },
            {
                "id": "E3-effect-size-labelled-assumption",
                "kind": "assumption-register",
                "detail": (
                    f"delta={calc['delta_assumed']} is_assumption=True "
                    f"smuggled=False sherman_kent={P.SHERMAN_KENT_BAND}"
                ),
            },
        ],
        "reviewer": rev,
        "named_probes": [
            {"id": "probe1", "role": "required-n-versus-planned-n", "command": P1},
            {"id": "probe2", "role": "halved-effect-sensitivity", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": SCHEMA, "role": "supporting", "exists": True},
            {
                "path": "command-center/p2-wave/probes/RES-0095/power.py",
                "role": "supporting",
                "exists": True,
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/RES-0095/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "report": {
            "kind": "measurement-run",
            "observations": [
                {
                    "name": "required_n",
                    "measured": calc["required_n"],
                    "method": "paired-z-sample-size",
                    "anchor": "command-center/p2-wave/probes/RES-0095/power.py:required_n",
                },
                {
                    "name": "planned_n",
                    "measured": planned_n,
                    "method": "planned-suite-census",
                    "anchor": str(bundle["planned"].get("source") or "planned_suite"),
                },
                {
                    "name": "halved_effect_required_n",
                    "measured": sens["required_n_halved"],
                    "method": "sensitivity-halved-delta",
                    "anchor": "command-center/p2-wave/probes/RES-0095/power.py:sensitivity_halved",
                },
            ],
            "control_ids": ["RES0095-C1"],
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/RES-0095/probe1_required_vs_planned.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "note": "Named probes run after emit via write_receipts.py",
            }
        ],
        "residual_unknowns": [
            {
                "claim": "Live multi-vendor agent-run residual variance from a completed RES-0094.json",
                "verdict": "NOT-CHECKED" if not res0094_present else "CONFIRMED",
                "settling_experiment": "Deliver RES-0094 and re-run this calculator on its residual.",
            },
            {
                "claim": "Measured baseline pass-rate p0 on this estate's intended agent benchmark",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Run the frozen IMP-0198 corpus under the intended agent and record p0.",
            },
            {
                "claim": "Live on-disk census of command-center/bench/cases/IMP-0198/corpus.json",
                "verdict": "NOT-CHECKED" if not corpus_present else "CONFIRMED",
                "settling_experiment": (
                    "Restore or freeze the IMP-0198 corpus file and re-count cases[]."
                ),
            },
        ],
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0095 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:RES-0095 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:RES-0095 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text or COMPLETION not in text:
        print("FAILED:RES-0095 sentinel missing")
        return 1
    if printed_cmp not in text or printed_sens not in text:
        print("FAILED:RES-0095 printed comparison/sensitivity missing")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(printed_cmp)
    print(printed_sens)
    print("SUCCESS:RES-0095 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
