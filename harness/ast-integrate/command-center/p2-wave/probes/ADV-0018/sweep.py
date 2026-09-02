"""Filesystem vault sweep for ADV-0018.

Probe 1 retrieves notes by topic and diffs load-bearing assertions against
live measurements. Probe 2 reads superseded_by / valid_as_of from file
bytes, not from a search snippet. MCP basic-memory is not mounted here;
the catalog itself prefers a vault FILESYSTEM read over semantic recall.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
VAULT_DIR = HERE / "vault"
DECISION_LOG = REPO / "17-DECISION-LOG.md"
OPTION_M = REPO / "command-center/option-id/07-OPTION-UNIVERSE.family-M-slice.md"
ARCH_POST = REPO / "command-center/option-id/13-ARCHITECTURE-CANDIDATES.post-fix-slice.md"
ARCH_PRE = REPO / "command-center/option-id/13-ARCHITECTURE-CANDIDATES.pre-fix-slice.md"
OUT_REL = "command-center/adversarial/ADV-0018-memory-vault-contradiction-sweep.json"
SCHEMA_REL = "command-center/schema/stale-premise-reprobe.schema.json"
UID = "ADV-0018"
RECALL_TOKEN = "VAULT-RECALL-PRESENT"
RECALL_NEEDLE = "ADV-0018-RECALL-TOKEN=VAULT-RECALL-PRESENT"

M_ID_RE = re.compile(r"\bM-(\d{2})\b")
MECH_ID_RE = re.compile(r"\bMECH-(\d{2})\b")
ASSERT_RE = re.compile(
    r"probe-assert:\s*([A-Za-z_][A-Za-z0-9_]*)\s*==\s*(\S+)",
    re.IGNORECASE,
)
COLLISION_LIVE_RE = re.compile(
    r"collision.{0,160}\bis live\b",
    re.IGNORECASE | re.DOTALL,
)
FM_KEY_RE = re.compile(
    r"^(superseded_by|supersedes|valid_as_of|status|note_id|title|date)\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)
SECTION_RE = re.compile(r"^## (DL-\S+)", re.MULTILINE)


def catalog_unit() -> dict:
    doc = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for unit in doc.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UID:
            return unit
    raise SystemExit("FAILED:ADV-0018 catalog unit missing")


def coerce_value(raw: str) -> Any:
    text = raw.strip().rstrip(".")
    low = text.lower()
    if low in {"true", "false"}:
        return low == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def parse_frontmatter(text: str) -> tuple[dict[str, str], str, int]:
    lines = text.splitlines()
    meta: dict[str, str] = {}
    if lines and lines[0].strip() == "---":
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is not None:
            for line in lines[1:end]:
                match = FM_KEY_RE.match(line)
                if match:
                    meta[match.group(1).lower()] = match.group(2).strip()
            body = "\n".join(lines[end + 1 :])
            return meta, body, end + 2
    consumed = 0
    for i, line in enumerate(lines):
        if not line.strip():
            if meta:
                consumed = i + 1
                break
            continue
        match = FM_KEY_RE.match(line)
        if match:
            meta[match.group(1).lower()] = match.group(2).strip()
            consumed = i + 1
            continue
        consumed = i
        break
    body = "\n".join(lines[consumed:])
    return meta, body, consumed + 1


def extract_assertions(body: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for match in ASSERT_RE.finditer(body):
        key = match.group(1)
        expected = coerce_value(match.group(2))
        tag = (key, str(expected))
        if tag in seen:
            continue
        seen.add(tag)
        found.append({"key": key, "expected": expected, "source": "probe-assert"})
    if COLLISION_LIVE_RE.search(body):
        tag = ("collision_live", "True")
        if tag not in seen:
            seen.add(tag)
            found.append(
                {"key": "collision_live", "expected": True, "source": "prose-is-live"}
            )
    return found


def ids_from(text: str, pattern: re.Pattern[str], prefix: str) -> set[str]:
    return {f"{prefix}-{m.group(1)}" for m in pattern.finditer(text)}


def _rel(path: Path) -> str | None:
    if not path.is_file() and not path.is_dir():
        return None
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def live_measurements() -> dict[str, Any]:
    option_text = OPTION_M.read_text(encoding="utf-8") if OPTION_M.is_file() else ""
    post_text = ARCH_POST.read_text(encoding="utf-8") if ARCH_POST.is_file() else ""
    pre_text = ARCH_PRE.read_text(encoding="utf-8") if ARCH_PRE.is_file() else ""
    option_ids = ids_from(option_text, M_ID_RE, "M")
    arch_ids = ids_from(post_text, M_ID_RE, "M") | ids_from(post_text, MECH_ID_RE, "MECH")
    pre_ids = ids_from(pre_text, M_ID_RE, "M")
    collision = sorted(option_ids & arch_ids)
    historical = sorted(option_ids & pre_ids)
    return {
        "option_family_m_count": len(option_ids),
        "collision_count": len(collision),
        "collision_live": len(collision) > 0,
        "option_ids_sample": sorted(option_ids)[:8],
        "arch_current_ids_sample": sorted(arch_ids)[:8],
        "shared_current_ids": collision,
        "historical_pre_fix_shared_count": len(historical),
        "option_path": _rel(OPTION_M),
        "arch_current_path": _rel(ARCH_POST),
        "arch_historical_path": _rel(ARCH_PRE),
        "recall_token": RECALL_TOKEN,
    }


def extra_vault_roots() -> list[Path]:
    env = os.environ.get("BASIC_MEMORY_DIR") or os.environ.get("BASIC_MEMORY_HOME")
    candidates = [
        Path(env) if env else None,
        Path.home() / ".basic-memory",
        Path.home() / "basic-memory",
        Path("/opt/p2/basic-memory"),
        REPO / "basic-memory",
        REPO / "memory-vault",
    ]
    roots: list[Path] = []
    for path in candidates:
        if path is not None and path.is_dir():
            roots.append(path)
    return roots


def load_markdown_note(path: Path, store: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    meta, body, body_line = parse_frontmatter(text)
    try:
        rel = path.relative_to(REPO).as_posix()
    except ValueError:
        rel = str(path)
    nid = meta.get("note_id") or path.stem
    return {
        "note_id": nid,
        "path": rel,
        "store": store,
        "frontmatter": meta,
        "superseded_by": (meta.get("superseded_by") or "").strip() or None,
        "valid_as_of": (meta.get("valid_as_of") or "").strip() or None,
        "status": (meta.get("status") or "").strip() or None,
        "body": body,
        "body_start_line": body_line,
        "text": text,
        "assertions": extract_assertions(body),
        "sha256_head": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
    }


def load_decision_log_notes() -> list[dict[str, Any]]:
    if not DECISION_LOG.is_file():
        return []
    text = DECISION_LOG.read_text(encoding="utf-8")
    matches = list(SECTION_RE.finditer(text))
    notes: list[dict[str, Any]] = []
    rel = DECISION_LOG.relative_to(REPO).as_posix()
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end]
        nid = match.group(1)
        _, _, rest = chunk.partition("\n")
        meta, body, body_line = parse_frontmatter(rest)
        line_no = text[:start].count("\n") + 1
        notes.append(
            {
                "note_id": nid,
                "path": rel,
                "store": "decision-log",
                "frontmatter": meta,
                "superseded_by": (meta.get("superseded_by") or "").strip() or None,
                "valid_as_of": (meta.get("valid_as_of") or "").strip() or None,
                "status": (meta.get("status") or "").strip() or None,
                "body": body,
                "body_start_line": line_no + body_line,
                "section_line": line_no,
                "text": chunk,
                "assertions": extract_assertions(body),
                "sha256_head": hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:16],
            }
        )
    return notes


def load_all_notes() -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    if VAULT_DIR.is_dir():
        for path in sorted(VAULT_DIR.glob("*.md")):
            notes.append(load_markdown_note(path, store="fixture-vault"))
    notes.extend(load_decision_log_notes())
    seen = {n["path"] + "#" + n["note_id"] for n in notes}
    for root in extra_vault_roots():
        for path in sorted(root.rglob("*.md")):
            if not path.is_file():
                continue
            note = load_markdown_note(path, store=f"extra:{root}")
            key = note["path"] + "#" + note["note_id"]
            if key not in seen:
                seen.add(key)
                notes.append(note)
    return notes


def values_equal(expected: Any, measured: Any) -> bool:
    if isinstance(expected, bool) or isinstance(measured, bool):
        return bool(expected) == bool(measured)
    if isinstance(expected, int) and not isinstance(expected, bool):
        try:
            return int(measured) == expected
        except (TypeError, ValueError):
            return False
    return str(expected) == str(measured)


def classify_note(note: dict[str, Any], measured: dict[str, Any]) -> dict[str, Any]:
    diffs = []
    for assertion in note["assertions"]:
        key = assertion["key"]
        if key not in measured:
            continue
        live = measured[key]
        ok = values_equal(assertion["expected"], live)
        diffs.append(
            {
                "key": key,
                "asserted": assertion["expected"],
                "measured": live,
                "source": assertion["source"],
                "matches": ok,
            }
        )
    contradicted = [d for d in diffs if d["matches"] is False]
    matching = [d for d in diffs if d["matches"] is True]
    still = bool(contradicted) and not note.get("superseded_by")
    return {
        "note_id": note["note_id"],
        "path": note["path"],
        "store": note["store"],
        "superseded_by": note.get("superseded_by"),
        "valid_as_of": note.get("valid_as_of"),
        "status": note.get("status"),
        "body_start_line": note.get("body_start_line"),
        "sha256_head": note.get("sha256_head"),
        "assertions": note["assertions"],
        "diffs": diffs,
        "contradicted": contradicted,
        "matching": matching,
        "is_contradicted": bool(contradicted),
        "still_recallable_as_truth": still,
        "matched_topics": note.get("matched_topics") or [],
    }


def topic_retrieve(notes: list[dict[str, Any]], needles: list[str]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    lowered = [(n, n.lower()) for n in needles]
    for note in notes:
        blob = f"{note['note_id']}\n{note.get('body') or ''}".lower()
        matched = [orig for orig, low in lowered if low in blob]
        if matched:
            rec = dict(note)
            rec["matched_topics"] = matched
            hits.append(rec)
    return hits


def recall_control(notes: list[dict[str, Any]]) -> dict[str, Any]:
    hits = []
    for note in notes:
        blob = note.get("text") or note.get("body") or ""
        if RECALL_NEEDLE in blob or RECALL_TOKEN in blob:
            hits.append(note["note_id"])
    return {
        "id": "recall-control",
        "needle": RECALL_NEEDLE,
        "required_token": RECALL_TOKEN,
        "hits": hits,
        "pass": bool(hits),
        "detail": (
            f"found {hits}" if hits else "known-present recall token was not retrieved"
        ),
    }


TOPICS = [
    "option_family_m_count",
    "collision",
    "family M",
    "ADV-0018",
    "Program B",
    "workflow_design",
    "recall",
    "MECH-",
    "option-id",
    "VAULT-RECALL-PRESENT",
    "probe-assert",
]


def run_sweep() -> dict[str, Any]:
    measured = live_measurements()
    notes = load_all_notes()
    retrieved = topic_retrieve(notes, TOPICS)
    classified = [classify_note(n, measured) for n in retrieved]
    contradicted = [c for c in classified if c["is_contradicted"]]
    still = [c for c in contradicted if c["still_recallable_as_truth"]]
    marked = [c for c in contradicted if c.get("superseded_by")]
    recall = recall_control(notes)
    frontmatter_rows = [
        {
            "note_id": n["note_id"],
            "path": n["path"],
            "store": n["store"],
            "superseded_by": n.get("superseded_by"),
            "valid_as_of": n.get("valid_as_of"),
            "status": n.get("status"),
            "frontmatter_keys": sorted((n.get("frontmatter") or {}).keys()),
            "from_file_not_snippet": True,
        }
        for n in notes
    ]
    extra = extra_vault_roots()
    return {
        "measured": measured,
        "notes_loaded": len(notes),
        "notes_retrieved": len(retrieved),
        "mcp_basic_memory": False,
        "vault_roots": [
            _rel(VAULT_DIR),
            _rel(DECISION_LOG),
            *[str(p) for p in extra],
        ],
        "recall": recall,
        "classified": classified,
        "contradicted": contradicted,
        "still_recallable": still,
        "marked_contradicted": marked,
        "frontmatter_rows": frontmatter_rows,
        "note_ids": [n["note_id"] for n in notes],
    }


def find_classified(sweep: dict[str, Any], note_id: str) -> dict[str, Any] | None:
    for row in sweep["classified"]:
        if row["note_id"] == note_id:
            return row
    return None


def find_frontmatter(sweep: dict[str, Any], note_id: str) -> dict[str, Any] | None:
    for row in sweep["frontmatter_rows"]:
        if row["note_id"] == note_id:
            return row
    return None
