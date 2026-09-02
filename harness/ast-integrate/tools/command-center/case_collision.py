"""Case-distinct JSON/YAML key collision detector (IMP-0468 / spec:11310).

A case-insensitive consumer folds ``Name`` and ``name`` into one slot and
silently drops a value. This module finds sibling keys that differ only by
case, using two independent signals:

* Signal A (walk): recursive walk of the loaded mapping (std ``json.loads``
  / ``yaml.safe_load``). Case-distinct keys survive a case-sensitive dict.
* Signal B (pairs/events): ``object_pairs_hook`` for JSON, YAML event stream
  for YAML. Exact duplicate keys are a different failure class and are not
  reported here; a group must contain two or more *distinct* original keys.

A zero shipped-scan is untrusted until the planted-collision control fires.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "command-center" / "p2-wave" / "probes" / "IMP-0468" / "fixtures"

# Product manifests that a shipped tree is expected to carry. Absence is
# recorded rather than treated as a silent zero.
CANONICAL_PATHS: tuple[str, ...] = (
    "hooks/_dispatch/manifest.json",
    "skills/DEPLOYED-MANIFEST.json",
    "skills/manifest.json",
    "marketplace.json",
    ".coverage-thresholds.json",
    ".github/workflows/",
)

# Bounded shipped surface: schema + tools package manifests + plugin
# manifests. Probe fixtures, receipts, and the work-unit catalog are out of
# scope (fixtures would plant collisions into the live count).
PLUGIN_MANIFESTS: tuple[str, ...] = (
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
)
PACKAGE_JSON: tuple[str, ...] = (
    "package.json",
    "tools/fanout-schema/package.json",
    "tools/agentspec-js/package.json",
    "tools/lib/package.json",
)

JSON_SUFFIXES = {".json"}
YAML_SUFFIXES = {".yml", ".yaml"}


class _PairObj(dict):
    """Dict that retains the original pair list for an independent key bag."""

    def __init__(self, pairs: list[tuple[Any, Any]]):
        self._pairs = [(str(k), v) for k, v in pairs]
        super().__init__(self._pairs)


def _is_ident_key(key: str) -> bool:
    if not key:
        return False
    if key[0].isdigit():
        return False
    return all(ch.isalnum() or ch == "_" for ch in key)


def child_path(parent: str, key: str) -> str:
    if _is_ident_key(key):
        return f"{parent}.{key}"
    return f"{parent}[{json.dumps(key, ensure_ascii=False)}]"


def _value_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except TypeError:
        return repr(value)


def colliding_groups(keys: Iterable[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for key in keys:
        groups[key.casefold()].append(key)
    return {
        folded: originals
        for folded, originals in groups.items()
        if len(set(originals)) > 1
    }


def hits_from_keybag(
    path: str, keys: list[str], values: dict[str, Any]
) -> list[dict[str, Any]]:
    hits = []
    for originals in colliding_groups(keys).values():
        ordered = list(dict.fromkeys(originals))
        hits.append(
            {
                "json_path": path,
                "keys": ordered,
                "values": {k: _value_text(values.get(k)) for k in ordered},
            }
        )
    return hits


def _walk_mapping(
    obj: Any, path: str, *, pair_attr: str | None
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    if pair_attr and isinstance(obj, _PairObj):
        keys = [k for k, _ in obj._pairs]
        values = dict(obj._pairs)
        hits.extend(hits_from_keybag(path, keys, values))
        seen: dict[str, int] = {}
        for key, value in obj._pairs:
            n = seen.get(key, 0)
            seen[key] = n + 1
            child = child_path(path, key) if n == 0 else f"{child_path(path, key)}#{n}"
            hits.extend(_walk_mapping(value, child, pair_attr=pair_attr))
        return hits
    if isinstance(obj, dict):
        keys = [str(k) for k in obj.keys()]
        values = {str(k): v for k, v in obj.items()}
        hits.extend(hits_from_keybag(path, keys, values))
        for key, value in obj.items():
            hits.extend(
                _walk_mapping(value, child_path(path, str(key)), pair_attr=pair_attr)
            )
        return hits
    if isinstance(obj, list):
        for i, value in enumerate(obj):
            hits.extend(_walk_mapping(value, f"{path}[{i}]", pair_attr=pair_attr))
    return hits


def _hit_signature(hits: list[dict[str, Any]]) -> set[tuple[str, tuple[str, ...]]]:
    return {(h["json_path"], tuple(sorted(h["keys"]))) for h in hits}


def _load_json_signals(text: str) -> tuple[Any, Any]:
    loaded = json.loads(text)
    paired = json.loads(text, object_pairs_hook=lambda pairs: _PairObj(list(pairs)))
    return loaded, paired


def _yaml_module():
    import yaml  # type: ignore

    return yaml


def _load_yaml_loaded(text: str) -> Any:
    yaml = _yaml_module()
    return yaml.safe_load(text)


def _yaml_event_hits(text: str) -> list[dict[str, Any]]:
    """Independent YAML signal: mapping keys from the event stream, not the dict."""
    yaml = _yaml_module()
    from yaml.events import (  # type: ignore
        AliasEvent,
        DocumentEndEvent,
        MappingEndEvent,
        MappingStartEvent,
        ScalarEvent,
        SequenceEndEvent,
        SequenceStartEvent,
        StreamEndEvent,
    )

    events = list(yaml.parse(text, Loader=yaml.SafeLoader))
    hits: list[dict[str, Any]] = []
    # stack frames: kind, path, keys, expecting_key, current_key
    stack: list[dict[str, Any]] = []

    def parent_path() -> str:
        for frame in reversed(stack):
            if frame["kind"] in {"map", "seq", "root"}:
                return frame["path"]
        return "$"

    def attach_child(path: str) -> None:
        if not stack:
            return
        top = stack[-1]
        if top["kind"] == "seq":
            top["index"] = int(top.get("index", -1)) + 1

    root = {"kind": "root", "path": "$", "keys": [], "expecting_key": False}
    stack.append(root)

    i = 0
    while i < len(events):
        ev = events[i]
        i += 1
        if isinstance(ev, StreamEndEvent) or isinstance(ev, DocumentEndEvent):
            continue
        if isinstance(ev, MappingStartEvent):
            path = "$"
            if stack and stack[-1]["kind"] == "map" and stack[-1].get("current_key") is not None:
                path = child_path(stack[-1]["path"], stack[-1]["current_key"])
                stack[-1]["current_key"] = None
                stack[-1]["expecting_key"] = True
            elif stack and stack[-1]["kind"] == "seq":
                stack[-1]["index"] = int(stack[-1].get("index", -1)) + 1
                path = f"{stack[-1]['path']}[{stack[-1]['index']}]"
            elif stack and stack[-1]["kind"] == "root":
                path = "$"
            stack.append(
                {
                    "kind": "map",
                    "path": path,
                    "keys": [],
                    "expecting_key": True,
                    "current_key": None,
                }
            )
            continue
        if isinstance(ev, SequenceStartEvent):
            path = "$"
            if stack and stack[-1]["kind"] == "map" and stack[-1].get("current_key") is not None:
                path = child_path(stack[-1]["path"], stack[-1]["current_key"])
                stack[-1]["current_key"] = None
                stack[-1]["expecting_key"] = True
            elif stack and stack[-1]["kind"] == "seq":
                stack[-1]["index"] = int(stack[-1].get("index", -1)) + 1
                path = f"{stack[-1]['path']}[{stack[-1]['index']}]"
            stack.append({"kind": "seq", "path": path, "index": -1})
            continue
        if isinstance(ev, MappingEndEvent):
            frame = stack.pop()
            if frame["kind"] == "map":
                dummy_vals = {k: "" for k in frame["keys"]}
                hits.extend(hits_from_keybag(frame["path"], frame["keys"], dummy_vals))
            continue
        if isinstance(ev, SequenceEndEvent):
            if stack and stack[-1]["kind"] == "seq":
                stack.pop()
            continue
        if isinstance(ev, (ScalarEvent, AliasEvent)):
            if not stack:
                continue
            top = stack[-1]
            if top["kind"] == "map" and top.get("expecting_key"):
                key = "" if isinstance(ev, AliasEvent) else str(ev.value)
                top["keys"].append(key)
                top["current_key"] = key
                top["expecting_key"] = False
                continue
            if top["kind"] == "map":
                top["current_key"] = None
                top["expecting_key"] = True
                continue
            if top["kind"] == "seq":
                top["index"] = int(top.get("index", -1)) + 1
            continue
    return hits


def detect_document(text: str, *, suffix: str = ".json") -> dict[str, Any]:
    suffix = suffix.lower()
    try:
        if suffix in YAML_SUFFIXES:
            loaded = _load_yaml_loaded(text)
            walk_hits = _walk_mapping(loaded, "$", pair_attr=None)
            try:
                event_hits = _yaml_event_hits(text)
            except Exception as exc:  # noqa: BLE001 — disagreement is the signal
                return {
                    "parse_ok": True,
                    "error": None,
                    "walk_hits": walk_hits,
                    "pairs_hits": [],
                    "signals_agree": False,
                    "signal_error": f"yaml-events:{type(exc).__name__}:{exc}",
                }
            agree = _hit_signature(walk_hits) == _hit_signature(event_hits)
            return {
                "parse_ok": True,
                "error": None,
                "walk_hits": walk_hits,
                "pairs_hits": event_hits,
                "signals_agree": agree,
                "signal_error": None,
            }
        loaded, paired = _load_json_signals(text)
        walk_hits = _walk_mapping(loaded, "$", pair_attr=None)
        pairs_hits = _walk_mapping(paired, "$", pair_attr="_pairs")
        return {
            "parse_ok": True,
            "error": None,
            "walk_hits": walk_hits,
            "pairs_hits": pairs_hits,
            "signals_agree": _hit_signature(walk_hits) == _hit_signature(pairs_hits),
            "signal_error": None,
        }
    except Exception as exc:  # noqa: BLE001 — parse failure is a documented row
        return {
            "parse_ok": False,
            "error": f"{type(exc).__name__}:{exc}",
            "walk_hits": [],
            "pairs_hits": [],
            "signals_agree": True,
            "signal_error": None,
        }


def detect_file(path: Path | str, repo: Path | str | None = None) -> dict[str, Any]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "parse_ok": False,
            "error": f"{type(exc).__name__}:{exc}",
            "walk_hits": [],
            "pairs_hits": [],
            "signals_agree": True,
            "file": str(path),
        }
    result = detect_document(text, suffix=path.suffix or ".json")
    rel = str(path)
    if repo is not None:
        try:
            rel = Path(path).resolve().relative_to(Path(repo).resolve()).as_posix()
        except ValueError:
            rel = Path(path).as_posix()
    result["file"] = rel
    return result


def simulate_casefold_consumer(obj: Any) -> dict[str, Any]:
    """Last-key-wins case-insensitive consumer. The silent-loss hazard."""
    if not isinstance(obj, dict):
        return {
            "silent_loss": False,
            "input_key_count": 0,
            "kept_count": 0,
            "kept": {},
        }
    keys = [str(k) for k in obj.keys()]
    kept: dict[str, Any] = {}
    dropped: list[dict[str, Any]] = []
    for key, value in obj.items():
        folded = str(key).casefold()
        if folded in kept:
            dropped.append(
                {
                    "dropped_key": str(key) if kept[folded] is not value else str(key),
                    "folded": folded,
                }
            )
        kept[folded] = value
    return {
        "silent_loss": len(kept) < len(keys),
        "input_key_count": len(keys),
        "kept_count": len(kept),
        "kept": kept,
        "dropped_count": len(keys) - len(kept),
    }


def _posix(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def iter_shipped_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for rel in PLUGIN_MANIFESTS:
        path = repo / rel
        if path.is_file():
            files.append(path)
    plugin_schema = repo / "tools" / "plugin" / "schema"
    if plugin_schema.is_dir():
        files.extend(sorted(plugin_schema.glob("*.json")))
    plat_schema = repo / "platform" / "schema"
    if plat_schema.is_dir():
        files.extend(sorted(p for p in plat_schema.glob("*.json") if p.is_file()))
    for rel in PACKAGE_JSON:
        path = repo / rel
        if path.is_file():
            files.append(path)
    for rel in CANONICAL_PATHS:
        path = repo / rel
        if rel.endswith("/"):
            if path.is_dir():
                files.extend(sorted(path.glob("*.yml")))
                files.extend(sorted(path.glob("*.yaml")))
        elif path.is_file():
            files.append(path)
    uniq: dict[str, Path] = {}
    for path in files:
        uniq[_posix(path, repo)] = path
    return [uniq[k] for k in sorted(uniq)]


def canonical_status(repo: Path) -> tuple[list[str], list[str]]:
    present: list[str] = []
    absent: list[str] = []
    for rel in CANONICAL_PATHS:
        path = repo / rel
        exists = path.is_dir() if rel.endswith("/") else path.is_file()
        (present if exists else absent).append(rel)
    return present, absent


def scan_shipped(repo: Path | str) -> dict[str, Any]:
    repo = Path(repo)
    present, absent = canonical_status(repo)
    files_scanned: list[str] = []
    collisions: list[dict[str, Any]] = []
    unreadable: list[dict[str, str]] = []
    disagreement: list[str] = []
    for path in iter_shipped_files(repo):
        rel = _posix(path, repo)
        files_scanned.append(rel)
        result = detect_file(path, repo=repo)
        if not result["parse_ok"]:
            unreadable.append({"file": rel, "error": str(result.get("error") or "")})
            continue
        if not result["signals_agree"]:
            disagreement.append(rel)
        for hit in result["walk_hits"]:
            collisions.append(
                {
                    "file": rel,
                    "json_path": hit["json_path"],
                    "keys": list(hit["keys"]),
                    "values": dict(hit["values"]),
                }
            )
    return {
        "collision_count": len(collisions),
        "collisions": collisions,
        "files_scanned_count": len(files_scanned),
        "files_scanned": files_scanned,
        "canonical_present": present,
        "canonical_absent": absent,
        "unreadable": unreadable,
        "signal_disagreement_files": disagreement,
    }


def run_required_controls() -> dict[str, Any]:
    planted_path = FIXTURES / "planted-collision.json"
    nested_path = FIXTURES / "nested-collision.json"
    non_case_path = FIXTURES / "non-case-distinct.json"
    clean_path = FIXTURES / "clean.json"
    id_path = FIXTURES / "id-case-collision.json"

    planted = detect_file(planted_path, repo=FIXTURES.parent)
    nested = detect_file(nested_path, repo=FIXTURES.parent)
    non_case = detect_file(non_case_path, repo=FIXTURES.parent)
    clean = detect_file(clean_path, repo=FIXTURES.parent)
    id_hit = detect_file(id_path, repo=FIXTURES.parent)

    planted_obj = json.loads(planted_path.read_text(encoding="utf-8"))
    consumer = simulate_casefold_consumer(planted_obj)

    planted_ok = (
        planted["parse_ok"]
        and planted["signals_agree"]
        and len(planted["walk_hits"]) == 1
        and set(planted["walk_hits"][0]["keys"]) == {"Name", "name"}
        and planted["walk_hits"][0]["json_path"] == "$"
        and consumer["silent_loss"]
        and consumer["input_key_count"] == 3
        and consumer["kept_count"] == 2
    )
    nested_ok = (
        nested["parse_ok"]
        and nested["signals_agree"]
        and len(nested["walk_hits"]) == 1
        and str(nested["walk_hits"][0]["json_path"]).endswith("inner")
        and set(nested["walk_hits"][0]["keys"]) == {"Host", "host"}
    )
    non_case_ok = non_case["parse_ok"] and not non_case["walk_hits"]
    clean_ok = clean["parse_ok"] and not clean["walk_hits"]
    id_ok = (
        id_hit["parse_ok"]
        and len(id_hit["walk_hits"]) == 1
        and set(id_hit["walk_hits"][0]["keys"]) == {"ID", "id"}
    )
    return {
        "all_passed": all((planted_ok, nested_ok, non_case_ok, clean_ok, id_ok)),
        "planted": {
            "fired": planted_ok,
            "hits": planted["walk_hits"],
            "consumer": consumer,
        },
        "nested": {"fired": nested_ok, "hits": nested["walk_hits"]},
        "non_case": {"silent": non_case_ok, "hits": non_case["walk_hits"]},
        "clean": {"silent": clean_ok, "hits": clean["walk_hits"]},
        "id_id": {"fired": id_ok, "hits": id_hit["walk_hits"]},
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--controls" in argv:
        report = run_required_controls()
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["all_passed"] else 1
    repo = REPO
    report = scan_shipped(repo)
    print(
        json.dumps(
            {
                "collision_count": report["collision_count"],
                "files_scanned_count": report["files_scanned_count"],
                "canonical_absent": report["canonical_absent"],
                "canonical_present": report["canonical_present"],
                "unreadable": report["unreadable"],
                "signal_disagreement_files": report["signal_disagreement_files"],
                "collisions": report["collisions"],
            },
            indent=2,
        )
    )
    if report["unreadable"] or report["signal_disagreement_files"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
