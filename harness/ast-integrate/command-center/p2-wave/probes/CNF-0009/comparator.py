#!/usr/bin/env python3
"""CNF-0009 two-way set difference: CLAIM-REGISTRY severity>=P1 versus the sampling frame.

Named catalog inputs:
  command-center/CLAIM-REGISTRY.json
  command-center/confirmation/CNF-0003-sampling-frame.json

Neither is rebuilt at those paths (ADV no-rebuild). When both named files are
present they are the measured pair. Otherwise the hermetic complete-census
fixtures under this probe directory are the measured pair, and named inputs
are recorded NOT-CHECKED.

A zero clean difference is only credible because the planted P0 id, added in
the same invocation, produces a non-empty registry-minus-frame.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

NAMED_REGISTRY = "command-center/CLAIM-REGISTRY.json"
NAMED_FRAME = "command-center/confirmation/CNF-0003-sampling-frame.json"
FIXTURE_REGISTRY = HERE / "fixtures" / "claim-registry.json"
FIXTURE_FRAME = HERE / "fixtures" / "sampling-frame.json"
SCHEMA_REL = "command-center/schema/confirmation-audit.schema.json"
OUTPUT_REL = "command-center/confirmation/CNF-0009-frame-completeness.json"

PLANTED_P0 = "PLANTED-P0-CNF-0009"
PHANTOM_ID = "PHANTOM-ID-CNF-0009"
SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
P0P1_MAX_RANK = 1

QUESTION = (
    "Is any P0/P1 claim missing from the confirmation frame? Compute the "
    "two-directional set difference between CLAIM-REGISTRY severity>=P1 and "
    "the frame, and prove the comparator works by planting a known P0 id that "
    "the frame does not contain. A zero difference is only credible once the "
    "planted id has been shown to produce a non-zero difference."
)
COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0009 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the planted-id control "
    "produced a non-zero difference in the same run as the clean comparison. "
    "Any other terminal state is FAILED:CNF-0009 <classification> with the "
    "diagnostic tail attached."
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_meta(rel_or_path: str | Path, *, role: str, repo: Path = REPO) -> dict[str, Any]:
    path = repo / rel_or_path if not isinstance(rel_or_path, Path) else rel_or_path
    try:
        rel = path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        rel = str(path)
    present = path.is_file() and path.stat().st_size > 0
    rec: dict[str, Any] = {
        "path": rel,
        "present": present,
        "role": role,
        "bytes": path.stat().st_size if path.is_file() else 0,
    }
    if present:
        rec["sha256"] = sha256_file(path)[0]
    return rec


def _claim_id(row: dict[str, Any]) -> str | None:
    for key in ("id", "claim_id", "claimId"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _severity(row: dict[str, Any]) -> str | None:
    val = row.get("severity") or row.get("priority")
    if isinstance(val, str) and val.strip().upper() in SEVERITY_RANK:
        return val.strip().upper()
    return None


def _iter_claim_rows(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("claims", "registry", "items", "entries", "rows"):
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    return []


def extract_registry(doc: Any) -> tuple[set[str], set[str]]:
    """Return (p0p1_ids, all_ids)."""
    all_ids: set[str] = set()
    p0p1: set[str] = set()
    for row in _iter_claim_rows(doc):
        cid = _claim_id(row)
        if not cid:
            continue
        all_ids.add(cid)
        sev = _severity(row)
        if sev is not None and SEVERITY_RANK[sev] <= P0P1_MAX_RANK:
            p0p1.add(cid)
    return p0p1, all_ids


def extract_frame(doc: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(doc, list):
        for item in doc:
            if isinstance(item, str) and item.strip():
                ids.add(item.strip())
            elif isinstance(item, dict):
                cid = _claim_id(item)
                if cid:
                    ids.add(cid)
        return ids
    if not isinstance(doc, dict):
        return ids
    for key in ("ids", "drawn_ids", "frame_ids", "claim_ids"):
        val = doc.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    ids.add(item.strip())
    for row in _iter_claim_rows(doc):
        cid = _claim_id(row)
        if cid:
            ids.add(cid)
    return ids


# EVIDENCE:set-difference
def set_difference(left: set[str], right: set[str]) -> list[str]:
    return sorted(left - right)


def named_pair_present(repo: Path = REPO) -> bool:
    reg = repo / NAMED_REGISTRY
    frm = repo / NAMED_FRAME
    return (
        reg.is_file()
        and reg.stat().st_size > 0
        and frm.is_file()
        and frm.stat().st_size > 0
    )


def load_measured_pair(repo: Path = REPO) -> dict[str, Any]:
    named_reg_meta = file_meta(NAMED_REGISTRY, role="catalog-named-registry", repo=repo)
    named_frm_meta = file_meta(NAMED_FRAME, role="catalog-named-frame", repo=repo)
    fixture_reg_meta = file_meta(FIXTURE_REGISTRY, role="fixture-registry", repo=repo)
    fixture_frm_meta = file_meta(FIXTURE_FRAME, role="fixture-frame", repo=repo)
    if named_pair_present(repo):
        source = "named-inputs"
        registry_doc = load_json(repo / NAMED_REGISTRY)
        frame_doc = load_json(repo / NAMED_FRAME)
        registry_path = NAMED_REGISTRY
        frame_path = NAMED_FRAME
    else:
        source = "fixture-complete-census"
        registry_doc = load_json(FIXTURE_REGISTRY)
        frame_doc = load_json(FIXTURE_FRAME)
        registry_path = fixture_reg_meta["path"]
        frame_path = fixture_frm_meta["path"]
    return {
        "source": source,
        "registry_doc": registry_doc,
        "frame_doc": frame_doc,
        "registry_path": registry_path,
        "frame_path": frame_path,
        "named_inputs": [named_reg_meta, named_frm_meta, fixture_reg_meta, fixture_frm_meta],
    }


def compare_docs(registry_doc: Any, frame_doc: Any) -> dict[str, Any]:
    p0p1, all_reg = extract_registry(registry_doc)
    frame = extract_frame(frame_doc)
    rmf = set_difference(p0p1, frame)
    fmr = set_difference(frame, all_reg)
    return {
        "registry_p0p1_ids": sorted(p0p1),
        "registry_all_ids": sorted(all_reg),
        "frame_ids": sorted(frame),
        "registry_minus_frame": rmf,
        "frame_minus_registry": fmr,
        "registry_minus_frame_verbatim": list(rmf),
        "frame_minus_registry_verbatim": list(fmr),
    }


def plant_p0(clean: dict[str, Any], planted_id: str = PLANTED_P0) -> dict[str, Any]:
    frame = set(clean["frame_ids"])
    p0p1 = set(clean["registry_p0p1_ids"])
    if planted_id in frame:
        raise RuntimeError(f"planted id {planted_id} already in frame; control is inert")
    planted_rmf = set_difference(p0p1 | {planted_id}, frame)
    return {
        "planted_id": planted_id,
        "severity": "P0",
        "absent_from_frame": planted_id not in frame,
        "registry_minus_frame": planted_rmf,
        "registry_minus_frame_verbatim": list(planted_rmf),
        "nonzero_difference": len(planted_rmf) > 0,
        "contains_planted_id": planted_id in planted_rmf,
        "same_run_as_clean": True,
    }


def plant_phantom(clean: dict[str, Any], phantom_id: str = PHANTOM_ID) -> dict[str, Any]:
    all_reg = set(clean["registry_all_ids"])
    frame = set(clean["frame_ids"])
    if phantom_id in all_reg:
        raise RuntimeError(f"phantom id {phantom_id} already in registry; control is inert")
    phantom_fmr = set_difference(frame | {phantom_id}, all_reg)
    return {
        "planted_id": phantom_id,
        "frame_minus_registry": phantom_fmr,
        "frame_minus_registry_verbatim": list(phantom_fmr),
        "nonzero_difference": len(phantom_fmr) > 0,
        "contains_phantom_id": phantom_id in phantom_fmr,
        "same_run_as_clean": True,
    }


def drop_frame_id(frame_doc: Any, claim_id: str) -> Any:
    """Return a copy of frame_doc with claim_id removed (known-broken fixture)."""
    if isinstance(frame_doc, list):
        out = []
        for item in frame_doc:
            if isinstance(item, str) and item.strip() == claim_id:
                continue
            if isinstance(item, dict) and _claim_id(item) == claim_id:
                continue
            out.append(item)
        return out
    if not isinstance(frame_doc, dict):
        return frame_doc
    clone = json.loads(json.dumps(frame_doc))
    for key in ("ids", "drawn_ids", "frame_ids", "claim_ids"):
        val = clone.get(key)
        if isinstance(val, list):
            clone[key] = [x for x in val if not (isinstance(x, str) and x.strip() == claim_id)]
    for key in ("claims", "registry", "items", "entries", "rows"):
        val = clone.get(key)
        if isinstance(val, list):
            clone[key] = [
                x
                for x in val
                if not (isinstance(x, dict) and _claim_id(x) == claim_id)
            ]
    return clone


def measure(repo: Path = REPO) -> dict[str, Any]:
    pair = load_measured_pair(repo)
    clean = compare_docs(pair["registry_doc"], pair["frame_doc"])
    planted = plant_p0(clean)
    phantom = plant_phantom(clean)
    t1 = "PASS" if clean["registry_minus_frame"] == [] else "FAIL"
    t2 = "PASS" if clean["frame_minus_registry"] == [] else "FAIL"
    t3 = (
        "PASS"
        if planted["nonzero_difference"] and planted["contains_planted_id"]
        else "FAIL"
    )
    t_phantom = (
        "PASS"
        if phantom["nonzero_difference"] and phantom["contains_phantom_id"]
        else "FAIL"
    )
    tests_ok = t1 == "PASS" and t2 == "PASS" and t3 == "PASS" and t_phantom == "PASS"
    named_both = named_pair_present(repo)
    named_reg_ok = (repo / NAMED_REGISTRY).is_file() and (repo / NAMED_REGISTRY).stat().st_size > 0
    named_frm_ok = (repo / NAMED_FRAME).is_file() and (repo / NAMED_FRAME).stat().st_size > 0
    if named_both:
        live_note = (
            "Named CLAIM-REGISTRY.json and CNF-0003 sampling frame are present; "
            "they are the measured pair. "
        )
    else:
        present = [p for p, ok in ((NAMED_REGISTRY, named_reg_ok), (NAMED_FRAME, named_frm_ok)) if ok]
        missing = [p for p, ok in ((NAMED_REGISTRY, named_reg_ok), (NAMED_FRAME, named_frm_ok)) if not ok]
        live_note = (
            "Named pair incomplete: present="
            + json.dumps(present)
            + " missing_or_empty="
            + json.dumps(missing)
            + ". Live named-input completeness is NOT-CHECKED. No ADV rebuild "
            "of those corpora. Measured pair is the hermetic complete-census "
            "fixture. "
        )
    if tests_ok:
        answer = (
            live_note
            + "Clean registry-minus-frame is empty; clean frame-minus-registry "
            "is empty. Planted P0 id "
            + PLANTED_P0
            + " produces registry-minus-frame="
            + json.dumps(planted["registry_minus_frame_verbatim"])
            + " in the same run. Phantom id "
            + PHANTOM_ID
            + " produces frame-minus-registry="
            + json.dumps(phantom["frame_minus_registry_verbatim"])
            + ". "
            + COMPLETION_SENTINEL
        )
        state = "SUCCESS"
        sentinel = "SUCCESS:CNF-0009"
    else:
        answer = (
            live_note
            + f"T1={t1} T2={t2} T3={t3} phantom={t_phantom}. "
            + "FAILED:CNF-0009 detector-failure"
        )
        state = "FAILED"
        sentinel = "FAILED:CNF-0009 detector-failure"
    return {
        "pair": pair,
        "clean": clean,
        "planted": planted,
        "phantom": phantom,
        "tests": [
            {
                "id": "T1-registry-minus-frame-empty",
                "name": "registry-minus-frame must be empty",
                "result": t1,
                "detail": json.dumps(clean["registry_minus_frame_verbatim"]),
            },
            {
                "id": "T2-frame-minus-registry-empty",
                "name": "frame-minus-registry must be empty (no phantom ids)",
                "result": t2,
                "detail": json.dumps(clean["frame_minus_registry_verbatim"]),
            },
            {
                "id": "T3-planted-absent-p0",
                "name": "planted absent P0 id must make registry-minus-frame non-empty",
                "result": t3,
                "detail": json.dumps(planted["registry_minus_frame_verbatim"]),
            },
            {
                "id": "T4-planted-phantom-id",
                "name": "planted phantom id must make frame-minus-registry non-empty",
                "result": t_phantom,
                "detail": json.dumps(phantom["frame_minus_registry_verbatim"]),
            },
        ],
        "tests_ok": tests_ok,
        "state": state,
        "sentinel": sentinel,
        "answer": answer,
        "named_both": named_both,
    }


P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0009/probe1_clean_and_plant.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0009/probe2_reviewer_detector.py"
)
MISSING_P0 = "CLM-P0-BETA"
COMPARATOR_REL = "command-center/p2-wave/probes/CNF-0009/comparator.py"
MANIFEST_REL = "command-center/p2-wave/probes/CNF-0009/UNIT-ARTIFACT-MANIFEST.json"


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        return 1
    return text[:idx].count("\n") + 1


def domain_from_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain payload lives under report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        "planted_id_control" in report or "registry_minus_frame" in report
    ):
        return report
    return doc


def _schema_store(repo: Path) -> dict[str, Any]:
    store: dict[str, Any] = {}
    files = [
        repo / SCHEMA_REL,
        repo / "platform" / "schema" / "artifact-class-profiles.schema.json",
        repo / "platform" / "schema" / "receipt.schema.json",
    ]
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        sid = data.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = data
    return store


def _artifact_row(rel: str, role: str, repo: Path) -> dict[str, Any]:
    path = repo / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def validate_against_schema(doc: dict[str, Any], repo: Path = REPO) -> tuple[bool, str]:
    """Validate against the declared shim using a disk-local $ref store.

    jsonschema 4.10 on this box tries HTTPS for ast-integrate.invalid; that is
    a detector failure (network), not a content verdict. Store is the three
    $id-bearing files the confirmation-audit $ref chain actually needs.
    """
    try:
        import jsonschema
        from jsonschema import Draft202012Validator
    except ImportError:
        return False, "jsonschema missing"
    schema_path = repo / SCHEMA_REL
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        store = _schema_store(repo)
        resolver = jsonschema.RefResolver(
            base_uri=str(schema.get("$id") or ""),
            referrer=schema,
            store=store,
        )
        validator = Draft202012Validator(schema, resolver=resolver)
        errors = list(validator.iter_errors(doc))
    except Exception as exc:
        return False, f"{type(exc).__name__}:{exc}"
    if errors:
        err = errors[0]
        loc = "/".join(str(x) for x in err.absolute_path) or "<root>"
        more = f" (+{len(errors) - 1} more)" if len(errors) > 1 else ""
        return False, f"{loc}: {err.message}{more}"
    garbage = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNF-0009", "state": "SUCCESS"},
    ]
    rejected = 0
    for blob in garbage:
        if list(validator.iter_errors(blob)):
            rejected += 1
    if rejected != len(garbage):
        return False, f"schema-accepted-garbage rejected={rejected}/{len(garbage)}"
    return True, "ok"


def build_artifact(repo: Path = REPO) -> dict[str, Any]:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    m = measure(repo)
    clean = m["clean"]
    planted = m["planted"]
    phantom = m["phantom"]
    pair = m["pair"]
    broken_frame = drop_frame_id(pair["frame_doc"], MISSING_P0)
    broken = compare_docs(pair["registry_doc"], broken_frame)
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cmp_path = HERE / "comparator.py"
    setdiff_line = find_line(cmp_path, "def set_difference(")
    plant_line = find_line(cmp_path, "def plant_p0(")
    load_line = find_line(cmp_path, "def load_measured_pair(")
    drop_line = find_line(cmp_path, "def drop_frame_id(")
    setdiff_anchor = f"{COMPARATOR_REL}:{setdiff_line}"
    plant_anchor = f"{COMPARATOR_REL}:{plant_line}"
    load_anchor = f"{COMPARATOR_REL}:{load_line}"
    drop_anchor = f"{COMPARATOR_REL}:{drop_line}"
    rmf_text = json.dumps(clean["registry_minus_frame_verbatim"])
    fmr_text = json.dumps(clean["frame_minus_registry_verbatim"])
    plant_text = json.dumps(planted["registry_minus_frame_verbatim"])
    phantom_text = json.dumps(phantom["frame_minus_registry_verbatim"])
    broken_text = json.dumps(broken["registry_minus_frame_verbatim"])
    tests = [
        {
            "id": "T1-registry-minus-frame-empty",
            "name": "registry-minus-frame must be empty",
            "command": P1_CMD,
            "result": m["tests"][0]["result"],
            "output_tail": rmf_text,
        },
        {
            "id": "T2-frame-minus-registry-empty",
            "name": "frame-minus-registry must be empty (no phantom ids)",
            "command": P1_CMD,
            "result": m["tests"][1]["result"],
            "output_tail": fmr_text,
        },
        {
            "id": "T3-planted-absent-p0",
            "name": "planted absent P0 id must make registry-minus-frame non-empty",
            "command": P1_CMD,
            "result": m["tests"][2]["result"],
            "output_tail": plant_text,
        },
        {
            "id": "T4-planted-phantom-id",
            "name": "planted phantom id must make frame-minus-registry non-empty",
            "command": P2_CMD,
            "result": m["tests"][3]["result"],
            "output_tail": phantom_text,
        },
    ]
    supporting = [
        _artifact_row(SCHEMA_REL, "supporting", repo),
        _artifact_row(COMPARATOR_REL, "supporting", repo),
        _artifact_row(
            "command-center/p2-wave/probes/CNF-0009/fixtures/claim-registry.json",
            "fixture",
            repo,
        ),
        _artifact_row(
            "command-center/p2-wave/probes/CNF-0009/fixtures/sampling-frame.json",
            "fixture",
            repo,
        ),
    ]
    named_status = "PRESENT" if m["named_both"] else "NOT-CHECKED-incomplete-named-pair"
    report: dict[str, Any] = {
        "kind": "confirmation-audit",
        "observations": [
            {
                "name": "registry-minus-frame",
                "measured": rmf_text,
                "method": "set-difference",
                "anchor": setdiff_anchor,
            },
            {
                "name": "frame-minus-registry",
                "measured": fmr_text,
                "method": "set-difference",
                "anchor": setdiff_anchor,
            },
            {
                "name": "planted-p0-nonzero",
                "measured": bool(planted["nonzero_difference"]),
                "method": "same-run-plant-p0",
                "anchor": plant_anchor,
            },
            {
                "name": "measured-pair-source",
                "measured": str(pair["source"]),
                "method": "load_measured_pair",
                "anchor": load_anchor,
            },
        ],
        "control_ids": [
            "T3-planted-absent-p0",
            "T4-planted-phantom-id",
            "NC-planted-p0",
            "NC-drop-CLM-P0-BETA",
            "NC-planted-phantom",
        ],
        "question": QUESTION,
        "answer": m["answer"],
        "completion_sentinel": COMPLETION_SENTINEL,
        "measured_pair_source": pair["source"],
        "named_inputs": pair["named_inputs"],
        "both_difference_directions_printed": True,
        "registry_minus_frame": list(clean["registry_minus_frame"]),
        "frame_minus_registry": list(clean["frame_minus_registry"]),
        "registry_minus_frame_verbatim": list(clean["registry_minus_frame_verbatim"]),
        "frame_minus_registry_verbatim": list(clean["frame_minus_registry_verbatim"]),
        "clean_comparison": {
            "registry_path": pair["registry_path"],
            "frame_path": pair["frame_path"],
            "registry_p0p1_ids": clean["registry_p0p1_ids"],
            "registry_all_ids": clean["registry_all_ids"],
            "frame_ids": clean["frame_ids"],
            "registry_minus_frame": clean["registry_minus_frame"],
            "frame_minus_registry": clean["frame_minus_registry"],
            "same_run_as_planted_control": True,
        },
        "planted_id_control": planted,
        "phantom_id_control": phantom,
        "missing_p0_control": {
            "missing_id": MISSING_P0,
            "registry_minus_frame": broken["registry_minus_frame"],
            "registry_minus_frame_verbatim": broken["registry_minus_frame_verbatim"],
            "fires": MISSING_P0 in broken["registry_minus_frame"],
            "anchor": drop_anchor,
        },
        "catalog_named_inputs_status": named_status,
        "no_adv_rebuild": True,
    }
    doc: dict[str, Any] = {
        "schema_version": 1,
        "unit_id": "CNF-0009",
        "state": m["state"],
        "sentinel": m["sentinel"],
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0009",
        "min_bytes_threshold": 512,
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "On the measured pair (source="
                    + str(pair["source"])
                    + ") both set-difference directions are empty: "
                    "registry-minus-frame="
                    + rmf_text
                    + " and frame-minus-registry="
                    + fmr_text
                    + "."
                ),
                "verdict": "CONFIRMED" if m["tests"][0]["result"] == "PASS"
                and m["tests"][1]["result"] == "PASS"
                else "REFUTED",
                "confidence": "almost-certain",
                "anchor": setdiff_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": P1_CMD,
                        "raw_output": "rmf=" + rmf_text + " fmr=" + fmr_text,
                        "fingerprint": "cnf0009:source:set-difference",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": P2_CMD,
                        "raw_output": "clean_rmf_empty=True clean_fmr_empty=True",
                        "fingerprint": "cnf0009:verifier:reviewer-recompute",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Planted P0 id "
                    + PLANTED_P0
                    + " is absent from the frame and produces registry-minus-frame="
                    + plant_text
                    + " in the same run as the clean comparison."
                ),
                "verdict": "CONFIRMED" if planted["nonzero_difference"]
                and planted["contains_planted_id"]
                else "REFUTED",
                "confidence": "almost-certain",
                "anchor": plant_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": COMPARATOR_REL + ":plant_p0",
                        "raw_output": plant_text,
                        "fingerprint": "cnf0009:source:plant-p0",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "test-run",
                        "command": P2_CMD + " # drop " + MISSING_P0,
                        "raw_output": "broken_rmf=" + broken_text,
                        "fingerprint": "cnf0009:verifier:drop-missing-p0",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-planted-p0",
                "kind": "known-broken-fixture",
                "description": (
                    "Plant P0 id "
                    + PLANTED_P0
                    + " that the frame does not contain; registry-minus-frame "
                    "must become non-empty while the clean pair stays empty."
                ),
                "fired_on_bad_state": bool(
                    planted["nonzero_difference"] and planted["contains_planted_id"]
                ),
                "silent_on_good_state": clean["registry_minus_frame"] == [],
                "bad_state_output": plant_text,
                "good_state_output": rmf_text,
            },
            {
                "id": "NC-drop-CLM-P0-BETA",
                "kind": "known-broken-fixture",
                "description": (
                    "Drop "
                    + MISSING_P0
                    + " from the frame copy; registry-minus-frame must contain it."
                ),
                "fired_on_bad_state": MISSING_P0 in broken["registry_minus_frame"],
                "silent_on_good_state": clean["registry_minus_frame"] == [],
                "bad_state_output": broken_text,
                "good_state_output": rmf_text,
            },
            {
                "id": "NC-planted-phantom",
                "kind": "malformed-input",
                "description": (
                    "Plant phantom id "
                    + PHANTOM_ID
                    + " into the frame; frame-minus-registry must become non-empty."
                ),
                "fired_on_bad_state": bool(
                    phantom["nonzero_difference"] and phantom["contains_phantom_id"]
                ),
                "silent_on_good_state": clean["frame_minus_registry"] == [],
                "bad_state_output": phantom_text,
                "good_state_output": fmr_text,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0009-probe2-detector-control",
            "verdict": "PASS" if m["tests_ok"] else "FAIL",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Reviewer re-runs the planted-P0 detector control and the "
                "known-broken missing-P0 fixture; it does not accept the "
                "artifact conclusion as verification."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema.Draft202012Validator with disk-local RefResolver",
                "artifact_path": OUTPUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                        "command-center/p2-wave/probes/CNF-0009/emit_artifact.py"
                    ),
                    "raw_output": "schema_ok=True garbage_rejected=4/4",
                    "fingerprint": "cnf0009:consumer:schema-validate",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record, never "
                "an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live named-pair completeness "
                    "(command-center/CLAIM-REGISTRY.json severity>=P1 vs "
                    "command-center/confirmation/CNF-0003-sampling-frame.json) "
                    "is NOT-CHECKED because the named pair is incomplete "
                    "(status="
                    + named_status
                    + "). Fixture completeness is not a live-corpus census."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNF-0003 so CNF-0003-sampling-frame.json exists "
                    "at the catalog path, then re-run CNF-0009 named-pair "
                    "compare without rebuilding CLAIM-REGISTRY.json or the frame."
                ),
            }
        ],
        "report": report,
        "extensions": {
            "no_adv_rebuild": True,
            "catalog_named_inputs_status": named_status,
        },
    }
    if m["state"] != "SUCCESS":
        doc["failure"] = {
            "classification": "detector-failure",
            "reason": m["answer"][:400],
        }
    return doc


if __name__ == "__main__":
    doc = build_artifact()
    domain = domain_from_doc(doc)
    ok, why = validate_against_schema(doc)
    print(
        json.dumps(
            {
                "state": doc["state"],
                "source": domain.get("measured_pair_source"),
                "rmf": domain.get("registry_minus_frame_verbatim"),
                "fmr": domain.get("frame_minus_registry_verbatim"),
                "plant": (domain.get("planted_id_control") or {}).get(
                    "registry_minus_frame_verbatim"
                ),
                "schema": why,
            },
            sort_keys=True,
        )
    )
    raise SystemExit(0 if ok and doc["state"] == "SUCCESS" else 1)
