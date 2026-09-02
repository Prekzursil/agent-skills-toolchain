#!/usr/bin/env python3
"""Measure the cost of applying the wrong evidence standard.

Two mechanically independent signals, both from recorded on-disk artifacts
(not recollection, not a live-growing transcript directory):

  S1  Checker verdicts on delivered research/receipt citation fields:
      zero-citation grounded outputs and ideation units grounded only in
      this repository.

  S2  Duplicate repo-path multiplicity: the same worktree file cited by
      more than one recorded agent, counted with a Counter over paths
      (independent of check_finding).

Planted controls in fixtures/prior_corpus.json are detector-calibration
only. Cost figures are scored from fixtures/prior_fanout_records.json, a
frozen citation extract of recorded research JSON and receipts. A live
rglob of those trees races concurrent G-1 delivery and is not remesure.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from checker import FILE_LINE_RE, URL_RE, DOI_RE, FIXTURE_URL_RE, check_finding
from lenses import GROUNDED, IDEATION, LENS_BY_ID, REPO, ROLE_TO_LENS

CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
RESEARCH = REPO / "command-center" / "research"
RECEIPTS = REPO / "command-center" / "receipts"
HERE = Path(__file__).resolve().parent
PLANTED = HERE / "fixtures" / "prior_corpus.json"
FROZEN = HERE / "fixtures" / "prior_fanout_records.json"
SELF_ARTIFACT = (
    "command-center/research/gem-hunt/"
    "RES-0156-grounded-vs-ideation-evidence-split.json"
)

UNIT_ID_RE = re.compile(r"\b([A-Z]{2,5}-\d{4})\b")
ANCHOR_RE = re.compile(
    r"(?:command-center|rules|tools|docs|hooks)/[^\s\"']+\.\w+:\d+"
)


def load_catalog_roles() -> dict[str, str]:
    if not CATALOG.is_file():
        return {}
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for unit in data.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        role = str((unit.get("assigned_model_vendor_role") or {}).get("role") or "")
        if uid and role:
            out[uid] = role
    return out


INTERESTING_KEYS = frozenset(
    {"anchor", "url", "permalink", "doi", "doi_or_arxiv", "file_line"}
)


def classify_anchor_string(text: str) -> str:
    t = text.strip().replace("\\", "/")
    if URL_RE.match(t) or DOI_RE.match(t) or FIXTURE_URL_RE.match(t):
        return "external"
    if FILE_LINE_RE.match(t) or ANCHOR_RE.fullmatch(t):
        return "repo"
    if t.startswith("http://") or t.startswith("https://"):
        return "external"
    return "other"


def extract_anchors(doc: dict) -> list[str]:
    found: list[str] = []

    def walk(obj: Any, key: str | None = None) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, str(k))
        elif isinstance(obj, list):
            for v in obj:
                walk(v, key)
        elif isinstance(obj, str) and key in INTERESTING_KEYS:
            s = obj.strip()
            if s:
                found.append(s)

    walk(doc)
    seen: set[str] = set()
    out: list[str] = []
    for a in found:
        if a not in seen:
            seen.add(a)
            out.append(a)
    return out


def unit_id_from_path(path: Path) -> str | None:
    m = UNIT_ID_RE.search(path.name)
    if m:
        return m.group(1)
    return None


def score_unit_anchors(anchors: list[str], lens_id: str) -> dict[str, Any]:
    citations = [{"value": a} for a in anchors]
    finding = {"lens_id": lens_id, "citations": citations, "object_scope": None}
    # CONTESTED lenses in the live corpus: bind by whether anchors are repo or external
    # is FORBIDDEN (preference). Score them as UNBOUND if mixed/empty; do not
    # pick a standard. For mapped non-contested lenses, apply the table.
    lens = LENS_BY_ID[lens_id]
    if lens["standard"] == "CONTESTED":
        kinds = [classify_anchor_string(a) for a in anchors]
        return {
            "status": "CONTESTED-UNBOUND",
            "compliant": False,
            "n_repo": kinds.count("repo"),
            "n_external": kinds.count("external"),
            "n_anchors": len(anchors),
            "zero_citation": len(anchors) == 0,
        }
    result = check_finding(finding)
    kinds = [classify_anchor_string(a) for a in anchors]
    return {
        "status": result.get("status"),
        "compliant": bool(result.get("compliant")),
        "n_repo": kinds.count("repo"),
        "n_external": kinds.count("external"),
        "n_anchors": len(anchors),
        "zero_citation": result.get("status") == "ZERO_CITATION" or len(anchors) == 0,
        "forbidden_grounding": result.get("status") == "FORBIDDEN_GROUNDING",
    }


def iter_json_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.json") if p.is_file())


def collect_source_records() -> list[dict[str, Any]]:
    """Walk research/ + receipts/ once. Used only to freeze the extract."""
    roles = load_catalog_roles()
    records: list[dict[str, Any]] = []
    for folder, kind in ((RESEARCH, "research-artifact"), (RECEIPTS, "receipt")):
        for path in iter_json_files(folder):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            uid = str(doc.get("unit_id") or doc.get("id") or "") or unit_id_from_path(
                path
            )
            if not uid:
                continue
            rel = path.relative_to(REPO).as_posix()
            if rel == SELF_ARTIFACT or rel.endswith(
                "RES-0156-grounded-vs-ideation-evidence-split.json"
            ):
                continue
            role = roles.get(uid, "")
            lens_id = ROLE_TO_LENS.get(role)
            records.append(
                {
                    "unit_id": uid,
                    "path": rel,
                    "kind": kind,
                    "role": role,
                    "lens_id": lens_id,
                    "anchors": extract_anchors(doc),
                }
            )
    return records


def score_record(rec: dict[str, Any]) -> dict[str, Any]:
    anchors = list(rec.get("anchors") or [])
    kinds = [classify_anchor_string(a) for a in anchors]
    repo_paths = []
    for a in anchors:
        if classify_anchor_string(a) == "repo":
            m = FILE_LINE_RE.match(a.replace("\\", "/").strip())
            if m:
                repo_paths.append(m.group("path"))
    row: dict[str, Any] = {
        "unit_id": rec.get("unit_id"),
        "path": rec.get("path"),
        "kind": rec.get("kind"),
        "role": rec.get("role"),
        "lens_id": rec.get("lens_id"),
        "n_anchors": len(anchors),
        "anchor_kinds": kinds,
        "repo_paths": repo_paths,
    }
    lens_id = rec.get("lens_id")
    if lens_id:
        row.update(score_unit_anchors(anchors, str(lens_id)))
    else:
        row.update(
            {
                "status": "UNMAPPED-ROLE",
                "compliant": None,
                "n_repo": kinds.count("repo"),
                "n_external": kinds.count("external"),
                "zero_citation": len(anchors) == 0,
                "forbidden_grounding": False,
            }
        )
    return row


def scan_live_artifacts() -> list[dict[str, Any]]:
    return [score_record(r) for r in collect_source_records()]


def freeze_prior_fanout() -> dict[str, Any]:
    records = collect_source_records()
    payload = {
        "note": (
            "Frozen citation extract of the recorded prior fan-out "
            "(research JSON + receipts), excluding this unit's own artifact. "
            "Live research/ and receipts/ trees grow during concurrent G-1 "
            "delivery; remesure scores this extract, not a live rglob."
        ),
        "self_excluded": SELF_ARTIFACT,
        "n_records": len(records),
        "records": records,
    }
    FROZEN.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return payload


def load_frozen_records() -> list[dict[str, Any]]:
    if not FROZEN.is_file():
        raise FileNotFoundError(f"missing frozen prior-fan-out extract: {FROZEN}")
    data = json.loads(FROZEN.read_text(encoding="utf-8"))
    recs = list(data.get("records") or [])
    if len(recs) < 1:
        raise ValueError("frozen prior-fan-out extract is empty")
    return recs


def load_planted() -> list[dict[str, Any]]:
    data = json.loads(PLANTED.read_text(encoding="utf-8"))
    return list(data.get("agents") or [])


def score_planted() -> list[dict[str, Any]]:
    out = []
    for agent in load_planted():
        finding = {
            "lens_id": agent["lens_id"],
            "citations": agent.get("citations") or [],
            "object_scope": agent.get("object_scope"),
        }
        result = check_finding(finding)
        out.append(
            {
                "id": agent["id"],
                "expected_status": agent["expected_status"],
                "observed_status": result.get("status"),
                "match": result.get("status") == agent["expected_status"],
                "lens_id": agent["lens_id"],
                "role": "planted-control",
            }
        )
    return out


def summarize(rows: list[dict[str, Any]], planted: list[dict[str, Any]]) -> dict[str, Any]:
    mapped = [r for r in rows if r.get("lens_id")]
    ideation = [r for r in mapped if LENS_BY_ID[r["lens_id"]]["standard"] == IDEATION]
    grounded = [r for r in mapped if LENS_BY_ID[r["lens_id"]]["standard"] == GROUNDED]
    zero = [r for r in mapped if r.get("zero_citation")]
    forbidden = [
        r
        for r in ideation
        if r.get("forbidden_grounding") or r.get("status") == "FORBIDDEN_GROUNDING"
    ]
    grounded_zero = [
        r
        for r in grounded
        if r.get("zero_citation") or r.get("status") == "ZERO_CITATION"
    ]
    ideation_repo_only = [
        r
        for r in ideation
        if (r.get("n_repo") or 0) > 0 and (r.get("n_external") or 0) == 0
    ]
    path_counter: Counter[str] = Counter()
    for r in rows:
        for p in r.get("repo_paths") or []:
            path_counter[p] += 1
    duplicate_repo_path_events = sum(n - 1 for n in path_counter.values() if n > 1)
    return {
        "n_live_records": len(rows),
        "n_mapped": len(mapped),
        "n_ideation_mapped": len(ideation),
        "n_grounded_mapped": len(grounded),
        "zero_citation_mapped": len(zero),
        "ideation_forbidden_grounding": len(forbidden),
        "ideation_repo_only": len(ideation_repo_only),
        "grounded_zero_citation": len(grounded_zero),
        "cost": {
            "duplicate_reads_ideation_repo_only": len(ideation_repo_only),
            "zero_citation_grounded_outputs": len(grounded_zero),
            "duplicate_repo_path_events": duplicate_repo_path_events,
        },
        "planted_controls_pass": all(p.get("match") for p in planted) and len(planted) >= 4,
        "planted_n": len(planted),
        "signal_s1": "checker-verdicts-on-recorded-citation-fields",
        "signal_s2": "duplicate-repo-path-citation-multiplicity",
        "ideation_repo_only_ids": [r["unit_id"] for r in ideation_repo_only][:12],
        "grounded_zero_ids": [r["unit_id"] for r in grounded_zero][:12],
    }


def measure() -> dict[str, Any]:
    frozen = load_frozen_records()
    rows = [score_record(r) for r in frozen]
    planted = score_planted()
    summary = summarize(rows, planted)
    summary["corpus_source"] = "frozen-prior-fanout-extract"
    summary["frozen_n"] = len(frozen)
    return {
        "summary": summary,
        "planted": planted,
        "live_sample": [
            {k: r[k] for k in r if k != "repo_paths"} for r in rows[:20]
        ],
        "n_live": len(rows),
    }


if __name__ == "__main__":
    if "--freeze" in sys.argv:
        payload = freeze_prior_fanout()
        print(f"froze {payload['n_records']} records -> {FROZEN.relative_to(REPO).as_posix()}")
        raise SystemExit(0)
    out = measure()
    print(json.dumps(out["summary"], indent=2, ensure_ascii=True))
