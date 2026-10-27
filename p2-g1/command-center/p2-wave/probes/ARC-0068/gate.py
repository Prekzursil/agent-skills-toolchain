#!/usr/bin/env python3
"""ARC-0068 full-read gate: citation coverage against file-derived anchors.

Metric (catalog): distinct dossier sections cited / sections present.
Threshold: 1/1 (every file-derived section must be cited). A judge's attestation is not evidence. Anchors are derived
from the dossier file's structure, not from a hand-listed name table.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
THRESHOLD_NUM = 1
THRESHOLD_DEN = 1
FR_COVERAGE = "FR-coverage"
FR_NO_CITATIONS = "FR-no-citations"
FR_EMPTY_DOSSIER = "FR-empty-dossier"
FIXTURE_DOSSIER = HERE / "fixtures" / "dossier.json"
FIXTURE_DIGEST = HERE / "fixtures" / "digest-scorecard.json"
FIXTURE_FULL = HERE / "fixtures" / "full-scorecard.json"
FIXTURE_ASSERT = HERE / "fixtures" / "assertion-only-scorecard.json"
LIVE_DOSSIERS = [
    "command-center/phase3/A1/DESIGN.json",
    "command-center/phase3/A2/DESIGN.json",
]


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_section_value(value: Any) -> bool:
    """Structured top-level values are sections; scalars are metadata."""
    if isinstance(value, dict) and value:
        return True
    if isinstance(value, list) and any(isinstance(item, dict) for item in value):
        return True
    return False


def extract_anchors(dossier: dict) -> list[str]:
    if not isinstance(dossier, dict):
        raise TypeError("dossier must be a JSON object")
    return sorted(key for key, value in dossier.items() if is_section_value(value))


def extract_anchors_from_path(path: Path) -> list[str]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise TypeError(f"{path} is not a JSON object")
    return extract_anchors(data)


def _collect_citation_strings(node: Any, into: list[str]) -> None:
    if isinstance(node, str):
        text = node.strip()
        if text:
            into.append(text)
        return
    if isinstance(node, list):
        for item in node:
            _collect_citation_strings(item, into)
        return
    if not isinstance(node, dict):
        return
    for key, value in node.items():
        if key in {
            "citation",
            "citations",
            "anchor",
            "anchors",
            "section",
            "section_id",
            "evidence_citation",
        }:
            _collect_citation_strings(value, into)
        elif key in {"dimensions", "evidence", "scores", "reads"}:
            _collect_citation_strings(value, into)


def extract_citations(scorecard: dict) -> list[str]:
    if not isinstance(scorecard, dict):
        raise TypeError("scorecard must be a JSON object")
    found: list[str] = []
    _collect_citation_strings(scorecard.get("citations"), found)
    _collect_citation_strings(scorecard.get("evidence"), found)
    _collect_citation_strings(scorecard.get("dimensions"), found)
    _collect_citation_strings(scorecard.get("reads"), found)
    seen: set[str] = set()
    ordered: list[str] = []
    for item in found:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def citation_matches(cite: str, anchors: set[str]) -> str | None:
    raw = cite.strip()
    if not raw:
        return None
    if raw in anchors:
        return raw
    if raw.startswith("#") and raw[1:] in anchors:
        return raw[1:]
    if "#" in raw:
        frag = raw.split("#", 1)[1].strip()
        if frag in anchors:
            return frag
    tail = raw.replace("\\", "/").rsplit("/", 1)[-1]
    if tail in anchors:
        return tail
    return None


def matched_anchors(citations: list[str], anchors: list[str]) -> list[str]:
    wanted = set(anchors)
    hit: list[str] = []
    seen: set[str] = set()
    for cite in citations:
        matched = citation_matches(cite, wanted)
        if matched and matched not in seen:
            seen.add(matched)
            hit.append(matched)
    return hit


def meets_threshold(cited: int, present: int) -> bool:
    return present > 0 and cited * THRESHOLD_DEN >= present * THRESHOLD_NUM


def coverage(scorecard: dict, dossier: dict) -> dict:
    anchors = extract_anchors(dossier)
    citations = extract_citations(scorecard)
    matched = matched_anchors(citations, anchors)
    present = len(anchors)
    cited = len(matched)
    ratio = (cited / present) if present else 0.0
    attested = bool(scorecard.get("judge_attested_full_read"))
    if present == 0:
        failing = FR_EMPTY_DOSSIER
        verdict = "FAIL"
    elif not citations:
        failing = FR_NO_CITATIONS
        verdict = "FAIL"
    elif not meets_threshold(cited, present):
        failing = FR_COVERAGE
        verdict = "FAIL"
    else:
        failing = None
        verdict = "PASS"
    return {
        "anchors": anchors,
        "citations": citations,
        "matched": matched,
        "cited_distinct": cited,
        "sections_present": present,
        "coverage": ratio,
        "coverage_fraction": f"{cited}/{present}" if present else "0/0",
        "threshold_num": THRESHOLD_NUM,
        "threshold_den": THRESHOLD_DEN,
        "meets_threshold": meets_threshold(cited, present),
        "judge_attested_full_read": attested,
        "attestation_ignored": True,
        "verdict": verdict,
        "failing_condition_id": failing,
    }


def admit(scorecard: dict, dossier: dict) -> dict:
    row = coverage(scorecard, dossier)
    return {
        "verdict": row["verdict"],
        "failing_condition_id": row["failing_condition_id"],
        "coverage": row,
    }


def admit_paths(scorecard_path: Path, dossier_path: Path) -> dict:
    scorecard = load_json(scorecard_path)
    dossier = load_json(dossier_path)
    if not isinstance(scorecard, dict) or not isinstance(dossier, dict):
        raise TypeError("scorecard and dossier must be JSON objects")
    result = admit(scorecard, dossier)
    result["scorecard_path"] = str(scorecard_path)
    result["dossier_path"] = str(dossier_path)
    result["anchors_from_file"] = extract_anchors_from_path(dossier_path)
    return result


def make_digest(dossier: dict) -> dict:
    """Compress structured sections into one prose blob; drop original keys."""
    if not isinstance(dossier, dict):
        raise TypeError("dossier must be a JSON object")
    digest: dict[str, Any] = {}
    lines: list[str] = []
    for key, value in dossier.items():
        if is_section_value(value):
            blob = json.dumps(value, sort_keys=True, ensure_ascii=True)
            lines.append(f"{len(blob)}B of structured content omitted from digest.")
        else:
            digest[key] = value
    digest["digest"] = {
        "kind": "prose-summary",
        "omitted_section_count": len(lines),
        "text": " ".join(lines) if lines else "empty",
    }
    digest["summary"] = "One-paragraph digest. Not a substitute for the full dossier."
    return digest


def score_from_source(source: dict, *, attested: bool = False, source_kind: str) -> dict:
    """Cite every derived section of the SOURCE the judge was given."""
    anchors = extract_anchors(source)
    return {
        "judge_id": f"J-{source_kind}",
        "source_kind": source_kind,
        "judge_attested_full_read": attested,
        "citations": list(anchors),
        "dimensions": [
            {
                "id": "fidelity",
                "score": 3,
                "citation": anchors[0] if anchors else "digest",
            }
        ],
    }


def rename_section(dossier: dict, old: str, new: str) -> dict:
    if old not in dossier:
        raise KeyError(old)
    if new in dossier:
        raise ValueError(f"target key already present: {new}")
    out = copy.deepcopy(dossier)
    out[new] = out.pop(old)
    return out


def hand_list_coverage(citations: list[str], hand_list: list[str]) -> dict:
    """Buggy oracle: coverage against a frozen name list, not the live file."""
    matched = matched_anchors(citations, hand_list)
    present = len(hand_list)
    cited = len(matched)
    return {
        "cited_distinct": cited,
        "sections_present": present,
        "coverage_fraction": f"{cited}/{present}" if present else "0/0",
        "meets_threshold": meets_threshold(cited, present),
        "verdict": "PASS" if meets_threshold(cited, present) else "FAIL",
        "failing_condition_id": None if meets_threshold(cited, present) else FR_COVERAGE,
        "oracle": "hand-listed-anchors",
    }


def both_states_for(dossier: dict) -> dict:
    digest_view = make_digest(dossier)
    digest_card = score_from_source(digest_view, attested=True, source_kind="digest")
    full_card = score_from_source(dossier, attested=False, source_kind="full-artifact")
    digest_row = admit(digest_card, dossier)
    full_row = admit(full_card, dossier)
    assertion_card = {
        "judge_id": "J-assert",
        "judge_attested_full_read": True,
        "citations": [],
        "source_kind": "attestation-only",
    }
    assertion_row = admit(assertion_card, dossier)
    ok = (
        digest_row["verdict"] == "FAIL"
        and full_row["verdict"] == "PASS"
        and assertion_row["verdict"] == "FAIL"
        and assertion_row["failing_condition_id"] == FR_NO_CITATIONS
    )
    return {
        "ok": ok,
        "digest_scorecard": digest_card,
        "full_scorecard": full_card,
        "assertion_scorecard": assertion_card,
        "digest": digest_row,
        "full": full_row,
        "assertion": assertion_row,
        "anchors": extract_anchors(dossier),
    }


def integrity_trial(dossier: dict, *, old: str | None = None) -> dict:
    anchors = extract_anchors(dossier)
    if len(anchors) < 2:
        raise ValueError("need at least two derived sections for a rename trial")
    old_name = old or anchors[0]
    new_name = f"{old_name}__renamed"
    mutated = rename_section(dossier, old_name, new_name)
    derived_after = extract_anchors(mutated)
    stale_card = {"citations": list(anchors), "source_kind": "stale-hand-list"}
    fresh_card = {"citations": list(derived_after), "source_kind": "file-derived"}
    stale = admit(stale_card, mutated)
    fresh = admit(fresh_card, mutated)
    hand = hand_list_coverage(stale_card["citations"], anchors)
    silent_pass = hand["verdict"] == "PASS" and stale["verdict"] == "FAIL"
    ok = (
        old_name not in derived_after
        and new_name in derived_after
        and stale["verdict"] == "FAIL"
        and fresh["verdict"] == "PASS"
        and silent_pass
    )
    return {
        "ok": ok,
        "old_name": old_name,
        "new_name": new_name,
        "anchors_before": anchors,
        "anchors_after": derived_after,
        "stale": stale,
        "fresh": fresh,
        "hand_list_on_stale_citations": hand,
        "hand_list_would_silently_pass": silent_pass,
        "renamed_section_present": new_name in derived_after,
        "old_name_absent": old_name not in derived_after,
    }


def integrity_trial_from_file(path: Path, tmp_mutated: Path) -> dict:
    """Rename a section in a file copy; re-derive anchors from the mutated bytes."""
    original = load_json(path)
    if not isinstance(original, dict):
        raise TypeError("dossier file must contain a JSON object")
    before = extract_anchors_from_path(path)
    trial = integrity_trial(original, old=before[0])
    mutated = rename_section(original, trial["old_name"], trial["new_name"])
    tmp_mutated.parent.mkdir(parents=True, exist_ok=True)
    tmp_mutated.write_text(dump(mutated), encoding="utf-8")
    after = extract_anchors_from_path(tmp_mutated)
    stale_card = {"citations": list(before)}
    fresh_card = {"citations": list(after)}
    stale = admit(stale_card, load_json(tmp_mutated))
    fresh = admit(fresh_card, load_json(tmp_mutated))
    hand = hand_list_coverage(before, before)
    ok = (
        trial["old_name"] not in after
        and trial["new_name"] in after
        and before != after
        and stale["verdict"] == "FAIL"
        and fresh["verdict"] == "PASS"
        and hand["verdict"] == "PASS"
    )
    trial.update(
        {
            "ok": ok,
            "anchors_after_from_file": after,
            "stale_from_file": stale,
            "fresh_from_file": fresh,
            "hand_list_frozen_from_original_file": hand,
            "mutated_path": str(tmp_mutated),
        }
    )
    return trial


def live_dossier_states(repo: Path | None = None) -> list[dict]:
    root = repo or REPO
    rows: list[dict] = []
    for rel in LIVE_DOSSIERS:
        path = root / rel
        row: dict[str, Any] = {"path": rel, "present": path.is_file() and path.stat().st_size > 0}
        if not row["present"]:
            row["both_states"] = None
            rows.append(row)
            continue
        dossier = load_json(path)
        if not isinstance(dossier, dict):
            row["both_states"] = None
            row["present"] = False
            rows.append(row)
            continue
        both = both_states_for(dossier)
        row["both_states"] = {
            "ok": both["ok"],
            "anchors": both["anchors"],
            "digest_verdict": both["digest"]["verdict"],
            "full_verdict": both["full"]["verdict"],
            "assertion_verdict": both["assertion"]["verdict"],
            "digest_failing_condition_id": both["digest"]["failing_condition_id"],
            "full_coverage_fraction": both["full"]["coverage"]["coverage_fraction"],
            "digest_coverage_fraction": both["digest"]["coverage"]["coverage_fraction"],
            "sections_present": both["full"]["coverage"]["sections_present"],
        }
        rows.append(row)
    return rows


def fixture_dossier() -> dict:
    return {
        "architecture_id": "FX-1",
        "title": "Synthetic dossier for ARC-0068 both-states",
        "answer": "Eight structured sections exist; the digest omits them.",
        "state": "SUCCESS",
        "file_set": [
            {"path": "control-plane/manifest.json", "role": "index"},
            {"path": "control-plane/capabilities.json", "role": "catalog"},
        ],
        "load_order": [
            {"order": 1, "path": "control-plane/manifest.json"},
            {"order": 2, "path": "control-plane/capabilities.json"},
        ],
        "precedence": {
            "rule": "later load_order replaces the whole object",
            "tie_break": "UTF-8 path order",
            "duplicate_in_one_file": "FAIL-CLOSED",
            "merge": "none",
        },
        "expressibility": {
            "catalogue_claim": "fixture only; not a catalogue proof",
            "first_non_expressible_construct": "runtime predicate over prior rounds",
            "stopped_at_first_inexpressible": True,
        },
        "samples": [
            {
                "kind": "skill",
                "id": "skill.fixture",
                "source_id": "S-FIX",
                "verdict": "EXPRESSIBLE",
                "transcription": {"id": "skill.fixture"},
            }
        ],
        "failure_modes": [
            {"id": "FM-digest", "mode": "scorecard from summary only"},
            {"id": "FM-rename", "mode": "hand-listed anchors miss a renamed section"},
        ],
        "migration": {
            "from": "digest-scoring",
            "to": "full-read-gate",
            "restore": "cite file-derived section anchors",
        },
        "evidence": [
            {
                "claim": "Fixture contains eight structured sections.",
                "verdict": "CONFIRMED",
                "anchor": "file_set",
            }
        ],
    }


def write_fixtures() -> dict:
    dossier = fixture_dossier()
    both = both_states_for(dossier)
    FIXTURE_DOSSIER.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_DOSSIER.write_text(dump(dossier), encoding="utf-8")
    FIXTURE_DIGEST.write_text(dump(both["digest_scorecard"]), encoding="utf-8")
    FIXTURE_FULL.write_text(dump(both["full_scorecard"]), encoding="utf-8")
    FIXTURE_ASSERT.write_text(dump(both["assertion_scorecard"]), encoding="utf-8")
    return {
        "dossier": str(FIXTURE_DOSSIER.relative_to(REPO)),
        "digest": str(FIXTURE_DIGEST.relative_to(REPO)),
        "full": str(FIXTURE_FULL.relative_to(REPO)),
        "assertion": str(FIXTURE_ASSERT.relative_to(REPO)),
        "anchors": extract_anchors(dossier),
    }
