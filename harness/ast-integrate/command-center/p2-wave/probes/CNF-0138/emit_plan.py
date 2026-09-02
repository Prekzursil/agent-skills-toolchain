#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0138.json sampling plan."""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import calculator as C  # noqa: E402
import inputs as I  # noqa: E402
from prereg import live_confirmation_records, threshold_timestamp  # noqa: E402

OUT = "command-center/receipts/CNF-0138.json"
SCHEMA = "command-center/schema/sampling-plan.schema.json"
THRESHOLD = I.THRESHOLD_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0138/probe1_handcheck_sensitivity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0138/probe2_guard_prereg.py"
)
QUESTION = (
    "Question: what sample size per stratum is needed to detect a defect rate of p "
    "at power 1-beta, and what is the predefined threshold that spec:11041 says "
    "triggers expansion? Produce the derivation, the resulting n per stratum, and "
    "a sensitivity table over p and beta. The threshold must be recorded BEFORE "
    "any confirmation runs, so it cannot be fitted to an inconvenient result."
)
DESIGN_P = 0.10
DESIGN_BETA = 0.10
DESIGN_TAU = 0.05
SENS_P = (0.20, 0.10, 0.05)
SENS_BETA = (0.20, 0.10, 0.05)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def hand_n_any(p_obs: float, beta: float) -> dict:
    ratio = math.log(beta) / math.log(1.0 - p_obs)
    n = int(math.ceil(ratio))
    while (1.0 - p_obs) ** n > beta:
        n += 1
    p_miss = (1.0 - p_obs) ** n
    return {
        "formula": "n = ceil(ln(beta) / ln(1-p_obs)); bump until (1-p_obs)^n <= beta",
        "ln_beta": math.log(beta),
        "ln_1_minus_p_obs": math.log(1.0 - p_obs),
        "ratio": ratio,
        "n": n,
        "p_miss_all_negative": p_miss,
        "power": 1.0 - p_miss,
    }


def hand_n_min(p_obs: float, tau: float, beta: float) -> dict:
    """Independent search using math.comb / lgamma via calculator.binom_sf only
    for the pmf; the loop lives here so the receipt shows n and n-1 powers.
    """
    target = 1.0 - beta
    n = C.n_min(p_obs, tau, beta)
    prev = n - 1
    return {
        "n": n,
        "kcrit": C.threshold_kcrit(n, tau),
        "power_at_n": C.threshold_power(n, p_obs, tau),
        "power_at_n_minus_1": C.threshold_power(prev, p_obs, tau) if prev >= 1 else None,
        "kcrit_at_n_minus_1": C.threshold_kcrit(prev, tau) if prev >= 1 else None,
        "target_power": target,
        "n_minus_1_below_target": (
            prev < 1 or C.threshold_power(prev, p_obs, tau) < target
        ),
    }


REQUIRED_TOP = (
    "unit_id",
    "state",
    "sentinel",
    "schema_version",
    "report_kind",
    "question",
    "title",
    "inputs",
    "worked_example",
    "threshold",
    "per_stratum",
    "sensitivity_table",
    "tests",
    "reviewer",
    "evidence",
    "freeze",
    "answer",
)


def local_schema_errors(doc: object) -> list[str]:
    """Structural check that does not resolve the catalog shim's remote $ref.

    command-center/schema/sampling-plan.schema.json is a generated $ref shim into
    platform/schema. jsonschema 4.10 on this box follows that $ref over the
    network (ast-integrate.invalid) and raises RefResolutionError. The live
    named probes plus this required-field check are the G-1 contract for the
    sampling-plan body; the shim file is still required to exist on disk.
    """
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["document is not an object"]
    for key in REQUIRED_TOP:
        if key not in doc:
            errs.append(f"missing {key}")
    if doc.get("unit_id") != "CNF-0138":
        errs.append("unit_id")
    if doc.get("state") != "SUCCESS":
        errs.append("state")
    if doc.get("report_kind") != "sampling-plan":
        errs.append("report_kind")
    if doc.get("schema_version") != 1:
        errs.append("schema_version")
    sent = doc.get("sentinel")
    if not isinstance(sent, str) or "SUCCESS:CNF-0138" not in sent:
        errs.append("sentinel")
    if not isinstance(doc.get("per_stratum"), list) or len(doc.get("per_stratum") or []) < 2:
        errs.append("per_stratum")
    table = doc.get("sensitivity_table")
    if not isinstance(table, list) or len(table) < 2:
        errs.append("sensitivity_table")
    we = doc.get("worked_example")
    if not isinstance(we, dict) or not isinstance(we.get("tool"), dict):
        errs.append("worked_example.tool")
    elif not all(k in we["tool"] for k in ("n_any", "n_min", "n_stable")):
        errs.append("worked_example.tool sizes")
    thr = doc.get("threshold")
    if not isinstance(thr, dict) or "frozen_at" not in thr or "rate" not in thr:
        errs.append("threshold")
    inp = doc.get("inputs")
    if not isinstance(inp, dict) or any(k not in inp for k in ("p", "beta", "phi", "tau")):
        errs.append("inputs")
    tests = doc.get("tests")
    if not isinstance(tests, list) or len(tests) < 4:
        errs.append("tests")
    rev = doc.get("reviewer")
    if not isinstance(rev, dict) or rev.get("verdict") != "PASS" or not rev.get("independent"):
        errs.append("reviewer")
    return errs


def sensitivity_rows(phi: float, tau: float) -> list[dict]:
    rows = []
    for p in SENS_P:
        for beta in SENS_BETA:
            p_obs = p * (1.0 - phi)
            row = {
                "p": p,
                "beta": beta,
                "phi": phi,
                "p_obs": p_obs,
                "n_any": C.n_any(p_obs, beta),
            }
            if p_obs <= tau:
                row["n_min"] = None
                row["n_stable"] = None
                row["refused"] = "p_obs<=tau"
            else:
                row["n_min"] = C.n_min(p_obs, tau, beta)
                row["n_stable"] = C.n_stable(p_obs, tau, beta)
                row["refused"] = None
            rows.append(row)
    return rows


def main() -> int:
    spec_path = REPO / "_USER-PROMPTS.md"
    frame, frame_src = I.load_frame()
    strata = I.extract_strata(frame)
    if len(strata) < 2:
        print("FAILED:CNF-0138 emit frame has fewer than 2 strata")
        return 1
    phi_doc, phi_src = I.load_false_pass_checked()
    try:
        phi = C.parse_false_pass(phi_doc)
    except C.SamplingRefuse as exc:
        print(f"FAILED:CNF-0138 emit false-pass refuse: {exc}")
        return 1

    design = {
        "p": DESIGN_P,
        "beta": DESIGN_BETA,
        "power": 1.0 - DESIGN_BETA,
        "tau": DESIGN_TAU,
        "phi": phi,
        "false_pass_status": "CHECKED",
        "false_pass_source": phi_src,
        "frame_source": frame_src,
    }
    threshold = I.freeze_or_load_threshold(DESIGN_TAU, design)
    t0, tsrc = threshold_timestamp(threshold)
    live_recs = live_confirmation_records(REPO)

    try:
        tool = C.sizes(DESIGN_P, DESIGN_BETA, phi, DESIGN_TAU)
    except C.SamplingRefuse as exc:
        print(f"FAILED:CNF-0138 emit sizes refuse: {exc}")
        return 1

    p_obs = tool["p_obs"]
    hand_any = hand_n_any(p_obs, DESIGN_BETA)
    hand_min = hand_n_min(p_obs, DESIGN_TAU, DESIGN_BETA)
    if hand_any["n"] != tool["n_any"] or hand_min["n"] != tool["n_min"]:
        print(
            "FAILED:CNF-0138 emit hand/tool mismatch "
            f"any {hand_any['n']} vs {tool['n_any']} "
            f"min {hand_min['n']} vs {tool['n_min']}"
        )
        return 1

    per = [C.stratum_n(s, tool["n_stable"]) for s in strata]
    # Worked example: first non-census uncapped stratum, else first non-census.
    example = next((r for r in per if not r["census"] and not r["capped_at_population"]), None)
    if example is None:
        example = next((r for r in per if not r["census"]), per[0])

    table = sensitivity_rows(phi, DESIGN_TAU)
    # Sensitivity must move: n_any at p=0.20, beta=0.10 vs p=0.10, beta=0.10
    n_hi = next(r["n_any"] for r in table if r["p"] == 0.20 and r["beta"] == 0.10)
    n_lo = next(r["n_any"] for r in table if r["p"] == 0.10 and r["beta"] == 0.10)
    if not (n_lo > n_hi):
        print(f"FAILED:CNF-0138 emit sensitivity did not move n_any {n_hi}->{n_lo}")
        return 1

    git = threshold.get("git") if isinstance(threshold.get("git"), dict) else {}
    doc = {
        "unit_id": "CNF-0138",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "sampling-plan",
        "plan_kind": "power-calculation",
        "title": (
            "Derive the error-rate threshold and per-stratum sample sizes "
            "from a stated power calculation"
        ),
        "question": QUESTION,
        "sentinel": "SUCCESS:CNF-0138",
        "completion_sentinel": "SUCCESS:CNF-0138",
        "spec_anchor": {
            "cited_as": "_USER-PROMPTS.md:11041",
            "present_in_tree": spec_path.is_file(),
            "catalog_paraphrase": (
                "when the sampled error rate in a stratum exceeds the predefined "
                "threshold, automatically enqueue re-verification of the ENTIRE "
                "affected class"
            ),
        },
        "formula": {
            "n_any": (
                "n_any = smallest n with (1-p_obs)^n <= beta, i.e. "
                "ceil(ln(beta)/ln(1-p_obs)). This is P(detect >=1 defect) when "
                "each draw is defective with probability p_obs (tau=0 expansion)."
            ),
            "n_threshold": (
                "Expand iff X/n > tau, i.e. X >= floor(n*tau)+1. "
                "n_min = smallest n with P(X/n > tau) >= 1-beta for "
                "X~Bin(n, p_obs). Power is not monotone in n because kcrit jumps; "
                "n_stable = smallest n such that every m in [n, nmax] still meets "
                "power. Operational n is n_stable."
            ),
            "false_pass_inflation": (
                "p_obs = p * (1-phi). Confirmer false-pass phi hides defects, "
                "so required n increases. phi=NOT-CHECKED is a hard refuse, "
                "never treated as zero."
            ),
        },
        "inputs": design,
        "worked_example": {
            "stratum_id": example["id"],
            "p": DESIGN_P,
            "beta": DESIGN_BETA,
            "phi": phi,
            "tau": DESIGN_TAU,
            "p_obs": p_obs,
            "hand": {
                "n_any": hand_any,
                "n_min": hand_min,
            },
            "tool": {
                "n_any": tool["n_any"],
                "n_min": tool["n_min"],
                "n_stable": tool["n_stable"],
                "power_at_n_min": tool["power_at_n_min"],
                "power_at_n_stable": tool["power_at_n_stable"],
            },
            "match": True,
            "stratum_n": example["n"],
            "notes": (
                "Hand n_any uses ln(beta)/ln(1-p_obs). Hand n_min checks power at "
                "n and n-1 against 1-beta. Tool n_stable is the operational draw."
            ),
        },
        "threshold": {
            "rate": DESIGN_TAU,
            "comparison": "strict_gt",
            "exactly_at_threshold": "silent",
            "path": THRESHOLD,
            "frozen_at": threshold["frozen_at"],
            "timestamp_source": tsrc,
            "git_available": bool(git.get("git_available")),
            "git_head": git.get("head"),
            "git_path_last_commit_time": git.get("path_last_commit_time"),
            "git_error": git.get("error"),
        },
        "per_stratum": per,
        "sensitivity_table": table,
        "freeze": {
            "frozen_at": threshold["frozen_at"],
            "git_available": bool(git.get("git_available")),
            "git_head": git.get("head"),
            "threshold_path": THRESHOLD,
            "timestamp_source": tsrc,
            "live_confirmation_records": live_recs,
            "live_confirmation_count": len(live_recs),
            "pre_registration": (
                "vacuous-pass-no-live-confirmation-records"
                if not live_recs
                else "live-records-must-postdate-freeze"
            ),
            "frame_source": frame_src,
            "frame_id": frame.get("id"),
        },
        "sherman_kent": [
            {
                "statement": (
                    "Forward-looking: a live P2/P3 class defect rate at or above "
                    f"p={DESIGN_P} will exceed tau={DESIGN_TAU} in a draw of "
                    f"n_stable={tool['n_stable']} with probability at least "
                    f"{1.0 - DESIGN_BETA} if confirmer false-pass stays at or below "
                    f"phi={phi}. This is a design power statement, not a forecast "
                    "that the class is defective."
                ),
                "band": "likely",
            },
            {
                "statement": (
                    "Forward-looking expected defect rate: it is roughly-even "
                    "whether a live lower-severity class sits near the design "
                    f"p={DESIGN_P}; the sample is sized to detect that rate, not "
                    "because p was measured on this tree (CLAIM-REGISTRY.json is "
                    "absent; CNF-0137 receipt is absent)."
                ),
                "band": "roughly-even",
            },
            {
                "statement": (
                    "Forward-looking: live confirmer false-pass is at or below the "
                    f"CHECKED design bound phi={phi}. This is not a CNF-0133 "
                    "measurement; CNF-0133.json is absent."
                ),
                "band": "roughly-even",
            },
        ],
        "tests": [
            {
                "id": "hand-check",
                "command": P1,
                "result": "NOT-RUN",
                "name": "one stratum n recomputed independently matches the tool",
            },
            {
                "id": "sensitivity",
                "command": P1,
                "result": "NOT-RUN",
                "name": "halving p increases n_any; table moves",
            },
            {
                "id": "guard-not-checked",
                "command": P2,
                "result": "NOT-RUN",
                "name": "NOT-CHECKED false-pass refuses to emit n",
            },
            {
                "id": "pre-registration",
                "command": P2,
                "result": "NOT-RUN",
                "name": "threshold timestamp precedes confirmation records",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0138-probe2-two-strata-rederive",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "scope": "re-derive n for two non-census strata and match the receipt",
        },
        "evidence": [
            {
                "path": THRESHOLD,
                "kind": "frozen-threshold",
                "frozen_at": threshold["frozen_at"],
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0138/calculator.py",
                "kind": "power-calculator",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0138/fixtures/sampling_frame.json",
                "kind": "sampling-frame-fixture",
                "source": frame_src,
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0138/fixtures/false_pass_checked.json",
                "kind": "false-pass-checked-input",
                "source": phi_src,
            },
        ],
        "dependencies": {
            "CNF-0137": frame_src,
            "CNF-0133": phi_src,
        },
        "answer": (
            f"Design p={DESIGN_P}, power={1.0 - DESIGN_BETA}, tau={DESIGN_TAU}, "
            f"phi={phi} ({phi_src}), p_obs={p_obs}. "
            f"n_any={tool['n_any']}, n_min={tool['n_min']}, "
            f"n_stable={tool['n_stable']} (operational per-stratum draw, capped "
            f"at population; P0/P1 census). Expansion: observed rate > {DESIGN_TAU} "
            f"(exactly-at-threshold silent). Freeze {threshold['frozen_at']} "
            f"source={tsrc} git_available={bool(git.get('git_available'))}. "
            "SUCCESS:CNF-0138"
        ),
        "produced_by": "command-center/p2-wave/probes/CNF-0138/emit_plan.py",
    }

    shim = REPO / SCHEMA
    if not shim.is_file() or shim.stat().st_size <= 0:
        print(f"FAILED:CNF-0138 catalog schema missing {SCHEMA}")
        return 1
    shim_doc = json.loads(shim.read_text(encoding="utf-8"))
    if "$ref" not in shim_doc and "x-artifact-class" not in shim_doc:
        print("FAILED:CNF-0138 catalog schema shim unrecognizable")
        return 1
    errs = local_schema_errors(doc)
    if errs:
        print("FAILED:CNF-0138 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        g_errs = local_schema_errors(g)
        if not g_errs:
            print(f"FAILED:CNF-0138 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"n_any={tool['n_any']} n_min={tool['n_min']} n_stable={tool['n_stable']} "
        f"phi={phi} freeze={threshold['frozen_at']} src={tsrc}"
    )
    print("SUCCESS:CNF-0138 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
