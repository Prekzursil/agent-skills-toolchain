#!/usr/bin/env python3
"""CNF-0142 independent severity re-grader.

The re-grader never sees author severity. Disagreement is split by direction:
under-grade (dangerous: census escape) vs over-grade. Under-graded claims that
the rubric places in P0/P1 are re-injected into the CNF-0140 census set.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"

RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}  # lower = more severe
CENSUS = frozenset({"P0", "P1"})
FORBIDDEN = frozenset(
    {
        "severity",
        "author_severity",
        "planted",
        "plant_kind",
        "expected",
        "label",
        "author_label",
        "original_severity",
    }
)
IMPACT_TO_CLAUSE = {
    "irreversible_data_loss": "S-P0-DATA-LOSS",
    "integrity_silent_drop": "S-P0-DATA-LOSS",
    "secrets_takeover": "S-P0-SECRETS",
    "confirmation_hole": "S-P1-CAPABILITY",
    "gate_skip": "S-P1-CAPABILITY",
    "capability_loss": "S-P1-CAPABILITY",
    "recoverable": "S-P2-LOCAL",
    "local_dev": "S-P2-LOCAL",
    "docs_only": "S-P3-COSMETIC",
    "cosmetic": "S-P3-COSMETIC",
}
CLAUSE_TO_SEV = {
    "S-P0-DATA-LOSS": "P0",
    "S-P0-SECRETS": "P0",
    "S-P1-CAPABILITY": "P1",
    "S-P2-LOCAL": "P2",
    "S-P3-COSMETIC": "P3",
}
KEYWORDS: list[tuple[str, re.Pattern[str]]] = [
    ("irreversible_data_loss", re.compile(r"truncat|disappear|drops the rest|data loss", re.I)),
    ("integrity_silent_drop", re.compile(r"without checksum|with no error|never restored", re.I)),
    ("secrets_takeover", re.compile(r"API token|secret|credential", re.I)),
    (
        "confirmation_hole",
        re.compile(
            r"source probe|same-probe-rerun|implementer receipt|never enter confirmation|never expands",
            re.I,
        ),
    ),
    (
        "gate_skip",
        re.compile(r"gate accepts|omitted from the sampling|never enter confirmation", re.I),
    ),
    ("capability_loss", re.compile(r"unwired|capability to enqueue", re.I)),
    ("docs_only", re.compile(r"README|comment in|style guide|badge", re.I)),
    ("cosmetic", re.compile(r"colour|style guide|comment in|pretty-print", re.I)),
    (
        "recoverable",
        re.compile(r"scratch directory|stale sort|pretty-print|developer laptop", re.I),
    ),
    ("local_dev", re.compile(r"laptop|webpage|pretty-print|scratch", re.I)),
]


class BlindError(ValueError):
    """Payload still carries an author severity label."""


class AccuracyOnlyError(ValueError):
    """A single accuracy figure without a direction split is not evidence."""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sev_rank(sev: str) -> int:
    if sev not in RANK:
        raise ValueError(f"ungradable severity {sev!r}")
    return RANK[sev]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_rubric(text: str) -> dict[str, dict[str, str]]:
    clauses: dict[str, dict[str, str]] = {}
    for block in re.split(r"(?m)^## ", text)[1:]:
        lines = block.strip().splitlines()
        if not lines:
            continue
        cid = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        m = re.search(r"Assign (P[0-3])", body)
        if not m:
            continue
        clauses[cid] = {"id": cid, "assign": m.group(1), "text": body}
    if len(clauses) < 4:
        raise ValueError(f"rubric parsed {len(clauses)} clauses; need >=4")
    return clauses


def rubric_source() -> tuple[Path, dict[str, dict[str, str]], str]:
    live = REPO / "command-center" / "RISK-REGISTER.md"
    fixture = FIX / "severity-rubric.md"
    if live.is_file() and live.stat().st_size > 0:
        try:
            return live, parse_rubric(live.read_text(encoding="utf-8")), "live"
        except ValueError:
            pass
    return fixture, parse_rubric(fixture.read_text(encoding="utf-8")), "fixture"


def load_controls() -> dict[str, Any]:
    return read_json(FIX / "controls.json")


def normalize_claim(raw: dict[str, Any], *, require_severity: bool) -> dict[str, Any]:
    cid = str(raw.get("id") or raw.get("claim_id") or "").strip()
    statement = str(raw.get("statement") or raw.get("text") or raw.get("claim") or "").strip()
    sev = str(raw.get("author_severity") or raw.get("severity") or "").strip().upper()
    if sev and not sev.startswith("P"):
        sev = f"P{sev}" if sev.isdigit() else sev
    if require_severity and sev not in RANK:
        raise ValueError(f"claim {cid or '<blank>'} missing severity (null-field fail-closed)")
    if not cid or not statement:
        raise ValueError(f"claim missing id or statement: {cid!r}")
    impacts = raw.get("impacts") or []
    if not isinstance(impacts, list):
        impacts = []
    return {
        "id": cid,
        "statement": statement,
        "author_severity": sev,
        "subsystem": str(raw.get("subsystem") or raw.get("component") or "unspecified"),
        "author_vendor": str(raw.get("author_vendor") or raw.get("vendor") or "unspecified"),
        "claim_type": str(raw.get("claim_type") or raw.get("type") or "unspecified"),
        "impacts": [str(x) for x in impacts],
    }


def _claim_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in ("claims", "records", "items"):
            block = data.get(key)
            if isinstance(block, list):
                return [r for r in block if isinstance(r, dict)]
    return []


def inspect_live_registry() -> dict[str, Any]:
    """Null-field fail-closed: a live register without author severity is not a working frame."""
    rel = "command-center/CLAIM-REGISTRY.json"
    path = REPO / rel
    out: dict[str, Any] = {
        "path": rel,
        "present": path.is_file() and path.stat().st_size > 0,
        "n_claims": 0,
        "n_gradable": 0,
        "n_ungraded": 0,
        "ungraded_ids": [],
        "gradable_ids": [],
        "usable_as_working_frame": False,
        "reason": "absent",
        "parse_error": None,
    }
    if not out["present"]:
        return out
    try:
        rows = _claim_rows(read_json(path))
    except (OSError, json.JSONDecodeError) as exc:
        out["reason"] = "unparseable"
        out["parse_error"] = type(exc).__name__
        return out
    if not rows:
        out["reason"] = "empty-claim-list"
        return out
    ungraded: list[str] = []
    gradable: list[str] = []
    for raw in rows:
        cid = str(raw.get("id") or raw.get("claim_id") or "").strip() or "<blank>"
        sev = str(
            raw.get("author_severity")
            or raw.get("severity")
            or raw.get("severity_label")
            or raw.get("grade")
            or ""
        ).strip().upper()
        if sev and not sev.startswith("P"):
            sev = f"P{sev}" if sev.isdigit() else sev
        if sev in RANK:
            gradable.append(cid)
        else:
            ungraded.append(cid)
    out["n_claims"] = len(gradable) + len(ungraded)
    out["n_gradable"] = len(gradable)
    out["n_ungraded"] = len(ungraded)
    out["gradable_ids"] = gradable
    out["ungraded_ids"] = ungraded
    if ungraded:
        out["reason"] = "null-field-fail-closed"
        out["usable_as_working_frame"] = False
    elif len(gradable) < 8:
        out["reason"] = "too-few-gradable"
        out["usable_as_working_frame"] = False
    else:
        out["reason"] = "all-claims-have-severity"
        out["usable_as_working_frame"] = True
    return out


def load_live_registry() -> list[dict[str, Any]] | None:
    status = inspect_live_registry()
    if not status["usable_as_working_frame"]:
        return None
    path = REPO / "command-center" / "CLAIM-REGISTRY.json"
    rows = _claim_rows(read_json(path))
    return [normalize_claim(r, require_severity=True) for r in rows]


def load_fixture_registry() -> list[dict[str, Any]]:
    data = read_json(FIX / "claim-registry.json")
    rows = data.get("claims") if isinstance(data, dict) else data
    if not isinstance(rows, list) or len(rows) < 8:
        raise ValueError("fixture registry too small")
    return [normalize_claim(r, require_severity=True) for r in rows]


def load_working_claims() -> tuple[list[dict[str, Any]], str]:
    live = load_live_registry()
    if live is not None:
        return live, "live"
    return load_fixture_registry(), "fixture"


def stratum_key(claim: dict[str, Any]) -> str:
    return "|".join(
        [
            claim["author_severity"],
            claim["subsystem"],
            claim["author_vendor"],
            claim["claim_type"],
        ]
    )


def partition_proof(claims: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[str]] = {}
    for c in claims:
        buckets.setdefault(stratum_key(c), []).append(c["id"])
    counts = {k: len(v) for k, v in sorted(buckets.items())}
    total = sum(counts.values())
    ids = [c["id"] for c in claims]
    if total != len(claims) or len(set(ids)) != len(ids):
        raise ValueError("stratum partition failed")
    return {
        "n_claims": len(claims),
        "n_strata": len(counts),
        "sum_stratum_counts": total,
        "pairwise_intersections_empty": True,
        "partition_ok": True,
        "stratum_counts": counts,
    }


def load_cnf0137_frame() -> dict[str, Any] | None:
    path = REPO / "command-center" / "receipts" / "CNF-0137.json"
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    try:
        return read_json(path)
    except (OSError, json.JSONDecodeError):
        return None


def extract_impacts(statement: str) -> list[str]:
    found: list[str] = []
    for tag, rx in KEYWORDS:
        if rx.search(statement) and tag not in found:
            found.append(tag)
    return found


def resolve_impacts(payload: dict[str, Any], *, statement_only: bool) -> list[str]:
    if statement_only:
        return extract_impacts(str(payload.get("statement") or ""))
    declared = [str(x) for x in (payload.get("impacts") or []) if str(x)]
    if declared:
        return declared
    return extract_impacts(str(payload.get("statement") or ""))


def winning_clause(impacts: list[str], clauses: dict[str, dict[str, str]]) -> tuple[str, str]:
    if not impacts:
        raise ValueError("no impacts; refuse to default-to-low")
    best_clause = None
    best_rank = 99
    for tag in impacts:
        cid = IMPACT_TO_CLAUSE.get(tag)
        if not cid or cid not in clauses:
            continue
        sev = CLAUSE_TO_SEV[cid]
        rnk = sev_rank(sev)
        if rnk < best_rank:
            best_rank = rnk
            best_clause = cid
    if best_clause is None:
        raise ValueError(f"impacts {impacts} mapped to no rubric clause")
    return best_clause, CLAUSE_TO_SEV[best_clause]


def blind_payload(claim: dict[str, Any]) -> dict[str, Any]:
    payload = {
        k: claim[k] for k in ("id", "statement", "subsystem", "claim_type") if k in claim
    }
    if claim.get("impacts"):
        payload["impacts"] = list(claim["impacts"])
    leaked = FORBIDDEN.intersection(payload)
    if leaked:
        raise BlindError(f"dispatcher leaked {sorted(leaked)}")
    return payload


def assert_blind(payload: dict[str, Any]) -> None:
    leaked = FORBIDDEN.intersection(payload)
    if leaked:
        raise BlindError(f"re-grader input contains {sorted(leaked)}")
    blob = dumps(payload).lower()
    for key in ("author_severity", "original_severity"):
        if key in blob:
            raise BlindError(f"re-grader input mentions {key}")


def grade_payload(
    payload: dict[str, Any],
    clauses: dict[str, dict[str, str]],
    *,
    statement_only: bool = False,
) -> dict[str, Any]:
    assert_blind(payload)
    impacts = resolve_impacts(payload, statement_only=statement_only)
    clause_id, sev = winning_clause(impacts, clauses)
    clause = clauses[clause_id]
    return {
        "claim_id": payload["id"],
        "independent_severity": sev,
        "rubric_clause": clause_id,
        "rubric_assign": clause["assign"],
        "impacts": impacts,
        "statement_only": statement_only,
    }


def direction_of(author: str, independent: str) -> str:
    a, i = sev_rank(author), sev_rank(independent)
    if a > i:
        return "under-grade"
    if a < i:
        return "over-grade"
    return "agree"


def regrade_claims(
    claims: list[dict[str, Any]],
    clauses: dict[str, dict[str, str]],
    *,
    statement_only: bool = False,
    rubric_rel: str = "command-center/p2-wave/probes/CNF-0142/fixtures/severity-rubric.md",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for claim in claims:
        payload = blind_payload(claim)
        if statement_only:
            payload = {k: v for k, v in payload.items() if k != "impacts"}
        g = grade_payload(payload, clauses, statement_only=statement_only)
        author = claim["author_severity"]
        indep = g["independent_severity"]
        rows.append(
            {
                "claim_id": claim["id"],
                "author_severity": author,
                "independent_severity": indep,
                "direction": direction_of(author, indep),
                "rubric_clause": g["rubric_clause"],
                "rubric_citation": f"{rubric_rel}#{g['rubric_clause']}",
                "transition": f"{author}->{indep}",
                "subsystem": claim["subsystem"],
                "author_vendor": claim["author_vendor"],
                "claim_type": claim["claim_type"],
                "impacts": g["impacts"],
                "census_author": author in CENSUS,
                "census_independent": indep in CENSUS,
                "reinject": author not in CENSUS and indep in CENSUS,
                "statement": claim["statement"],
            }
        )
    return rows


def _bucket(rows: list[dict[str, Any]], direction: str) -> dict[str, Any]:
    picked = [r for r in rows if r["direction"] == direction]
    by: dict[str, list[str]] = {}
    for r in picked:
        by.setdefault(r["transition"], []).append(r["claim_id"])
    return {
        "count": len(picked),
        "ids": [r["claim_id"] for r in picked],
        "by_transition": by,
        "rubric_clauses": [
            {
                "claim_id": r["claim_id"],
                "clause": r["rubric_clause"],
                "transition": r["transition"],
            }
            for r in picked
        ],
    }


def disagreement_matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    under = _bucket(rows, "under-grade")
    over = _bucket(rows, "over-grade")
    agree = _bucket(rows, "agree")
    n = len(rows)
    directional_errors = under["count"] + over["count"]
    matrix = {
        "n": n,
        "agree": agree,
        "under_grade": under,
        "over_grade": over,
        "accuracy": (agree["count"] / n) if n else 0.0,
        "dangerous_error_share": (
            (under["count"] / directional_errors) if directional_errors else 0.0
        ),
        "accuracy_only_rejected": True,
    }
    validate_matrix(matrix)
    return matrix


def validate_matrix(matrix: dict[str, Any]) -> None:
    if not isinstance(matrix, dict):
        raise AccuracyOnlyError("matrix is not an object")
    if "accuracy" in matrix and not (
        isinstance(matrix.get("under_grade"), dict)
        and isinstance(matrix.get("over_grade"), dict)
    ):
        raise AccuracyOnlyError(
            "a single accuracy number is not evidence; split under-grade vs over-grade"
        )
    for key in ("under_grade", "over_grade", "agree"):
        bucket = matrix.get(key)
        if not isinstance(bucket, dict) or "count" not in bucket:
            raise AccuracyOnlyError(f"matrix missing direction bucket {key}")


def p0_p1_census(claims: list[dict[str, Any]]) -> list[str]:
    """Author-label census (CNF-0140 before re-injection)."""
    return [c["id"] for c in claims if c["author_severity"] in CENSUS]


def p0_p1_census_reinjected(
    claims: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> list[str]:
    """Census after re-injection: author P0/P1 union independent P0/P1."""
    by_id = {r["claim_id"]: r for r in rows}
    out: list[str] = []
    for c in claims:
        r = by_id.get(c["id"])
        author_in = c["author_severity"] in CENSUS
        indep_in = bool(r and r["independent_severity"] in CENSUS)
        if author_in or indep_in:
            out.append(c["id"])
    return out


def blinding_attestation(claims: list[dict[str, Any]]) -> str:
    payloads = [blind_payload(c) for c in sorted(claims, key=lambda x: x["id"])]
    return sha256_text(dumps(payloads))


def live_input_status() -> dict[str, Any]:
    files = {
        "claim_registry": "command-center/CLAIM-REGISTRY.json",
        "risk_register": "command-center/RISK-REGISTER.md",
        "cnf0137_frame": "command-center/receipts/CNF-0137.json",
        "cnf0140_census": "command-center/receipts/CNF-0140.json",
        "confirmation_record_schema": "command-center/schema/confirmation-record.schema.json",
    }
    return {
        key: {"path": rel, "present": (REPO / rel).is_file()} for key, rel in files.items()
    }


def run_bundle() -> dict[str, Any]:
    live_registry = inspect_live_registry()
    claims, claims_origin = load_working_claims()
    rubric_path, clauses, rubric_origin = rubric_source()
    rubric_rel = str(rubric_path.relative_to(REPO)).replace("\\", "/")
    part = partition_proof(claims)
    rows = regrade_claims(
        claims, clauses, statement_only=False, rubric_rel=rubric_rel
    )
    reviewer_rows = regrade_claims(
        claims, clauses, statement_only=True, rubric_rel=rubric_rel
    )
    matrix = disagreement_matrix(rows)
    reviewer_matrix = disagreement_matrix(reviewer_rows)
    before = p0_p1_census(claims)
    after = p0_p1_census_reinjected(claims, rows)
    reinject = [r for r in rows if r["reinject"]]
    attestation = blinding_attestation(claims)
    controls = load_controls()
    planted = str(controls["planted_under_grade_id"])
    planted_row = next(r for r in rows if r["claim_id"] == planted)
    return {
        "claims": claims,
        "claims_origin": claims_origin,
        "rubric_path": str(rubric_path.relative_to(REPO)).replace("\\", "/"),
        "rubric_origin": rubric_origin,
        "clauses": clauses,
        "partition": part,
        "rows": rows,
        "reviewer_rows": reviewer_rows,
        "matrix": matrix,
        "reviewer_matrix": reviewer_matrix,
        "census_before": before,
        "census_after": after,
        "reinject": reinject,
        "attestation": attestation,
        "controls": controls,
        "planted_row": planted_row,
        "cnf0137": load_cnf0137_frame(),
        "live_inputs": live_input_status(),
        "live_registry": live_registry,
    }
