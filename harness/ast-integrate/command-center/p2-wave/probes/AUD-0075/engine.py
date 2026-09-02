#!/usr/bin/env python3
"""AUD-0075 stale-premise engine.

Fingerprint tuple is (tool, shell, data_field, measurement_kind) as specified
by CNF-0006. An undeclared source probe is zero signals, not one. A
same-fingerprint re-run is rejected and is never counted as CONFIRMED.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0075"
OUT_REL = "command-center/audit/AUD-0075-stale-premise-sweep.json"
DECLARED_SCHEMA = "command-center/schema/audit-finding.schema.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/AUD-0075/artifact.schema.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
GROUNDING_REL = "command-center/p2-wave/P2-GROUNDING.md"
P13_REL = "command-center/P13-BLINDSPOT-REVIEW.md"
DECISION_LOG_REL = "17-DECISION-LOG.md"
EXTRACTOR_REL = "command-center/p2-wave/probes/BLD-0001/extract_read_ledger.py"
SENTINEL = (
    "SUCCESS:AUD-0075 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For each fact currently pinned as program ground truth, is it still true "
    "today when re-measured by a probe MECHANICALLY DIFFERENT from the one "
    "that produced it?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0075/probe1_remeasure.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0075/probe2_origin_audit.py"
)
FP_KEYS = ("tool", "shell", "data_field", "measurement_kind")
PINNED_WF_A = "pinned-workflow-run-A"
PINNED_WF_B = "pinned-workflow-run-B"
HARVEST_READY = {
    "ABSENT": 404,
    "NEEDS-OWNER": 5,
    "TRANCHE-READY": 38,
    "VERIFIED-DELIVERED": 2,
}


def dump(doc: Any) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


dump = dump


def fingerprint(tuple_doc: dict[str, Any] | None) -> str | None:
    if not isinstance(tuple_doc, dict):
        return None
    body = {k: str(tuple_doc.get(k) or "") for k in FP_KEYS}
    if not any(body.values()):
        return None
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def independence_gate(
    source: dict[str, Any] | None, verifier: dict[str, Any] | None
) -> dict[str, Any]:
    src_fp = fingerprint(source)
    ver_fp = fingerprint(verifier)
    if src_fp is None:
        return {
            "accepted": False,
            "reason": (
                "UNDECLARED_SOURCE: zero source signals; independence is not computable"
            ),
            "source_fingerprint": None,
            "verifier_fingerprint": ver_fp,
            "source_signals": 0,
        }
    if ver_fp is None:
        return {
            "accepted": False,
            "reason": "UNDECLARED_VERIFIER: a missing verifier cannot certify",
            "source_fingerprint": src_fp,
            "verifier_fingerprint": None,
            "source_signals": 1,
        }
    if src_fp == ver_fp:
        return {
            "accepted": False,
            "reason": "SAME_FINGERPRINT: re-running the producing probe is rejected",
            "source_fingerprint": src_fp,
            "verifier_fingerprint": ver_fp,
            "source_signals": 1,
        }
    return {
        "accepted": True,
        "reason": (
            "DISTINCT_FINGERPRINT: at least one declared mechanical axis differs"
        ),
        "source_fingerprint": src_fp,
        "verifier_fingerprint": ver_fp,
        "source_signals": 1,
    }


def ready_count_control(good: dict[str, int], mutant: dict[str, int]) -> dict[str, Any]:
    def _ok(counts: dict[str, int]) -> bool:
        return counts == HARVEST_READY and sum(counts.values()) == 449

    return {
        "good_ready_counts": dict(good),
        "bad_ready_counts": dict(mutant),
        "comparator_silent_on_good": _ok(good),
        "comparator_fires_on_bad": not _ok(mutant),
    }


def _run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 124, "", str(exc)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _catalog() -> dict[str, Any]:
    return json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))


def _catalog_unit_count() -> int:
    data = _catalog()
    units = data.get("work_units")
    return len(units) if isinstance(units, list) else -1


def _catalog_has(needle: str) -> bool:
    return needle in (REPO / CATALOG_REL).read_text(encoding="utf-8")


def _grounding_brief_and_measured() -> dict[str, Any]:
    path = REPO / GROUNDING_REL
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    briefed = None
    match = re.search(
        r"Briefed:\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)",
        text,
    )
    if match:
        briefed = {
            "units": int(match.group(1)),
            "delivered": int(match.group(2)),
            "ready": int(match.group(3)),
            "blocked": int(match.group(4)),
            "owner_gated": int(match.group(5)),
        }
    live = None
    match2 = re.search(
        r"units\s+(\d+)\s*\|\s*delivered\s+(\d+)\s*\|\s*READY\s+(\d+)\s*\|\s*"
        r"blocked\s+(\d+)\s*\|\s*owner-gated\s+(\d+)",
        text,
    )
    if match2:
        live = {
            "units": int(match2.group(1)),
            "delivered": int(match2.group(2)),
            "ready": int(match2.group(3)),
            "blocked": int(match2.group(4)),
            "owner_gated": int(match2.group(5)),
        }
    return {"briefed": briefed, "measured_in_grounding": live, "path": GROUNDING_REL}


def _condition11() -> dict[str, Any]:
    code, out, err = _run(
        [sys.executable, "-B", "tools/command-center/unit_manifest.py", "--check"]
    )
    text = (out + err).strip()
    first = ""
    for line in text.splitlines():
        if line.strip():
            first = line.strip()
            break
    return {
        "exit_code": code,
        "green": code == 0,
        "first_line": first,
        "first_line": first,
        "stdout": text[:2000],
    }


def _git_inside() -> dict[str, Any]:
    code, out, err = _run(["git", "rev-parse", "--is-inside-work-tree"])
    flag = (out or "").strip().lower()
    return {
        "exit_code": code,
        "stdout": flag,
        "stderr": (err or "").strip()[:400],
        "is_worktree": code == 0 and flag == "true",
        "is_worktree": code == 0 and flag == "true",
    }


def _workflow_primary(run_id: str) -> dict[str, Any]:
    workflows = REPO / ".github" / "workflows"
    return {
        "run_id": run_id,
        "workflows_dir_exists": workflows.is_dir(),
        "primary_result_present": False,
        "reason": "no-pinned-run-artifact-on-this-worker",
    }


def measure_fact(fact: dict[str, Any]) -> dict[str, Any]:
    fid = fact["id"]
    if fid == "F01_catalog_unit_count_2007":
        count = _catalog_unit_count()
        ok = count == 2007
        return {
            "observed": count,
            "matches_pin": ok,
            "verdict": "SUPPORTED" if ok else "CONTRADICTED",
            "detail": f"work_units_len={count}",
        }
    if fid == "F02_briefed_delivered_is_4":
        grounding = _grounding_brief_and_measured()
        live = (grounding.get("measured_in_grounding") or {}).get("delivered")
        ok = live == 4
        return {
            "observed": live,
            "matches_pin": ok,
            "verdict": "SUPPORTED" if ok else "CONTRADICTED",
            "detail": (
                f"P2-GROUNDING measured delivered={live} briefed={grounding.get('briefed')}"
            ),
        }
    if fid == "F03_briefed_ready_is_447":
        grounding = _grounding_brief_and_measured()
        live = (grounding.get("measured_in_grounding") or {}).get("ready")
        ok = live == 447
        return {
            "observed": live,
            "matches_pin": ok,
            "verdict": "SUPPORTED" if ok else "CONTRADICTED",
            "detail": (
                f"P2-GROUNDING measured READY={live} briefed={grounding.get('briefed')}"
            ),
        }
    if fid == "F04_condition11_green":
        c11 = _condition11()
        return {
            "observed": c11["green"],
            "matches_pin": c11["green"] is True,
            "verdict": "SUPPORTED" if c11["green"] else "CONTRADICTED",
            "detail": c11["first_line"],
            "condition11": c11,
        }
    if fid == "F05_c11_first_red_is_bld0023_p13":
        c11 = _condition11()
        first = c11["first_line"]
        pin_shape = "BLD-0023" in first and "P13-BLINDSPOT-REVIEW.md" in first
        if c11["green"]:
            verdict = "CONTRADICTED"
        elif pin_shape:
            verdict = "SUPPORTED"
        else:
            verdict = "CONTRADICTED-CURRENT-ENVIRONMENT"
        return {
            "observed": first,
            "matches_pin": verdict == "SUPPORTED",
            "verdict": verdict,
            "detail": (
                "harvest first-red was BLD-0023/P13-BLINDSPOT-REVIEW.md; "
                f"live first-red={first!r}"
            ),
        }
    if fid == "F06_p13_exists":
        path = REPO / P13_REL
        exists = path.is_file()
        size = path.stat().st_size if exists else 0
        return {
            "observed": {"exists": exists, "bytes": size},
            "matches_pin": exists,
            "verdict": "SUPPORTED" if exists else "CONTRADICTED-CURRENT-ENVIRONMENT",
            "detail": f"{P13_REL} exists={exists} bytes={size}",
        }
    if fid == "F07_linux_worker_is_git_worktree":
        git = _git_inside()
        return {
            "observed": git["is_worktree"],
            "matches_pin": git["is_worktree"],
            "verdict": "SUPPORTED" if git["is_worktree"] else "CONTRADICTED",
            "detail": (
                "git rev-parse --is-inside-work-tree "
                f"rc={git['exit_code']} {git['stderr'] or git['stdout']}"
            ),
        }
    if fid == "F08_pinned_workflow_run_a_primary":
        wf = _workflow_primary(PINNED_WF_A)
        return {
            "observed": wf,
            "matches_pin": False,
            "verdict": "NOT-CHECKED",
            "detail": wf["reason"],
        }
    if fid == "F09_pinned_workflow_run_b_primary":
        wf = _workflow_primary(PINNED_WF_B)
        return {
            "observed": wf,
            "matches_pin": False,
            "verdict": "NOT-CHECKED",
            "detail": wf["reason"],
        }
    if fid == "F10_precedent_four_vgt_false_recorded":
        hit = _catalog_has("four briefed VERIFIED GROUND TRUTH facts were false")
        return {
            "observed": hit,
            "matches_pin": hit,
            "verdict": "SUPPORTED" if hit else "CONTRADICTED",
            "detail": (
                "catalog still records the four-false-VGT precedent"
                if hit
                else "precedent sentence absent from catalog"
            ),
        }
    if fid == "F11_precedent_two_agents_same_probe_recorded":
        hit = _catalog_has("CONFIRMED a false fact by re-running the broken probe")
        return {
            "observed": hit,
            "matches_pin": hit,
            "verdict": "SUPPORTED" if hit else "CONTRADICTED",
            "detail": (
                "catalog still records the two-agent same-probe confirmation precedent"
                if hit
                else "precedent sentence absent from catalog"
            ),
        }
    if fid == "F12_mnn_collision_present_tense_in_decision_log":
        path = REPO / DECISION_LOG_REL
        if not path.is_file():
            return {
                "observed": {"exists": False},
                "matches_pin": False,
                "verdict": "CONTRADICTED",
                "detail": (
                    f"{DECISION_LOG_REL} absent; present-tense collision claim "
                    "is not on this tree"
                ),
            }
        text = path.read_text(encoding="utf-8", errors="replace")
        mech = len(re.findall(r"\bMECH\b", text))
        present = bool(
            re.search(r"31-way|M-NN collision|option-id collision", text, re.I)
        ) and mech == 0
        return {
            "observed": {
                "exists": True,
                "mech_tokens": mech,
                "collision_present_tense": present,
            },
            "matches_pin": present,
            "verdict": "SUPPORTED" if present else "CONTRADICTED",
            "detail": f"mech_tokens={mech} collision_present_tense={present}",
        }
    raise KeyError(fid)


def pinned_facts() -> list[dict[str, Any]]:
    """Twelve program-wide Frozen claims. Source tuples are undeclared on the pin."""
    return [
        {
            "id": "F01_catalog_unit_count_2007",
            "pinned_claim": "The work-unit catalog contains 2007 units.",
            "source": None,
            "verifier": {
                "tool": "python3",
                "shell": "linux-bash",
                "data_field": "work_units.length",
                "measurement_kind": "json-array-len",
            },
        },
        {
            "id": "F02_briefed_delivered_is_4",
            "pinned_claim": "Delivered count is 4 (briefed partition).",
            "source": None,
            "verifier": {
                "tool": "python3",
                "shell": "linux-bash",
                "data_field": "P2-GROUNDING.measured.delivered",
                "measurement_kind": "markdown-field-parse",
            },
        },
        {
            "id": "F03_briefed_ready_is_447",
            "pinned_claim": "READY count is 447 (briefed partition).",
            "source": None,
            "verifier": {
                "tool": "python3",
                "shell": "linux-bash",
                "data_field": "P2-GROUNDING.measured.ready",
                "measurement_kind": "markdown-field-parse",
            },
        },
        {
            "id": "F04_condition11_green",
            "pinned_claim": "Condition 11 (unit_manifest.py --check) is green.",
            "source": None,
            "verifier": {
                "tool": "python3",
                "shell": "linux-bash",
                "data_field": "unit_manifest --check exit_code",
                "measurement_kind": "cli-exit",
            },
        },
        {
            "id": "F05_c11_first_red_is_bld0023_p13",
            "pinned_claim": (
                "Condition-11 first-red is BLD-0023 / P13-BLINDSPOT-REVIEW.md."
            ),
            "source": None,
            "verifier": {
                "tool": "python3",
                "shell": "linux-bash",
                "data_field": "unit_manifest --check first_line",
                "measurement_kind": "cli-stdout-first-line",
            },
        },
        {
            "id": "F06_p13_exists",
            "pinned_claim": "command-center/P13-BLINDSPOT-REVIEW.md exists.",
            "source": None,
            "verifier": {
                "tool": "python3",
                "shell": "linux-bash",
                "data_field": "Path.is_file",
                "measurement_kind": "filesystem-stat",
            },
        },
        {
            "id": "F07_linux_worker_is_git_worktree",
            "pinned_claim": "This Linux worker is a Git worktree.",
            "source": None,
            "verifier": {
                "tool": "git",
                "shell": "linux-bash",
                "data_field": "rev-parse --is-inside-work-tree",
                "measurement_kind": "vcs-query",
            },
        },
        {
            "id": "F08_pinned_workflow_run_a_primary",
            "pinned_claim": (
                "Pinned workflow run A retains a primary result on this worker."
            ),
            "source": None,
            "verifier": {
                "tool": "python3",
                "shell": "linux-bash",
                "data_field": "pinned-workflow-run-A.primary",
                "measurement_kind": "artifact-presence",
            },
        },
        {
            "id": "F09_pinned_workflow_run_b_primary",
            "pinned_claim": (
                "Pinned workflow run B retains a primary result on this worker."
            ),
            "source": None,
            "verifier": {
                "tool": "python3",
                "shell": "linux-bash",
                "data_field": "pinned-workflow-run-B.primary",
                "measurement_kind": "artifact-presence",
            },
        },
        {
            "id": "F10_precedent_four_vgt_false_recorded",
            "pinned_claim": (
                "The catalog records the precedent that four briefed VERIFIED "
                "GROUND TRUTH facts were false in one run."
            ),
            "source": None,
            "verifier": {
                "tool": "python3",
                "shell": "linux-bash",
                "data_field": "WORK-UNIT-CATALOG.json substring",
                "measurement_kind": "literal-corpus-search",
            },
        },
        {
            "id": "F11_precedent_two_agents_same_probe_recorded",
            "pinned_claim": (
                "The catalog records the precedent that two agents CONFIRMED a "
                "false fact by re-running the broken probe."
            ),
            "source": None,
            "verifier": {
                "tool": "python3",
                "shell": "linux-bash",
                "data_field": "WORK-UNIT-CATALOG.json substring",
                "measurement_kind": "literal-corpus-search",
            },
        },
        {
            "id": "F12_mnn_collision_present_tense_in_decision_log",
            "pinned_claim": (
                "17-DECISION-LOG.md still states the 31-way M-NN collision in "
                "the present tense with zero MECH tokens."
            ),
            "source": None,
            "verifier": {
                "tool": "python3",
                "shell": "linux-bash",
                "data_field": "17-DECISION-LOG.md tokens",
                "measurement_kind": "file-read-plus-regex",
            },
        },
    ]


def fingerprint_controls() -> dict[str, Any]:
    source = {
        "tool": "node",
        "shell": "none",
        "data_field": "ready_population",
        "measurement_kind": "JSON field read",
    }
    same = dict(source)
    distinct = {
        "tool": "python3",
        "shell": "linux-bash",
        "data_field": "ready_population",
        "measurement_kind": "JSON field read",
    }
    same_gate = independence_gate(source, same)
    dist_gate = independence_gate(source, distinct)
    missing_gate = independence_gate(None, distinct)
    mutant = dict(HARVEST_READY)
    mutant["ABSENT"] = mutant["ABSENT"] - 1
    ready = ready_count_control(HARVEST_READY, mutant)
    return {
        "same_fingerprint": same_gate,
        "distinct_fingerprint": dist_gate,
        "undeclared_source": missing_gate,
        "ready_count": ready,
        "same_fingerprint_rejected": same_gate["accepted"] is False,
        "distinct_fingerprint_accepted": dist_gate["accepted"] is True,
        "missing_source_is_rejected": (
            missing_gate["accepted"] is False and missing_gate["source_signals"] == 0
        ),
        "ready_comparator_silent_on_good": ready["comparator_silent_on_good"],
        "ready_comparator_fires_on_bad": ready["comparator_fires_on_bad"],
        "same_fingerprint_rejected": same_gate["accepted"] is False,
        "distinct_fingerprint_accepted": dist_gate["accepted"] is True,
        "missing_source_is_rejected": (
            missing_gate["accepted"] is False and missing_gate["source_signals"] == 0
        ),
        "ready_comparator_silent_on_good": ready["comparator_silent_on_good"],
        "ready_comparator_fires_on_bad": ready["comparator_fires_on_bad"],
    }


def sweep() -> dict[str, Any]:
    facts = pinned_facts()
    rows: list[dict[str, Any]] = []
    tallies = {
        "SUPPORTED": 0,
        "CONTRADICTED": 0,
        "CONTRADICTED-CURRENT-ENVIRONMENT": 0,
        "NOT-CHECKED": 0,
        "declared_source_probes": 0,
        "undeclared_source_probes": 0,
        "source_signals": 0,
        "independently_certified_confirmed_or_refuted": 0,
        "facts": len(facts),
    }
    for fact in facts:
        gate = independence_gate(fact.get("source"), fact["verifier"])
        meas = measure_fact(fact)
        certified = bool(
            gate["accepted"] and meas["verdict"] in {"SUPPORTED", "CONTRADICTED"}
        )
        if gate["source_signals"]:
            tallies["declared_source_probes"] += 1
            tallies["source_signals"] += int(gate["source_signals"])
        else:
            tallies["undeclared_source_probes"] += 1
        tallies[meas["verdict"]] = tallies.get(meas["verdict"], 0) + 1
        if certified:
            tallies["independently_certified_confirmed_or_refuted"] += 1
        rows.append(
            {
                "id": fact["id"],
                "pinned_claim": fact["pinned_claim"],
                "source_probe": fact.get("source"),
                "verifier_probe": fact["verifier"],
                "source_fingerprint": gate["source_fingerprint"],
                "verifier_fingerprint": gate["verifier_fingerprint"],
                "gate_accepted": gate["accepted"],
                "gate_reason": gate["reason"],
                "source_signals": gate["source_signals"],
                "current_truth": meas["verdict"],
                "observed": meas["observed"],
                "detail": meas["detail"],
                "independently_certified": certified,
            }
        )
    controls = fingerprint_controls()
    c11 = _condition11()
    git = _git_inside()
    p13 = REPO / P13_REL
    return {
        "headline": tallies,
        "facts": rows,
        "controls": controls,
        "condition11": c11,
        "git": git,
        "p13": {
            "path": P13_REL,
            "exists": p13.is_file(),
            "bytes": p13.stat().st_size if p13.is_file() else 0,
            "bytes": p13.stat().st_size if p13.is_file() else 0,
        },
        "extractor_present": (REPO / EXTRACTOR_REL).is_file(),
        "catalog_schema_present": (REPO / DECLARED_SCHEMA).is_file(),
        "local_schema": LOCAL_SCHEMA,
        "headline": tallies,
        "catalog_schema_present": (REPO / DECLARED_SCHEMA).is_file(),
        "controls_pass": all(
            [
                controls["same_fingerprint_rejected"],
                controls["distinct_fingerprint_accepted"],
                controls["missing_source_is_rejected"],
                controls["ready_comparator_silent_on_good"],
                controls["ready_comparator_fires_on_bad"],
            ]
        ),
        "local_schema": LOCAL_SCHEMA,
        "controls_pass": all(
            [
                controls["same_fingerprint_rejected"],
                controls["distinct_fingerprint_accepted"],
                controls["missing_source_is_rejected"],
                controls["ready_comparator_silent_on_good"],
                controls["ready_comparator_fires_on_bad"],
            ]
        ),
    }


def load_artifact() -> tuple[str, dict[str, Any]]:
    path = REPO / OUT_REL
    text = path.read_text(encoding="utf-8")
    return text, json.loads(text)


def artifact_ok(text: str, doc: dict[str, Any]) -> str | None:
    if SENTINEL not in text:
        return "sentinel-absent"
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{state}"
    if doc.get("unit_id") != UNIT and doc.get("id") != UNIT:
        return f"unit-id:{doc.get('unit_id')}"
    return None


# Names used by emit.py / probes (same values, stable aliases).
SENTINEL = SENTINEL
dump = dump
DECLARED_SCHEMA = DECLARED_SCHEMA
LOCAL_SCHEMA = LOCAL_SCHEMA
UNIT = UNIT
OUT_REL = OUT_REL
QUESTION = QUESTION
QUESTION = QUESTION
artifact_ok = artifact_ok
load_artifact = load_artifact
pinned_facts = pinned_facts
fingerprint = fingerprint
