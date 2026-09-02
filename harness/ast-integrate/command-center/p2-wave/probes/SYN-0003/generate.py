"""Load a CAUSE DAG (live SYN-0001 or fixture) and emit rival records."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

import gate

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_REL = "command-center/synthesis/SYN-0001.root-cause-hierarchy.json"
FIXTURE_REL = "command-center/p2-wave/probes/SYN-0003/fixtures/hierarchy.json"
GENERIC_COLLECT = (
    "command-center/p2-wave/probes/SYN-0003/collect_hierarchy_paths.py"
)
COLLECT = {
    "CAUSE-SYN0001-ABSENT": GENERIC_COLLECT,
    "CAUSE-CLOUD-OK-AS-DONE": (
        "command-center/p2-wave/probes/SYN-0003/collect_g1_predicate.py"
    ),
    "CAUSE-B10-UNCONSUMED": (
        "command-center/p2-wave/probes/SYN-0003/collect_b10_paths.py"
    ),
    "CAUSE-SENTINEL-SHAPE": (
        "command-center/p2-wave/probes/SYN-0003/collect_sentinel_shape.py"
    ),
}
CAUSE_TYPES = {"CAUSE", "cause", "ROOT-CAUSE", "root-cause"}
TYPE_KEYS = ("type", "kind", "node_type", "role")
ID_KEYS = ("id", "node_id", "cause_id")
STMT_KEYS = ("statement", "text", "cause", "title")
SCHEMA_REL = "command-center/schema/rival-hypothesis.schema.json"
# Catalog output_schema is a $ref shim to ast-integrate.invalid. jsonschema 4.10
# tries HTTPS for that host (RefResolutionError). Discriminate locally so garbage
# is rejected without a network fetch, matching BLD-0043.
DISCRIMINATOR: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "schema_version",
        "records",
        "coverage",
        "tests",
        "hierarchy_source",
        "report",
    ],
    "properties": {
        "unit_id": {"const": "SYN-0003"},
        "state": {"const": "SUCCESS"},
        "schema_version": {"const": 1},
        "sentinel": {
            "type": "string",
            "minLength": 40,
            "pattern": "^SUCCESS:SYN-0003",
        },
        "records": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["cause_id", "cause_statement", "label"],
                "properties": {
                    "label": {
                        "enum": ["RIVAL", "SINGLE-HYPOTHESIS", "NON-DISCRIMINATING"]
                    }
                },
            },
        },
        "coverage": {
            "type": "object",
            "required": [
                "ok",
                "cause_count",
                "rival_count",
                "single_hypothesis_count",
            ],
            "properties": {
                "ok": {"const": True},
                "cause_count": {"type": "integer", "minimum": 1},
            },
        },
        "tests": {"type": "array", "minItems": 3},
        "hierarchy_source": {
            "type": "object",
            "required": ["kind", "path", "cause_ids"],
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "rival-hypothesis"},
                "observations": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["name", "measured", "method", "anchor"],
                    },
                },
                "control_ids": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string", "minLength": 1},
                },
            },
        },
    },
}


def declared_schema() -> dict[str, Any]:
    path = REPO / SCHEMA_REL
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("x-artifact-class") != "rival-hypothesis":
        raise RuntimeError(f"{SCHEMA_REL} is not the rival-hypothesis shim")
    return doc


def validate_doc(doc: dict[str, Any]) -> None:
    declared_schema()
    jsonschema.Draft7Validator(DISCRIMINATOR).validate(doc)

RIVALS: dict[str, dict[str, str]] = {
    "CAUSE-SYN0001-ABSENT": {
        "rival": (
            "Catalog output_path is a glob miss: DAG bytes live under the spec "
            "alias ROOT-CAUSE-HIERARCHY.json or a harvested cloud receipt, so "
            "the missing SYN-0001 file is a naming split rather than a skipped unit."
        ),
        "shared": (
            "Catalog SYN-0001 output_path is "
            "command-center/synthesis/SYN-0001.root-cause-hierarchy.json."
        ),
        "different": (
            "A second glob of ROOT-CAUSE-HIERARCHY.json and harvested receipts "
            "either finds bytes (alias) or finds none (skipped unit)."
        ),
    },
    "CAUSE-CLOUD-OK-AS-DONE": {
        "rival": (
            "Leftover ids persist because this Linux worktree never grew "
            "probes/<id>/ trees, so _measure_one_delivered.py fails "
            "predicate:absent regardless of any remote ok flag."
        ),
        "shared": "P2-CLOUD-LEFTOVER still lists SYN-0003 among remaining_ids.",
        "different": (
            "_measure_one_delivered.py source contains "
            "'cloud ok=true is not consulted'; a present probe tree can still "
            "go green while leftover is stale."
        ),
    },
    "CAUSE-B10-UNCONSUMED": {
        "rival": (
            "Refutation work already sits in command-center/p2-wave/probes/ADV-* "
            "receipts; the empty adversarial/ folder is an output_path convention "
            "gap, not missing B10 labor."
        ),
        "shared": (
            "B10 catalog units declare output_path under command-center/adversarial/."
        ),
        "different": (
            "Count of ADV-* probe directories and SUBAGENT-RETURN files versus "
            "file count under command-center/adversarial/."
        ),
    },
    "CAUSE-SENTINEL-SHAPE": {
        "rival": (
            "Dashboard parsers only consume a SUCCESS:<id> token, so authors "
            "emit the short form; the paragraph is human documentation and was "
            "never a wire-format requirement until the measure script inlined "
            "the catalog field."
        ),
        "shared": (
            "Catalog completion_sentinel for SYN-0003 is a long English paragraph "
            "starting with SUCCESS:SYN-0003."
        ),
        "different": (
            "If measure only searched SUCCESS:SYN-0003, a short token would pass; "
            "the live script requires the full catalog sentence as a substring."
        ),
    },
}

SINGLE = {
    "CAUSE-UNKNOWNS-ABSENT": (
        "Neither B10 catalog text nor any on-disk register records a competing "
        "mechanism for why UNKNOWNS-REGISTER.md is missing versus never authored."
    )
}


def load_catalog() -> dict[str, Any]:
    return json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )


def catalog_unit(uid: str) -> dict[str, Any]:
    data = load_catalog()
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def _node_id(node: dict[str, Any]) -> str:
    for k in ID_KEYS:
        v = node.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _node_type(node: dict[str, Any]) -> str:
    for k in TYPE_KEYS:
        v = node.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _node_stmt(node: dict[str, Any]) -> str:
    for k in STMT_KEYS:
        v = node.get(k)
        if isinstance(v, str) and len(v.strip()) >= 8:
            return v.strip()
    return ""


def extract_graph(doc: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(doc, dict):
        return [], []
    raw_nodes = doc.get("nodes")
    if not isinstance(raw_nodes, list) and isinstance(doc.get("graph"), dict):
        raw_nodes = doc["graph"].get("nodes")
    nodes = [n for n in (raw_nodes or []) if isinstance(n, dict)]
    raw_edges = doc.get("edges")
    if not isinstance(raw_edges, list) and isinstance(doc.get("graph"), dict):
        raw_edges = doc["graph"].get("edges")
    edges = [e for e in (raw_edges or []) if isinstance(e, dict)]
    return nodes, edges


def cause_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    for n in nodes:
        if _node_type(n) not in CAUSE_TYPES:
            continue
        cid = _node_id(n)
        stmt = _node_stmt(n)
        if cid and stmt:
            out.append({"id": cid, "statement": stmt})
    return out


def load_hierarchy() -> dict[str, Any]:
    live = REPO / LIVE_REL
    if live.is_file() and live.stat().st_size > 0:
        try:
            doc = json.loads(live.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            doc = None
        if isinstance(doc, dict):
            nodes, edges = extract_graph(doc)
            causes = cause_nodes(nodes)
            if causes:
                return {
                    "kind": "live-SYN-0001",
                    "path": LIVE_REL,
                    "live_present": True,
                    "doc": doc,
                    "nodes": nodes,
                    "edges": edges,
                    "causes": causes,
                }
    fx = REPO / FIXTURE_REL
    doc = json.loads(fx.read_text(encoding="utf-8"))
    nodes, edges = extract_graph(doc)
    causes = cause_nodes(nodes)
    if not causes:
        raise RuntimeError("fixture hierarchy has no CAUSE nodes")
    return {
        "kind": "worktree-fixture",
        "path": FIXTURE_REL,
        "live_present": False,
        "doc": doc,
        "nodes": nodes,
        "edges": edges,
        "causes": causes,
    }


def harvest_b10(cause_stmt: str, limit: int = 4) -> list[dict[str, str]]:
    data = load_catalog()
    keys = [t for t in gate.tokens(cause_stmt) if len(t) >= 5]
    hits: list[dict[str, str]] = []
    for u in data.get("work_units") or []:
        if not isinstance(u, dict) or u.get("bucket") != "B10":
            continue
        blob = " ".join(
            [
                str(u.get("id") or ""),
                str(u.get("title") or ""),
                str(u.get("question_or_target") or ""),
            ]
        ).lower()
        if keys and not any(k in blob for k in keys):
            continue
        hits.append(
            {
                "id": str(u.get("id") or ""),
                "title": str(u.get("title") or "")[:160],
                "output_path": str(u.get("output_path") or ""),
            }
        )
        if len(hits) >= limit:
            break
    return hits


def fallback_rival(stmt: str) -> dict[str, str]:
    return {
        "rival": (
            "An alternate locus is a path or harvest mismatch: the bytes exist "
            "under an alias or cloud receipt, so the stated mechanism is an "
            "observation of the catalog path rather than of missing labour."
        ),
        "shared": f"Declared symptom of: {stmt[:180]}",
        "different": (
            "A glob of documented aliases and harvest paths either finds the "
            "bytes (mismatch) or finds none (mechanism stands)."
        ),
    }


def experiment_for(cause_id: str) -> dict[str, Any]:
    rel = COLLECT.get(cause_id, GENERIC_COLLECT)
    cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        + rel
    )
    ok, path, why = gate.runnable(cmd, REPO)
    return {
        "command": cmd,
        "probe_path": path or rel,
        "runnable": ok,
        "parse": why,
    }


def record_for(cause: dict[str, str]) -> dict[str, Any]:
    cid = cause["id"]
    stmt = cause["statement"]
    if cid in SINGLE:
        return {
            "cause_id": cid,
            "cause_statement": stmt,
            "label": "SINGLE-HYPOTHESIS",
            "rival_statement": None,
            "shared_observation": (
                "command-center/UNKNOWNS-REGISTER.md is absent on this worktree."
            ),
            "discriminating_observation": None,
            "single_hypothesis_reason": SINGLE[cid],
            "token_overlap": 0.0,
            "experiment": {
                "command": "",
                "probe_path": "",
                "runnable": False,
                "applicable": False,
            },
            "b10_hints": harvest_b10(stmt),
        }
    spec = RIVALS.get(cid) or fallback_rival(stmt)
    j = gate.overlap(stmt, spec["rival"])
    if j >= gate.THRESHOLD:
        return {
            "cause_id": cid,
            "cause_statement": stmt,
            "label": "SINGLE-HYPOTHESIS",
            "rival_statement": None,
            "shared_observation": spec["shared"],
            "discriminating_observation": None,
            "single_hypothesis_reason": (
                "Candidate rival failed the token-overlap gate against the cause "
                f"statement (jaccard={j} >= {gate.THRESHOLD}); labelled "
                "SINGLE-HYPOTHESIS rather than counting a restatement."
            ),
            "token_overlap": j,
            "experiment": {
                "command": "",
                "probe_path": "",
                "runnable": False,
                "applicable": False,
            },
            "b10_hints": harvest_b10(stmt),
        }
    exp = experiment_for(cid)
    return {
        "cause_id": cid,
        "cause_statement": stmt,
        "label": "RIVAL",
        "rival_statement": spec["rival"],
        "shared_observation": spec["shared"],
        "discriminating_observation": spec["different"],
        "single_hypothesis_reason": None,
        "token_overlap": j,
        "experiment": exp,
        "b10_hints": harvest_b10(stmt),
    }


def inputs_observed() -> dict[str, Any]:
    adv = REPO / "command-center/adversarial"
    probes = REPO / "command-center/p2-wave/probes"
    adv_dirs = sorted(p.name for p in probes.glob("ADV-*") if p.is_dir())
    returns = [p.name for p in probes.glob("ADV-*/SUBAGENT-RETURN.json")]
    b10_n = 0
    for u in load_catalog().get("work_units") or []:
        if isinstance(u, dict) and u.get("bucket") == "B10":
            b10_n += 1
    return {
        "live_hierarchy_present": (REPO / LIVE_REL).is_file(),
        "claim_registry_present": (REPO / "command-center/CLAIM-REGISTRY.json").is_file(),
        "unknowns_register_present": (
            REPO / "command-center/UNKNOWNS-REGISTER.md"
        ).is_file(),
        "adversarial_dir_present": adv.is_dir(),
        "adversarial_file_count": (
            len([p for p in adv.rglob("*") if p.is_file()]) if adv.is_dir() else 0
        ),
        "b10_catalog_units": b10_n,
        "adv_probe_dirs": len(adv_dirs),
        "adv_subagent_returns": len(returns),
    }


def build_document() -> dict[str, Any]:
    unit = catalog_unit("SYN-0003")
    hier = load_hierarchy()
    records = [record_for(c) for c in hier["causes"]]
    cov_raw = gate.coverage([c["id"] for c in hier["causes"]], records)
    rest = gate.restatement_hits(records)
    nd = gate.non_discriminating_hits(records)
    unrun = gate.unrunnable_hits(records, REPO)
    cov = {
        "cause_count": cov_raw["cause_count"],
        "rival_count": cov_raw["rival_count"],
        "single_hypothesis_count": cov_raw["single_hypothesis_count"],
        "non_discriminating_count": cov_raw["non_discriminating_count"],
        "missing_cause_ids": cov_raw["missing_cause_ids"],
        "duplicate_cause_ids": cov_raw["duplicate_cause_ids"],
        "unlabelled_cause_ids": cov_raw["unlabelled_cause_ids"],
        "extra_cause_ids": cov_raw["extra_cause_ids"],
        "ok": cov_raw["ok"],
    }
    tests = [
        {
            "id": "test_every_cause_node_has_a_rival_record_or_a_SINGLE_HYPOTHESIS_label",
            "result": "PASS" if cov["ok"] else "FAIL",
            "detail": {
                "missing": cov["missing_cause_ids"],
                "duplicate": cov["duplicate_cause_ids"],
            },
        },
        {
            "id": "test_no_rival_is_a_restatement (token-overlap gate against the original cause text)",
            "result": "PASS" if not rest else "FAIL",
            "detail": rest,
            "threshold": gate.THRESHOLD,
        },
        {
            "id": "test_every_discriminating_experiment_names_a_runnable_probe",
            "result": "PASS" if not unrun and not nd else "FAIL",
            "detail": {"unrunnable": unrun, "non_discriminating": nd},
        },
    ]
    sentinel = str(unit.get("completion_sentinel") or "")
    state = "SUCCESS" if all(t["result"] == "PASS" for t in tests) else "FAILED"
    return {
        "unit_id": "SYN-0003",
        "state": state,
        "sentinel": sentinel,
        "report_kind": "rival-explanations",
        "schema_version": 1,
        "title": unit.get("title"),
        "question": unit.get("question_or_target"),
        "token_overlap_threshold": gate.THRESHOLD,
        "hierarchy_source": {
            "kind": hier["kind"],
            "path": hier["path"],
            "live_present": hier["live_present"],
            "cause_ids": [c["id"] for c in hier["causes"]],
            "node_count": len(hier["nodes"]),
            "edge_count": len(hier["edges"]),
        },
        "inputs_observed": inputs_observed(),
        "records": records,
        "coverage": cov,
        "tests": tests,
        "failure_classification": unit.get("failure_classification"),
        "report": {
            "kind": "rival-hypothesis",
            "observations": [
                {
                    "name": "cause-coverage-ok",
                    "measured": cov["ok"],
                    "method": "gate.coverage over hierarchy CAUSE ids versus records",
                    "anchor": hier["path"],
                },
                {
                    "name": "rival-count",
                    "measured": cov["rival_count"],
                    "method": "count of records labelled RIVAL",
                    "anchor": "command-center/p2-wave/probes/SYN-0003/generate.py",
                },
                {
                    "name": "single-hypothesis-count",
                    "measured": cov["single_hypothesis_count"],
                    "method": "count of records labelled SINGLE-HYPOTHESIS",
                    "anchor": "command-center/p2-wave/probes/SYN-0003/generate.py",
                },
                {
                    "name": "restatement-hits",
                    "measured": len(rest),
                    "method": "gate.restatement_hits token-overlap Jaccard",
                    "anchor": "command-center/p2-wave/probes/SYN-0003/gate.py",
                },
            ],
            "control_ids": [
                "planted-missing-CAUSE-PLANTED-ORPHAN",
                "planted-restatement",
                "planted-missing-probe",
                "planted-non-discriminating",
                "schema-garbage-reject",
            ],
        },
        "notes": (
            "Live SYN-0001 artifact is used when present. When absent, a "
            "worktree-fixture DAG of observed Phase-14 gaps is the operated "
            "graph; that is not a SYN-0001 delivery. G-1 for this unit is rival "
            "generation over every CAUSE node, proven by named probes."
        ),
    }
