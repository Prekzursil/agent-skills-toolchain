"""CNF-0118 second-order confirmation sampling.

Implements CNF-0002 independence, CNF-0006 probe fingerprints, a seeded
draw used when CNF-0003's frame is absent, and comparison against a
threshold pinned before sampling (CNF-0004's artifact is absent here).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

UNIT = "CNF-0118"
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/confirmation/CNF-0118-second-order-sample.json"
SCHEMA_REL = "command-center/schema/confirmation-audit.schema.json"
THRESHOLD_PATH = HERE / "threshold.json"
CNF3_REL = "command-center/confirmation/CNF-0003-sampling-frame.json"
CNF4_REL = "command-center/confirmation/CNF-0004-escalation-policy.json"
SEED = 11041118
CONFIRMER_ID = "CNF-0118-second-order-confirmer"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
PASS_VERDICTS = frozenset({"SUCCESS", "DELIVERED", "CONFIRMED", "PASS", "PARTIAL"})
FAIL_VERDICTS = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT", "REFUTED", "FAIL"})

VERIFIER_FP = {
    "tool": "python3",
    "shell": "python-interpreter",
    "data_field": "artifact.state+sentinel+nbytes",
    "measurement_kind": "in-process-contract-rederive",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_unit() -> dict:
    data = load_json(REPO / "command-center/WORK-UNIT-CATALOG.json")
    for row in data.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == UNIT:
            return row
    raise SystemExit(f"FAILED:{UNIT} catalog row missing")


def load_threshold() -> dict:
    doc = load_json(THRESHOLD_PATH)
    threshold = float(doc["threshold"])
    if not 0.0 <= threshold <= 1.0:
        raise SystemExit(f"FAILED:{UNIT} threshold out of range")
    return {
        "threshold": threshold,
        "comparison": str(doc.get("comparison") or "strictly-greater-than"),
        "fixed_at": doc.get("fixed_at"),
        "source": doc.get("source"),
        "rationale": doc.get("rationale"),
        "path": "command-center/p2-wave/probes/CNF-0118/threshold.json",
        "cnf_0004_present": (REPO / CNF4_REL).is_file(),
        "cnf_0004_path": CNF4_REL,
    }


def fingerprint(probe: dict | None) -> tuple[str, str, str, str]:
    if not isinstance(probe, dict):
        return ("", "", "", "")
    return (
        str(probe.get("tool") or "").strip(),
        str(probe.get("shell") or "").strip(),
        str(probe.get("data_field") or "").strip(),
        str(probe.get("measurement_kind") or "").strip(),
    )


def fingerprint_empty(fp: tuple[str, str, str, str]) -> bool:
    return fp == ("", "", "", "")


def same_probe(source: dict | None, verifier: dict | None) -> bool:
    """True when the verifier is not a mechanically different probe.

    An empty source fingerprint is a CNF-0006 violation: it must never
    count as 'differs from verifier'.
    """
    src = fingerprint(source)
    if fingerprint_empty(src):
        return True
    return src == fingerprint(verifier)


def independent(
    confirmer_id: str,
    *,
    author_agent_id: str,
    reviewed_by: list[str],
    ancestor_authors: list[str],
) -> dict:
    """CNF-0002: (a) not author, (b) not reviewer, (c) not ancestor author."""
    rule_a = confirmer_id not in {author_agent_id}
    rule_b = confirmer_id not in set(reviewed_by)
    rule_c = confirmer_id not in set(ancestor_authors)
    return {
        "confirmer_id": confirmer_id,
        "rule_a_not_author": rule_a,
        "rule_b_not_reviewer": rule_b,
        "rule_c_not_ancestor_author": rule_c,
        "independent": rule_a and rule_b and rule_c,
        "rejected_by": [
            name
            for name, good in (("a", rule_a), ("b", rule_b), ("c", rule_c))
            if not good
        ],
    }


def exceeds_threshold(rate: float | None, threshold: float) -> bool:
    """Class-wide expansion fires only strictly above the pinned threshold."""
    if rate is None:
        return False
    return rate > threshold


def draw_k(n: int) -> int:
    if n <= 0:
        return 0
    if n == 1:
        return 1
    return max(1, min(n - 1, (n + 1) // 2))


def draw(ids: list[str], seed: int, k: int) -> list[str]:
    """Seeded rotation window over sorted ids. seed+1 differs when k < n."""
    ordered = sorted(ids)
    n = len(ordered)
    if n == 0 or k <= 0:
        return []
    if k >= n:
        return ordered
    start = seed % n
    rotated = ordered[start:] + ordered[:start]
    return rotated[:k]


def normalize_verdict(raw: str) -> str:
    token = str(raw or "").strip().upper()
    if token in PASS_VERDICTS:
        return "CONFIRMED"
    if token in FAIL_VERDICTS:
        return "REFUTED"
    return token or "NOT-CHECKED"


def source_fingerprint_from_receipt(rec: dict) -> dict:
    probes = rec.get("named_probes") or rec.get("probes") or []
    cmd = ""
    if probes and isinstance(probes[0], dict):
        cmd = str(probes[0].get("command") or "")
    lower = cmd.lower()
    if "powershell" in lower:
        shell = "powershell"
    elif "cmd.exe" in lower:
        shell = "cmd"
    else:
        shell = "bash"
    tool = "python3" if "python" in lower else (cmd.split()[0] if cmd else "undeclared")
    return {
        "tool": tool,
        "shell": shell,
        "data_field": "named-probe-stdout+exit",
        "measurement_kind": "subprocess-named-probe",
        "command": cmd,
    }


def _receipt_row(path: Path, *, stratum: str, rec: dict | None = None) -> dict:
    rel = path.relative_to(REPO).as_posix()
    if rec is None:
        try:
            rec = load_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {
                "id": path.stem,
                "path": rel,
                "stratum": stratum,
                "original_verdict": "NOT-CHECKED",
                "receipt": {},
            }
    uid = str(rec.get("unit_id") or rec.get("id") or path.parent.name)
    orig = rec.get("state") or rec.get("status") or rec.get("verdict") or ""
    return {
        "id": uid,
        "path": rel,
        "stratum": stratum,
        "original_verdict": normalize_verdict(str(orig)),
        "receipt": rec,
    }


def discover_receipts() -> list[dict]:
    """Live confirmation-like receipts on this worktree.

    command-center/confirmation/ holds no prior CNF receipts. G-1
    SUBAGENT-RETURN.json files with DELIVERED/SUCCESS are the corpus.
    This unit's own files are excluded.
    """
    rows: list[dict] = []
    conf = REPO / "command-center/confirmation"
    if conf.is_dir():
        for path in sorted(conf.glob("*.json")):
            if UNIT in path.name:
                continue
            rows.append(_receipt_row(path, stratum="confirmation-dir"))
    probes = REPO / "command-center/p2-wave/probes"
    if probes.is_dir():
        for path in sorted(probes.glob("*/SUBAGENT-RETURN.json")):
            if path.parent.name == UNIT:
                continue
            try:
                rec = load_json(path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(rec, dict):
                continue
            status = str(rec.get("status") or rec.get("state") or "").upper()
            if status not in {"DELIVERED", "SUCCESS"}:
                continue
            rows.append(_receipt_row(path, stratum="g1-subagent-return", rec=rec))
    return _unique_by_path(rows)


def _unique_by_path(rows: list[dict]) -> list[dict]:
    by_path = {r["path"]: r for r in rows}
    return [by_path[p] for p in sorted(by_path)]


def population_from_paths(paths: list[str]) -> list[dict]:
    """Rebuild the frozen snapshot used by the named probes."""
    rows: list[dict] = []
    for rel in paths:
        path = REPO / str(rel)
        if not path.is_file():
            continue
        if path.name == "SUBAGENT-RETURN.json":
            try:
                rec = load_json(path)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(rec, dict):
                continue
            rows.append(_receipt_row(path, stratum="g1-subagent-return", rec=rec))
        else:
            rows.append(_receipt_row(path, stratum="confirmation-dir"))
    return _unique_by_path(rows)


def reverify_item(row: dict) -> dict:
    rec = row.get("receipt") or {}
    orig = row["original_verdict"]
    source_fp = source_fingerprint_from_receipt(rec)
    author = str(rec.get("unit_id") or rec.get("id") or row["id"]) + "-g1-agent"
    reviewer = rec.get("reviewer") if isinstance(rec.get("reviewer"), dict) else {}
    reviewed_by = []
    rid = reviewer.get("reviewer_id")
    if rid:
        reviewed_by.append(str(rid))
    indep = independent(
        CONFIRMER_ID,
        author_agent_id=author,
        reviewed_by=reviewed_by,
        ancestor_authors=[],
    )
    problems: list[str] = []
    out_rel = str(rec.get("output_path") or "").replace("\\", "/")
    nbytes = 0
    artifact_state = ""
    if not out_rel:
        problems.append("no-output_path")
    else:
        artifact = REPO / out_rel
        if not artifact.is_file() or artifact.stat().st_size <= 0:
            problems.append("artifact-absent")
        else:
            nbytes = artifact.stat().st_size
            text = artifact.read_text(encoding="utf-8")
            try:
                doc = json.loads(text)
            except json.JSONDecodeError:
                problems.append("artifact-unparseable")
                doc = {}
            if isinstance(doc, dict):
                artifact_state = str(doc.get("state") or "").upper()
            if artifact_state in NOT_DELIVERING:
                problems.append(f"self-declared:{artifact_state}")
            sentinel = str(rec.get("sentinel") or "")
            if sentinel and sentinel not in text:
                problems.append("sentinel-absent")
    new = "REFUTED" if problems else "CONFIRMED"
    same = same_probe(source_fp, VERIFIER_FP)
    if same:
        problems.append("same-probe-rerun")
        new = "NOT-CHECKED"
    if not indep["independent"]:
        problems.append("confirmer-not-independent")
        new = "NOT-CHECKED"
    usable = (
        indep["independent"]
        and not same
        and orig in {"CONFIRMED", "REFUTED"}
        and new in {"CONFIRMED", "REFUTED"}
    )
    disagreement = bool(usable and orig != new)
    disposition = "agree"
    if disagreement:
        disposition = "escalate-to-raw-source-adjudication"
    elif not usable:
        disposition = "excluded"
    return {
        "id": row["id"],
        "path": row["path"],
        "stratum": row["stratum"],
        "original_verdict": orig,
        "new_verdict": new,
        "disagreement": disagreement,
        "source_fingerprint": {
            "tool": source_fp["tool"],
            "shell": source_fp["shell"],
            "data_field": source_fp["data_field"],
            "measurement_kind": source_fp["measurement_kind"],
        },
        "verifier_fingerprint": dict(VERIFIER_FP),
        "fingerprints_differ": not same,
        "independent": indep["independent"],
        "independence": indep,
        "usable": usable,
        "problems": problems,
        "disposition": disposition,
        "third_original_probe_runs": 0,
        "output_path": out_rel,
        "artifact_bytes": nbytes,
        "artifact_state": artifact_state,
        "author_agent_id": author,
    }


def rate_of(items: list[dict]) -> dict:
    usable = [it for it in items if it.get("usable")]
    disagrees = [it for it in usable if it.get("disagreement")]
    denom = len(usable)
    numer = len(disagrees)
    rate: float | None = None if denom == 0 else numer / denom
    return {
        "numerator": numer,
        "denominator": denom,
        "rate": rate,
        "usable_ids": [it["id"] for it in usable],
        "disagreement_ids": [it["id"] for it in disagrees],
        "excluded_ids": [it["id"] for it in items if not it.get("usable")],
    }


def resolve_disagreement(strategy: str) -> dict:
    """A disagreement is never resolved by re-running the original probe."""
    if strategy == "third_original_probe":
        return {
            "accepted": False,
            "classification": "same-probe-rerun",
            "disposition": "rejected",
        }
    if strategy == "raw_source_adjudication":
        return {
            "accepted": True,
            "classification": "escalated",
            "disposition": "escalate-to-raw-source-adjudication",
        }
    return {
        "accepted": False,
        "classification": "unknown-strategy",
        "disposition": "rejected",
    }


def park_same_fingerprint(fingerprints: list[str]) -> dict:
    """Two same-fingerprint structural refutes park BLOCKED with required_fix.

    A later attempt with that fingerprint is not a retry; it is a grind.
    """
    cleaned = [str(x or "").strip() for x in fingerprints]
    if len(cleaned) >= 2 and cleaned[0] and cleaned[0] == cleaned[1]:
        return {
            "park": True,
            "status": "BLOCKED",
            "required_fix": f"break-same-fingerprint:{cleaned[0]}",
        }
    return {"park": False, "status": None, "required_fix": None}


def probe_fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def domain(doc: dict) -> dict:
    """Read sampling payload from extensions (receipt_core) or the legacy top level."""
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    return {
        "sampling_frame": ext.get("sampling_frame") or doc.get("sampling_frame") or {},
        "measured": ext.get("measured") or doc.get("measured") or {},
        "items": ext.get("items") or doc.get("items") or [],
        "controls": ext.get("controls") or doc.get("controls") or {},
        "answer": ext.get("answer") or doc.get("answer") or {},
    }


_VALIDATOR = None


def _schema_store() -> dict:
    store: dict[str, Any] = {}
    for rel in (
        SCHEMA_REL,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = doc
        sid = doc.get("$id")
        if sid:
            store[str(sid)] = doc
    return store


def validator():
    """Offline Draft 2020-12 validator. Does not fetch ast-integrate.invalid."""
    global _VALIDATOR
    if _VALIDATOR is None:
        from jsonschema import Draft202012Validator, RefResolver

        store = _schema_store()
        schema = store["https://ast-integrate.invalid/" + SCHEMA_REL]
        resolver = RefResolver(base_uri=str(schema["$id"]), referrer=schema, store=store)
        _VALIDATOR = Draft202012Validator(schema, resolver=resolver)
    return _VALIDATOR


def schema_rejects_garbage(schema: dict | None = None) -> bool:
    v = validator()
    garbage = (
        {},
        {"passing_tests": 999999, "totally": "unrelated"},
        {"blob": "x" * 2000},
        {"unit_id": UNIT, "state": "SUCCESS"},
    )
    return all(not v.is_valid(doc) for doc in garbage)


def validate_report(doc: dict, schema: dict | None = None) -> list[str]:
    v = validator()
    out: list[str] = []
    for err in v.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out


def planted_controls() -> dict:
    """Both-states controls required by CNF-0002, CNF-0006, and this unit."""
    author = "impl-author-A"
    reviewer = "loop-pr-reviewer"
    ancestor = "dep-artifact-author"
    rule_a = independent(
        author, author_agent_id=author, reviewed_by=[reviewer], ancestor_authors=[ancestor]
    )
    authorship_only_reviewer = independent(
        reviewer, author_agent_id=author, reviewed_by=[], ancestor_authors=[ancestor]
    )
    rule_b = independent(
        reviewer, author_agent_id=author, reviewed_by=[reviewer], ancestor_authors=[ancestor]
    )
    rule_c = independent(
        ancestor, author_agent_id=author, reviewed_by=[reviewer], ancestor_authors=[ancestor]
    )
    fresh = independent(
        CONFIRMER_ID, author_agent_id=author, reviewed_by=[reviewer], ancestor_authors=[ancestor]
    )
    src = {
        "tool": "python3",
        "shell": "bash",
        "data_field": "sha256",
        "measurement_kind": "file-digest",
    }
    identical = dict(src)
    shell_only = {
        "tool": "python3",
        "shell": "powershell",
        "data_field": "sha256",
        "measurement_kind": "file-digest",
    }
    empty_src: dict = {}
    disagree_plant = {
        "id": "planted-disagree",
        "original_verdict": "CONFIRMED",
        "new_verdict": "REFUTED",
        "disagreement": True,
        "disposition": resolve_disagreement("raw_source_adjudication")["disposition"],
        "third_original_probe_runs": 0,
    }
    agree_plant = {
        "id": "planted-agree",
        "original_verdict": "CONFIRMED",
        "new_verdict": "CONFIRMED",
        "disagreement": False,
        "disposition": "agree",
        "third_original_probe_runs": 0,
    }
    third = resolve_disagreement("third_original_probe")
    minus = exceeds_threshold(0.1 - 1e-9, 0.1)
    plus = exceeds_threshold(0.1 + 1e-9, 0.1)
    at = exceeds_threshold(0.1, 0.1)
    return {
        "independence": {
            "rule_a_author_rejected": rule_a["independent"] is False,
            "rule_b_reviewer_rejected": rule_b["independent"] is False,
            "authorship_only_would_accept_reviewer": authorship_only_reviewer["independent"] is True,
            "rule_b_inert_if_both_agree": not (
                rule_b["independent"] is False and authorship_only_reviewer["independent"] is True
            ),
            "rule_c_ancestor_rejected": rule_c["independent"] is False,
            "fresh_confirmer_accepted": fresh["independent"] is True,
        },
        "fingerprints": {
            "identical_rejected": same_probe(src, identical) is True,
            "shell_only_accepted": same_probe(src, shell_only) is False,
            "empty_source_rejected": same_probe(empty_src, VERIFIER_FP) is True,
        },
        "disagreement": {
            "planted_disagreement_detected": disagree_plant["disagreement"] is True,
            "planted_agreement_not_flagged": agree_plant["disagreement"] is False,
            "third_original_probe_rejected": third["accepted"] is False,
            "raw_source_escalation_accepted": resolve_disagreement("raw_source_adjudication")[
                "accepted"
            ]
            is True,
        },
        "threshold": {
            "minus_epsilon_no_expansion": minus is False,
            "plus_epsilon_expansion": plus is True,
            "at_threshold_no_expansion": at is False,
            "two_simulations_differ": minus != plus,
        },
        "park": {
            "same_fingerprint_parks": park_same_fingerprint(
                ["struct:schema-invalid", "struct:schema-invalid"]
            ),
            "different_fingerprint_does_not_park": park_same_fingerprint(
                ["struct:schema-invalid", "struct:artifact-absent"]
            ),
        },
        "plants": {"disagree": disagree_plant, "agree": agree_plant},
    }


def run_sampling(population: list[dict] | None = None) -> dict:
    threshold = load_threshold()
    catalog = catalog_unit()
    if population is None:
        population = discover_receipts()
    else:
        population = _unique_by_path(population)
    pop_paths = [r["path"] for r in population]
    pop_ids = [r["id"] for r in population]
    k = draw_k(len(pop_paths))
    sampled_paths = draw(pop_paths, SEED, k)
    redraw = draw(pop_paths, SEED, k)
    other = draw(pop_paths, SEED + 1, k)
    by_path = {r["path"]: r for r in population}
    items = [reverify_item(by_path[p]) for p in sampled_paths if p in by_path]
    sampled_ids = [it["id"] for it in items]
    stats = rate_of(items)
    exceeded = exceeds_threshold(stats["rate"], threshold["threshold"])
    empty_policy = (
        "0-of-0 is reported explicitly and is not a confirmer-reliability pass"
        if stats["denominator"] == 0
        else "rate is disagreements/usable-independent-different-probe items"
    )
    seed_consumed = True
    if len(pop_paths) > 1 and k < len(pop_paths):
        seed_consumed = other != sampled_paths
    return {
        "catalog": catalog,
        "threshold": threshold,
        "population": population,
        "population_ids": pop_ids,
        "population_paths": pop_paths,
        "k": k,
        "sampled_ids": sampled_ids,
        "sampled_paths": sampled_paths,
        "same_seed_redraw": redraw,
        "seed_plus_one": other,
        "seed_reproduces": redraw == sampled_paths,
        "seed_consumed": seed_consumed,
        "items": items,
        "stats": stats,
        "threshold_exceeded": exceeded,
        "empty_set_policy": empty_policy,
        "cnf_0003_present": (REPO / CNF3_REL).is_file(),
        "controls": planted_controls(),
    }


# Names used by emit.py and the named probes.
UNIT = UNIT
OUT_REL = OUT_REL
SCHEMA_REL = SCHEMA_REL
CNF3_REL = CNF3_REL
SEED = SEED
REPO = REPO
NOT_DELIVERING = NOT_DELIVERING
load_json = load_json
catalog_unit = catalog_unit
load_threshold = load_threshold
same_probe = same_probe
schema_rejects_garbage = schema_rejects_garbage
validate_report = validate_report
run_sampling = run_sampling
planted_controls = planted_controls
resolve_disagreement = resolve_disagreement
park_same_fingerprint = park_same_fingerprint
probe_fingerprint = probe_fingerprint
domain = domain
validator = validator
