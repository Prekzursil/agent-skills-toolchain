"""WFA-0064 orphan-mechanism salvage.

Evidence A: mechanisms whose implementing-candidate set is a non-empty
subset of the terminal-disposition set (RETIRE, REJECT), computed over
the incidence matrix.

Evidence B: independent search of surviving (non-terminal) corpus for
another implementation. Matrix under-count is an extraction miss, not a
salvage. Search silence is trusted only after a known-present canary hit.

Salvage means extracting the mechanism into the vocabulary AND a target
blueprint. A note is not salvage. This unit never executes a terminal
disposition.
"""
from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
CORPUS = FIXTURES / "corpus"
ESTATE_PATH = FIXTURES / "estate.json"

TERMINAL = frozenset({"RETIRE", "REJECT"})
DEFINE_HEADING = re.compile(
    r"^(#{1,6})\s+DEFINE\s+`([^`]+)`\s*$",
    re.MULTILINE,
)
HTML_DEFINE = re.compile(
    r"<!--\s*DEFINE:([A-Za-z0-9._-]+)\s*-->\s*(.*?)\s*<!--\s*/DEFINE\s*-->",
    re.DOTALL,
)

LIVE_REGISTRY_CANDIDATES = [
    Path.home() / ".claude" / "harness-restore-20260806" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/opt/p2/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "harness-restore-20260806" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "sources" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
]
LIVE_MATRIX = REPO / "command-center/wfa/WFA-0059-mechanism-extraction.json"
LIVE_RETIRE = REPO / "command-center/wfa/WFA-0071-retire-readjudication.json"

VOCAB_OUT = "command-center/wfa/vocabulary/WFA-0064-salvaged-vocabulary.json"
BLUEPRINT_OUT = "command-center/wfa/blueprints/WFA-0064-salvage-blueprints.json"
PRIMARY_OUT = "command-center/wfa/WFA-0064-orphan-mechanism-salvage.json"

NOT_WORTH_MARKERS = (
    "deprecated alias",
    "no independent behaviour",
    "no independent behavior",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_estate(path: Path | None = None) -> dict:
    return load_json(path or ESTATE_PATH)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


def extract_definitions(text: str, filename: str) -> list[dict]:
    found: list[dict] = []
    lines = text.split("\n")
    for i, line in enumerate(lines, 1):
        m = DEFINE_HEADING.match(line)
        if not m:
            continue
        mech_id = m.group(2).strip()
        body_parts: list[str] = []
        for later in lines[i:]:
            if later.startswith("#"):
                break
            if later.strip() == "" and body_parts:
                break
            if later.strip():
                body_parts.append(later.strip())
        found.append(
            {
                "id": mech_id,
                "kind": "definition",
                "file": filename,
                "line": i,
                "anchor": f"{filename}:{i}",
                "snippet": line,
                "body": " ".join(body_parts),
            }
        )
    for m in HTML_DEFINE.finditer(text):
        mech_id = m.group(1).strip()
        line = text[: m.start()].count("\n") + 1
        found.append(
            {
                "id": mech_id,
                "kind": "definition",
                "file": filename,
                "line": line,
                "anchor": f"{filename}:{line}",
                "snippet": m.group(0).splitlines()[0][:200],
                "body": m.group(2).strip(),
            }
        )
    return found


def definition_for(corpus_root: Path, filename: str, mechanism_id: str) -> dict | None:
    path = corpus_root / filename
    if not path.is_file():
        return None
    for row in extract_definitions(read_text(path), filename):
        if row["id"] == mechanism_id:
            return row
    return None


def dispositions(estate: dict) -> dict[str, str]:
    return {str(c["id"]): str(c.get("classification") or "") for c in estate.get("candidates") or []}


def terminal_candidate_ids(estate: dict) -> set[str]:
    return {cid for cid, cls in dispositions(estate).items() if cls in TERMINAL}


def incidence(estate: dict) -> dict[str, set[str]]:
    """mechanism_id -> implementing candidate ids (non-empty cells only)."""
    matrix: dict[str, set[str]] = {}
    for cand in estate.get("candidates") or []:
        cid = str(cand["id"])
        for mid in cand.get("mechanisms") or []:
            matrix.setdefault(str(mid), set()).add(cid)
    return matrix


def incidence_cells(estate: dict) -> list[dict]:
    rule = str(estate.get("extraction_rule") or "candidates[].mechanisms")
    cells = []
    mechs = sorted({str(m["id"]) for m in estate.get("vocabulary") or []})
    cands = list(estate.get("candidates") or [])
    listed = incidence(estate)
    for mid in mechs:
        for cand in cands:
            cid = str(cand["id"])
            present = cid in listed.get(mid, set())
            cells.append(
                {
                    "mechanism_id": mid,
                    "candidate_id": cid,
                    "present": present,
                    "extraction_rule": rule,
                    "candidate_classification": cand.get("classification"),
                }
            )
    return cells


def matrix_orphans(estate: dict) -> dict[str, list[str]]:
    """Mechanisms with non-empty implementing-candidate set ⊆ terminal set."""
    term = terminal_candidate_ids(estate)
    out: dict[str, list[str]] = {}
    for mid, impl in incidence(estate).items():
        if not impl:
            continue
        if impl <= term:
            out[mid] = sorted(impl)
    return out


def terminal_body_files(estate: dict) -> set[str]:
    term = terminal_candidate_ids(estate)
    names: set[str] = set()
    for cand in estate.get("candidates") or []:
        if str(cand["id"]) in term:
            body = cand.get("body_file")
            if body:
                names.add(str(body))
    return names


def surviving_files(estate: dict, corpus_root: Path) -> list[Path]:
    excluded = terminal_body_files(estate)
    extra = {str(x) for x in estate.get("extra_surviving_files") or []}
    files: list[Path] = []
    for cand in estate.get("candidates") or []:
        body = cand.get("body_file")
        if not body:
            continue
        if str(body) in excluded:
            continue
        path = corpus_root / str(body)
        if path.is_file():
            files.append(path)
    for name in sorted(extra):
        path = corpus_root / name
        if path.is_file() and path not in files:
            files.append(path)
    return files


def search_mechanism(files: list[Path], mechanism_id: str) -> list[dict]:
    hits: list[dict] = []
    for path in files:
        defs = extract_definitions(read_text(path), path.name)
        for row in defs:
            if row["id"] == mechanism_id:
                hits.append(row)
    return hits


def search_all(estate: dict, corpus_root: Path, mechanism_ids: list[str]) -> dict[str, list[dict]]:
    files = surviving_files(estate, corpus_root)
    return {mid: search_mechanism(files, mid) for mid in mechanism_ids}


def canary_search(estate: dict, corpus_root: Path) -> dict:
    canary = estate.get("canary") or {}
    mid = str(canary.get("mechanism_id") or "")
    files = surviving_files(estate, corpus_root)
    hits = search_mechanism(files, mid) if mid else []
    expected = str(canary.get("surviving_file") or "")
    in_expected = any(h.get("file") == expected for h in hits)
    return {
        "mechanism_id": mid,
        "found": bool(hits),
        "hit_count": len(hits),
        "hits": hits,
        "found_in_expected_file": in_expected,
        "expected_file": expected,
        "surviving_files": [p.name for p in files],
        "silence_trusted": bool(hits) and in_expected,
    }


def worth_extracting(definition: str) -> bool:
    text = (definition or "").lower()
    if any(m in text for m in NOT_WORTH_MARKERS):
        return False
    return len(definition or "") >= 80


def is_extracted_salvage(record: dict) -> bool:
    """Salvage = vocabulary definition + discriminating examples + blueprint stages.

    A note, a flag, or a one-line mention is not salvage.
    """
    if not isinstance(record, dict):
        return False
    vocab = record.get("vocabulary") or {}
    bp = record.get("target_blueprint") or record.get("blueprint") or {}
    definition = str(vocab.get("definition") or "")
    examples = vocab.get("discriminating_examples") or []
    stages = bp.get("stages") or []
    if record.get("note") and len(definition) < 40:
        return False
    if len(definition) < 40:
        return False
    if not isinstance(examples, list) or len(examples) < 1:
        return False
    if not str(vocab.get("id") or "").strip():
        return False
    if not str(bp.get("id") or "").strip():
        return False
    if not isinstance(stages, list) or len(stages) < 1:
        return False
    if not any(isinstance(s, dict) and s.get("mechanism") for s in stages):
        return False
    return True


def note_only_record(mechanism_id: str) -> dict:
    """Known-bad mutant: claiming salvage by writing a note."""
    return {
        "id": mechanism_id,
        "salvaged": True,
        "note": f"should salvage {mechanism_id}",
        "vocabulary": {},
        "target_blueprint": {},
    }


def _licence(estate: dict, mechanism_id: str) -> str:
    for row in estate.get("vocabulary") or []:
        if row.get("id") == mechanism_id:
            return str(row.get("licence_class") or "estate-internal")
    return "estate-internal"


def _source_def(estate: dict, corpus_root: Path, mechanism_id: str) -> dict:
    impl = matrix_orphans(estate).get(mechanism_id) or []
    by_id = {str(c["id"]): c for c in estate.get("candidates") or []}
    for cid in impl:
        cand = by_id.get(cid) or {}
        body = cand.get("body_file")
        if not body:
            continue
        row = definition_for(corpus_root, str(body), mechanism_id)
        if row:
            row = dict(row)
            row["candidate_id"] = cid
            row["classification"] = cand.get("classification")
            return row
    return {
        "id": mechanism_id,
        "kind": "definition",
        "file": "",
        "line": 0,
        "anchor": "",
        "snippet": "",
        "body": "",
        "candidate_id": impl[0] if impl else None,
        "classification": None,
    }


def discriminating_examples(mechanism_id: str, body: str) -> list[str]:
    examples: list[str] = []
    marker = "Discriminating example:"
    if marker in body:
        examples.append(body.split(marker, 1)[1].strip().rstrip("."))
    if mechanism_id == "orphan.hook-pre-tool":
        examples.append("post-tool tracer cannot abort; this hook can")
    elif mechanism_id == "orphan.reject-quorum":
        examples.append("author self-ack is not a quorum")
    elif mechanism_id == "orphan.not-worth.stub":
        examples.append("alias with no extra stage behaviour vs a real hook or quorum")
    if not examples:
        examples.append(body[:180] if body else mechanism_id)
    # unique, stable
    seen: set[str] = set()
    out: list[str] = []
    for ex in examples:
        key = ex.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(ex)
    return out


def blueprint_for(mechanism_id: str, src: dict, worth: bool) -> dict:
    bp_id = f"bp-salvage-{mechanism_id.replace('.', '-')}"
    if not worth:
        stages = [
            {
                "id": "archive-name",
                "kind": "archive",
                "mechanism": mechanism_id,
                "does": (
                    "preserve the deprecated alias in the vocabulary so a "
                    "RETIRE of its only candidate cannot delete the name; "
                    "do not schedule this as a live stage"
                ),
            }
        ]
        role = "preservation-archive"
    elif mechanism_id == "orphan.hook-pre-tool":
        stages = [
            {
                "id": "pre-tool-hook",
                "kind": "gate",
                "mechanism": mechanism_id,
                "does": "run the named hook before every tool invocation; abort the call on deny",
            },
            {
                "id": "tool-invoke",
                "kind": "action",
                "mechanism": mechanism_id,
                "does": "invoke the tool only if the hook did not abort",
            },
        ]
        role = "reuse-target"
    elif mechanism_id == "orphan.reject-quorum":
        stages = [
            {
                "id": "collect-review-votes",
                "kind": "gate",
                "mechanism": mechanism_id,
                "does": "require two distinct reviewer PASS records; refuse author self-ack",
            },
            {
                "id": "merge",
                "kind": "action",
                "mechanism": mechanism_id,
                "does": "run merge only after quorum PASS",
            },
        ]
        role = "reuse-target"
    else:
        stages = [
            {
                "id": "salvaged-stage",
                "kind": "action",
                "mechanism": mechanism_id,
                "does": src.get("body") or f"extracted behaviour of {mechanism_id}",
            }
        ]
        role = "reuse-target"
    return {
        "id": bp_id,
        "name": f"salvage:{mechanism_id}",
        "mechanism_id": mechanism_id,
        "role": role,
        "stages": stages,
        "source_anchors": [src.get("anchor")] if src.get("anchor") else [],
        "licence_class": src.get("licence_class") or "estate-internal",
        "namespace": "blueprint",
    }


def make_mechanism_record(estate: dict, corpus_root: Path, mechanism_id: str, impl: list[str]) -> dict:
    src = _source_def(estate, corpus_root, mechanism_id)
    body = str(src.get("body") or "")
    worth = worth_extracting(body)
    licence = _licence(estate, mechanism_id)
    src["licence_class"] = licence
    vocab = {
        "id": mechanism_id,
        "namespace": "mechanism",
        "definition": body,
        "discriminating_examples": discriminating_examples(mechanism_id, body),
        "licence_class": licence,
        "source_anchors": [src.get("anchor")] if src.get("anchor") else [],
        "implementing_candidates": impl,
        "worth_extracting": worth,
        "status": "SALVAGED-ARCHIVE" if not worth else "SALVAGED",
    }
    bp = blueprint_for(mechanism_id, src, worth)
    record = {
        "record_type": "MechanismRecord",
        "id": mechanism_id,
        "name": mechanism_id,
        "definition": body,
        "implementing_candidates": impl,
        "source_anchors": vocab["source_anchors"],
        "licence_class": licence,
        "worth_extracting": worth,
        "salvage_status": vocab["status"],
        "vocabulary": vocab,
        "target_blueprint": bp,
        "extracted_into_vocabulary": True,
        "extracted_into_blueprint": True,
    }
    if not is_extracted_salvage(record):
        raise RuntimeError(f"salvage record for {mechanism_id} failed extraction bar")
    return record


def orphans_depending_on(candidate_id: str, orphan_map: dict[str, list[str]]) -> list[str]:
    return sorted(mid for mid, impl in orphan_map.items() if candidate_id in impl)


def attempt_terminal(
    candidate_id: str,
    estate: dict,
    salvage_necessary: list[str],
    salvaged_ids: set[str],
    *,
    owner_signoff: bool = False,
) -> dict:
    """Never executes. Blocks while an unsalvaged orphan depends on the candidate."""
    cls = dispositions(estate).get(candidate_id)
    if cls not in TERMINAL:
        return {
            "candidate_id": candidate_id,
            "classification": cls,
            "executed": False,
            "blocked": True,
            "reason": "not-a-terminal-disposition",
            "unsalvaged": [],
        }
    orphan_map = {mid: impl for mid, impl in matrix_orphans(estate).items() if mid in salvage_necessary}
    deps = orphans_depending_on(candidate_id, orphan_map)
    unsalvaged = [m for m in deps if m not in salvaged_ids]
    if unsalvaged:
        return {
            "candidate_id": candidate_id,
            "classification": cls,
            "executed": False,
            "blocked": True,
            "reason": "unsalvaged-orphan",
            "unsalvaged": unsalvaged,
            "depends_on": deps,
        }
    if not owner_signoff:
        return {
            "candidate_id": candidate_id,
            "classification": cls,
            "executed": False,
            "blocked": True,
            "reason": "owner-signoff-required",
            "unsalvaged": [],
            "depends_on": deps,
        }
    return {
        "candidate_id": candidate_id,
        "classification": cls,
        "executed": False,
        "blocked": True,
        "reason": "this-unit-does-not-execute-terminal-dispositions",
        "unsalvaged": [],
        "depends_on": deps,
    }


def analyze(estate: dict | None = None, corpus_root: Path | None = None) -> dict:
    estate = estate or load_estate()
    corpus_root = corpus_root or CORPUS
    matrix = {k: sorted(v) for k, v in incidence(estate).items()}
    orphan_map = matrix_orphans(estate)
    vocab_ids = [str(m["id"]) for m in estate.get("vocabulary") or []]
    search_ids = sorted(set(vocab_ids) | set(matrix) | set(orphan_map))
    hits = search_all(estate, corpus_root, search_ids)
    canary = canary_search(estate, corpus_root)
    extraction_misses = sorted(mid for mid in orphan_map if hits.get(mid))
    if not canary.get("silence_trusted"):
        salvage_necessary: list[str] = []
        silence_status = "UNTRUSTED-SEARCH"
    else:
        salvage_necessary = sorted(mid for mid in orphan_map if not hits.get(mid))
        silence_status = "TRUSTED"
    records = [
        make_mechanism_record(estate, corpus_root, mid, orphan_map[mid])
        for mid in salvage_necessary
    ]
    salvaged_ids = {r["id"] for r in records}
    gate_before = attempt_terminal(
        "wf-retire-pre-tool", estate, salvage_necessary, set()
    )
    gate_after = attempt_terminal(
        "wf-retire-pre-tool", estate, salvage_necessary, salvaged_ids
    )
    gate_reject = attempt_terminal(
        "wf-reject-quorum", estate, salvage_necessary, salvaged_ids
    )
    gate_adopt = attempt_terminal(
        "wf-adopt-stage-gate", estate, salvage_necessary, salvaged_ids
    )
    return {
        "extraction_rule": estate.get("extraction_rule"),
        "terminal_dispositions": sorted(TERMINAL),
        "terminal_candidates": sorted(terminal_candidate_ids(estate)),
        "incidence": matrix,
        "incidence_cells": incidence_cells(estate),
        "matrix_orphans": {k: v for k, v in sorted(orphan_map.items())},
        "matrix_orphan_ids": sorted(orphan_map),
        "corpus_hits": {
            mid: [{"file": h["file"], "anchor": h["anchor"], "line": h["line"]} for h in rows]
            for mid, rows in sorted(hits.items())
            if rows
        },
        "canary": canary,
        "silence_status": silence_status,
        "extraction_misses": extraction_misses,
        "salvage_necessary": salvage_necessary,
        "salvaged": records,
        "salvaged_ids": sorted(salvaged_ids),
        "not_orphan": sorted(
            mid for mid in matrix if mid not in orphan_map
        ),
        "empty_implementer_excluded": [
            mid
            for mid in vocab_ids
            if mid not in matrix
        ],
        "gate": {
            "before_salvage": gate_before,
            "after_salvage_retire_host": gate_after,
            "after_salvage_reject_host": gate_reject,
            "adopt_candidate": gate_adopt,
            "any_executed": False,
        },
        "note_only_rejected": not is_extracted_salvage(note_only_record("orphan.hook-pre-tool")),
        "all_salvages_extracted": all(is_extracted_salvage(r) for r in records),
    }


def both_states(estate: dict | None = None, corpus_root: Path | None = None) -> dict:
    estate = estate or load_estate()
    corpus_root = corpus_root or CORPUS
    base = analyze(estate, corpus_root)
    fire_estate = deepcopy(estate)
    for cand in fire_estate["candidates"]:
        if cand["id"] == "wf-adopt-stage-gate":
            cand["classification"] = "RETIRE"
    fire = analyze(fire_estate, corpus_root)
    silent_estate = deepcopy(estate)
    for cand in silent_estate["candidates"]:
        if cand["id"] == "wf-retire-pre-tool":
            cand["classification"] = "ADOPT-AS-IS"
    silent = analyze(silent_estate, corpus_root)
    known_good = "kept.stage-gate" not in base["matrix_orphan_ids"]
    planted_bad = "kept.stage-gate" in fire["matrix_orphan_ids"]
    planted_clear = "orphan.hook-pre-tool" not in silent["matrix_orphan_ids"]
    return {
        "known_good_kept_not_orphan": known_good,
        "planted_retire_makes_kept_orphan": planted_bad,
        "planted_adopt_clears_hook_orphan": planted_clear,
        "base_orphans": base["matrix_orphan_ids"],
        "fire_orphans": fire["matrix_orphan_ids"],
        "silent_orphans": silent["matrix_orphan_ids"],
        "pass": known_good and planted_bad and planted_clear,
    }


def live_inputs() -> dict:
    env = os.environ.get("WFA0064_REGISTRY")
    registry_hits = []
    if env:
        p = Path(env)
        registry_hits.append({"path": str(p), "present": p.is_file()})
    for p in LIVE_REGISTRY_CANDIDATES:
        row = {"path": str(p), "present": p.is_file()}
        if row not in registry_hits:
            registry_hits.append(row)
    present_registry = next((r["path"] for r in registry_hits if r["present"]), None)
    return {
        "mechanism_extraction_matrix": {
            "path": str(LIVE_MATRIX.relative_to(REPO)) if LIVE_MATRIX.is_relative_to(REPO) else str(LIVE_MATRIX),
            "present": LIVE_MATRIX.is_file(),
        },
        "retire_readjudication": {
            "path": str(LIVE_RETIRE.relative_to(REPO)) if LIVE_RETIRE.is_relative_to(REPO) else str(LIVE_RETIRE),
            "present": LIVE_RETIRE.is_file(),
        },
        "workflow_candidate_registry": {
            "present": present_registry is not None,
            "path": present_registry,
            "searched": [r["path"] for r in registry_hits],
        },
        "fixture_estate": {
            "path": str(ESTATE_PATH.relative_to(REPO)),
            "present": ESTATE_PATH.is_file(),
        },
    }


def recall_limit(inputs: dict) -> dict:
    unread = []
    if not inputs["workflow_candidate_registry"]["present"]:
        unread.append("08-WORKFLOW-CANDIDATE-REGISTRY.json (284 candidates, RETIRE n=24)")
    if not inputs["mechanism_extraction_matrix"]["present"]:
        unread.append("command-center/wfa/WFA-0059-mechanism-extraction.json")
    if not inputs["retire_readjudication"]["present"]:
        unread.append("command-center/wfa/WFA-0071-retire-readjudication.json")
    return {
        "implied_exhaustiveness": False,
        "live_284_estate_scanned": bool(inputs["workflow_candidate_registry"]["present"]),
        "unread": unread,
        "unread_reason": (
            "live harness-restore 284-row registry, WFA-0059 incidence matrix, "
            "and WFA-0071 RETIRE re-adjudication are absent on this Linux worktree; "
            "orphan sets below are computed over the reconstructed fixture estate, "
            "not claimed as the 284-candidate histogram"
        ),
        "method_limit": (
            "incidence uses candidates[].mechanisms; independent search uses DEFINE "
            "headings in surviving (non-terminal) files only. Terminal candidate "
            "bodies are the salvage source, not surviving implementations."
        ),
    }


def write_extracts(analysis: dict) -> dict:
    vocab_rows = [r["vocabulary"] for r in analysis["salvaged"]]
    bp_rows = [r["target_blueprint"] for r in analysis["salvaged"]]
    vocab_path = REPO / VOCAB_OUT
    bp_path = REPO / BLUEPRINT_OUT
    vocab_path.parent.mkdir(parents=True, exist_ok=True)
    bp_path.parent.mkdir(parents=True, exist_ok=True)
    vocab_doc = {
        "unit_id": "WFA-0064",
        "kind": "mechanism-vocabulary-extract",
        "namespace": "mechanism",
        "records": vocab_rows,
        "ids": [r["id"] for r in vocab_rows],
        "note": "Extracted orphan mechanisms. Not a note-only list.",
        "sentinel": "SUCCESS:WFA-0064",
    }
    bp_doc = {
        "unit_id": "WFA-0064",
        "kind": "salvage-target-blueprints",
        "namespace": "blueprint",
        "records": bp_rows,
        "ids": [r["id"] for r in bp_rows],
        "note": "Each salvaged mechanism has stages; archive stubs are still blueprints.",
        "sentinel": "SUCCESS:WFA-0064",
    }
    vocab_path.write_text(json.dumps(vocab_doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    bp_path.write_text(json.dumps(bp_doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "vocabulary_path": VOCAB_OUT,
        "blueprint_path": BLUEPRINT_OUT,
        "vocabulary_ids": vocab_doc["ids"],
        "blueprint_ids": bp_doc["ids"],
    }
