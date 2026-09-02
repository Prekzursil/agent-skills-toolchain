#!/usr/bin/env python3
"""Live reader × encoding matrix for TST-0055.

Exercises production config/artifact JSON readers against UTF-8, UTF-8-with-BOM,
UTF-16-LE, and Latin-1. Classification is HANDLE / REJECT_LOUD / SILENT_EMPTY /
SILENT_WRONG. Exception text is captured verbatim.
"""
from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
NOTE_ASCII = "cafe"
NOTE_LATIN1 = "café"
LATIN1_MARK = "é"
ENCODINGS = (
    {"id": "utf-8", "codec": "utf-8", "bom": None},
    {"id": "utf-8-bom", "codec": "utf-8", "bom": b"\xef\xbb\xbf"},
    {"id": "utf-16-le", "codec": "utf-16-le", "bom": None},
    {"id": "latin-1", "codec": "latin-1", "bom": None},
)
ENGINE_LOAD_LINE = 'json.loads(path.read_text(encoding="utf-8"))'
_MOD_CACHE: dict[str, Any] = {}


ABSENT_READERS = (
    "tools/marketplace/package_cache.py",
    "tools/council/protocol/socratic.py",
    "tools/plugin/heartbeat.py",
)


def load_module(name: str, rel: str):
    if name in _MOD_CACHE:
        return _MOD_CACHE[name]
    path = REPO / rel
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {rel}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    _MOD_CACHE[name] = mod
    return mod


def source_anchor(rel: str, needle: str) -> str:
    text = (REPO / rel).read_text(encoding="utf-8")
    hits = [i for i, ln in enumerate(text.splitlines(), 1) if needle in ln]
    if len(hits) != 1:
        raise RuntimeError(f"source_anchor {rel} {needle!r} hits={hits}")
    return f"{rel}:{hits[0]}"


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def encode_text(text: str, spec: dict) -> bytes:
    body = text.encode(spec["codec"])
    bom = spec.get("bom")
    return (bom + body) if bom else body


def hex_prefix(raw: bytes, n: int = 16) -> str:
    return raw[:n].hex()


def _catalog_load(path: Path) -> Any:
    mod = load_module("tst0055_catalog", "tools/command-center/catalog.py")
    return mod.load(path)


def _compat_load(path: Path) -> Any:
    mod = load_module("tst0055_compat", "tools/marketplace/compat.py")
    return mod.load_candidates(path)


def _trust_load(path: Path) -> Any:
    mod = load_module("tst0055_trust", "tools/marketplace/trust_levels.py")
    return mod.load_fixture(path)


def _quality_load(path: Path) -> Any:
    mod = load_module("tst0055_qscore", "tools/marketplace/quality_score.py")
    return mod.load_measurements(path)


def _stability_load(path: Path) -> Any:
    mod = load_module("tst0055_stability", "tools/council/stability.py")
    return mod.load_preset_pack(path)


def _documented_ids(path: Path) -> Any:
    mod = load_module("tst0055_id_closure", "tools/agentspec/agentspec/id_closure.py")
    return mod.documented_ids(path)


def _ledger_load(path: Path) -> Any:
    mod = load_module("tst0055_ledger", "command-center/blueprints/engineering/ledger.py")
    return mod.read_events(path)


def _engine_sourced_load(path: Path) -> Any:
    src = (REPO / "command-center/blueprints/engineering/engine.py").read_text(
        encoding="utf-8"
    )
    if ENGINE_LOAD_LINE not in src:
        raise RuntimeError("engine.py no longer uses read_text(encoding='utf-8')+json.loads")
    return json.loads(path.read_text(encoding="utf-8"))


def _inventory_load(path: Path) -> Any:
    """Live production swallower: JSONDecodeError / missing file returns {}."""
    mod = load_module("tst0055_inventory", "tools/mcp-manager/core/inventory.py")
    return mod._load_json(path)


def _unit_manifest_one(path: Path) -> Any:
    """The per-file json.loads(read_text utf-8) used by unit_manifest._load_receipts."""
    src = (REPO / "tools/command-center/unit_manifest.py").read_text(encoding="utf-8")
    needle = "json.loads(path.read_text(encoding=\"utf-8\"))"
    if needle not in src:
        raise RuntimeError("unit_manifest.py reader line missing")
    return json.loads(path.read_text(encoding="utf-8"))


def planted_silent_empty(path: Path) -> Any:
    """Known-broken decoder: UTF-16 (NUL-dense) returns {} with no exception."""
    raw = path.read_bytes()
    if not raw:
        return {}
    nuls = raw.count(0)
    if nuls * 2 >= len(raw) and nuls > 0:
        return {}
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _eq(expected: Any) -> Callable[[Any], bool]:
    def check(got: Any) -> bool:
        if isinstance(expected, set):
            return set(got) == expected
        return got == expected

    return check


def _docs(note: str) -> dict[str, Any]:
    return {
        "catalog": {"note": note, "schema_version": 1, "work_units": []},
        "packages": {
            "note": note,
            "packages": [{"name": "tst-0055-probe", "version": "1.0.0", "note": note}],
        },
        "measures": {"note": note, "tests": {"total": 1, "passed": 1, "failed": 0}},
        "presets": {
            "note": note,
            "presets": [
                {"id": "preset.a", "note": note},
                {"id": "preset.b", "note": note},
            ],
        },
        "corpus": {"items": [{"id": "c1", "note": note}]},
        "ids": {"ids": [{"id": "duplicate-work-id", "note": note}], "baseline_count": 1},
        "heartbeat": {"token": 7, "pid": 42, "mono_ns": 99, "note": note},
        "trust": {
            "note": note,
            "publishers": [{"id": "tst-0055-pub", "note": note}],
        },
        "ledger": {"seq": 1, "note": note, "event": "probe"},
        "engine": {"id": "tst-0055-blueprint", "note": note},
        "receipt": {
            "note": note,
            "unit_id": "TST-0055",
            "artifacts": [{"path": "command-center/receipts/TST-0055.json"}],
        },
        "plant": {"ok": True, "note": note},
    }


def reader_specs() -> list[dict[str, Any]]:
    ascii_docs = _docs(NOTE_ASCII)
    latin_docs = _docs(NOTE_LATIN1)
    plant_anchor = (
        "command-center/p2-wave/probes/TST-0055/matrix.py:"
        f"{planted_silent_empty.__code__.co_firstlineno}"
    )
    return [
        {
            "reader_id": "catalog.load",
            "module_rel": "tools/command-center/catalog.py",
            "source_anchor": source_anchor(
                "tools/command-center/catalog.py",
                'data = json.loads(target.read_text(encoding="utf-8"))',
            ),
            "kind": "config-artifact",
            "in_required_tests": True,
            "text_ascii": dumps(ascii_docs["catalog"]),
            "text_latin1": dumps(latin_docs["catalog"]),
            "invoke": _catalog_load,
            "expect_ascii": _eq(ascii_docs["catalog"]),
            "expect_latin1": _eq(latin_docs["catalog"]),
        },
        {
            "reader_id": "compat.load_candidates",
            "module_rel": "tools/marketplace/compat.py",
            "source_anchor": source_anchor(
                "tools/marketplace/compat.py",
                "data = json.loads(loc.read_text(encoding=\"utf-8\"))",
            ),
            "kind": "config-artifact",
            "in_required_tests": True,
            "text_ascii": dumps(ascii_docs["packages"]),
            "text_latin1": dumps(latin_docs["packages"]),
            "invoke": _compat_load,
            "expect_ascii": _eq(ascii_docs["packages"]["packages"]),
            "expect_latin1": _eq(latin_docs["packages"]["packages"]),
        },
        {
            "reader_id": "quality_score.load_measurements",
            "module_rel": "tools/marketplace/quality_score.py",
            "source_anchor": source_anchor(
                "tools/marketplace/quality_score.py",
                'data = json.loads(Path(path).read_text(encoding="utf-8"))',
            ),
            "kind": "config-artifact",
            "in_required_tests": True,
            "text_ascii": dumps(ascii_docs["measures"]),
            "text_latin1": dumps(latin_docs["measures"]),
            "invoke": _quality_load,
            "expect_ascii": _eq(ascii_docs["measures"]),
            "expect_latin1": _eq(latin_docs["measures"]),
        },
        {
            "reader_id": "trust_levels.load_fixture",
            "module_rel": "tools/marketplace/trust_levels.py",
            "source_anchor": source_anchor(
                "tools/marketplace/trust_levels.py",
                "return json.loads(target.read_text(encoding=\"utf-8\"))",
            ),
            "kind": "config-artifact",
            "in_required_tests": True,
            "text_ascii": dumps(ascii_docs["trust"]),
            "text_latin1": dumps(latin_docs["trust"]),
            "invoke": _trust_load,
            "expect_ascii": _eq(ascii_docs["trust"]),
            "expect_latin1": _eq(latin_docs["trust"]),
        },
        {
            "reader_id": "stability.load_preset_pack",
            "module_rel": "tools/council/stability.py",
            "source_anchor": source_anchor(
                "tools/council/stability.py",
                "return json.loads(Path(path).read_text(encoding=\"utf-8\"))",
            ),
            "kind": "config-artifact",
            "in_required_tests": True,
            "text_ascii": dumps(ascii_docs["presets"]),
            "text_latin1": dumps(latin_docs["presets"]),
            "invoke": _stability_load,
            "expect_ascii": _eq(ascii_docs["presets"]),
            "expect_latin1": _eq(latin_docs["presets"]),
        },
        {
            "reader_id": "id_closure.documented_ids",
            "module_rel": "tools/agentspec/agentspec/id_closure.py",
            "source_anchor": source_anchor(
                "tools/agentspec/agentspec/id_closure.py",
                'text = target.read_text(encoding="utf-8")',
            ),
            "kind": "config-artifact",
            "in_required_tests": True,
            "text_ascii": dumps(ascii_docs["ids"]),
            "text_latin1": dumps(latin_docs["ids"]),
            "invoke": _documented_ids,
            "expect_ascii": _eq({"duplicate-work-id"}),
            "expect_latin1": _eq({"duplicate-work-id"}),
        },
        {
            "reader_id": "ledger.read_events",
            "module_rel": "command-center/blueprints/engineering/ledger.py",
            "source_anchor": source_anchor(
                "command-center/blueprints/engineering/ledger.py",
                "row = json.loads(text)",
            ),
            "kind": "config-artifact",
            "in_required_tests": True,
            "text_ascii": dumps(ascii_docs["ledger"]) + "\n",
            "text_latin1": dumps(latin_docs["ledger"]) + "\n",
            "invoke": _ledger_load,
            "expect_ascii": _eq([ascii_docs["ledger"]]),
            "expect_latin1": _eq([latin_docs["ledger"]]),
        },
        {
            "reader_id": "engine.json.loads+read_text",
            "module_rel": "command-center/blueprints/engineering/engine.py",
            "source_anchor": source_anchor(
                "command-center/blueprints/engineering/engine.py",
                ENGINE_LOAD_LINE,
            ),
            "kind": "config-artifact",
            "in_required_tests": True,
            "text_ascii": dumps(ascii_docs["engine"]),
            "text_latin1": dumps(latin_docs["engine"]),
            "invoke": _engine_sourced_load,
            "expect_ascii": _eq(ascii_docs["engine"]),
            "expect_latin1": _eq(latin_docs["engine"]),
        },
        {
            "reader_id": "unit_manifest.json.loads+read_text",
            "module_rel": "tools/command-center/unit_manifest.py",
            "source_anchor": source_anchor(
                "tools/command-center/unit_manifest.py",
                'value = json.loads(path.read_text(encoding="utf-8"))',
            ),
            "kind": "config-artifact",
            "in_required_tests": True,
            "text_ascii": dumps(ascii_docs["receipt"]),
            "text_latin1": dumps(latin_docs["receipt"]),
            "invoke": _unit_manifest_one,
            "expect_ascii": _eq(ascii_docs["receipt"]),
            "expect_latin1": _eq(latin_docs["receipt"]),
        },
        {
            "reader_id": "inventory._load_json",
            "module_rel": "tools/mcp-manager/core/inventory.py",
            "source_anchor": source_anchor(
                "tools/mcp-manager/core/inventory.py",
                "except (FileNotFoundError, json.JSONDecodeError, OSError):",
            ),
            "kind": "runtime-json",
            "in_required_tests": False,
            "text_ascii": dumps(ascii_docs["heartbeat"]),
            "text_latin1": dumps(latin_docs["heartbeat"]),
            "invoke": _inventory_load,
            "expect_ascii": _eq(ascii_docs["heartbeat"]),
            "expect_latin1": _eq(latin_docs["heartbeat"]),
        },
        {
            "reader_id": "planted.silent_empty_decoder",
            "module_rel": "command-center/p2-wave/probes/TST-0055/matrix.py",
            "source_anchor": plant_anchor,
            "kind": "control",
            "in_required_tests": False,
            "text_ascii": dumps(ascii_docs["plant"]),
            "text_latin1": dumps(latin_docs["plant"]),
            "invoke": planted_silent_empty,
            "expect_ascii": lambda got: isinstance(got, dict) and got.get("ok") is True,
            "expect_latin1": lambda got: isinstance(got, dict) and got.get("ok") is True,
        },
    ]


def _jsonable(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


def is_silent_empty(spec: dict, value: Any) -> bool:
    if value is None or value == {} or value == [] or value == "":
        return True
    if spec["reader_id"] == "inventory._load_json":
        if isinstance(value, dict) and int(value.get("token") or 0) == 0:
            return True
    if spec["reader_id"] == "id_closure.documented_ids" and value == set():
        return True
    return False


def classify_cell(spec: dict, enc: dict, raised: BaseException | None, value: Any) -> str:
    if raised is not None:
        return "REJECT_LOUD"
    if is_silent_empty(spec, value):
        return "SILENT_EMPTY"
    expect = spec["expect_latin1"] if enc["id"] == "latin-1" else spec["expect_ascii"]
    try:
        ok = bool(expect(value))
    except Exception:
        ok = False
    if ok:
        return "HANDLE"
    return "SILENT_WRONG"


def payload_text(spec: dict, enc: dict) -> str:
    if enc["id"] == "latin-1":
        return spec["text_latin1"]
    return spec["text_ascii"]


def run_one(spec: dict, enc: dict, tmp: Path) -> dict[str, Any]:
    text = payload_text(spec, enc)
    raw = encode_text(text, enc)
    path = tmp / f"{spec['reader_id'].replace('.', '_')}.{enc['id']}.json"
    path.write_bytes(raw)
    raised: BaseException | None = None
    value: Any = None
    try:
        value = spec["invoke"](path)
    except BaseException as exc:  # noqa: BLE001 — matrix must record whatever the reader raises
        raised = exc
    classification = classify_cell(spec, enc, raised, value)
    exc_type = type(raised).__name__ if raised is not None else None
    exc_text = None
    if raised is not None:
        exc_text = f"{type(raised).__name__}: {raised}"
    decoded_utf8 = None
    decode_err = None
    try:
        decoded_utf8 = path.read_text(encoding="utf-8")[:40]
    except Exception as exc:  # noqa: BLE001
        decode_err = f"{type(exc).__name__}: {exc}"
    return {
        "reader_id": spec["reader_id"],
        "module_rel": spec["module_rel"],
        "source_anchor": spec["source_anchor"],
        "kind": spec["kind"],
        "in_required_tests": spec["in_required_tests"],
        "encoding": enc["id"],
        "codec": enc["codec"],
        "byte_count": len(raw),
        "hex_prefix": hex_prefix(raw),
        "payload_kind": "latin-1-discriminator" if enc["id"] == "latin-1" else "ascii",
        "contains_latin1_mark_byte": LATIN1_MARK.encode("latin-1") in raw,
        "nul_count": raw.count(0),
        "classification": classification,
        "exception_type": exc_type,
        "exception_text": exc_text,
        "value": _jsonable(value) if raised is None else None,
        "utf8_decode_prefix": decoded_utf8,
        "utf8_decode_error": decode_err,
        "handled": classification == "HANDLE",
        "silent_empty": classification == "SILENT_EMPTY",
        "rejected_loudly": classification == "REJECT_LOUD",
    }


def encoding_self_check() -> dict[str, Any]:
    sample = dumps({"note": NOTE_LATIN1})
    bodies = {enc["id"]: encode_text(sample, enc) for enc in ENCODINGS}
    utf8 = bodies["utf-8"]
    latin1 = bodies["latin-1"]
    bom = bodies["utf-8-bom"]
    utf16 = bodies["utf-16-le"]
    utf16_ascii = '{"ok":true}'.encode("utf-16-le")
    return {
        "utf8_neq_latin1": utf8 != latin1,
        "latin1_has_e9": b"\xe9" in latin1,
        "utf8_has_c3a9": b"\xc3\xa9" in utf8,
        "bom_prefix": bom[:3] == b"\xef\xbb\xbf",
        "utf16_has_nuls": utf16.count(0) > 0,
        "utf16_no_bom": not utf16.startswith(b"\xff\xfe"),
        "utf16_ascii_nul_dense": utf16_ascii.count(0) * 2 >= len(utf16_ascii),
        "utf16_ascii_decodes_as_utf8": True,
        "sample_hex": {k: hex_prefix(v) for k, v in bodies.items()},
        "pass": (
            utf8 != latin1
            and b"\xe9" in latin1
            and b"\xc3\xa9" in utf8
            and bom[:3] == b"\xef\xbb\xbf"
            and utf16.count(0) > 0
            and not utf16.startswith(b"\xff\xfe")
            and utf16_ascii.count(0) * 2 >= len(utf16_ascii)
        ),
    }


def platform_info() -> dict[str, Any]:
    shells = {
        "bash": shutil.which("bash"),
        "pwsh": shutil.which("pwsh"),
        "powershell": shutil.which("powershell"),
    }
    win_shell_live = REPO / "rules/common/windows-shell.md"
    win_shell_fixture = (
        REPO
        / "command-center/p2-wave/probes/ARC-0005/fixtures/census/live/rules/common/windows-shell.md"
    )
    return {
        "system": platform.system(),
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "machine": platform.machine(),
        "windows": sys.platform == "win32",
        "shells": {k: v or None for k, v in shells.items()},
        "windows_shell_md_live": win_shell_live.is_file(),
        "windows_shell_md_fixture": win_shell_fixture.is_file(),
        "cwd": os.getcwd(),
        "note": (
            "Catalog evidence_requirement asks for a matrix produced on a Windows "
            "box. This worktree is Linux. The matrix is encoding-level against "
            "the live Python readers (codecs + json.loads), not a PowerShell "
            "Set-Content emission capture."
        ),
    }


def run_matrix() -> dict[str, Any]:
    specs = reader_specs()
    enc_check = encoding_self_check()
    cells: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="tst0055-") as td:
        tmp = Path(td)
        for spec in specs:
            for enc in ENCODINGS:
                cells.append(run_one(spec, enc, tmp))
    required = [c for c in cells if c["in_required_tests"]]
    bom_required = [c for c in required if c["encoding"] == "utf-8-bom"]
    utf16_required = [c for c in required if c["encoding"] == "utf-16-le"]
    utf8_required = [c for c in required if c["encoding"] == "utf-8"]
    bom_ok = all(c["classification"] in {"HANDLE", "REJECT_LOUD"} for c in bom_required)
    utf16_not_silent = all(c["classification"] != "SILENT_EMPTY" for c in utf16_required)
    utf8_handle = all(c["classification"] == "HANDLE" for c in utf8_required)
    inventory_utf16 = next(
        c
        for c in cells
        if c["reader_id"] == "inventory._load_json" and c["encoding"] == "utf-16-le"
    )
    plant_utf16 = next(
        c
        for c in cells
        if c["reader_id"] == "planted.silent_empty_decoder"
        and c["encoding"] == "utf-16-le"
    )
    plant_utf8 = next(
        c
        for c in cells
        if c["reader_id"] == "planted.silent_empty_decoder" and c["encoding"] == "utf-8"
    )
    silent = [
        {"reader_id": c["reader_id"], "encoding": c["encoding"], "classification": c["classification"]}
        for c in cells
        if c["classification"] in {"SILENT_EMPTY", "SILENT_WRONG"}
    ]
    loud = [
        {
            "reader_id": c["reader_id"],
            "encoding": c["encoding"],
            "exception_type": c["exception_type"],
            "exception_text": c["exception_text"],
        }
        for c in cells
        if c["classification"] == "REJECT_LOUD"
    ]
    handle = [
        {"reader_id": c["reader_id"], "encoding": c["encoding"]}
        for c in cells
        if c["classification"] == "HANDLE"
    ]
    return {
        "encoding_self_check": enc_check,
        "platform": platform_info(),
        "reader_count": len(specs),
        "cell_count": len(cells),
        "matrix": cells,
        "summary": {
            "handle": handle,
            "loud_failures": loud,
            "silent": silent,
            "required_utf8_handle": utf8_handle,
            "required_bom_handled_or_loud": bom_ok,
            "required_utf16_not_silent_empty": utf16_not_silent,
            "heartbeat_utf16_silent_empty": inventory_utf16["classification"]
            == "SILENT_EMPTY",
            "inventory_utf16_silent_empty": inventory_utf16["classification"]
            == "SILENT_EMPTY",
            "plant_utf16_silent_empty": plant_utf16["classification"] == "SILENT_EMPTY",
            "plant_utf8_handle": plant_utf8["classification"] == "HANDLE",
            "absent_readers": list(ABSENT_READERS),
        },
        "tests": {
            "test_bom_prefixed_json_is_handled_or_rejected_loudly": bom_ok and utf8_handle,
            "test_utf16_input_does_not_silently_parse_as_empty": utf16_not_silent,
        },
    }


def cell_fingerprint(cell: dict[str, Any]) -> dict[str, Any]:
    return {
        "reader_id": cell["reader_id"],
        "encoding": cell["encoding"],
        "classification": cell["classification"],
        "exception_type": cell.get("exception_type"),
        "exception_text": cell.get("exception_text"),
        "silent_empty": cell.get("silent_empty"),
        "rejected_loudly": cell.get("rejected_loudly"),
        "handled": cell.get("handled"),
    }


if __name__ == "__main__":
    doc = run_matrix()
    tests = doc["tests"]
    print(json.dumps({"tests": tests, "summary": doc["summary"], "cells": doc["cell_count"]}, sort_keys=True))
    if not doc["encoding_self_check"]["pass"]:
        print("FAILED:TST-0055-matrix encoding self-check")
        raise SystemExit(1)
    if not tests["test_bom_prefixed_json_is_handled_or_rejected_loudly"]:
        print("FAILED:TST-0055-matrix BOM test")
        raise SystemExit(1)
    if not tests["test_utf16_input_does_not_silently_parse_as_empty"]:
        print("FAILED:TST-0055-matrix UTF-16 silent-empty")
        raise SystemExit(1)
    print("SUCCESS:TST-0055-matrix")
