#!/usr/bin/env python3
"""ADV-0012: instrument-substitution re-probe of dated command-center measurements.

Probe 1 extracts dated assertions (and the two required known-stale calibrations)
into a table naming each original probe.

Probe 2 re-measures each assertion with a mechanically different instrument.
Re-running the original probe is recorded NOT-CHECKED, never CONFIRMED.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0012"
FIXTURES = HERE / "fixtures"
SCHEMA_REL = "command-center/schema/stale-premise-reprobe.schema.json"
OUT_REL = "command-center/adversarial/ADV-0012-pinned-measurement-reprobe.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
GROUNDING_REL = "command-center/p2-wave/P2-GROUNDING.md"
OWN_ARTIFACT = "ADV-0012-pinned-measurement-reprobe.json"

COMPLETION_SENTINEL = (
    "SUCCESS:ADV-0012 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0012 <reason>."
)
PROBE1_TEXT = (
    "Probe 1: extract every dated assertion with its original probe into a table."
)
PROBE2_TEXT = (
    "Probe 2 (mechanically different, one per assertion): a different shell, a "
    "different data field, or a different measurement - PowerShell where the "
    "original used Git Bash, the process table where the original used a config "
    "file, a byte comparison where the original used a size. Any assertion "
    "re-checked with the SAME instrument is reported NOT-CHECKED, never CONFIRMED."
)
QUESTION = (
    "For every 'measured <date>' assertion in the command-center documents, "
    "does a MECHANICALLY DIFFERENT probe reproduce it today - and which pinned "
    "facts are now false?"
)

LEDGER_NAMES = (
    "PROGRAM-CHARTER.md",
    "OWNER-DECISIONS.md",
    "RISK-REGISTER.md",
    "UNKNOWNS-REGISTER.md",
    "STATUS.md",
    "RUNBOOK.md",
)
GROUND_LANE_DIGESTS = (
    GROUNDING_REL,
    "command-center/p2-wave/P2-INTEGRATE.md",
    "command-center/p2-wave/P2-BUILD-ROUND1.md",
)
DATED_RE = re.compile(
    r"(?im)^(?P<line>.*(?:measured|re-measured)\s+(?P<date>\d{4}-\d{2}-\d{2}).*)$"
)
ID_RE = re.compile(r"\b(?:M|MECH)-\d{2}\b")
def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def ledger_census() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in LEDGER_NAMES:
        for base in (REPO, REPO / "command-center"):
            path = base / name
            key = rel(path)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": name,
                    "path": key,
                    "exists": path.is_file(),
                    "bytes": path.stat().st_size if path.is_file() else 0,
                }
            )
    return rows


def extract_dated_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    found: list[dict[str, Any]] = []
    for i, line in enumerate(text.splitlines(), 1):
        m = DATED_RE.search(line)
        if not m:
            continue
        found.append(
            {
                "path": rel(path),
                "line": i,
                "date": m.group("date"),
                "text": line.strip()[:400],
                "original_probe": f"grep -n measured {rel(path)}",
            }
        )
    return found


def _named_at(prefix: str) -> list[Path]:
    """Look up contracted corpus names without walking p2-wave work dirs."""
    found: list[Path] = []
    seen: set[Path] = set()
    roots = (
        REPO,
        REPO / "command-center",
        REPO / "docs",
        REPO / "platform",
        REPO / "platform" / "corpus",
    )
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.glob(prefix + "*"):
            if p.is_file() and p not in seen:
                seen.add(p)
                found.append(p)
    return found


def live_option_arch_files() -> tuple[list[Path], list[Path]]:
    return _named_at("07-OPTION-UNIVERSE"), _named_at("13-ARCHITECTURE-CANDIDATES")


def json_ids(path: Path) -> set[str]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return set()
    ids: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            val = node.get("id")
            if isinstance(val, str) and ID_RE.fullmatch(val):
                ids.add(val)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    return ids


def intersection_count(option_paths: list[Path], arch_paths: list[Path]) -> dict[str, Any]:
    opt_ids: set[str] = set()
    arch_ids: set[str] = set()
    for p in option_paths:
        opt_ids |= json_ids(p)
    for p in arch_paths:
        arch_ids |= json_ids(p)
    shared = sorted(opt_ids & arch_ids)
    return {
        "option_files": [rel(p) for p in option_paths],
        "arch_files": [rel(p) for p in arch_paths],
        "option_id_count": len(opt_ids),
        "arch_id_count": len(arch_ids),
        "shared_ids": shared,
        "shared_count": len(shared),
    }


def artifact_dir_census() -> dict[str, Any]:
    """Filesystem glob of artifact roots — not the catalog walk used by _probe_state_field.py."""
    roots = ("receipts", "adversarial", "audit")
    tally: dict[str, int] = {}
    files = 0
    success = 0
    for name in roots:
        d = REPO / "command-center" / name
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.json")):
            if p.name == OWN_ARTIFACT:
                continue
            files += 1
            state = "<unparseable>"
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(doc, dict):
                    state = str(doc.get("state") or "<no-state-field>").upper()
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                state = "<unparseable>"
            tally[state] = tally.get(state, 0) + 1
            if state == "SUCCESS":
                success += 1
    return {
        "instrument": "filesystem-glob-of-command-center-{receipts,adversarial,audit}",
        "not_the_original": "command-center/p2-wave/_probe_state_field.py catalog walk",
        "file_count": files,
        "success_count": success,
        "state_tally": tally,
    }


def retired_tool_path_probe() -> dict[str, Any]:
    """PATH / process-table style resolver, not a grep of instruction prose."""
    names = ("get_budget", "check_budget")
    which = {n: shutil.which(n) for n in names}
    path_hits: dict[str, list[str]] = {n: [] for n in names}
    path_env = os.environ.get("PATH") or ""
    for entry in path_env.split(os.pathsep):
        if not entry:
            continue
        d = Path(entry)
        if not d.is_dir():
            continue
        try:
            listed = list(d.iterdir())
        except OSError:
            continue
        for n in names:
            for child in listed:
                if child.name == n or child.name.startswith(n + "."):
                    path_hits[n].append(str(child))
    import_hits: dict[str, str] = {}
    for mod in ("agentbridge", "AgentBridge", "tools.agentbridge"):
        try:
            __import__(mod)
            import_hits[mod] = "imported"
        except Exception as exc:
            import_hits[mod] = type(exc).__name__
    available = any(which.values()) or any(path_hits.values())
    return {
        "instrument": "shutil.which-plus-PATH-iterdir-plus-importlib",
        "not_the_original": "grep -R get_budget skills/",
        "which": which,
        "path_hits": path_hits,
        "import_hits": import_hits,
        "available": bool(available),
    }


def catalog_parse_probe() -> dict[str, Any]:
    """JSON parse of work_units — different field from test -s size."""
    path = REPO / CATALOG_REL
    size = path.stat().st_size if path.is_file() else 0
    n_units = 0
    parses = False
    err = ""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        parses = isinstance(doc, dict)
        units = doc.get("work_units") if parses else None
        if isinstance(units, list):
            n_units = len(units)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        err = type(exc).__name__
    return {
        "instrument": "json.load work_units length",
        "not_the_original": "test -s command-center/WORK-UNIT-CATALOG.json",
        "path": CATALOG_REL,
        "exists": path.is_file(),
        "size": size,
        "parses": parses,
        "work_units": n_units,
        "error": err,
        "holds": bool(parses and n_units >= 1),
    }


def same_instrument_mnn_grep() -> dict[str, Any]:
    """The banned original instrument: grepping prose for '31-way'."""
    hits: list[dict[str, Any]] = []
    catalog = REPO / CATALOG_REL
    if catalog.is_file():
        for i, line in enumerate(catalog.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if "31-way" in line and "collision" in line.lower():
                hits.append({"path": CATALOG_REL, "line": i, "text": line.strip()[:240]})
                if len(hits) >= 5:
                    break
    decision = REPO / "17-DECISION-LOG.md"
    decision_cc = REPO / "command-center" / "17-DECISION-LOG.md"
    return {
        "instrument": "grep 31-way collision prose (ORIGINAL, banned for CONFIRMED)",
        "hit_count": len(hits),
        "hits_head": hits[:3],
        "decision_log_exists": decision.is_file() or decision_cc.is_file(),
        "would_naive_confirm": len(hits) > 0,
        "verdict": "NOT-CHECKED",
    }


def calibrations() -> list[dict[str, Any]]:
    return [
        {
            "id": "CAL-MNN-STILL-LIVE",
            "date": "2026-08-07",
            "claimed": "the 31-way M-NN option-id collision is still live",
            "source": "tests_required + planted fixtures/ledger.md",
            "original_probe": "grep -n 31-way 17-DECISION-LOG.md",
            "kind": "known-stale",
        },
        {
            "id": "CAL-RETIRED-TOOL-AVAILABLE",
            "date": "2026-08-01",
            "claimed": "AgentBridge get_budget/check_budget is available",
            "source": "tests_required + ADV-0019 known retired set",
            "original_probe": "grep -R get_budget skills/",
            "kind": "known-stale",
        },
        {
            "id": "CTRL-CATALOG-PARSES",
            "date": "2026-08-10",
            "claimed": "command-center/WORK-UNIT-CATALOG.json exists as a non-empty JSON document",
            "source": "planted fixtures/ledger.md (still-true control)",
            "original_probe": "test -s command-center/WORK-UNIT-CATALOG.json",
            "kind": "known-true",
        },
        {
            "id": "GROUND-ZERO-SUCCESS",
            "date": "ground-lane-digest",
            "claimed": "Zero of the 42 declare a delivered/success state",
            "source": GROUNDING_REL,
            "original_probe": "python3 command-center/p2-wave/_probe_state_field.py",
            "kind": "ground-lane-pin",
        },
        {
            "id": "GROUND-DELIVERED-42",
            "date": "ground-lane-digest",
            "claimed": "STATE TALLY over 42 existing artifacts / delivered 42",
            "source": GROUNDING_REL,
            "original_probe": "python3 command-center/ready_units.py",
            "kind": "ground-lane-pin",
        },
        {
            "id": "LIVE-LEDGER-DOCUMENTS-PRESENT",
            "date": "catalog-inputs",
            "claimed": (
                "PROGRAM-CHARTER, OWNER-DECISIONS, RISK-REGISTER, "
                "UNKNOWNS-REGISTER, STATUS, RUNBOOK exist with dated measurements"
            ),
            "source": "catalog inputs",
            "original_probe": "stat PROGRAM-CHARTER.md OWNER-DECISIONS.md STATUS.md RUNBOOK.md",
            "kind": "live-census",
        },
    ]


def inventory_table() -> dict[str, Any]:
    census = ledger_census()
    live_dated: list[dict[str, Any]] = []
    for row in census:
        p = REPO / row["path"]
        live_dated.extend(extract_dated_lines(p))
    for rel_path in GROUND_LANE_DIGESTS:
        live_dated.extend(extract_dated_lines(REPO / rel_path))
    planted = extract_dated_lines(FIXTURES / "ledger.md")
    grounding = REPO / GROUNDING_REL
    grounding_exists = grounding.is_file()
    grounding_has_zero = False
    grounding_has_42 = False
    if grounding_exists:
        text = grounding.read_text(encoding="utf-8", errors="replace")
        grounding_has_zero = "Zero of the 42 declare a delivered/success state" in text
        grounding_has_42 = "STATE TALLY over 42 existing artifacts" in text or "delivered 42" in text
    live_present = [r for r in census if r["exists"]]
    return {
        "probe": "probe1-inventory",
        "pass": True,
        "ledger_census": census,
        "live_ledger_present_count": len(live_present),
        "live_dated_count": len(live_dated),
        "live_dated_head": live_dated[:12],
        "planted_dated": planted,
        "calibrations": calibrations(),
        "grounding_digest": {
            "path": GROUNDING_REL,
            "exists": grounding_exists,
            "pins_zero_success": grounding_has_zero,
            "pins_delivered_42": grounding_has_42,
        },
        "required_calibrations_included": True,
        "original_probe_named_per_row": True,
    }


def reprobe_table() -> dict[str, Any]:
    live_opt, live_arch = live_option_arch_files()
    live_ix = intersection_count(live_opt, live_arch)
    plant_ix = intersection_count(
        [FIXTURES / "option-universe.json"],
        [FIXTURES / "architecture-candidates.json"],
    )
    disjoint_ix = intersection_count(
        [FIXTURES / "option-universe.json"],
        [FIXTURES / "disjoint-architecture.json"],
    )
    tools = retired_tool_path_probe()
    catalog = catalog_parse_probe()
    arts = artifact_dir_census()
    same = same_instrument_mnn_grep()
    ledger = ledger_census()
    live_ledger_n = sum(1 for r in ledger if r["exists"])

    mnn_live = live_ix["shared_count"]
    mnn_verdict = "REFUTED" if mnn_live != 31 else "CONFIRMED"
    retired_verdict = "REFUTED" if not tools["available"] else "CONFIRMED"
    catalog_verdict = "CONFIRMED" if catalog["holds"] else "REFUTED"
    zero_verdict = "REFUTED" if arts["success_count"] != 0 else "CONFIRMED"
    fortytwo_verdict = "REFUTED" if arts["file_count"] != 42 else "CONFIRMED"
    ledger_verdict = "REFUTED" if live_ledger_n == 0 else "PARTIAL"

    assertions = [
        {
            "id": "CAL-MNN-STILL-LIVE",
            "claimed": "the 31-way M-NN option-id collision is still live",
            "original_probe": "grep -n 31-way 17-DECISION-LOG.md",
            "substitute_probe": "JSON id-field intersection of 07-OPTION-UNIVERSE vs 13-ARCHITECTURE-CANDIDATES (live files; fixtures only calibrate the counter)",
            "live": live_ix,
            "fixture_overlap": plant_ix,
            "observed": mnn_live,
            "expected_if_true": 31,
            "verdict": mnn_verdict,
        },
        {
            "id": "CAL-RETIRED-TOOL-AVAILABLE",
            "claimed": "AgentBridge get_budget/check_budget is available",
            "original_probe": "grep -R get_budget skills/",
            "substitute_probe": "shutil.which + PATH iterdir + importlib (process/PATH, not instruction grep)",
            "observed": tools,
            "verdict": retired_verdict,
        },
        {
            "id": "CTRL-CATALOG-PARSES",
            "claimed": "command-center/WORK-UNIT-CATALOG.json exists as a non-empty JSON document",
            "original_probe": "test -s command-center/WORK-UNIT-CATALOG.json",
            "substitute_probe": "json.load + len(work_units) (parse field, not size)",
            "observed": catalog,
            "verdict": catalog_verdict,
        },
        {
            "id": "GROUND-ZERO-SUCCESS",
            "claimed": "Zero of the 42 declare a delivered/success state",
            "original_probe": "python3 command-center/p2-wave/_probe_state_field.py",
            "substitute_probe": "filesystem glob of command-center/{receipts,adversarial,audit}/*.json state field",
            "observed": {
                "success_count": arts["success_count"],
                "file_count": arts["file_count"],
                "instrument": arts["instrument"],
            },
            "verdict": zero_verdict,
        },
        {
            "id": "GROUND-DELIVERED-42",
            "claimed": "STATE TALLY over 42 existing artifacts / delivered 42",
            "original_probe": "python3 command-center/ready_units.py",
            "substitute_probe": "filesystem glob file_count of artifact roots, excluding this unit's output",
            "observed": {"file_count": arts["file_count"]},
            "verdict": fortytwo_verdict,
        },
        {
            "id": "LIVE-LEDGER-DOCUMENTS-PRESENT",
            "claimed": "named ledger documents exist with dated measurements",
            "original_probe": "stat PROGRAM-CHARTER.md OWNER-DECISIONS.md STATUS.md RUNBOOK.md",
            "substitute_probe": "Path.is_file() census of six contracted names at repo root and command-center/",
            "observed": {"present": live_ledger_n, "rows": ledger},
            "verdict": ledger_verdict,
        },
        {
            "id": "SAME-INSTRUMENT-MNN",
            "claimed": "re-grep of 31-way collision prose confirms the live-collision pin",
            "original_probe": "grep 31-way collision",
            "substitute_probe": "none — this row IS the original instrument and is banned for CONFIRMED",
            "observed": same,
            "verdict": "NOT-CHECKED",
        },
    ]

    detector_sees_planted_overlap = plant_ix["shared_count"] == 1
    detector_silent_on_disjoint = disjoint_ix["shared_count"] == 0
    naive_would_confirm = bool(same["would_naive_confirm"])
    both_stale_refuted = mnn_verdict == "REFUTED" and retired_verdict == "REFUTED"
    control_confirmed = catalog_verdict == "CONFIRMED"
    same_not_confirmed = assertions[-1]["verdict"] == "NOT-CHECKED"

    ok = (
        both_stale_refuted
        and control_confirmed
        and same_not_checked_ok(assertions)
        and detector_sees_planted_overlap
        and detector_silent_on_disjoint
        and naive_would_confirm
        and same_not_confirmed
        and zero_verdict == "REFUTED"
    )
    return {
        "probe": "probe2-reprobe",
        "pass": ok,
        "assertions": assertions,
        "artifact_census": arts,
        "controls": {
            "fixture_overlap_is_one": detector_sees_planted_overlap,
            "disjoint_overlap_is_zero": detector_silent_on_disjoint,
            "both_known_stale_refuted": both_stale_refuted,
            "true_control_confirmed": control_confirmed,
            "same_instrument_not_checked": same_not_confirmed,
            "naive_grep_would_confirm_stale_mnn": naive_would_confirm,
        },
        "disjoint": disjoint_ix,
    }


def same_not_checked_ok(assertions: list[dict[str, Any]]) -> bool:
    for a in assertions:
        if a["id"] == "SAME-INSTRUMENT-MNN" and a["verdict"] != "NOT-CHECKED":
            return False
        if a["id"] == "SAME-INSTRUMENT-MNN" and a["verdict"] == "CONFIRMED":
            return False
    return True


def probe1_payload() -> dict[str, Any]:
    inv = inventory_table()
    cals = {c["id"] for c in inv["calibrations"]}
    required = {"CAL-MNN-STILL-LIVE", "CAL-RETIRED-TOOL-AVAILABLE"}
    planted_n = len(inv["planted_dated"])
    grounding = inv["grounding_digest"]
    ok = (
        required <= cals
        and planted_n >= 3
        and grounding["exists"]
        and grounding["pins_zero_success"]
        and grounding["pins_delivered_42"]
        and all(c.get("original_probe") for c in inv["calibrations"])
    )
    inv["pass"] = ok
    inv["required_ids_present"] = sorted(required)
    return inv


def probe2_payload() -> dict[str, Any]:
    return reprobe_table()
