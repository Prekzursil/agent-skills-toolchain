#!/usr/bin/env python3
"""Independent evaluators for the 21 program stopping conditions.

Spec text is reconstructed from WORK-UNIT-CATALOG.json anchors because
_USER-PROMPTS.md is absent on this worktree. Live verdicts are derived from
disk (and in-memory fixtures for detector controls), never from a prior-lane
sidecar. Missing evidence yields NOT-CHECKED plus the settling experiment.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0187/probe1_live_controls.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0187/probe2_independence.py"
)
FLOOR_WU = 2048
FLOOR_WF = 160
FLOOR_BP = 96
FLOOR_PROTO = 48
FLOOR_PRESET = 64
FLOOR_OPT = 160
CANARY_TOKEN = "SYNTHETIC_CANARY_TOKEN_CNF0187_NOT_A_SECRET"
VERDICTS = frozenset({"TRUE", "FALSE", "NOT-CHECKED"})


def _v(verdict: str, reason: str, **extra: Any) -> dict:
    if verdict not in VERDICTS:
        raise ValueError(verdict)
    row = {"verdict": verdict, "reason": reason}
    row.update(extra)
    return row


def _nc(experiment: str, reason: str) -> dict:
    return _v("NOT-CHECKED", reason, settling_experiment=experiment)


def _present(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def load_catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def count_work_units(catalog: dict) -> dict:
    units = [u for u in (catalog.get("work_units") or []) if isinstance(u, dict)]
    ids = [str(u.get("id") or "") for u in units]
    uniq = {i for i in ids if i}
    return {
        "extractor_len": len(units),
        "extractor_unique_ids": len(uniq),
        "agree": len(units) == len(uniq),
        "floor": FLOOR_WU,
    }


def build_live_world(repo: Path | None = None) -> dict:
    root = repo or REPO
    catalog = load_catalog()
    wu = count_work_units(catalog)
    cc = root / "command-center"
    return {
        "kind": "live",
        "repo": str(root),
        "option_rows": None,
        "requirement_rows": None,
        "ci_attempts_max": None,
        "required_tests_red": None,
        "suites_with_observed_failing_control": None,
        "secret_scan_complete": False,
        "secret_hits": None,
        "compat_untested_as_supported": None,
        "benchmark_net": None,
        "reviewer_independent_pass": None,
        "manifest_disk_delta": None,
        "release_scanner_fresh": None,
        "docs_code_divergence": None,
        "release_mode": "PR-ONLY",
        "release_mode_source": "catalog-unit-input-CNF-0187",
        "owner_decisions_present": _present(cc / "OWNER-DECISIONS.md"),
        "canary_channel_present": False,
        "canary_success": False,
        "rollback_rehearsal_pass": None,
        "unknowns_missing_experiment": None,
        "workflow_candidates_qualified": None,
        "blueprints_executable": None,
        "council_protocols": None,
        "presets": None,
        "work_unit_count": wu["extractor_len"],
        "work_unit_count_b": wu["extractor_unique_ids"],
        "work_unit_extractors_agree": wu["agree"],
        "platform_options": None,
        "completion_gates_present": _present(cc / "COMPLETION-GATES.json"),
        "spec_prompts_present": _present(root / "_USER-PROMPTS.md"),
        "prior_lane_sidecar_consulted": False,
    }


def world_good() -> dict:
    """Synthetic known-good: every predicate can return TRUE."""
    return {
        "kind": "good",
        "option_rows": [
            {"id": "M-01", "state": "IMPLEMENTED"},
            {"id": "M-02", "state": "SUPERSEDED"},
            {"id": "M-03", "state": "REJECTED-WITH-OWNER-REASONING"},
        ],
        "requirement_rows": [
            {"id": "R1", "label": "BOUND", "unit": "CC-0024"},
            {"id": "R2", "label": "RESIDUAL", "unit": None},
        ],
        "ci_attempts_max": 1,
        "required_tests_red": 0,
        "suites_with_observed_failing_control": 4,
        "secret_scan_complete": True,
        "secret_hits": 0,
        "compat_untested_as_supported": 0,
        "benchmark_net": "IMPROVED",
        "reviewer_independent_pass": True,
        "manifest_disk_delta": 0,
        "release_scanner_fresh": True,
        "docs_code_divergence": 0,
        "release_mode": "CANARY",
        "canary_channel_present": True,
        "canary_success": True,
        "rollback_rehearsal_pass": True,
        "unknowns_missing_experiment": 0,
        "workflow_candidates_qualified": FLOOR_WF,
        "blueprints_executable": FLOOR_BP,
        "council_protocols": FLOOR_PROTO,
        "presets": FLOOR_PRESET,
        "work_unit_count": FLOOR_WU,
        "work_unit_count_b": FLOOR_WU,
        "work_unit_extractors_agree": True,
        "platform_options": FLOOR_OPT,
        "secret_corpus": ["readme: install with pip"],
        "prior_lane_sidecar_consulted": False,
    }


def world_broken() -> dict:
    """Synthetic known-broken: every predicate must return FALSE."""
    return {
        "kind": "broken",
        "option_rows": [
            {"id": "M-01", "state": "IMPLEMENTED"},
            {"id": "M-99", "state": "OPEN"},
        ],
        "requirement_rows": [
            {"id": "R1", "label": "UNBOUND", "unit": None},
        ],
        "ci_attempts_max": 6,
        "required_tests_red": 3,
        "suites_with_observed_failing_control": 0,
        "secret_scan_complete": True,
        "secret_hits": 2,
        "compat_untested_as_supported": 4,
        "benchmark_net": "REGRESSED",
        "reviewer_independent_pass": False,
        "manifest_disk_delta": 7,
        "release_scanner_fresh": False,
        "docs_code_divergence": 5,
        "release_mode": "PR-ONLY",
        "canary_channel_present": False,
        "canary_success": False,
        "rollback_rehearsal_pass": False,
        "unknowns_missing_experiment": 3,
        "workflow_candidates_qualified": 12,
        "blueprints_executable": 8,
        "council_protocols": 2,
        "presets": 3,
        "work_unit_count": 100,
        "work_unit_count_b": 100,
        "work_unit_extractors_agree": True,
        "platform_options": 9,
        "secret_corpus": [f"token={CANARY_TOKEN}"],
        "prior_lane_sidecar_consulted": False,
    }


def eval_c01(w: dict) -> dict:
    exp = (
        "Produce selected-option rows with namespace-resolved ids and exactly one "
        "terminal state in {IMPLEMENTED, SUPERSEDED, REJECTED-WITH-OWNER-REASONING} "
        "(SYN-0028 / ARC-0111)."
    )
    rows = w.get("option_rows")
    if rows is None:
        return _nc(exp, "option-closure artifact absent")
    allowed = {"IMPLEMENTED", "SUPERSEDED", "REJECTED-WITH-OWNER-REASONING"}
    bad = [r for r in rows if str(r.get("state") or "") not in allowed]
    ids = [r.get("id") for r in rows]
    if bad or len(ids) != len(set(ids)):
        return _v("FALSE", f"unclosed_or_duplicate={len(bad)} n={len(rows)}")
    return _v("TRUE", f"n={len(rows)} all_terminal")


def eval_c02(w: dict) -> dict:
    exp = (
        "Bind every extracted owner requirement to a catalog unit or an explicit "
        "RESIDUAL label (CC-0024 / SYN-0029)."
    )
    rows = w.get("requirement_rows")
    if rows is None:
        return _nc(exp, "requirement-register artifact absent")
    bad = [r for r in rows if str(r.get("label") or "") not in {"BOUND", "RESIDUAL"}]
    if bad:
        return _v("FALSE", f"unlabelled={len(bad)}")
    return _v("TRUE", f"n={len(rows)}")


def eval_c03(w: dict) -> dict:
    exp = (
        "Join each cited green to its full run history by commit SHA and count "
        "attempts; a green with attempts>1 is laundering (ADV-0090)."
    )
    n = w.get("ci_attempts_max")
    if n is None:
        return _nc(exp, "CI run history absent")
    if int(n) > 1:
        return _v("FALSE", f"max_attempts={n}")
    return _v("TRUE", "max_attempts=1")


def eval_c04(w: dict) -> dict:
    exp = "Execute the required-test registry and count currently red required tests."
    n = w.get("required_tests_red")
    if n is None:
        return _nc(exp, "required-test status ledger absent")
    if int(n) > 0:
        return _v("FALSE", f"red={n}")
    return _v("TRUE", "red=0")


def eval_c05(w: dict) -> dict:
    exp = (
        "For each registered suite, resolve the declared negative control to an "
        "executable and confirm it has been observed FAILING (CC-0014 / TST-0347)."
    )
    n = w.get("suites_with_observed_failing_control")
    if n is None:
        return _nc(exp, "mutation-census artifact absent")
    if int(n) < 1:
        return _v("FALSE", "zero suites with observed failing control")
    return _v("TRUE", f"suites_with_control={n}")


def eval_c06(w: dict) -> dict:
    exp = (
        "Run a canary-controlled secret scan over receipts, events and packaged "
        "artifacts; do not print values (CC-0011 / IMP-0458)."
    )
    corpus = w.get("secret_corpus")
    if corpus is not None:
        hits = sum(1 for s in corpus if CANARY_TOKEN in str(s))
        if hits:
            return _v("FALSE", f"canary_hits={hits}")
        return _v("TRUE", "canary_hits=0")
    if not w.get("secret_scan_complete"):
        return _nc(exp, "full-corpus secret scan with canary not on disk")
    hits = int(w.get("secret_hits") or 0)
    if hits:
        return _v("FALSE", f"hits={hits}")
    return _v("TRUE", "hits=0 scan_complete")


def eval_c07(w: dict) -> dict:
    exp = (
        "Populate the compatibility matrix from recorded test runs only; an "
        "UNTESTED cell must not read SUPPORTED (ARC-0095)."
    )
    n = w.get("compat_untested_as_supported")
    if n is None:
        return _nc(exp, "compatibility-matrix artifact absent")
    if int(n) > 0:
        return _v("FALSE", f"untested_as_supported={n}")
    return _v("TRUE", "untested_cells_not_supported")


def eval_c08(w: dict) -> dict:
    exp = (
        "Compute condition 8 from the results ledger with a pre-registered "
        "non-inferiority margin; missing data is NOT-CHECKED (SYN-0034)."
    )
    net = w.get("benchmark_net")
    if net is None:
        return _nc(exp, "benchmark ledger / margin table absent")
    if str(net) != "IMPROVED":
        return _v("FALSE", f"net={net}")
    return _v("TRUE", "net=IMPROVED")


def eval_c09(w: dict) -> dict:
    exp = (
        "Check every completion receipt for an independent reviewer PASS "
        "(CNF-0121 / completion-predicate condition 9)."
    )
    v = w.get("reviewer_independent_pass")
    if v is None:
        return _nc(exp, "completion-receipt reviewer census absent")
    if not v:
        return _v("FALSE", "independent_reviewer_pass=false")
    return _v("TRUE", "independent_reviewer_pass=true")


def eval_c10(w: dict) -> dict:
    exp = (
        "Walk the artifact trees independently of the manifest writer and "
        "require empty set-difference plus matching hashes (CNF-0122)."
    )
    n = w.get("manifest_disk_delta")
    if n is None:
        return _nc(exp, "ARTIFACT-MANIFEST.json absent")
    if int(n) != 0:
        return _v("FALSE", f"disk_delta={n}")
    return _v("TRUE", "manifest_matches_disk")


def eval_c11(w: dict) -> dict:
    exp = (
        "Execute the release gate twice with a synthetic advisory injected "
        "between runs; the second run must go red (ADV-0016)."
    )
    v = w.get("release_scanner_fresh")
    if v is None:
        return _nc(exp, "release-time scanner freshness probe not run")
    if not v:
        return _v("FALSE", "scanner_accepted_stale_result")
    return _v("TRUE", "release_scanner_reexecuted")


def eval_c12(w: dict) -> dict:
    exp = (
        "Extract fenced commands from shipped docs and execute them; separately "
        "diff documented flags/paths against parser and tree (CNF-0191)."
    )
    n = w.get("docs_code_divergence")
    if n is None:
        return _nc(exp, "docs-versus-code execution report absent")
    if int(n) > 0:
        return _v("FALSE", f"divergences={n}")
    return _v("TRUE", "divergences=0")


def eval_c13(w: dict) -> dict:
    """release/canary succeeds.

    A successful canary is detected only when a canary channel exists and
    reports success. Under PR-ONLY there is no canary channel, so the
    condition as written cannot be satisfied.
    """
    mode = str(w.get("release_mode") or "")
    channel = bool(w.get("canary_channel_present"))
    success = bool(w.get("canary_success"))
    extra = {
        "canary_detector": "canary_channel_present AND canary_success",
        "canary_possible_under_pr_only": False if mode == "PR-ONLY" else True,
        "satisfiability": (
            "UNSATISFIABLE-AS-WRITTEN" if mode == "PR-ONLY" else "SATISFIABLE"
        ),
    }
    if mode == "PR-ONLY" or not channel:
        return _v(
            "FALSE",
            "no canary channel under PR-ONLY; condition 13 unsatisfiable as written",
            **extra,
        )
    if success:
        return _v("TRUE", "canary_success observed", **extra)
    return _v("FALSE", "canary channel present but success not observed", **extra)


def eval_c14(w: dict) -> dict:
    exp = (
        "Three-point inventory (pre-upgrade, post-upgrade, post-rollback) plus "
        "golden-journey execution after rollback (REL-0006 / ADV-0119)."
    )
    v = w.get("rollback_rehearsal_pass")
    if v is None:
        return _nc(exp, "rollback rehearsal receipt absent")
    if not v:
        return _v("FALSE", "rollback_rehearsal_pass=false")
    return _v("TRUE", "rollback_rehearsal_pass=true")


def eval_c15(w: dict) -> dict:
    exp = (
        "Reconcile UNKNOWNS-REGISTER.md against residual/UNVERIFIED/NOT-CHECKED "
        "tags; every open unknown needs a named settling experiment (SYN-0041)."
    )
    n = w.get("unknowns_missing_experiment")
    if n is None:
        return _nc(exp, "unknowns register absent")
    if int(n) > 0:
        return _v("FALSE", f"missing_experiment={n}")
    return _v("TRUE", "all_unknowns_named_experiment")


def _floor(w: dict, key: str, floor: int, exp: str, absent: str) -> dict:
    n = w.get(key)
    if n is None:
        return _nc(exp, absent)
    n = int(n)
    if n < floor:
        return _v("FALSE", f"count={n} floor={floor}")
    return _v("TRUE", f"count={n} floor={floor}")


def eval_c16(w: dict) -> dict:
    return _floor(
        w,
        "workflow_candidates_qualified",
        FLOOR_WF,
        "Count candidates that are classified AND have resolved provenance AND "
        "a fetched licence class after alias/fork collapse (WFA-0123).",
        "qualified workflow-candidate registry absent",
    )


def eval_c17(w: dict) -> dict:
    return _floor(
        w,
        "blueprints_executable",
        FLOOR_BP,
        "Load each blueprint into the IR and run a smoke case; count only "
        "those that execute (WFA-0124).",
        "blueprint executability census absent",
    )


def eval_c18(w: dict) -> dict:
    return _floor(
        w,
        "council_protocols",
        FLOOR_PROTO,
        "Count distinct council protocol ids from the protocol registry; "
        "prove disjointness from preset ids (CNF-0188 / SYN-0031).",
        "council protocol registry absent",
    )


def eval_c19(w: dict) -> dict:
    return _floor(
        w,
        "presets",
        FLOOR_PRESET,
        "Count distinct editable preset ids; intersection with protocol ids "
        "must be empty (CNF-0188 / SYN-0031).",
        "preset registry absent",
    )


def eval_c20(w: dict) -> dict:
    a = w.get("work_unit_count")
    b = w.get("work_unit_count_b")
    if a is None or b is None:
        return _nc(
            "Count work_units length and unique ids in WORK-UNIT-CATALOG.json.",
            "catalog unreadable",
        )
    a, b = int(a), int(b)
    if a != b:
        return _v("FALSE", f"extractor_disagreement a={a} b={b}")
    if a < FLOOR_WU:
        return _v("FALSE", f"count={a} floor={FLOOR_WU} shortfall={FLOOR_WU - a}")
    return _v("TRUE", f"count={a} floor={FLOOR_WU}")


def eval_c21(w: dict) -> dict:
    return _floor(
        w,
        "platform_options",
        FLOOR_OPT,
        "Count platform option ids from 07-OPTION-UNIVERSE after namespace "
        "resolution (CNF-0188 / SYN-0031).",
        "option-universe artifact absent",
    )


EVAL: dict[int, Callable[[dict], dict]] = {
    1: eval_c01,
    2: eval_c02,
    3: eval_c03,
    4: eval_c04,
    5: eval_c05,
    6: eval_c06,
    7: eval_c07,
    8: eval_c08,
    9: eval_c09,
    10: eval_c10,
    11: eval_c11,
    12: eval_c12,
    13: eval_c13,
    14: eval_c14,
    15: eval_c15,
    16: eval_c16,
    17: eval_c17,
    18: eval_c18,
    19: eval_c19,
    20: eval_c20,
    21: eval_c21,
}

# Reconstructed from catalog spec_anchor / question_or_target citations.
# _USER-PROMPTS.md is not on this worktree; these are not inherited sidecar verdicts.
META = [
    {
        "id": 1,
        "spec_line": 11378,
        "text": "Every selected option id is IMPLEMENTED, SUPERSEDED, or REJECTED-WITH-OWNER-REASONING.",
        "source": "SYN-0028 / ARC-0111 catalog text",
    },
    {
        "id": 2,
        "spec_line": 11379,
        "text": "Every extracted owner requirement is BOUND to a unit or explicitly RESIDUAL.",
        "source": "CC-0024 / SYN-0029 (reconstructed; spec file absent)",
    },
    {
        "id": 3,
        "spec_line": 11380,
        "text": "Cited greens are not rerun-until-green; required suites are stable.",
        "source": "ADV-0090 spec_anchor 11380",
    },
    {
        "id": 4,
        "spec_line": 11381,
        "text": "No required test is red.",
        "source": "SYN-0043 tests_required (condition 4)",
    },
    {
        "id": 5,
        "spec_line": 11382,
        "text": "Mutation and negative-control coverage demonstrate detector validity.",
        "source": "CC-0014 / TST census catalog text",
    },
    {
        "id": 6,
        "spec_line": 11383,
        "text": "No credentials or decrypted secrets enter an artifact bundle.",
        "source": "reconstructed from adjacent failure class 11345 / IMP-0458",
    },
    {
        "id": 7,
        "spec_line": 11384,
        "text": "Compatibility matrix: an UNTESTED cell is never read as SUPPORTED.",
        "source": "ARC-0095 input :11384",
    },
    {
        "id": 8,
        "spec_line": 11385,
        "text": "Benchmark results show the intended improvement without material regression.",
        "source": "SYN-0034 / TST catalog text",
    },
    {
        "id": 9,
        "spec_line": 11386,
        "text": "Independent reviewer PASS is enforced on completion receipts.",
        "source": "reconstructed from CNF-0121 / predicate condition 9",
    },
    {
        "id": 10,
        "spec_line": 11387,
        "text": "Artifact manifest matches disk (no missing, extra, or hash-mismatched entries).",
        "source": "reconstructed from CNF-0122 / CNF-0192",
    },
    {
        "id": 11,
        "spec_line": 11388,
        "text": "Vulnerability and license scanners re-run at release time (not a cached implementation-time result).",
        "source": "ADV-0016 spec_anchor 11388",
    },
    {
        "id": 12,
        "spec_line": 11389,
        "text": "Docs and code agree.",
        "source": "CNF-0191 / SYN docs-parity catalog text",
    },
    {
        "id": 13,
        "spec_line": 11390,
        "text": "Release/canary succeeds.",
        "source": "CC-0015 / REL-0003 catalog text (verbatim claim)",
    },
    {
        "id": 14,
        "spec_line": 11391,
        "text": "Rollback is tested.",
        "source": "ADV-0119 / REL catalog text",
    },
    {
        "id": 15,
        "spec_line": 11392,
        "text": "Every residual unknown has a named settling experiment and an owner-visible impact statement.",
        "source": "CC-0022 / SYN unknowns catalog text",
    },
    {
        "id": 16,
        "spec_line": 11393,
        "text": "At least 160 workflow candidates classified with provenance and licence records.",
        "source": "WFA-0123 / SYN-0031",
    },
    {
        "id": 17,
        "spec_line": 11394,
        "text": "At least 96 materially distinct workflow blueprints executable under the selected quality tiers.",
        "source": "WFA-0124 / SYN-0031",
    },
    {
        "id": 18,
        "spec_line": 11395,
        "text": "At least 48 council protocols.",
        "source": "SYN-0031 floors list",
    },
    {
        "id": 19,
        "spec_line": 11396,
        "text": "At least 64 presets.",
        "source": "SYN-0031 floors list",
    },
    {
        "id": 20,
        "spec_line": 11397,
        "text": "At least 2048 work units.",
        "source": "SYN-0031 floors list / catalog work_units_meta.target",
    },
    {
        "id": 21,
        "spec_line": 11398,
        "text": "At least 160 platform options.",
        "source": "SYN-0031 floors list",
    },
]


def detector_control(cid: int) -> dict:
    fn = EVAL[cid]
    good = fn(world_good())
    broken = fn(world_broken())
    silent = good["verdict"] == "TRUE"
    fired = broken["verdict"] == "FALSE"
    return {
        "condition": cid,
        "good_verdict": good["verdict"],
        "broken_verdict": broken["verdict"],
        "silent_on_good": silent,
        "fired_on_broken": fired,
        "pass": silent and fired,
        "good_reason": good["reason"],
        "broken_reason": broken["reason"],
    }


def evaluate_world(world: dict) -> list[dict]:
    rows = []
    for meta in META:
        cid = meta["id"]
        live = EVAL[cid](world)
        ctrl = detector_control(cid)
        row = {
            "id": cid,
            "spec_line": meta["spec_line"],
            "text": meta["text"],
            "text_source": meta["source"],
            "probe": f"CNF-0187-C{cid:02d}",
            "command": P1_CMD,
            "verdict": live["verdict"],
            "reason": live["reason"],
            "settling_experiment": live.get("settling_experiment"),
            "detector_control": {
                "fired_on_broken": ctrl["fired_on_broken"],
                "silent_on_good": ctrl["silent_on_good"],
                "good_verdict": ctrl["good_verdict"],
                "broken_verdict": ctrl["broken_verdict"],
            },
        }
        for k, v in live.items():
            if k not in {"verdict", "reason", "settling_experiment"}:
                row[k] = v
        rows.append(row)
    return rows


def overall_verdict(rows: list[dict]) -> str:
    if any(r["verdict"] != "TRUE" for r in rows):
        return "NO-GO"
    return "GO"


_GATE_KEYS = (
    "conditions",
    "independence",
    "overall_verdict",
    "counts",
    "condition_13_owner_routing",
    "honesty",
    "detector_controls_summary",
)


def gate_payload(doc: dict) -> dict:
    """Read the 21-condition payload from report/extensions or top-level.

    program-gate-report receipts keep domain fields under ``report`` because
    receipt_core sets additionalProperties=false. Older drafts put the same
    keys at top level; both shapes are accepted.
    """
    merged: dict = {}
    for src in (
        doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {},
        doc.get("report") if isinstance(doc.get("report"), dict) else {},
        {k: doc[k] for k in _GATE_KEYS if k in doc},
    ):
        merged.update(src)
    return merged


def assert_controls() -> list[dict]:
    ctrls = [detector_control(i) for i in range(1, 22)]
    bad = [c for c in ctrls if not c["pass"]]
    if bad:
        raise SystemExit(f"FAILED:CNF-0187 detector-control {bad}")
    return ctrls
