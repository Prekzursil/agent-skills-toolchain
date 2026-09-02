"""Reference detectors for CNL-0099.

Hallucinated expertise: expert weight is refused unless a seat beats the
non-expert baseline on a verifiable calibration set AND answers the
unanswerable control with unknown. Self-assertion and tag overlap are not
evidence.

Hidden conflict of interest: a conflicts declaration is required, but the
catch is the provenance join (seat identity vs artifact author/owner/vendor).
A provenance match missing from the declaration is undeclared COI. A
provenance-matched seat whose ballot still counts is counting-while-conflicted.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

UNKNOWN = frozenset(
    {"unknown", "i_do_not_know", "idk", "cannot_answer", "i-do-not-know"}
)
EVIDENCE_OK = frozenset(
    {"calibration_record", "past_accuracy", "demonstrated_competence"}
)


def load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_index() -> dict[str, Any]:
    return json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _seat_probe(council: dict[str, Any], seat_id: str) -> dict[str, Any] | None:
    probes = council.get("probes") or {}
    row = probes.get(seat_id)
    return row if isinstance(row, dict) else None


def _calibration_for(seat: dict[str, Any], domain: str) -> dict[str, Any] | None:
    rec = seat.get("calibration")
    if not isinstance(rec, dict):
        return None
    if _norm(rec.get("domain")) != _norm(domain):
        return None
    return rec


def _probe_scores(probe: dict[str, Any]) -> dict[str, Any]:
    items = probe.get("verifiable") or []
    n = len(items)
    correct = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if _norm(item.get("answer")) == _norm(item.get("expected")):
            correct += 1
    accuracy = (correct / n) if n else 0.0
    unans = probe.get("unanswerable") or {}
    u_ans = _norm(unans.get("answer")) if isinstance(unans, dict) else ""
    unanswerable_unknown = u_ans in UNKNOWN
    return {
        "n_verifiable": n,
        "n_correct": correct,
        "accuracy": accuracy,
        "unanswerable_unknown": unanswerable_unknown,
        "unanswerable_answer": u_ans,
    }


def _calibration_passes(rec: dict[str, Any], baseline: float) -> bool:
    try:
        acc = float(rec.get("accuracy"))
    except (TypeError, ValueError):
        return False
    u = _norm(rec.get("unanswerable_response"))
    return acc > baseline and u in UNKNOWN


def expertise_findings(council: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    baseline = float(council.get("non_expert_baseline", 0.25))
    task = council.get("task") or {}
    required = [_norm(x) for x in (task.get("required_domains") or [])]
    for seat in council.get("seats") or []:
        if not isinstance(seat, dict):
            continue
        if not seat.get("requests_expert_weight"):
            continue
        sid = str(seat.get("id") or "")
        claimed = [_norm(x) for x in (seat.get("claimed_domains") or [])]
        domain = claimed[0] if claimed else (required[0] if required else "")
        probe = _seat_probe(council, sid)
        rec = _calibration_for(seat, domain) if domain else None
        evidence = _norm(seat.get("evidence_basis"))
        reasons: list[str] = []
        if evidence and evidence not in EVIDENCE_OK and rec is None and probe is None:
            reasons.append("self_assertion_without_evidence")
        if probe is not None:
            scores = _probe_scores(probe)
            if scores["n_verifiable"] < 1:
                reasons.append("probe_empty")
            if scores["accuracy"] <= baseline:
                reasons.append("accuracy_at_or_below_non_expert_baseline")
            if not scores["unanswerable_unknown"]:
                reasons.append("unanswerable_answered_confidently")
        elif rec is not None:
            if not _calibration_passes(rec, baseline):
                reasons.append("calibration_record_fails_bar")
        else:
            reasons.append("no_calibration_and_no_live_probe")
        if reasons:
            findings.append(
                {
                    "detector": "hallucinated_expertise",
                    "seat_id": sid,
                    "domain": domain,
                    "reasons": reasons,
                    "tag_overlap": bool(set(claimed) & set(required)),
                }
            )
    return findings


def _provenance_conflicts(
    seat: dict[str, Any], artifact: dict[str, Any]
) -> list[dict[str, str]]:
    sid = str(seat.get("id") or "")
    out: list[dict[str, str]] = []
    author = str(artifact.get("author_id") or "")
    owner = str(artifact.get("owner_id") or "")
    vendor = str(artifact.get("vendor_id") or "")
    art_id = str(artifact.get("id") or "")
    if sid and author and sid == author:
        out.append({"kind": "authored_artifact", "subject_id": art_id})
    if sid and owner and sid == owner:
        out.append({"kind": "owns_proposal", "subject_id": art_id})
    if sid and vendor and sid == vendor:
        out.append({"kind": "is_evaluated_vendor", "subject_id": vendor})
    return out


def _declared(seat: dict[str, Any]) -> set[tuple[str, str]]:
    rows = seat.get("conflicts_declared") or []
    out: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "")
        subject = str(row.get("subject_id") or "")
        if kind and subject:
            out.add((kind, subject))
    return out


def coi_findings(council: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    artifact = council.get("artifact") or {}
    if not isinstance(artifact, dict):
        return findings
    for seat in council.get("seats") or []:
        if not isinstance(seat, dict):
            continue
        sid = str(seat.get("id") or "")
        proven = _provenance_conflicts(seat, artifact)
        if not proven:
            continue
        declared = _declared(seat)
        ballot = seat.get("ballot") or {}
        counts = bool(ballot.get("counts")) if isinstance(ballot, dict) else False
        undeclared = [c for c in proven if (c["kind"], c["subject_id"]) not in declared]
        reasons: list[str] = []
        if undeclared:
            reasons.append("undeclared_provenance_conflict")
        if counts:
            reasons.append("counting_vote_while_conflicted")
        if reasons:
            findings.append(
                {
                    "detector": "hidden_conflict_of_interest",
                    "seat_id": sid,
                    "provenance": proven,
                    "undeclared": undeclared,
                    "declared": sorted(declared),
                    "ballot_counts": counts,
                    "reasons": reasons,
                }
            )
    return findings


def evaluate(council: dict[str, Any]) -> dict[str, Any]:
    exp = expertise_findings(council)
    coi = coi_findings(council)
    findings = exp + coi
    return {
        "council_id": council.get("id"),
        "fired": bool(findings),
        "n_findings": len(findings),
        "expertise_findings": exp,
        "coi_findings": coi,
        "findings": findings,
    }


def naive_expertise_tag_match(council: dict[str, Any]) -> dict[str, Any]:
    """Weak check: tag overlap alone. Silent on self-asserted experts."""
    task = council.get("task") or {}
    required = {_norm(x) for x in (task.get("required_domains") or [])}
    findings: list[dict[str, Any]] = []
    for seat in council.get("seats") or []:
        if not isinstance(seat, dict) or not seat.get("requests_expert_weight"):
            continue
        claimed = {_norm(x) for x in (seat.get("claimed_domains") or [])}
        if required and not (claimed & required):
            findings.append(
                {
                    "detector": "naive_tag_match",
                    "seat_id": seat.get("id"),
                    "reasons": ["no_tag_overlap"],
                }
            )
    return {
        "council_id": council.get("id"),
        "fired": bool(findings),
        "n_findings": len(findings),
        "findings": findings,
        "naive": True,
    }


def naive_coi_declaration_only(council: dict[str, Any]) -> dict[str, Any]:
    """Weak check: trust the form. Silent when the declaration is empty."""
    findings: list[dict[str, Any]] = []
    for seat in council.get("seats") or []:
        if not isinstance(seat, dict):
            continue
        declared = _declared(seat)
        ballot = seat.get("ballot") or {}
        counts = bool(ballot.get("counts")) if isinstance(ballot, dict) else False
        if declared and counts:
            findings.append(
                {
                    "detector": "naive_declaration_only",
                    "seat_id": seat.get("id"),
                    "reasons": ["declared_conflict_but_ballot_counts"],
                }
            )
    return {
        "council_id": council.get("id"),
        "fired": bool(findings),
        "n_findings": len(findings),
        "findings": findings,
        "naive": True,
    }


def scan_with_control(
    target: dict[str, Any], known_present: dict[str, Any]
) -> dict[str, Any]:
    control = evaluate(known_present)
    if not control["fired"]:
        return {
            "ok": False,
            "refused_absence_claim": True,
            "reason": "detector-control missed a known-present instance",
            "control": control,
            "result": None,
        }
    result = evaluate(target)
    return {
        "ok": True,
        "refused_absence_claim": False,
        "reason": "",
        "control": control,
        "result": result,
    }


def fixture_false_positive_rate() -> dict[str, Any]:
    index = load_index()
    silent_ids = list(index.get("silent") or [])
    fires = 0
    rows = []
    for name in silent_ids:
        council = load_fixture(name)
        result = evaluate(council)
        fired = bool(result["fired"])
        if fired:
            fires += 1
        rows.append({"fixture_id": name, "fired": fired})
    n = len(silent_ids)
    rate = (fires / n) if n else 1.0
    return {
        "false_positive_numerator": fires,
        "false_positive_denominator": n,
        "false_positive_rate": rate,
        "rows": rows,
    }


def dump_result(result: dict[str, Any]) -> str:
    return json.dumps(result, sort_keys=True, separators=(",", ":"))
