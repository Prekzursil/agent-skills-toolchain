"""Load candidate stopping sources and normalise them into the Boolean grammar."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from grammar import ParseError, differential, parse_normalized, synthetic_states

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

REGISTRY_NAMES = (
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
)
PROMPT_NAMES = ("_USER-PROMPTS.md", "_USER-PROMPTS.md")
PRESET_NAMES = (
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
)

IN_TREE_STOPPING_FILES = (
    "command-center/p2-wave/probes/ARC-0003/samples.json",
    "command-center/p2-wave/probes/ARC-0010/registry.json",
    "command-center/p2-wave/probes/ARC-0014/fixtures/live/workflows/wf.catalog-class.discovery-only.json",
    "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/hatch/workflows/wf.catalog-class.discovery-only.json",
    "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/hatch/council/presets/council.preset.catalog-class.editable.json",
    "command-center/phase3/A1/DESIGN.json",
    "command-center/phase3/A2/DESIGN.json",
)

INSPECT_IDS = (
    "wf-saved-agentic-repair-reliability",
    "wf-saved-bc-stage-compendium-enrichment",
    "wf-saved-codex-auth-research-fanout",
    "wf-saved-design-gate",
    "wf-saved-harness-self-improve-sweep",
)

# Live 08-WORKFLOW-CANDIDATE-REGISTRY.json is not on this Linux worktree.
# command-center/_wfa2_entries.json is the 284-id estate list (no stopping fields).
ESTATE_ENTRIES = "command-center/_wfa2_entries.json"
SECTION_FAMILY = {
    "A": "A-saved-workflow",
    "B": "B-repo-workflow",
    "C": "C-repo-tool",
    "D": "D-harness-runtime",
    "E": "E-agent",
    "F": "F-plugin",
    "G": "G-skill",
    "H": "H-executed-corpus",
    "I": "I-command",
}

PLANTED = (
    {
        "id": "planted-no-stop",
        "kind": "planted-control",
        "raw_stopping": None,
        "note": "candidate with no stopping rule; must record NONE, not a blank",
    },
    {
        "id": "planted-degenerate-tautology",
        "kind": "planted-control",
        "source_prose": "(unique_ideas >= 0) OR (unique_ideas < 0)",
        "note": "always-true on the 20 numeric states; must flag DEGENERATE",
    },
    {
        "id": "planted-degenerate-contradiction",
        "kind": "planted-control",
        "source_prose": "(unique_ideas >= 0) AND (unique_ideas < 0)",
        "note": "always-false on the 20 numeric states; must flag DEGENERATE",
    },
    {
        "id": "planted-runtime-over-prior-rounds",
        "kind": "planted-control",
        "inexpressible": True,
        "source_prose": "prior_rounds[-1].consensus == true && score(prior_rounds) > threshold",
        "note": "runtime predicate over prior rounds is UNKNOWN-NEEDS-PROBE, not approximated",
    },
)


def _corpus_roots() -> list[Path]:
    home = Path.home()
    return [
        HERE / "fixtures" / "harness-restore-20260806",
        home / ".claude" / "harness-restore-20260806",
        REPO / "harness-restore-20260806",
        Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
        Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
        REPO,
        REPO / "command-center",
    ]


def find_named(names: tuple[str, ...]) -> dict[str, Any]:
    tried: list[str] = []
    for root in _corpus_roots():
        for name in names:
            cand = root / name
            tried.append(str(cand))
            if cand.is_file() and cand.stat().st_size > 0:
                return {
                    "path": str(cand),
                    "present": True,
                    "bytes": cand.stat().st_size,
                    "tried": tried,
                }
    return {"path": None, "present": False, "bytes": 0, "tried": tried}


def _candidates_from_registry(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("candidates") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        out.append(
            {
                "id": str(row["id"]),
                "kind": "registry",
                "family": row.get("family"),
                "name": row.get("name"),
                "does": row.get("does"),
                "mechanisms": row.get("mechanisms"),
                "notes": row.get("notes"),
                "raw_stopping": row.get("stopping")
                or row.get("stop_rule")
                or row.get("stop_rules")
                or row.get("stopping_rule"),
            }
        )
    return out


def _walk_stopping(obj: Any, parent_id: str | None, source: str, acc: list) -> None:
    if isinstance(obj, dict):
        cid = obj.get("id") or parent_id
        stopping = obj.get("stopping")
        if stopping is not None and cid:
            acc.append(
                {
                    "id": str(cid),
                    "kind": "in-tree",
                    "source_path": source,
                    "raw_stopping": stopping,
                }
            )
        for v in obj.values():
            _walk_stopping(v, str(cid) if cid else parent_id, source, acc)
    elif isinstance(obj, list):
        for item in obj:
            _walk_stopping(item, parent_id, source, acc)


def in_tree_stopping() -> list[dict[str, Any]]:
    acc: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rel in IN_TREE_STOPPING_FILES:
        path = REPO / rel
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        found: list[dict[str, Any]] = []
        _walk_stopping(data, None, rel, found)
        for row in found:
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            acc.append(row)
    return acc


def _prose_from_stopping(raw: Any) -> tuple[str | None, str, str | None]:
    if raw is None or raw == "" or raw == {} or raw == []:
        return None, "NONE", "no stopping rule recorded"
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None, "NONE", "blank stopping string"
        low = text.lower()
        if "prior_round" in low or "runtime_predicate" in low:
            return text, "UNKNOWN-NEEDS-PROBE", "runtime predicate over prior rounds"
        return text, "EXTRACTED", None
    if isinstance(raw, dict):
        if raw.get("rule") == "runtime_predicate" or raw.get("over") == "prior_rounds":
            pred = raw.get("predicate") or json.dumps(raw, sort_keys=True)
            return (
                str(pred),
                "UNKNOWN-NEEDS-PROBE",
                "runtime predicate over prior rounds; not approximated as ANY/ALL/NOT",
            )
        if "max_rounds" in raw and isinstance(raw["max_rounds"], (int, float)):
            n = int(raw["max_rounds"])
            return f"rounds >= {n}", "EXTRACTED", "normalised from stopping.max_rounds"
        if "max_stages" in raw and isinstance(raw["max_stages"], (int, float)):
            n = int(raw["max_stages"])
            return f"stages >= {n}", "EXTRACTED", "normalised from stopping.max_stages"
        keys = set(raw.keys())
        if keys <= {"on_error", "on_timeout", "on_unresolved"}:
            return None, "NONE", "handlers only; no boolean stopping predicate"
        return (
            json.dumps(raw, sort_keys=True),
            "UNKNOWN-NEEDS-PROBE",
            "stopping object has no ANY/ALL/NOT-expressible predicate",
        )
    return None, "NONE", f"unsupported-stopping-type:{type(raw).__name__}"


def _extract_prose_from_registry_row(row: dict[str, Any]) -> tuple[str | None, str, str | None]:
    if row.get("raw_stopping") is not None:
        return _prose_from_stopping(row["raw_stopping"])
    blobs = []
    for key in ("does", "mechanisms", "notes"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            blobs.append(val)
        elif isinstance(val, list):
            blobs.extend(str(x) for x in val if x)
    text = "\n".join(blobs).lower()
    needles = (
        "stop when",
        "stopping",
        "halt when",
        "until consensus",
        "max_rounds",
        "max rounds",
        "unique_ideas",
        "unique_ideas",
    )
    if any(n in text for n in needles):
        return (
            None,
            "UNKNOWN-NEEDS-PROBE",
            "stopping language in prose fields but no typed predicate",
        )
    return None, "NONE", "no stopping field; inspect census stop_rules=0"


def normalise_candidate(row: dict[str, Any], states: list[dict[str, Any]]) -> dict[str, Any]:
    cid = row["id"]
    if row.get("inexpressible"):
        return {
            "id": cid,
            "kind": row.get("kind"),
            "status": "UNKNOWN-NEEDS-PROBE",
            "source_prose": row.get("source_prose"),
            "normalized": None,
            "degenerate": None,
            "differential": None,
            "note": row.get("note"),
        }

    if "raw_stopping" in row:
        prose, status, note = _prose_from_stopping(row["raw_stopping"])
    elif row.get("source_prose"):
        prose, status, note = row["source_prose"], "EXTRACTED", row.get("note")
    else:
        prose, status, note = _extract_prose_from_registry_row(row)

    rec = {
        "id": cid,
        "kind": row.get("kind"),
        "family": row.get("family"),
        "source_path": row.get("source_path"),
        "status": status,
        "source_prose": prose,
        "normalized": None,
        "degenerate": None,
        "differential": None,
        "note": note or row.get("note"),
    }
    if status != "EXTRACTED" or not prose:
        return rec
    try:
        tree = parse_normalized(prose)
        diff = differential(prose, states)
    except ParseError as exc:
        rec["status"] = "UNKNOWN-NEEDS-PROBE"
        rec["note"] = f"parse-failed:{exc}; not approximated"
        return rec
    rec["normalized"] = tree
    rec["degenerate"] = diff["degenerate"]
    rec["differential"] = {
        "n_states": diff["n_states"],
        "n_true": diff["n_true"],
        "n_false": diff["n_false"],
        "disagreements": diff["disagreements"],
        "errors": diff["errors"],
    }
    if diff["errors"]:
        rec["status"] = "UNKNOWN-NEEDS-PROBE"
        rec["note"] = f"eval-error:{diff['errors'][:2]}"
    elif diff["disagreements"]:
        rec["status"] = "MISNORMALISED"
        rec["note"] = "two evaluators disagreed on at least one synthetic state"
    elif diff["degenerate"]:
        rec["status"] = "DEGENERATE"
        rec["note"] = f"degenerate:{diff['degenerate']} on 20 synthetic states"
    return rec


def load_estate_id_list() -> dict[str, Any]:
    """284 candidate ids from _wfa2_entries.json. Not the typed 08-registry."""
    path = REPO / ESTATE_ENTRIES
    if not path.is_file() or path.stat().st_size <= 0:
        return {"present": False, "path": ESTATE_ENTRIES, "n": 0, "rows": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"present": False, "path": ESTATE_ENTRIES, "n": 0, "rows": []}
    if not isinstance(data, list):
        return {"present": False, "path": ESTATE_ENTRIES, "n": 0, "rows": []}
    rows: list[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        section = str(row.get("section") or "")
        rows.append(
            {
                "id": str(row["id"]),
                "kind": "estate-id-list",
                "family": SECTION_FAMILY.get(section, section or None),
                "name": row.get("name"),
                "raw_stopping": None,
                "note": (
                    "id from command-center/_wfa2_entries.json; the id-list has "
                    "no stopping field. WFA-0042 inspect census stop_rules nonempty=0. "
                    "Recorded NONE rather than invented."
                ),
            }
        )
    return {
        "present": True,
        "path": ESTATE_ENTRIES,
        "bytes": path.stat().st_size,
        "n": len(rows),
        "rows": rows,
    }


def inspect_census() -> dict[str, Any]:
    path = REPO / "command-center/p2-wave/probes/WFA-0042/_inspect_source_out.json"
    if not path.is_file():
        return {"present": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"present": False, "path": path.relative_to(REPO).as_posix()}
    nonempty = data.get("dim_nonempty") or data.get("nonempty_dims") or {}
    return {
        "present": True,
        "path": path.relative_to(REPO).as_posix(),
        "json_n": data.get("json_n") or data.get("n_records"),
        "source_bytes": data.get("source_bytes") or data.get("bytes"),
        "source_sha256": data.get("source_sha256") or data.get("sha256"),
        "stop_rules_nonempty": nonempty.get("stop_rules", 0),
        "families": data.get("json_family_counts") or data.get("family_counts"),
    }


def build_records() -> dict[str, Any]:
    states = synthetic_states()
    registry_hit = find_named(REGISTRY_NAMES)
    prompt_hit = find_named(PROMPT_NAMES)
    preset_hit = find_named(PRESET_NAMES)
    census = inspect_census()

    estate = load_estate_id_list()
    raw_rows: list[dict[str, Any]] = []
    if registry_hit["present"]:
        raw_rows.extend(_candidates_from_registry(Path(registry_hit["path"])))
    elif estate["rows"]:
        raw_rows.extend(estate["rows"])
    else:
        for cid in INSPECT_IDS:
            raw_rows.append(
                {
                    "id": cid,
                    "kind": "inspect-sample",
                    "raw_stopping": None,
                    "note": "live registry absent; id from WFA-0042 inspect sample; stop_rules census 0",
                }
            )

    raw_rows.extend(in_tree_stopping())
    raw_rows.extend(PLANTED)

    seen: set[str] = set()
    records = []
    for row in raw_rows:
        cid = row["id"]
        if cid in seen:
            continue
        seen.add(cid)
        records.append(normalise_candidate(row, states))

    counts: dict[str, int] = {}
    for rec in records:
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
    return {
        "registry": registry_hit,
        "prompts": prompt_hit,
        "presets": preset_hit,
        "estate_id_list": {
            "present": estate["present"],
            "path": estate.get("path"),
            "n": estate.get("n"),
            "bytes": estate.get("bytes"),
        },
        "inspect_census": census,
        "records": records,
        "counts": counts,
        "n_records": len(records),
        "n_states": len(states),
    }
