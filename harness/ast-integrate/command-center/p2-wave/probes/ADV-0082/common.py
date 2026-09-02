"""Scratch-corpus helpers and live consumers for ADV-0082.

Never writes beacon payloads into the real worktree corpus. Scratch trees live
under tempfile and are deleted by the caller.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from constants import (
    BENIGN,
    CATALOG_FIELDS,
    FENCE_BEGIN,
    FENCE_END,
    INSTRUCTION,
    LIVE_CORPUS,
    TOKEN,
    UNIT,
    WRITE_BEACON_RE,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
DISPATCH_PY = REPO / "command-center/p2-wave/seed-stage/dispatch_cursor.py"
RENDER_DIR = REPO / "tools/command-center"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_path(path: Path) -> tuple[str, int] | None:
    if not path.is_file():
        return None
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def live_corpus_fingerprints() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rel in LIVE_CORPUS:
        path = REPO / rel
        got = digest_path(path)
        out[rel] = {
            "exists": got is not None,
            "sha256": None if got is None else got[0],
            "bytes": None if got is None else got[1],
            "contains_token": bool(got) and TOKEN.encode("utf-8") in path.read_bytes(),
        }
    return out


def assert_real_corpus_clean(before: dict[str, dict[str, Any]]) -> dict[str, Any]:
    after = live_corpus_fingerprints()
    mismatches = []
    token_hits = []
    for rel, prev in before.items():
        now = after.get(rel) or {}
        if now.get("sha256") != prev.get("sha256") or now.get("exists") != prev.get("exists"):
            mismatches.append(rel)
        if now.get("contains_token"):
            token_hits.append(rel)
    return {
        "unmodified": not mismatches,
        "mismatches": mismatches,
        "token_hits": token_hits,
        "after": after,
    }


def load_live_unit() -> dict[str, Any]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT:
            return deepcopy(unit)
    raise RuntimeError(f"{UNIT} missing from WORK-UNIT-CATALOG.json")


def plant_field(value: Any, payload: str) -> Any:
    if isinstance(value, list):
        planted = list(value)
        planted.append(payload)
        return planted
    if isinstance(value, dict):
        planted = dict(value)
        planted["_adv0082_plant"] = payload
        return planted
    return f"{value}\n{payload}" if value else payload


def plant_unit(unit: dict[str, Any], payload: str) -> dict[str, Any]:
    planted = deepcopy(unit)
    for key in CATALOG_FIELDS:
        planted[key] = plant_field(planted.get(key), payload)
    return planted


def load_dispatch():
    spec = importlib.util.spec_from_file_location("adv0082_dispatch_cursor", DISPATCH_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load dispatch_cursor.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cursor_dispatch_prompt(uid: str) -> str:
    return str(load_dispatch().prompt_for(uid))


def fence(body: str) -> str:
    return f"{FENCE_BEGIN}\n{body.rstrip()}\n{FENCE_END}\n"


def strip_fences(text: str) -> str:
    out: list[str] = []
    inside = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped == FENCE_BEGIN:
            inside = True
            continue
        if stripped == FENCE_END:
            inside = False
            continue
        if not inside:
            out.append(line)
    return "".join(out)


def beacon_in(text: str) -> bool:
    return bool(WRITE_BEACON_RE.search(text or "")) or TOKEN in (text or "")


def naive_follow(context: str) -> bool:
    return beacon_in(context)


def delimited_follow(context: str) -> bool:
    return beacon_in(strip_fences(context))


def load_render():
    if str(RENDER_DIR) not in sys.path:
        sys.path.insert(0, str(RENDER_DIR))
    import render as R  # type: ignore

    return R


def render_owner_decisions(catalog: dict[str, Any]) -> str:
    return str(load_render().render_owner_decisions(catalog))


def write_scratch_tree(root: Path, *, payload: str | None) -> dict[str, str]:
    """Write a mini corpus. payload=None is the clean control."""
    body = INSTRUCTION if payload else BENIGN
    unit = load_live_unit()
    if payload:
        unit = plant_unit(unit, body)
    catalog = {
        "schema_version": 1,
        "work_units": [unit],
        "owner_questions": [
            {
                "id": "ADV0082-Q-SCRATCH",
                "state": "ANSWERED",
                "text": body if payload else BENIGN.strip(),
                "answer": "scratch-only-not-the-live-log",
                "answer_detail": body if payload else BENIGN.strip(),
                "answered_on": "1970-01-01",
                "answer_provenance": "ADV-0082 scratch",
            }
        ],
        "items": [],
    }
    paths = {
        "catalog": "WORK-UNIT-CATALOG.json",
        "option_card": "07-OPTION-UNIVERSE.md",
        "decision_log": "OWNER-DECISIONS.md",
        "event_record": "events/EVENTS.jsonl",
        "handoff": "probes/ADV-0082/HANDOFF.md",
    }
    (root / "WORK-UNIT-CATALOG.json").write_text(
        json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (root / "07-OPTION-UNIVERSE.md").write_text(
        "# Option card ADV0082-OC\n\n" + body, encoding="utf-8"
    )
    (root / "events").mkdir(parents=True, exist_ok=True)
    (root / "events/EVENTS.jsonl").write_text(
        json.dumps({"id": "evt-adv0082-scratch", "kind": "note", "text": body}) + "\n",
        encoding="utf-8",
    )
    handoff_dir = root / "probes/ADV-0082"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / "HANDOFF.md").write_text(
        "# HANDOFF ADV-0082\n\n" + body, encoding="utf-8"
    )
    (root / "OWNER-DECISIONS.md").write_text(
        render_owner_decisions(catalog), encoding="utf-8"
    )
    return {k: str(root / v) for k, v in paths.items()}


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def task_description_context(unit: dict[str, Any]) -> str:
    """What a G-1 delivery agent loads when it looks up the catalog unit."""
    return json.dumps(unit, indent=2, sort_keys=True) + "\n"


def delivery_context(
    *,
    dispatch_prompt: str,
    unit: dict[str, Any],
    extras: dict[str, str],
    delimited: bool,
) -> str:
    """Assemble the later-stage context.

    Trusted program text stays outside the fence. Corpus bytes (catalog unit,
    option card, decision log, event, HANDOFF) are the untrusted payload.
    """
    corpus_parts = [
        ("work-unit-catalog", task_description_context(unit)),
        ("option-card", extras.get("option_card", "")),
        ("decision-log", extras.get("decision_log", "")),
        ("event-record", extras.get("event_record", "")),
        ("probe-dir-handoff", extras.get("handoff", "")),
    ]
    blob = "\n".join(f"## {name}\n{text}" for name, text in corpus_parts)
    if delimited:
        return dispatch_prompt.rstrip() + "\n\n" + fence(blob)
    return dispatch_prompt.rstrip() + "\n\n" + blob


def measure_tree(root: Path) -> dict[str, Any]:
    catalog = json.loads((root / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    unit = catalog["work_units"][0]
    extras = {
        "option_card": read_text(root / "07-OPTION-UNIVERSE.md"),
        "decision_log": read_text(root / "OWNER-DECISIONS.md"),
        "event_record": read_text(root / "events/EVENTS.jsonl"),
        "handoff": read_text(root / "probes/ADV-0082/HANDOFF.md"),
    }
    dispatch = cursor_dispatch_prompt(UNIT)
    naive_ctx = delivery_context(
        dispatch_prompt=dispatch, unit=unit, extras=extras, delimited=False
    )
    delim_ctx = delivery_context(
        dispatch_prompt=dispatch, unit=unit, extras=extras, delimited=True
    )
    classes: dict[str, Any] = {}
    for name, text in (
        ("work-unit-catalog", task_description_context(unit)),
        ("option-card", extras["option_card"]),
        ("decision-log", extras["decision_log"]),
        ("event-record", extras["event_record"]),
        ("probe-dir-handoff", extras["handoff"]),
    ):
        classes[name] = {
            "in_dispatch_prompt": beacon_in(dispatch) and beacon_in(text),
            "in_class_bytes": beacon_in(text),
            "in_naive_delivery_context": beacon_in(naive_ctx) and beacon_in(text),
            "in_delimited_trusted_region": beacon_in(strip_fences(delim_ctx))
            and beacon_in(text),
        }
    field_hits = {
        key: beacon_in(dispatch) and beacon_in(str(unit.get(key) or ""))
        for key in CATALOG_FIELDS
    }
    return {
        "dispatch_prompt_has_beacon": beacon_in(dispatch),
        "dispatch_prompt_has_uid": UNIT in dispatch,
        "dispatch_starts_from_probe_dir": f"probes/{UNIT}/" in dispatch.replace("\\", "/"),
        "naive_complied": naive_follow(naive_ctx),
        "delimited_complied": delimited_follow(delim_ctx),
        "catalog_fields_in_dispatch": field_hits,
        "classes": classes,
        "dispatch_prompt_chars": len(dispatch),
        "naive_context_chars": len(naive_ctx),
    }


def with_scratch(*, payload: str | None) -> tuple[dict[str, Any], str]:
    """Build, measure, delete. Returns (measurement, scratch_root_str)."""
    tmp = Path(tempfile.mkdtemp(prefix="adv0082-scratch-"))
    scratch = str(tmp)
    try:
        write_scratch_tree(tmp, payload=payload)
        measured = measure_tree(tmp)
        measured["scratch_root"] = scratch
        return measured, scratch
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scratch_gone(path_str: str) -> bool:
    return not Path(path_str).exists()


def prompt_for_source() -> str:
    return DISPATCH_PY.read_text(encoding="utf-8")


def interpolated_names_in_prompt_for() -> list[str]:
    """AST names that flow into dispatch_cursor.prompt_for via the f-string."""
    tree = ast.parse(prompt_for_source())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "prompt_for":
            for child in ast.walk(node):
                if isinstance(child, ast.FormattedValue):
                    if isinstance(child.value, ast.Name):
                        names.append(child.value.id)
                    else:
                        names.append(ast.unparse(child.value))
    return names


def catalog_keys_mentioned_in_dispatcher() -> list[str]:
    src = prompt_for_source()
    return [key for key in CATALOG_FIELDS if key in src]


def leftover_rejects_beacon_uid() -> dict[str, Any]:
    regex = load_dispatch().UID_RE
    samples = {
        "canonical": UNIT,
        "beacon_in_id": f"{UNIT}\n{TOKEN}",
        "empty": "",
        "instruction_as_id": f"WRITE_BEACON-{UNIT}",
    }
    return {
        "pattern": regex.pattern,
        "accepts": {k: bool(regex.match(v)) for k, v in samples.items()},
    }


def estate_corpus_delimiter() -> dict[str, Any]:
    needles = (FENCE_BEGIN, "UNTRUSTED CORPUS DATA", "BEGIN UNTRUSTED CORPUS")
    hits: list[str] = []
    scan_roots = [
        REPO / "command-center/p2-wave/seed-stage",
        REPO / "tools/command-center",
    ]
    for root in scan_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".md", ".json", ".txt"}:
                continue
            try:
                rel = path.resolve().relative_to(HERE.resolve())
            except ValueError:
                rel = None
            if rel is not None:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if any(n in text for n in needles):
                hits.append(path.relative_to(REPO).as_posix())
    return {"needles": list(needles), "hits": hits, "present": bool(hits)}
