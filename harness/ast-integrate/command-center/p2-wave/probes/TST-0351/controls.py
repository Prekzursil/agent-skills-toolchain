"""Catalog-required tests for TST-0351."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from extract import extract_from_text, extract_mentions, extract_path
from ledger import load_ledger, load_registry
from resolve import CONTRADICTED, RESOLVED, UNRESOLVED, classify_claims, resolve_claim

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
LABELLED = FIXTURES / "labelled"
LEDGER_DIR = "command-center/p2-wave/probes/TST-0351/fixtures/ledger"
REGISTRY_REL = "command-center/p2-wave/probes/TST-0351/fixtures/ledger/TEST-REGISTRY.json"


def _repo() -> Path:
    return HERE.parents[3]


def _load_labels() -> dict[str, Any]:
    return json.loads((LABELLED / "labels.json").read_text(encoding="utf-8"))


def test_claim_extraction_recall_against_hand_labelled_sample() -> dict[str, Any]:
    labels = _load_labels()
    repo = _repo()
    missing: list[dict[str, Any]] = []
    found_forms: list[dict[str, Any]] = []
    for spec in labels["use"]:
        path = LABELLED / spec["file"]
        rel = path.relative_to(repo).as_posix()
        rows = extract_path(path, repo)
        forms = {r["form"] for r in rows if r.get("role") == "use"}
        hit = spec["form"] in forms
        found_forms.append(
            {
                "file": spec["file"],
                "want_form": spec["form"],
                "got_forms": sorted(forms),
                "hit": hit,
                "count": len(rows),
            }
        )
        if not hit:
            missing.append({"file": spec["file"], "form": spec["form"], "got": sorted(forms)})
    mention_leaks: list[dict[str, Any]] = []
    for spec in labels["mention"]:
        path = LABELLED / spec["file"]
        rel = path.relative_to(repo).as_posix()
        text = path.read_text(encoding="utf-8")
        uses = extract_from_text(text, rel)
        mentions = extract_mentions(text, rel)
        if uses:
            mention_leaks.append(
                {
                    "file": spec["file"],
                    "use_count": len(uses),
                    "forms": [u["form"] for u in uses],
                }
            )
        if not mentions:
            missing.append({"file": spec["file"], "form": "mention-expected", "got": []})
    labelled_n = len(labels["use"])
    recalled = labelled_n - len([m for m in missing if m.get("form") != "mention-expected"])
    passed = not missing and not mention_leaks
    return {
        "id": "test_claim_extraction_recall_against_hand_labelled_sample",
        "pass": passed,
        "labelled_use": labelled_n,
        "recalled": recalled,
        "missing": missing,
        "mention_leaks": mention_leaks,
        "per_file": found_forms,
    }


def test_use_versus_mention_describing_document_is_silent() -> dict[str, Any]:
    """C16: a document DESCRIBING this defect class must not be flagged as making the claim."""
    repo = _repo()
    path = LABELLED / "mention-defect-class.md"
    rel = path.relative_to(repo).as_posix()
    text = path.read_text(encoding="utf-8")
    uses = extract_from_text(text, rel)
    mentions = extract_mentions(text, rel)
    passed = uses == [] and len(mentions) >= 3
    return {
        "id": "test_use_versus_mention_describing_document_is_silent",
        "pass": passed,
        "use_count": len(uses),
        "mention_count": len(mentions),
        "mention_forms": sorted({m["form"] for m in mentions}),
        "leaked_uses": uses,
    }


def test_resolution_attempted_against_ledger_before_unbacked() -> dict[str, Any]:
    repo = _repo()
    ledger = load_ledger(repo, ledger_dir=LEDGER_DIR)
    registry = load_registry(repo, registry_rel=REGISTRY_REL)
    path = LABELLED / "use-unit-only.json"
    rel = path.relative_to(repo).as_posix()
    claims = extract_path(path, repo)
    live = [resolve_claim(c, ledger, registry) for c in claims]
    empty_ledger = {
        "present": False,
        "by_run_id": {},
        "by_unit_id": {},
        "rows": [],
        "path": LEDGER_DIR,
        "files": [],
        "row_count": 0,
    }
    skipped = [resolve_claim(c, empty_ledger, None) for c in claims]
    live_resolved = [r for r in live if r["class"] == RESOLVED]
    skipped_unbacked = [r for r in skipped if r["class"] == UNRESOLVED]
    attempted = all(r.get("resolution_attempted") is True for r in live + skipped)
    passed = (
        bool(claims)
        and bool(live_resolved)
        and bool(skipped_unbacked)
        and attempted
        and live_resolved[0].get("resolved_run_id") == "run-ok-unit-only"
        and (
            "by_unit_id" in (live_resolved[0].get("ledger_lookups") or [])
            or "registry" in (live_resolved[0].get("ledger_lookups") or [])
        )
    )
    return {
        "id": "test_resolution_attempted_against_ledger_before_unbacked",
        "pass": passed,
        "claim_count": len(claims),
        "live_classes": [r["class"] for r in live],
        "skipped_classes": [r["class"] for r in skipped],
        "live_run_id": (live_resolved[0].get("resolved_run_id") if live_resolved else None),
        "attempted": attempted,
        "both_states": {
            "ledger_read_resolves": bool(live_resolved),
            "unread_ledger_is_unbacked": bool(skipped_unbacked),
        },
    }


def test_contradiction_planted_failed_run_is_caught() -> dict[str, Any]:
    repo = _repo()
    ledger = load_ledger(repo, ledger_dir=LEDGER_DIR)
    registry = load_registry(repo, registry_rel=REGISTRY_REL)
    path = LABELLED / "use-failed-run.json"
    claims = extract_path(path, repo)
    report = classify_claims(claims, ledger, registry)
    contradicted = report["contradicted"]
    order = report["classes_in_severity_order"]
    passed = (
        bool(claims)
        and len(contradicted) >= 1
        and contradicted[0]["class"] == CONTRADICTED
        and contradicted[0].get("reason") == "cited-run-failed"
        and contradicted[0].get("resolved_run_id") == "run-fail-1"
        and order[0] == CONTRADICTED
        and report["defects"]
        and report["defects"][0]["class"] == CONTRADICTED
    )
    return {
        "id": "test_contradiction_planted_failed_run_is_caught",
        "pass": passed,
        "claim_count": len(claims),
        "contradicted": len(contradicted),
        "first_class": order[0],
        "reason": contradicted[0].get("reason") if contradicted else None,
        "run_id": contradicted[0].get("resolved_run_id") if contradicted else None,
    }


def run_required_tests() -> list[dict[str, Any]]:
    return [
        test_claim_extraction_recall_against_hand_labelled_sample(),
        test_resolution_attempted_against_ledger_before_unbacked(),
        test_contradiction_planted_failed_run_is_caught(),
        test_use_versus_mention_describing_document_is_silent(),
    ]
