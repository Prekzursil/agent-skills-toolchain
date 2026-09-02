"""Second-order three-test review and recursion stopping rule for SYN-0039."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from corpus import REPO, load_findings

MAX_DEPTH = 2
IG_THRESHOLD = 0.05
UNIV_RE = re.compile(
    r"\b(every|all|none|never|always|almost certain|100 percent|no unit|all units)\b",
    re.I,
)
BOUND_RE = re.compile(
    r"\b(per |denominator|n\s*=\s*\d+|sample of|at least \d+|this (unit|file|fixture|control)|scoped to|SYN-\d{4}|planted fixture|N=1)\b",
    re.I,
)
REMEDY_RE = re.compile(
    r"\b(rewrite|require|enforce|refuse|record|stop|plant|fix|declare|emit|attach|name a|must )\b",
    re.I,
)
RULE_STATEMENT = (
    "Stop when measured information gain at this depth is below "
    f"threshold {IG_THRESHOLD}, or when depth reaches {MAX_DEPTH}, "
    "whichever fires first. Do not launch a third-order pass once the rule fires."
)


def is_anchored(finding: dict[str, Any], repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    probes = []
    for rel in finding.get("cited_paths") or []:
        if not isinstance(rel, str) or not rel.strip():
            continue
        path = root / rel.replace("\\", "/").lstrip("./")
        probes.append({"path": rel, "exists": path.is_file()})
    return {
        "anchored": any(p["exists"] for p in probes),
        "path_probes": probes,
    }


def is_scoped(finding: dict[str, Any]) -> bool:
    claim = str(finding.get("claim") or "")
    evidence = str(finding.get("evidence_text") or "")
    text = f"{claim} {evidence}"
    has_univ = bool(UNIV_RE.search(claim))
    has_bound = bool(BOUND_RE.search(text))
    if has_univ and not has_bound:
        return False
    if has_bound:
        return True
    src = str(finding.get("source_unit") or "")
    return bool(re.fullmatch(r"SYN-\d{4}", src))


def has_remedy(finding: dict[str, Any]) -> bool:
    remedy = str(finding.get("remedy") or "").strip()
    if len(remedy) >= 8 and REMEDY_RE.search(remedy):
        return True
    claim = str(finding.get("claim") or "")
    return "Target:" in claim and bool(REMEDY_RE.search(claim))


def disposition_of(anchored: bool, scoped: bool, remedy_named: bool) -> str:
    fails = []
    if not anchored:
        fails.append("unanchored")
    if not scoped:
        fails.append("unscoped")
    if not remedy_named:
        fails.append("no-remedy")
    if not fails:
        return "ACCEPT"
    return "HOLD:" + "+".join(fails)


def review_finding(finding: dict[str, Any], repo: Path | None = None) -> dict[str, Any]:
    anchor = is_anchored(finding, repo)
    scoped = is_scoped(finding)
    remedy = has_remedy(finding)
    disp = disposition_of(anchor["anchored"], scoped, remedy)
    return {
        "id": finding["id"],
        "source_unit": finding.get("source_unit"),
        "claim": finding.get("claim"),
        "kind": finding.get("kind"),
        "live_present": finding.get("live_present"),
        "cited_paths": list(finding.get("cited_paths") or []),
        "path_probes": anchor["path_probes"],
        "anchored": anchor["anchored"],
        "scoped": scoped,
        "remedy_named": remedy,
        "disposition": disp,
        "failing_tests": []
        if disp == "ACCEPT"
        else disp.removeprefix("HOLD:").split("+"),
    }


def failing_axes(reviews: list[dict[str, Any]]) -> set[tuple[str, str]]:
    axes: set[tuple[str, str]] = set()
    for row in reviews:
        fid = str(row.get("id") or "")
        if not row.get("anchored"):
            axes.add((fid, "anchored"))
        if not row.get("scoped"):
            axes.add((fid, "scoped"))
        if not row.get("remedy_named"):
            axes.add((fid, "remedy_named"))
    return axes


def information_gain(
    current: list[dict[str, Any]],
    prior_failing: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Novelty of 3-test fail axes versus a prior set on the same subjects.

    First application (empty prior): gain is 1.0 when any fail axis exists,
    else 0.0. Re-applying the same tests to the same reviews yields 0.0.
    """
    current_fail = failing_axes(current)
    prior = prior_failing or set()
    new = current_fail - prior
    union = current_fail | prior
    if not union:
        gain = 0.0
    else:
        gain = len(new) / len(union)
    return {
        "information_gain": gain,
        "n_current_fail_axes": len(current_fail),
        "n_prior_fail_axes": len(prior),
        "n_new_fail_axes": len(new),
        "formula": (
            "|fail_axes(current) - fail_axes(prior)| / "
            "|fail_axes(current) ∪ fail_axes(prior)| "
            "on a fixed subject set; empty-empty is 0.0"
        ),
    }


def should_launch_deeper(depth: int, information_gain_value: float) -> dict[str, Any]:
    """Whichever-first: IG below threshold, else depth >= max, else continue."""
    if information_gain_value < IG_THRESHOLD:
        return {
            "launch": False,
            "trigger": "information_gain",
            "fired": True,
            "depth": depth,
            "information_gain": information_gain_value,
        }
    if depth >= MAX_DEPTH:
        return {
            "launch": False,
            "trigger": "depth",
            "fired": True,
            "depth": depth,
            "information_gain": information_gain_value,
        }
    return {
        "launch": True,
        "trigger": "none",
        "fired": False,
        "depth": depth,
        "information_gain": information_gain_value,
    }


def refuse_deeper_pass(depth: int, information_gain_value: float) -> dict[str, Any]:
    decision = should_launch_deeper(depth, information_gain_value)
    if decision["launch"]:
        raise RuntimeError(
            "SYN-0039 stopping rule did not fire; a deeper pass would still pay"
        )
    return {
        "launched": False,
        "reason": decision["trigger"],
        "depth": depth,
        "information_gain": information_gain_value,
        "rule": RULE_STATEMENT,
    }


def review(
    *,
    include_fixtures: bool = True,
    depth: int = MAX_DEPTH,
    prior_failing: set[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    corpus = load_findings(include_fixtures=include_fixtures)
    reviews = [review_finding(f) for f in corpus["findings"]]
    ig = information_gain(reviews, prior_failing)
    gain = float(ig["information_gain"])
    ig_if_repeated = information_gain(reviews, failing_axes(reviews))
    decision = should_launch_deeper(depth, gain)
    refusal = refuse_deeper_pass(depth, gain)
    planted = next((r for r in reviews if r["id"] == "PLANT-UNANCHORED"), None)
    good = next((r for r in reviews if r["id"] == "CTRL-GOOD"), None)
    return {
        "corpus": {
            "subject_ids": corpus["subject_ids"],
            "n_findings": corpus["n_findings"],
            "n_live_units": corpus["n_live_units"],
            "n_absent_units": corpus["n_absent_units"],
            "input_status": corpus["input_status"],
        },
        "meta_findings": reviews,
        "counts": {
            "reviewed": len(reviews),
            "accept": sum(1 for r in reviews if r["disposition"] == "ACCEPT"),
            "hold": sum(1 for r in reviews if r["disposition"] != "ACCEPT"),
            "unanchored": sum(1 for r in reviews if not r["anchored"]),
            "unscoped": sum(1 for r in reviews if not r["scoped"]),
            "no_remedy": sum(1 for r in reviews if not r["remedy_named"]),
        },
        "stopping_rule": {
            "statement": RULE_STATEMENT,
            "information_gain_threshold": IG_THRESHOLD,
            "max_depth": MAX_DEPTH,
            "depth": depth,
            "information_gain": gain,
            "information_gain_if_same_subjects_reapplied": ig_if_repeated[
                "information_gain"
            ],
            "information_gain_detail": ig,
            "evaluated": True,
            "fired": bool(decision["fired"]),
            "trigger": decision["trigger"],
            "deeper_pass_launched": False,
            "deeper_pass_refusal": refusal,
        },
        "controls": {
            "planted_unanchored": planted,
            "known_good": good,
        },
        "distinct_from": {
            "SYN-0026": (
                "SYN-0026 is a different vendor at the same first-order "
                "meta-review; this unit is a second-order pass with a depth cap"
            ),
            "SYN-0027": (
                "SYN-0027 reapplies the same lenses to their own output; "
                "this unit applies only anchored/scoped/remedy tests plus a "
                "written stopping rule"
            ),
        },
    }


def payload_from_artifact(doc: dict[str, Any]) -> dict[str, Any]:
    """Read stopping_rule / meta_findings from report (schema) or top-level."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    rule: dict[str, Any] = {}
    findings: list[Any] = []
    for src in (doc, report, ext):
        if not isinstance(src, dict):
            continue
        if isinstance(src.get("stopping_rule"), dict) and src["stopping_rule"] and not rule:
            rule = src["stopping_rule"]
        if isinstance(src.get("meta_findings"), list) and src["meta_findings"] and not findings:
            findings = src["meta_findings"]
    return {"stopping_rule": rule, "meta_findings": findings}
