"""WFA-0119 supersession path.

A newly certified workflow may retire an older certified one only when:

  A) replacement mechanism set is a superset of the retired set, computed
     from the mechanism incidence matrix (not from prose self-description);
  B) every retired-workflow benchmark case re-run against the replacement
     passes — mechanically independent of A: a matrix id does not imply
     reachable behaviour;
  preservation of the retired definition succeeds (content hash + retrieval);
  owner sign-off is present when the retired workflow is owner-relied.

Refusal records no superseded_by edge and leaves the retired status CERTIFIED.
Preservation is performed before any terminal disposition (WFA-0076 stand-in).
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
PRESERVE = FIXTURES / "preserve-store"

Behavior = Callable[[str], str]


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_matrix() -> dict:
    return load_json(FIXTURES / "incidence_matrix.json")


def load_workflows() -> dict:
    return load_json(FIXTURES / "workflows.json")


def load_benchmarks() -> dict:
    return load_json(FIXTURES / "benchmarks.json")


def load_owner_signoff() -> dict:
    return load_json(FIXTURES / "owner_signoff.json")


def mechanisms_of(matrix: dict, workflow_id: str) -> set[str]:
    rows = (matrix.get("artifacts") or {}).get(workflow_id)
    if rows is None:
        raise KeyError(f"incidence matrix has no row for {workflow_id}")
    return set(rows)


def signal_a_superset(matrix: dict, retired_id: str, replacement_id: str) -> dict:
    retired = mechanisms_of(matrix, retired_id)
    replacement = mechanisms_of(matrix, replacement_id)
    missing = sorted(retired - replacement)
    extra = sorted(replacement - retired)
    return {
        "signal": "A-incidence-superset",
        "pass": not missing,
        "retired_id": retired_id,
        "replacement_id": replacement_id,
        "retired_mechanisms": sorted(retired),
        "replacement_mechanisms": sorted(replacement),
        "missing": missing,
        "extra": extra,
        "extraction_rule": matrix.get("extraction_rule"),
        "matrix_id": matrix.get("matrix_id"),
    }


def _parse(inp: str) -> str:
    return inp.strip().upper()


def _validate(inp: str) -> str:
    return "OK" if inp.isalpha() else "BAD"


def _persist(inp: str) -> str:
    return "STORED:" + inp


def _notify(inp: str) -> str:
    return "NOTIFIED:" + inp


def _audit(inp: str) -> str:
    return "AUDITED:" + inp


def _notify_disconnected(_inp: str) -> str:
    return ""


BEHAVIOR_PACKS: dict[str, dict[str, Behavior]] = {
    "faithful": {
        "mech.parse": _parse,
        "mech.validate": _validate,
        "mech.persist": _persist,
        "mech.notify": _notify,
    },
    "faithful_plus_audit": {
        "mech.parse": _parse,
        "mech.validate": _validate,
        "mech.persist": _persist,
        "mech.notify": _notify,
        "mech.audit": _audit,
    },
    "missing_notify": {
        "mech.parse": _parse,
        "mech.validate": _validate,
        "mech.persist": _persist,
    },
    "disconnected_notify": {
        "mech.parse": _parse,
        "mech.validate": _validate,
        "mech.persist": _persist,
        "mech.notify": _notify_disconnected,
    },
    "helper_faithful": {
        "mech.parse": _parse,
        "mech.persist": _persist,
    },
    "helper_plus_audit": {
        "mech.parse": _parse,
        "mech.persist": _persist,
        "mech.audit": _audit,
    },
}


def behaviors_for(workflow: dict) -> dict[str, Behavior]:
    pack = workflow.get("behavior_pack")
    if pack not in BEHAVIOR_PACKS:
        raise KeyError(f"unknown behavior_pack {pack!r} on {workflow.get('id')}")
    return BEHAVIOR_PACKS[pack]


def run_one_case(workflow: dict, case: dict) -> dict:
    mech = case["mechanism"]
    fn = behaviors_for(workflow).get(mech)
    if fn is None:
        return {
            "id": case["id"],
            "mechanism": mech,
            "pass": False,
            "reason": "behavior-absent",
            "expected": case["expected"],
            "got": None,
        }
    got = fn(case["input"])
    ok = got == case["expected"]
    return {
        "id": case["id"],
        "mechanism": mech,
        "pass": ok,
        "reason": "ok" if ok else "behavior-mismatch",
        "expected": case["expected"],
        "got": got,
    }


def signal_b_benchmarks(replacement: dict, cases: list[dict]) -> dict:
    results = [run_one_case(replacement, c) for c in cases]
    failed = [r for r in results if not r["pass"]]
    return {
        "signal": "B-retired-benchmarks-rerun",
        "pass": not failed,
        "replacement_id": replacement["id"],
        "cases_run": len(results),
        "cases_failed": [r["id"] for r in failed],
        "results": results,
        "independence": (
            "Benchmark execution uses behavior_pack callables, not the incidence "
            "matrix row. A mechanism id present in the matrix does not make a case pass."
        ),
    }


def preserve_definition(workflow: dict, store: Path | None = None) -> dict:
    store = store or PRESERVE
    store.mkdir(parents=True, exist_ok=True)
    definition = workflow["definition"]
    payload = _canon(definition)
    digest = sha256_text(payload)
    dest = store / f"{digest}.json"
    dest.write_text(payload + "\n", encoding="utf-8")
    return {
        "workflow_id": workflow["id"],
        "sha256": digest,
        "bytes": len(payload.encode("utf-8")),
        "path": str(dest.relative_to(HERE)).replace("\\", "/"),
        "stored": dest.is_file(),
    }


def retrieve_definition(sha256: str, store: Path | None = None) -> dict:
    store = store or PRESERVE
    dest = store / f"{sha256}.json"
    if not dest.is_file():
        return {"ok": False, "reason": "missing", "sha256": sha256, "path": str(dest)}
    raw = dest.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
    live = sha256_text(raw)
    return {
        "ok": live == sha256,
        "reason": "match" if live == sha256 else "hash-mismatch",
        "sha256": sha256,
        "retrieved_sha256": live,
        "bytes": len(raw.encode("utf-8")),
        "path": str(dest.relative_to(HERE)).replace("\\", "/"),
        "definition": json.loads(raw),
    }


def owner_gate(retired: dict, signoff: dict | None) -> dict:
    relied = bool(retired.get("owner_relied"))
    if not relied:
        return {
            "required": False,
            "pass": True,
            "reason": "retired-workflow-not-owner-relied",
            "owner_relied": False,
        }
    if not isinstance(signoff, dict):
        return {
            "required": True,
            "pass": False,
            "reason": "owner-signoff-absent",
            "owner_relied": True,
        }
    action = str(signoff.get("action") or "")
    matches = signoff.get("workflow_id") == retired["id"]
    allow = action == "ALLOW-SUPERSESSION"
    ok = matches and allow
    return {
        "required": True,
        "pass": ok,
        "reason": (
            "owner-allow"
            if ok
            else "owner-signoff-mismatch"
            if not matches
            else f"owner-action-{action or 'empty'}"
        ),
        "owner_relied": True,
        "decision_id": signoff.get("decision_id"),
        "actor": signoff.get("actor"),
        "scope": signoff.get("scope"),
    }


def attempt_supersession(
    retired: dict,
    replacement: dict,
    matrix: dict,
    cases: list[dict],
    signoff: dict | None,
    store: Path | None = None,
) -> dict:
    """Attempt supersession. Side effect: preserve retired definition first."""
    retired = deepcopy(retired)
    replacement = deepcopy(replacement)
    preserved = preserve_definition(retired, store=store)
    retrieved = retrieve_definition(preserved["sha256"], store=store)
    sig_a = signal_a_superset(matrix, retired["id"], replacement["id"])
    sig_b = signal_b_benchmarks(replacement, cases)
    own = owner_gate(retired, signoff)

    refusals: list[str] = []
    if not preserved.get("stored"):
        refusals.append("preservation-failed")
    if not retrieved.get("ok"):
        refusals.append("retrieval-failed")
    if not sig_a["pass"]:
        refusals.append("capability-loss")
    if not sig_b["pass"]:
        refusals.append("benchmark-fail")
    if not own["pass"]:
        refusals.append("owner-blocked")

    accepted = not refusals
    edge = None
    retired_status = retired.get("status")
    if accepted:
        edge = {
            "superseded": retired["id"],
            "superseded_by": replacement["id"],
            "kind": "certified-successor",
        }
        retired_status = "SUPERSEDED"
    result = {
        "accepted": accepted,
        "refusals": refusals,
        "retired_id": retired["id"],
        "replacement_id": replacement["id"],
        "retired_status_after": retired_status,
        "superseded_by": edge,
        "preservation": preserved,
        "retrieval": {
            "ok": retrieved.get("ok"),
            "reason": retrieved.get("reason"),
            "sha256": retrieved.get("sha256"),
            "retrieved_sha256": retrieved.get("retrieved_sha256"),
            "bytes": retrieved.get("bytes"),
            "path": retrieved.get("path"),
        },
        "signal_a": sig_a,
        "signal_b": {
            k: v
            for k, v in sig_b.items()
            if k != "results"
        },
        "signal_b_results": sig_b["results"],
        "owner": own,
        "independence_check": {
            "a_uses_matrix_not_behaviors": True,
            "b_uses_behaviors_not_matrix": True,
            "a_pass": sig_a["pass"],
            "b_pass": sig_b["pass"],
            "can_diverge": sig_a["pass"] != sig_b["pass"],
        },
    }
    return result


def run_controls(store: Path | None = None) -> dict:
    matrix = load_matrix()
    workflows = load_workflows()
    benches = load_benchmarks()
    signoff = load_owner_signoff()
    retired_cases = benches["cases"]
    helper_cases = benches["helper_cases"]

    happy = attempt_supersession(
        workflows["wf-certified-intake-v1"],
        workflows["wf-certified-intake-v2"],
        matrix,
        retired_cases,
        signoff,
        store=store,
    )
    disconnected = attempt_supersession(
        workflows["wf-certified-intake-v1"],
        workflows["wf-matrix-only"],
        matrix,
        retired_cases,
        signoff,
        store=store,
    )
    lossy = attempt_supersession(
        workflows["wf-certified-intake-v1"],
        workflows["wf-lossy-intake"],
        matrix,
        retired_cases,
        signoff,
        store=store,
    )
    no_owner = attempt_supersession(
        workflows["wf-certified-intake-v1"],
        workflows["wf-certified-intake-v2"],
        matrix,
        retired_cases,
        None,
        store=store,
    )
    unused = attempt_supersession(
        workflows["wf-unused-helper-v1"],
        workflows["wf-unused-helper-v2"],
        matrix,
        helper_cases,
        None,
        store=store,
    )
    return {
        "happy": happy,
        "disconnected": disconnected,
        "lossy": lossy,
        "no_owner": no_owner,
        "unused_no_owner": unused,
    }


def controls_ok(ctrls: dict) -> tuple[bool, list[str]]:
    failed: list[str] = []
    h = ctrls["happy"]
    if not h["accepted"] or h["retired_status_after"] != "SUPERSEDED":
        failed.append("happy-not-accepted")
    if h["superseded_by"] is None:
        failed.append("happy-missing-edge")
    if not h["signal_a"]["pass"] or not h["signal_b"]["pass"]:
        failed.append("happy-signals")
    if not h["retrieval"]["ok"]:
        failed.append("happy-retrieval")

    d = ctrls["disconnected"]
    if d["accepted"]:
        failed.append("disconnected-accepted")
    if "benchmark-fail" not in d["refusals"]:
        failed.append("disconnected-no-benchmark-refuse")
    if not d["signal_a"]["pass"]:
        failed.append("disconnected-a-should-pass")
    if d["signal_b"]["pass"]:
        failed.append("disconnected-b-should-fail")
    if d["superseded_by"] is not None:
        failed.append("disconnected-wrote-edge")
    if d["retired_status_after"] != "CERTIFIED":
        failed.append("disconnected-status-changed")

    l = ctrls["lossy"]
    if l["accepted"]:
        failed.append("lossy-accepted")
    if "capability-loss" not in l["refusals"]:
        failed.append("lossy-no-capability-refuse")
    if l["signal_a"]["pass"]:
        failed.append("lossy-a-should-fail")
    if l["superseded_by"] is not None:
        failed.append("lossy-wrote-edge")

    n = ctrls["no_owner"]
    if n["accepted"]:
        failed.append("no-owner-accepted")
    if "owner-blocked" not in n["refusals"]:
        failed.append("no-owner-not-blocked")
    if n["superseded_by"] is not None:
        failed.append("no-owner-wrote-edge")
    if n["retired_status_after"] != "CERTIFIED":
        failed.append("no-owner-status-changed")
    if not n["signal_a"]["pass"] or not n["signal_b"]["pass"]:
        failed.append("no-owner-other-gates-should-pass")

    u = ctrls["unused_no_owner"]
    if not u["accepted"]:
        failed.append("unused-should-accept-without-owner")
    if u["owner"]["required"]:
        failed.append("unused-owner-should-not-be-required")
    return (not failed, failed)
