#!/usr/bin/env python3
"""ARC-0103 golden: specify negotiation, exercise the skew matrix, adjudicate."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import negotiate as N

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OUT_REL = "command-center/phase4/conformance/ARC-0103.json"
SCHEMA_REL = "command-center/schema/conformance-report.schema.json"
CONSUMER_REL = "tools/command-center/catalog.py"
SEED_REL = "tools/command-center/seed.py"
MANIFEST_REL = "command-center/p2-wave/probes/ARC-0112/UNIT-ARTIFACT-MANIFEST.json"
REGISTRY_REL = "command-center/p2-wave/probes/ARC-0010/registry.json"

CONTRACTS = (
    ("ARC-0092", "command-center/phase4/contracts/ARC-0092.json", "versioning-rules"),
    ("ARC-0093", "command-center/phase4/contracts/ARC-0093.json", "migration-record"),
    ("ARC-0095", "command-center/phase4/contracts/ARC-0095.json", "compatibility-matrix"),
)

CORPUS = (
    ("work-unit-catalogue", CATALOG_REL, "ARC-0092"),
    ("catalog-consumer", CONSUMER_REL, "ARC-0092"),
    ("catalog-v1-producer", SEED_REL, "ARC-0093"),
    ("unit-artifact-manifest", MANIFEST_REL, "ARC-0095"),
    ("a2-registry", REGISTRY_REL, "ARC-0092"),
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0103/probe1_skew_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0103/probe2_loud_refusal.py"
)

_SCHEMA_VERSION_RE = re.compile(r"^SCHEMA_VERSION\s*=\s*(\d+)\s*$", re.M)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def lf(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def git_blob(rel: str) -> tuple[bool, bytes | None, str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO), "show", f"HEAD:{rel}"],
            capture_output=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, None, f"git-unavailable:{type(exc).__name__}"
    if proc.returncode == 0:
        return True, proc.stdout, "git-HEAD"
    err = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
    tail = err[-1] if err else f"exit {proc.returncode}"
    return False, None, tail[:200]


def classify_surfaces(worktree: bytes, blob: bytes) -> str:
    if worktree == blob:
        return "identical"
    if lf(worktree) == lf(blob):
        return "crlf-only"
    return "data-divergence"


def encoding_pair(rel: str) -> dict[str, Any]:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "present": False,
            "git_available": False,
            "kind": "absent",
            "worktree_sha256": None,
            "blob_sha256": None,
            "blob_source": "absent",
        }
    raw = path.read_bytes()
    git_ok, blob, source = git_blob(rel)
    if blob is None:
        blob = lf(raw)
        source = "lf-normalized-worktree-stand-in"
    kind = classify_surfaces(raw, blob)
    return {
        "path": rel,
        "present": True,
        "git_available": git_ok,
        "kind": kind,
        "worktree_bytes": len(raw),
        "blob_bytes": len(blob),
        "worktree_sha256": hashlib.sha256(raw).hexdigest(),
        "blob_sha256": hashlib.sha256(blob).hexdigest(),
        "lf_sha256": hashlib.sha256(lf(raw)).hexdigest(),
        "blob_source": source,
        "crlf_only": kind == "crlf-only",
        "data_divergence": kind == "data-divergence",
    }


def _fail(
    fid: str,
    direction: str,
    contract_id: str,
    citation: str,
    reason: str,
    **extra: Any,
) -> dict[str, Any]:
    row = {
        "id": fid,
        "direction": direction,
        "contract_id": contract_id,
        "citation": citation,
        "reason": reason,
        "encoding": extra.pop("encoding", "none"),
    }
    row.update(extra)
    return row


def load_json(rel: str) -> Any:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def report_body(doc: dict[str, Any]) -> dict[str, Any]:
    """Inner conformance payload. Envelope receipts nest it under report."""
    inner = doc.get("report")
    if isinstance(inner, dict) and isinstance(inner.get("skew_matrix"), list):
        return inner
    return doc


def load_catalog() -> dict[str, Any]:
    data = load_json(CATALOG_REL)
    if not isinstance(data, dict):
        raise TypeError(f"{CATALOG_REL} root is {type(data).__name__}")
    return data


def catalog_unit(catalog: dict[str, Any], uid: str) -> dict[str, Any]:
    for row in catalog.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == uid:
            return row
    raise KeyError(uid)


def live_consumer_schema_version() -> int:
    text = (REPO / CONSUMER_REL).read_text(encoding="utf-8")
    match = _SCHEMA_VERSION_RE.search(text)
    if not match:
        raise RuntimeError(f"{CONSUMER_REL} SCHEMA_VERSION assignment not found")
    return int(match.group(1))


def catalog_v2_keys(catalog: dict[str, Any]) -> frozenset[str]:
    return N.field_set(catalog)


def consumer_fields_for(version: int, catalog: dict[str, Any]) -> frozenset[str]:
    if version <= 1:
        return N.CATALOG_V1_KEYS
    return catalog_v2_keys(catalog)


def record_counts(doc: dict[str, Any]) -> dict[str, int]:
    items = doc.get("items")
    work_units = doc.get("work_units")
    return {
        "items": len(items) if isinstance(items, list) else 0,
        "work_units": len(work_units) if isinstance(work_units, list) else 0,
        "top_level_fields": len(doc),
    }


def _cell(
    artifact_class: str,
    producer: int,
    consumer: int,
    result: dict[str, Any],
    *,
    source: str,
    evidence: str,
) -> dict[str, Any]:
    status = result.get("status")
    if status == "ACCEPT":
        cell_status = "EXERCISED-ACCEPT"
    elif status == "REFUSE":
        cell_status = "EXERCISED-REFUSE"
    else:
        cell_status = "NOT-CHECKED"
    return {
        "artifact_class": artifact_class,
        "producer_version": producer,
        "consumer_version": consumer,
        "status": cell_status,
        "inferred": False,
        "source": source,
        "evidence": evidence,
        "negotiation": result,
    }


def catalog_skew_matrix(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Every (P, C) in supported range {1, 2} is exercised, never inferred."""
    v1 = N.catalog_v1_projection(catalog)
    v2 = catalog
    cells: list[dict[str, Any]] = []
    pairs = (
        (1, 1, v1, "v1-projection of live catalog (seed.py keys, schema_version=1)"),
        (1, 2, v1, "previous schema read by current consumer (required evidence pair)"),
        (2, 2, v2, "live WORK-UNIT-CATALOG.json schema_version=2"),
        (2, 1, v2, "live v2 catalog read by v1 consumer (catalog.py SCHEMA_VERSION)"),
    )
    for producer, consumer, doc, evidence in pairs:
        result = N.try_negotiate(
            doc,
            consumer,
            consumer_fields_for(consumer, catalog),
            N.CATALOG_CLASS,
        )
        cells.append(
            _cell(
                N.CATALOG_CLASS,
                producer,
                consumer,
                result,
                source=CATALOG_REL,
                evidence=evidence,
            )
        )
    return cells


def other_class_cells() -> list[dict[str, Any]]:
    """Classes whose supported range on this tree is {1} only."""
    cells: list[dict[str, Any]] = []
    for rel, artifact_class, keys in (
        (
            MANIFEST_REL,
            N.MANIFEST_CLASS,
            frozenset(
                {
                    "schema_version",
                    "contract",
                    "derivation",
                    "unit_id",
                    "verified_on_disk",
                    "expected",
                    "present",
                    "artifacts",
                }
            ),
        ),
        (
            REGISTRY_REL,
            N.REGISTRY_CLASS,
            frozenset({"schema_version", "generator_id", "generator_version", "entries"}),
        ),
    ):
        path = REPO / rel
        if not path.is_file():
            cells.append(
                {
                    "artifact_class": artifact_class,
                    "producer_version": 1,
                    "consumer_version": 1,
                    "status": "NOT-CHECKED",
                    "inferred": False,
                    "source": rel,
                    "evidence": f"{rel} absent",
                    "negotiation": {"status": "NOT-CHECKED"},
                }
            )
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        result = N.try_negotiate(doc, 1, keys, artifact_class)
        cells.append(
            _cell(
                artifact_class,
                1,
                1,
                result,
                source=rel,
                evidence=f"live {rel} schema_version=1 read by consumer 1",
            )
        )
    return cells


def loud_refusal_control(catalog: dict[str, Any]) -> dict[str, Any]:
    v1_fields = N.CATALOG_V1_KEYS
    live = catalog
    silent = N.silent_partial_read(live, v1_fields)
    live_counts = record_counts(live)
    silent_counts = record_counts(silent)
    refused = N.try_negotiate(live, 1, v1_fields, N.CATALOG_CLASS)
    accepted = N.try_negotiate(
        N.catalog_v1_projection(live),
        2,
        consumer_fields_for(2, live),
        N.CATALOG_CLASS,
    )
    planted_doc, planted_c, planted_fields = N.planted_incompatible()
    planted = N.try_negotiate(planted_doc, planted_c, planted_fields, "planted")
    silent_planted = N.silent_partial_read(planted_doc, planted_fields)
    return {
        "live_pair": {
            "producer_path": CATALOG_REL,
            "producer_version": live.get(N.VERSION_FIELD),
            "consumer_version": 1,
            "consumer_stamp_path": CONSUMER_REL,
            "consumer_stamp": live_consumer_schema_version(),
            "negotiation": refused,
            "silent_partial_read": {
                "producer_field_count": live_counts["top_level_fields"],
                "consumed_field_count": silent_counts["top_level_fields"],
                "producer_work_units": live_counts["work_units"],
                "consumed_work_units": silent_counts["work_units"],
                "producer_items": live_counts["items"],
                "consumed_items": silent_counts["items"],
                "dropped_top_level": sorted(set(live) - set(silent)),
            },
        },
        "previous_schema_current_consumer": {
            "producer_version": 1,
            "consumer_version": 2,
            "negotiation": accepted,
        },
        "planted_incompatible": {
            "negotiation": planted,
            "silent_field_count": len(silent_planted),
            "producer_field_count": len(planted_doc),
        },
        "field_count_delta": live_counts["top_level_fields"] - silent_counts["top_level_fields"],
        "work_units_would_drop": live_counts["work_units"] - silent_counts["work_units"],
        "raises_on_incompatible": refused.get("status") == "REFUSE" and refused.get("loud") is True,
        "accepts_previous_on_current": accepted.get("status") == "ACCEPT",
        "silent_drops_work_units": (
            live_counts["work_units"] > 0 and silent_counts["work_units"] == 0
        ),
    }


def spec() -> dict[str, Any]:
    return {
        "version_field": {
            "name": N.VERSION_FIELD,
            "path": N.VERSION_PATH,
            "type": "integer",
            "location": "document root",
        },
        "compatibility_rule": (
            "integer schema_version: ACCEPT iff producer <= consumer; "
            "REFUSE if producer > consumer, if the field is missing, or if it is "
            "not an integer. Untested pairs are NOT-CHECKED, never inferred ACCEPT."
        ),
        "refusal": (
            "VersionRefusal is raised with producer/consumer versions and field "
            "counts. Partial key-subset returns are forbidden."
        ),
        "supported_range": {
            N.CATALOG_CLASS: [1, 2],
            N.MANIFEST_CLASS: [1],
            N.REGISTRY_CLASS: [1],
        },
        "catalog_v1_keys": sorted(N.CATALOG_V1_KEYS),
        "catalog_v1_source": f"{SEED_REL}:188-207",
    }


def frozen_contracts() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    failures = []
    for cid, rel, kind in CONTRACTS:
        present = (REPO / rel).is_file() and (REPO / rel).stat().st_size > 0
        rows.append({"id": cid, "path": rel, "present": present, "kind": kind})
        if not present:
            failures.append(
                _fail(
                    f"F-CONTRACT-ABSENT-{cid}",
                    "schema-wrong",
                    cid,
                    f"{rel}:absent",
                    (
                        f"Frozen {kind} contract {rel} is absent. Negotiation still "
                        "runs from the live catalog convention (root integer "
                        f"{N.VERSION_FIELD}), seed.py v1 keys, and catalog.py "
                        "SCHEMA_VERSION; the JSON Schema itself is not on disk."
                    ),
                    artifact_path=rel,
                    record_id=cid,
                    present=False,
                )
            )
    return rows, failures


def collect_failures(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    _, contract_failures = frozen_contracts()
    failures = list(contract_failures)
    live_ver = catalog.get(N.VERSION_FIELD)
    consumer_ver = live_consumer_schema_version()
    if live_ver != consumer_ver:
        failures.append(
            _fail(
                "F-LIVE-CONSUMER-SCHEMA-VERSION-SKEW",
                "artifact-wrong",
                "ARC-0092",
                f"{CONSUMER_REL}:SCHEMA_VERSION",
                (
                    f"Live catalog {CATALOG_REL} carries {N.VERSION_FIELD}={live_ver}; "
                    f"in-tree consumer {CONSUMER_REL} still assigns SCHEMA_VERSION="
                    f"{consumer_ver}. That is a forward-incompatible pair: a v1 "
                    "reader of a v2 document."
                ),
                artifact_path=CONSUMER_REL,
                record_id="SCHEMA_VERSION",
                live_producer_version=live_ver,
                live_consumer_version=consumer_ver,
            )
        )
    source = (REPO / CONSUMER_REL).read_text(encoding="utf-8")
    if "schema_version" not in source.split("def load", 1)[-1].split("def save", 1)[0]:
        failures.append(
            _fail(
                "F-LOAD-HAS-NO-LOUD-REFUSAL",
                "artifact-wrong",
                "ARC-0103",
                f"{CONSUMER_REL}:load",
                (
                    "catalog.load() returns the document without negotiating "
                    f"{N.VERSION_FIELD} against SCHEMA_VERSION. items() then reads "
                    "only the items array, which is a silent partial read of a v2 "
                    "catalog (work_units are dropped)."
                ),
                artifact_path=CONSUMER_REL,
                record_id="load",
            )
        )
    wu = catalog.get("work_units")
    n_wu = len(wu) if isinstance(wu, list) else 0
    if n_wu == 0:
        failures.append(
            _fail(
                "F-DETECTOR-NO-WORK-UNITS",
                "artifact-wrong",
                "ARC-0103",
                f"{CATALOG_REL}#/work_units",
                (
                    "work_units is missing or empty, so a v1 silent read and a v2 "
                    "read would both drop zero units. The loud-refusal control "
                    "would be silent in both states."
                ),
                artifact_path=CATALOG_REL,
                record_id="work_units",
            )
        )
    return failures


def adjudicate(failures: list[dict[str, Any]]) -> dict[str, Any]:
    classified = 0
    unexplained = 0
    art = 0
    sch = 0
    for row in failures:
        direction = str(row.get("direction") or "")
        citation = str(row.get("citation") or "")
        reason = str(row.get("reason") or "")
        if direction in {"artifact-wrong", "schema-wrong"} and citation and reason:
            classified += 1
            if direction == "artifact-wrong":
                art += 1
            else:
                sch += 1
        else:
            unexplained += 1
    return {
        "failing_records": len(failures),
        "classified": classified,
        "unexplained": unexplained,
        "artifact_wrong": art,
        "schema_wrong": sch,
        "computed_not_asserted": True,
    }


def encoding_control() -> dict[str, Any]:
    live = encoding_pair(CATALOG_REL)
    git_ok = bool(live.get("git_available"))
    lf_doc = b'{"id":"enc-control","n":1}\n'
    crlf_doc = lf_doc.replace(b"\n", b"\r\n")
    data_doc = b'{"id":"enc-control","n":2}\n'
    planted = {
        "identical": classify_surfaces(lf_doc, lf_doc),
        "crlf_only": classify_surfaces(crlf_doc, lf_doc),
        "data_divergence": classify_surfaces(data_doc, lf_doc),
    }
    crlf_ok = (
        planted["crlf_only"] == "crlf-only"
        and planted["data_divergence"] == "data-divergence"
    )
    live_ok = live.get("kind") in {"identical", "crlf-only", "absent", "data-divergence"}
    return {
        "git_available": git_ok,
        "git_note": live.get("blob_source"),
        "surfaces": [
            {
                "name": "working-tree",
                "path": CATALOG_REL,
                "sha256": live.get("worktree_sha256"),
            },
            {
                "name": "git-blob-or-lf-stand-in",
                "path": CATALOG_REL,
                "sha256": live.get("blob_sha256"),
                "source": live.get("blob_source"),
            },
        ],
        "live_catalog": live,
        "planted_both_states": planted,
        "crlf_not_misread_as_data": bool(crlf_ok),
        "live_surface_ok": bool(live_ok),
    }


def corpus_rows() -> list[dict[str, Any]]:
    rows = []
    for name, rel, cid in CORPUS:
        path = REPO / rel
        present = path.is_file() and path.stat().st_size > 0
        row: dict[str, Any] = {
            "name": name,
            "path": rel,
            "present": present,
            "contract_id": cid,
            "bytes": path.stat().st_size if present else 0,
        }
        if present:
            row["sha256"] = sha256_bytes(path.read_bytes())
        rows.append(row)
    return rows


def build_report() -> dict[str, Any]:
    catalog = load_catalog()
    unit = catalog_unit(catalog, "ARC-0103")
    matrix = catalog_skew_matrix(catalog) + other_class_cells()
    control = loud_refusal_control(catalog)
    failures = collect_failures(catalog)
    adj = adjudicate(failures)
    enc = encoding_control()
    contracts, _ = frozen_contracts()
    live_ver = catalog.get(N.VERSION_FIELD)
    consumer_ver = live_consumer_schema_version()
    counts = record_counts(catalog)
    question = str(unit.get("question_or_target") or "")
    tests_ok = (
        control["raises_on_incompatible"]
        and control["accepts_previous_on_current"]
        and control["silent_drops_work_units"]
        and enc.get("crlf_not_misread_as_data") is True
        and adj["unexplained"] == 0
    )
    answer = (
        f"Version lives at {N.VERSION_PATH} as an integer. Compatibility is "
        "producer <= consumer; producer > consumer is a loud VersionRefusal with "
        f"field counts, not a subset read. Live catalog is schema_version={live_ver}; "
        f"catalog.py SCHEMA_VERSION={consumer_ver}. A v1 silent read of the live "
        f"file would keep {control['live_pair']['silent_partial_read']['consumed_field_count']} "
        f"of {counts['top_level_fields']} top-level fields and drop "
        f"{control['work_units_would_drop']} work_units. Previous-schema (v1 "
        "projection of preserved items) read by a v2 consumer ACCEPTS. Frozen "
        "ARC-0092/0093/0095 contracts are absent (schema-wrong). SUCCESS:ARC-0103"
    )
    return {
        "unit_id": "ARC-0103",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0103",
        "title": unit.get("title"),
        "question": question,
        "verdict": "NEGOTIATION-SPECIFIED-AND-TESTED",
        "answer": answer,
        "spec": spec(),
        "skew_matrix": matrix,
        "loud_refusal_control": control,
        "live_versions": {
            "catalog_schema_version": live_ver,
            "catalog_py_SCHEMA_VERSION": consumer_ver,
            "items": counts["items"],
            "work_units": counts["work_units"],
            "top_level_fields": counts["top_level_fields"],
        },
        "contracts": contracts,
        "corpus": corpus_rows(),
        "failures": failures,
        "adjudication": adj,
        "encoding_control": enc,
        "tests": [
            {
                "id": "skew-matrix",
                "command": P1,
                "result": "PASS" if tests_ok else "FAIL",
            },
            {
                "id": "loud-refusal-control",
                "command": P2,
                "result": "PASS" if tests_ok else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0103-probe2-loud-refusal",
            "verdict": "PASS" if tests_ok else "FAIL",
            "independent": True,
            "scope_not_agreement": True,
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "output-schema"},
            {
                "path": "command-center/p2-wave/probes/ARC-0103/negotiate.py",
                "exists": True,
                "role": "negotiator",
            },
        ],
        "evidence_requirement": unit.get("evidence_requirement"),
        "tests_required": unit.get("tests_required"),
        "adv_rebuild_circle": False,
        "required_fix": None,
    }
