"""Briefed premises and mechanically different live re-probes."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from cnf0006_fingerprint import (
    INDEPENDENT,
    as_tuple,
    close_verdict,
    fingerprint_hex,
    pair_status,
)
from constants import MNN_FACT_ID, OUTPUT_REL, REPO

M_NN = re.compile(r"\bM-(\d{1,2})\b")
MECH_NN = re.compile(r"\bMECH-(\d{1,2})\b")
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})

OPTION_NAMES = (
    "07-OPTION-UNIVERSE.md",
    "07-OPTION-UNIVERSE.json",
    "07-OPTION-UNIVERSE.txt",
)
ARCH_NAMES = (
    "13-ARCHITECTURE-CANDIDATES.md",
    "13-ARCHITECTURE-CANDIDATES.json",
    "13-ARCHITECTURE-CANDIDATES.txt",
)
DECISION_NAMES = ("17-DECISION-LOG.md",)
SEARCH_ROOTS = (
    REPO,
    REPO / "command-center",
    REPO / "docs",
    REPO / "platform",
    REPO / "platform" / "corpus",
)


def _dump(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _estate_declaring_rel(rel: str) -> bool:
    """True only for estate declaring files, not sibling-unit probe fixtures.

    A recursive walk of command-center/ harvests planted 07-OPTION-UNIVERSE.*
    twins under p2-wave/probes/*/fixtures. Those are other units' controls,
    not the option-universe / architecture documents the 31-way pin names.
    """
    posix = rel.replace("\\", "/")
    parts = posix.split("/")
    if "__pycache__" in parts or ".git" in parts or "node_modules" in parts:
        return False
    if "fixtures" in parts:
        return False
    if "p2-wave" in parts and "probes" in parts:
        return False
    return True


def _rel_of(path: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return None
    if not _estate_declaring_rel(rel):
        return None
    return rel


def _find_named(names: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    command_center = (REPO / "command-center").resolve()
    for root in SEARCH_ROOTS:
        if not root.is_dir() and root != REPO:
            continue
        for name in names:
            direct = root / name
            if direct.is_file():
                rel = _rel_of(direct)
                if rel is not None and rel not in seen:
                    seen.add(rel)
                    found.append(rel)
        # Direct hits at command-center/ still count. Do not rglob it:
        # that tree holds every unit's probe fixtures.
        if root.is_dir() and root != REPO and root.resolve() != command_center:
            for name in names:
                for hit in root.rglob(name):
                    if not hit.is_file():
                        continue
                    rel = _rel_of(hit)
                    if rel is not None and rel not in seen:
                        seen.add(rel)
                        found.append(rel)
    return found


def _read_ids(rel: str, pattern: re.Pattern[str]) -> set[str]:
    path = REPO / rel
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return set(pattern.findall(text))


def measure_mnn_collision() -> dict[str, Any]:
    """Live collision = |option-universe M-ids ∩ architecture-candidate BARE M-ids|.

    MECH-NN tokens are the post-2026-08-07 architecture namespace and do not
    collide with option-universe M-NN. Missing declaring files are a genuine
    zero, not NOT-CHECKED: there is no live shared-id set to count as 31.
    Sibling-unit probe fixtures (p2-wave/probes, /fixtures/) are not declaring
    files; counting them made live verifier_output drift as other units landed.
    """
    option_files = _find_named(OPTION_NAMES)
    arch_files = _find_named(ARCH_NAMES)
    option_ids: set[str] = set()
    arch_bare: set[str] = set()
    arch_mech: set[str] = set()
    for rel in option_files:
        option_ids |= _read_ids(rel, M_NN)
    for rel in arch_files:
        arch_bare |= _read_ids(rel, M_NN)
        arch_mech |= _read_ids(rel, MECH_NN)
    shared = sorted(option_ids & arch_bare, key=lambda x: int(x))
    return {
        "briefed_collision_count": 31,
        "option_universe_files": option_files,
        "architecture_files": arch_files,
        "option_m_ids": sorted(option_ids, key=lambda x: int(x)),
        "architecture_bare_m_ids": sorted(arch_bare, key=lambda x: int(x)),
        "architecture_mech_ids": sorted(arch_mech, key=lambda x: int(x)),
        "shared_bare_m_ids": shared,
        "live_collision_count": len(shared),
        "declaring_files_absent": not option_files and not arch_files,
    }


def measure_catalog_unit_count() -> dict[str, Any]:
    data = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    units = data.get("work_units") or []
    return {
        "briefed_unit_count": 2007,
        "work_units_array_length": len(units),
        "top_level_keys": sorted(str(k) for k in data.keys())[:24],
    }


def measure_delivered_success_count() -> dict[str, Any]:
    data = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    exists = 0
    success = 0
    not_delivering = 0
    unparseable = 0
    missing_path = 0
    for unit in data.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        if not rel:
            missing_path += 1
            continue
        if rel == OUTPUT_REL:
            continue
        path = REPO / rel
        if not path.is_file() or path.stat().st_size <= 0:
            continue
        exists += 1
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            unparseable += 1
            continue
        if not isinstance(doc, dict):
            unparseable += 1
            continue
        st = str(doc.get("state") or "").upper()
        if st == "SUCCESS":
            success += 1
        if st in NOT_DELIVERING:
            not_delivering += 1
    return {
        "briefed_delivered": 4,
        "existing_nonempty_artifacts": exists,
        "state_success_count": success,
        "self_declared_not_delivering": not_delivering,
        "unparseable": unparseable,
        "units_without_output_path": missing_path,
        "excluded_self_output": OUTPUT_REL,
    }


def measure_receipt_schema() -> dict[str, Any]:
    rel = "command-center/schema/receipt.schema.json"
    path = REPO / rel
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    return {
        "briefed_absent": True,
        "path": rel,
        "exists": exists,
        "bytes": size,
    }


def measure_decision_log_line_175() -> dict[str, Any]:
    files = _find_named(DECISION_NAMES)
    if not files:
        return {
            "briefed_present_tense_collision_at_line_175": True,
            "files": [],
            "exists": False,
            "line_175": None,
            "states_collision_present_tense": False,
        }
    rel = files[0]
    lines = (REPO / rel).read_text(encoding="utf-8", errors="replace").splitlines()
    line = lines[174] if len(lines) >= 175 else None
    text = line or ""
    present = bool(
        line
        and ("31" in line or "collision" in line.lower() or "M-NN" in line or "M-" in line)
        and ("was" not in line.lower() or "is" in line.lower() or "are" in line.lower())
    )
    return {
        "briefed_present_tense_collision_at_line_175": True,
        "files": files,
        "exists": True,
        "line_count": len(lines),
        "line_175": line,
        "states_collision_present_tense": present,
    }


def _content_verdict(fact_id: str, measured: dict[str, Any]) -> str:
    if fact_id == MNN_FACT_ID:
        live = int(measured["live_collision_count"])
        if live != 31:
            return "REFUTED-AS-BRIEFED"
        return "CONFIRMED"
    if fact_id == "F-CATALOG-UNITS-2007":
        return (
            "CONFIRMED"
            if int(measured["work_units_array_length"]) == 2007
            else "REFUTED"
        )
    if fact_id == "F-DELIVERED-COUNT-4":
        return (
            "CONFIRMED" if int(measured["state_success_count"]) == 4 else "REFUTED"
        )
    if fact_id == "F-RECEIPT-SCHEMA-ABSENT":
        # Briefed: the schema file does not exist. exists=True refutes the pin.
        return "CONFIRMED" if measured["exists"] is False else "REFUTED"
    if fact_id == "F-DECISION-LOG-LINE-175-PRESENT-TENSE":
        if measured.get("exists") is not True:
            return "REFUTED"
        return (
            "CONFIRMED"
            if measured.get("states_collision_present_tense") is True
            else "REFUTED"
        )
    return "NOT-CHECKED"


def _record(
    fact_id: str,
    briefed_claim: str,
    source_probe: dict[str, str],
    verifier_probe: dict[str, str],
    source_note: str,
    measured: dict[str, Any],
) -> dict[str, Any]:
    status = pair_status(source_probe, verifier_probe)
    content = _content_verdict(fact_id, measured)
    verdict = close_verdict(status, content)
    src_fp = fingerprint_hex(source_probe)
    ver_fp = fingerprint_hex(verifier_probe)
    if status == INDEPENDENT and src_fp == ver_fp:
        raise RuntimeError(f"{fact_id}: independent status but identical hex")
    return {
        "fact_id": fact_id,
        "briefed_claim": briefed_claim,
        "source_probe": dict(source_probe),
        "verifier_probe": dict(verifier_probe),
        "source_output": source_note,
        "verifier_output": _dump(measured),
        "source_fingerprint": src_fp,
        "verifier_fingerprint": ver_fp,
        "source_tuple": list(as_tuple(source_probe)),
        "verifier_tuple": list(as_tuple(verifier_probe)),
        "pair_status": status,
        "content_verdict": content,
        "verdict": verdict,
    }


FACTS: list[tuple[str, str, dict[str, str], dict[str, str], str, Callable[[], dict]] ] = [
    (
        MNN_FACT_ID,
        (
            "Pinned ground truth: a 31-way M-NN option-id collision between "
            "07-OPTION-UNIVERSE family M and 13-ARCHITECTURE-CANDIDATES "
            "mechanisms is still live."
        ),
        {
            "tool": "markdown-reader",
            "shell": "git-bash",
            "data_field": "17-DECISION-LOG.md:175 present-tense collision count",
            "measurement_kind": "prose-literal",
        },
        {
            "tool": "python3",
            "shell": "python3",
            "data_field": "option-universe M-ids ∩ architecture-candidate bare M-ids",
            "measurement_kind": "set-cardinality",
        },
        (
            "ORIGINAL PRODUCING PROBE (reconstructed from the pin, not re-run as "
            "confirmation): git-bash markdown read of 17-DECISION-LOG.md line 175 "
            "which stated the 31-way collision in the present tense and queued it "
            "as P2-09. That prose is the source signal; it is not the verifier."
        ),
        measure_mnn_collision,
    ),
    (
        "F-DELIVERED-COUNT-4",
        (
            "Pinned ground truth: the live partition has delivered=4 "
            "(briefed 2007 / 4 / 447 / 1389 / 167)."
        ),
        {
            "tool": "ready_units.py",
            "shell": "python",
            "data_field": "output_path Path.exists",
            "measurement_kind": "existence-count",
        },
        {
            "tool": "python3-json",
            "shell": "python3",
            "data_field": "artifact.state",
            "measurement_kind": "SUCCESS-count",
        },
        (
            "ORIGINAL PRODUCING PROBE: ready_units.py existence-only delivered() "
            "(historically Path.exists on output_path). Existence is one signal; "
            "this unit's verifier reads the JSON state field instead."
        ),
        measure_delivered_success_count,
    ),
    (
        "F-RECEIPT-SCHEMA-ABSENT",
        (
            "Pinned ground truth (IMP-0433): command-center/schema/receipt.schema.json "
            "does not exist on disk."
        ),
        {
            "tool": "catalog-prose",
            "shell": "none",
            "data_field": "IMP-0433.question_or_target",
            "measurement_kind": "literal-claim",
        },
        {
            "tool": "python3-pathlib",
            "shell": "python3",
            "data_field": "Path.stat().st_size",
            "measurement_kind": "file-bytes",
        },
        (
            "ORIGINAL PRODUCING PROBE: catalog/unit prose asserting the schema "
            "file is missing. Verifier is a pathlib stat of the declared path."
        ),
        measure_receipt_schema,
    ),
    (
        "F-CATALOG-UNITS-2007",
        "Pinned ground truth: the merged work-unit catalog contains 2007 units.",
        {
            "tool": "grounding-banner",
            "shell": "none",
            "data_field": "P2-GROUNDING.md ready_units banner",
            "measurement_kind": "printed-integer",
        },
        {
            "tool": "python3-json",
            "shell": "python3",
            "data_field": "work_units array length",
            "measurement_kind": "json-array-len",
        },
        (
            "ORIGINAL PRODUCING PROBE: the P2-GROUNDING.md printed banner "
            "'units 2007'. Verifier is len(json work_units), a different field."
        ),
        measure_catalog_unit_count,
    ),
    (
        "F-DECISION-LOG-LINE-175-PRESENT-TENSE",
        (
            "Pinned ground truth: 17-DECISION-LOG.md line 175 still states the "
            "M-NN collision in the present tense."
        ),
        {
            "tool": "catalog-citation",
            "shell": "none",
            "data_field": "catalog question_or_target citing :175",
            "measurement_kind": "citation-echo",
        },
        {
            "tool": "python3",
            "shell": "python3",
            "data_field": "17-DECISION-LOG.md splitlines()[174]",
            "measurement_kind": "line-index-read",
        },
        (
            "ORIGINAL PRODUCING PROBE: catalog citations of 17-DECISION-LOG.md:175. "
            "Verifier reads the live file's line 175 (1-indexed) if the file exists."
        ),
        measure_decision_log_line_175,
    ),
]


def build_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fact_id, claim, source, verifier, note, measurer in FACTS:
        rows.append(_record(fact_id, claim, source, verifier, note, measurer()))
    return rows


def report_of(doc: dict[str, Any]) -> dict[str, Any]:
    report = doc.get("report")
    return report if isinstance(report, dict) else {}


def records_of(doc: dict[str, Any]) -> list[dict[str, Any]]:
    recs = report_of(doc).get("records") or doc.get("records") or []
    return recs if isinstance(recs, list) else []


def fingerprint_spec_of(doc: dict[str, Any]) -> dict[str, Any]:
    spec = report_of(doc).get("fingerprint_spec") or doc.get("fingerprint_spec") or {}
    return spec if isinstance(spec, dict) else {}


def controls_of(doc: dict[str, Any]) -> dict[str, Any]:
    controls = report_of(doc).get("controls") or doc.get("controls") or {}
    return controls if isinstance(controls, dict) else {}


def summarize(records: list[dict[str, Any]]) -> dict[str, int]:
    def count(key: str, value: str) -> int:
        return sum(1 for row in records if row.get(key) == value)

    return {
        "fact_count": len(records),
        "confirmed": count("verdict", "CONFIRMED"),
        "refuted": count("verdict", "REFUTED"),
        "refuted_as_briefed": count("verdict", "REFUTED-AS-BRIEFED"),
        "not_checked": count("verdict", "NOT-CHECKED"),
        "violations": count("verdict", "VIOLATION"),
        "independent_pairs": count("pair_status", INDEPENDENT),
        "same_probe_reruns": count("pair_status", "SAME-PROBE-RERUN"),
        "undeclared_sources": count("pair_status", "UNDECLARED-SOURCE"),
    }
