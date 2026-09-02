"""Live encoding / BOM / gated-mojibake census for AUD-0085."""
from __future__ import annotations

import codecs
import json
import os
from pathlib import Path
from typing import Any

import yaml

from common import (
    BINARY_SUFFIXES,
    FX_BOM,
    FX_CORRECT,
    FX_DOUBLE,
    FX_INVALID,
    FX_PLUGIN,
    OUT_REL,
    REPO,
    SELF_FIXTURE_PREFIX,
    SELF_PROBE_PREFIX,
    SKIP_BASENAMES,
    SKIP_DIR_NAMES,
    STRUCTURED_MAX_BYTES,
    STRUCTURED_SUFFIXES,
    TEXT_SUFFIXES,
    UNSTRUCTURED_MAX_BYTES,
)
from detector import control_vectors, detect_spans
from fixtures import ensure_fixtures

BOM_TABLE = (
    (b"\x00\x00\xfe\xff", "UTF-32-BE"),
    (b"\xff\xfe\x00\x00", "UTF-32-LE"),
    (b"\xef\xbb\xbf", "UTF-8"),
    (b"\xfe\xff", "UTF-16-BE"),
    (b"\xff\xfe", "UTF-16-LE"),
)
PROBE_DIR = "command-center/p2-wave/probes/AUD-0085/"


def relpath(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def classify_scope(path: Path, prefix: bytes) -> str:
    suf = path.suffix.lower()
    if suf in BINARY_SUFFIXES:
        return "binary"
    if suf in TEXT_SUFFIXES or path.name in {"plugin.json", "marketplace.json"}:
        return "text"
    if b"\x00" in prefix:
        return "binary"
    return "text" if suf else "binary"


def detect_bom(prefix: bytes) -> str | None:
    for magic, name in BOM_TABLE:
        if prefix.startswith(magic):
            return name
    return None


def incremental_decode(path: Path) -> tuple[bool, str | None]:
    try:
        with path.open("rb") as fh:
            decoder = codecs.getincrementaldecoder("utf-8")("strict")
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    decoder.decode(b"", final=True)
                    break
                decoder.decode(chunk, final=False)
        return True, None
    except UnicodeDecodeError as exc:
        return False, str(exc)
    except OSError as exc:
        return False, f"read-error:{exc}"


def load_utf8(path: Path) -> tuple[bool, str | None, dict | None]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return False, None, {"reason": f"read-error:{exc}"}
    try:
        return True, raw.decode("utf-8"), None
    except UnicodeDecodeError as exc:
        return (
            False,
            None,
            {
                "reason": "unicode-decode",
                "start": exc.start,
                "message": str(exc),
                "offending_hex": raw[exc.start : exc.start + 8].hex(),
            },
        )


def walk_strings(obj: Any, prefix: str = "$") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(obj, str):
        out.append((prefix, obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k)
            out.extend(walk_strings(key, f"{prefix}/~key"))
            out.extend(walk_strings(v, f"{prefix}/{key}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(walk_strings(v, f"{prefix}/{i}"))
    return out


def parse_structured(path: Path, text: str) -> tuple[str | None, Any, str | None]:
    name = path.name
    suf = path.suffix.lower()
    if suf == ".json" or name in {"plugin.json", "marketplace.json"}:
        try:
            return "json", json.loads(text), None
        except json.JSONDecodeError as exc:
            return "json", None, f"json:{exc.msg} line {exc.lineno}"
    if suf == ".jsonl":
        rows = []
        for i, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                return "jsonl", None, f"jsonl:{i}:{exc.msg}"
        return "jsonl", rows, None
    if suf in {".yaml", ".yml"}:
        try:
            return "yaml", yaml.safe_load(text), None
        except yaml.YAMLError as exc:
            return "yaml", None, f"yaml:{exc}"
    return None, None, None


def is_plugin_manifest(path: Path, obj: Any) -> bool:
    if path.name not in {"plugin.json", "marketplace.json"}:
        return False
    return isinstance(obj, dict) and "name" in obj


def find_path_readers(needles: list[str]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {n: [] for n in needles}
    if not needles:
        return hits
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            p = Path(dirpath) / fn
            try:
                blob = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = relpath(p)
            for n in needles:
                if n in blob:
                    hits[n].append(rel)
    return hits


def span_dicts(text: str, location: str) -> list[dict]:
    return [
        {
            "location": location,
            "original": sp.original,
            "recovered": sp.recovered,
            "utf8_hex": sp.utf8_hex,
            "start": sp.start,
            "end": sp.end,
        }
        for sp in detect_spans(text)
    ]


def consumer_for(rel: str, row: dict, readers: dict[str, list[str]]) -> dict:
    hits = readers.get(rel) or []
    product = [h for h in hits if PROBE_DIR not in h]
    probe = [h for h in hits if PROBE_DIR in h]
    parse_ok = bool(
        row.get("json_loads_ok")
        or row.get("yaml_load_ok")
        or row.get("plugin_manifest_ok")
    )
    ext = Path(rel).suffix.lower().lstrip(".")
    if product and parse_ok:
        consumption = "product-reader-and-parse-ok"
    elif parse_ok:
        consumption = "parse-ok-unproven-product-reader"
    elif probe:
        consumption = "probe-rehearsal-only"
    else:
        consumption = "NOT-CHECKED"
    return {
        "extension_suggested": ext or None,
        "json_loads_ok": row.get("json_loads_ok"),
        "yaml_load_ok": row.get("yaml_load_ok"),
        "plugin_manifest_ok": row.get("plugin_manifest_ok"),
        "path_specific_readers_product": product[:8],
        "path_specific_readers_probe": probe[:8],
        "strict_parser_consumed": bool(product) and parse_ok,
        "consumption": consumption,
    }


def run_census() -> dict:
    ensure_fixtures()
    files_scanned = 0
    invalid_all: list[dict] = []
    invalid_text: list[dict] = []
    bom_rows: list[dict] = []
    mojibake: list[dict] = []
    parse_failed: list[dict] = []
    skipped_large: list[str] = []
    plugin_checked = 0
    plugin_ok = 0

    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        base = Path(dirpath)
        for fn in filenames:
            if fn in SKIP_BASENAMES:
                continue
            path = base / fn
            if not path.is_file() or path.is_symlink():
                continue
            rel = relpath(path)
            if rel == OUT_REL:
                continue
            if rel.startswith(SELF_PROBE_PREFIX) and not rel.startswith(
                SELF_FIXTURE_PREFIX
            ):
                continue
            files_scanned += 1
            try:
                with path.open("rb") as fh:
                    prefix = fh.read(16)
                size = path.stat().st_size
            except OSError as exc:
                invalid_all.append(
                    {"path": rel, "error": f"read-error:{exc}", "scope": "unknown"}
                )
                continue
            bom = detect_bom(prefix)
            scope = classify_scope(path, prefix)
            if bom:
                bom_rows.append(
                    {"path": rel, "bom": bom, "scope": scope, "size": size}
                )

            if scope == "binary" or size > STRUCTURED_MAX_BYTES:
                ok, err = incremental_decode(path)
                if bom:
                    bom_rows[-1]["utf8_ok"] = ok
                if not ok:
                    invalid_all.append(
                        {
                            "path": rel,
                            "scope": scope,
                            "error": err or "decode-failed",
                            "size": size,
                        }
                    )
                continue

            ok, text, err = load_utf8(path)
            if bom:
                bom_rows[-1]["utf8_ok"] = ok
            if not ok:
                row = {
                    "path": rel,
                    "scope": scope,
                    "error": (err or {}).get("message", "decode-failed"),
                    "offending_hex": (err or {}).get("offending_hex"),
                    "size": size,
                }
                invalid_all.append(row)
                if scope == "text":
                    invalid_text.append(row)
                continue
            assert text is not None
            suf = path.suffix.lower()
            structured = suf in STRUCTURED_SUFFIXES or fn in {
                "plugin.json",
                "marketplace.json",
            }
            if structured:
                kind, obj, perr = parse_structured(path, text)
                if perr:
                    parse_failed.append({"path": rel, "kind": kind, "error": perr})
                    continue
                if kind is None:
                    continue
                plugin_hit = is_plugin_manifest(path, obj)
                if path.name in {"plugin.json", "marketplace.json"}:
                    plugin_checked += 1
                    if plugin_hit:
                        plugin_ok += 1
                spans_here: list[dict] = []
                for loc, s in walk_strings(obj):
                    spans_here.extend(span_dicts(s, loc))
                if spans_here:
                    json_ok = kind in {"json", "jsonl"}
                    yaml_ok = kind == "yaml"
                    mojibake.append(
                        {
                            "path": rel,
                            "kind": kind,
                            "span_count": len(spans_here),
                            "spans": spans_here[:12],
                            "json_loads_ok": json_ok,
                            "yaml_load_ok": yaml_ok,
                            "plugin_manifest_ok": plugin_hit,
                            "parse_rehearsal": kind,
                        }
                    )
            elif scope == "text" and size <= UNSTRUCTURED_MAX_BYTES:
                spans_u = span_dicts(text, "$/text")
                if spans_u:
                    mojibake.append(
                        {
                            "path": rel,
                            "kind": "unstructured-after-utf8-decode",
                            "span_count": len(spans_u),
                            "spans": spans_u[:12],
                            "json_loads_ok": False,
                            "yaml_load_ok": False,
                            "plugin_manifest_ok": False,
                            "parse_rehearsal": "utf8-decode",
                        }
                    )
            elif scope == "text" and size > UNSTRUCTURED_MAX_BYTES:
                skipped_large.append(rel)

    finding_paths = sorted(
        set(
            [r["path"] for r in invalid_text]
            + [r["path"] for r in bom_rows]
            + [r["path"] for r in mojibake]
        )
    )
    readers = find_path_readers(finding_paths)

    for row in mojibake:
        row["consumer"] = consumer_for(row["path"], row, readers)
    for row in invalid_text:
        row["json_loads_ok"] = False
        row["yaml_load_ok"] = False
        row["plugin_manifest_ok"] = False
        row["consumer"] = consumer_for(row["path"], row, readers)
    for row in bom_rows:
        json_ok = False
        if row.get("utf8_ok") and str(row["path"]).endswith(".json"):
            p = REPO / row["path"]
            try:
                json.loads(p.read_text(encoding="utf-8"))
                json_ok = True
            except (OSError, UnicodeError, json.JSONDecodeError):
                json_ok = False
        row["json_loads_ok"] = json_ok
        row["yaml_load_ok"] = False
        row["plugin_manifest_ok"] = False
        row["consumer"] = consumer_for(row["path"], row, readers)

    overclaim = [
        r["path"]
        for r in mojibake
        if r["consumer"]["strict_parser_consumed"]
        and not r["consumer"]["path_specific_readers_product"]
    ]
    controls = control_vectors()
    double_hit = any(r["path"] == FX_DOUBLE for r in mojibake)
    correct_hit = any(r["path"] == FX_CORRECT for r in mojibake)
    bom_hit = any(r["path"] == FX_BOM for r in bom_rows)
    inv_hit = any(r["path"] == FX_INVALID for r in invalid_text)

    summary = {
        "files_scanned": files_scanned,
        "invalid_utf8_all_count": len(invalid_all),
        "invalid_utf8_text_count": len(invalid_text),
        "invalid_utf8_text_paths": sorted(r["path"] for r in invalid_text),
        "bom_count": len(bom_rows),
        "bom_paths": sorted(r["path"] for r in bom_rows),
        "confirmed_mojibake_count": len(mojibake),
        "confirmed_mojibake_paths": sorted(r["path"] for r in mojibake),
        "strict_consumed_count": sum(
            1 for r in mojibake if r["consumer"]["strict_parser_consumed"]
        ),
        "parse_failed_structured_count": len(parse_failed),
        "plugin_manifests_checked": plugin_checked,
        "plugin_manifests_ok": plugin_ok,
        "skipped_large_count": len(skipped_large),
        "extension_only_overclaim_paths": overclaim,
        "planted_double_decoded_fired": double_hit,
        "planted_correct_silent": not correct_hit,
        "planted_bom_seen": bom_hit,
        "planted_invalid_seen": inv_hit,
        "controls": controls,
        "planted": {
            "double_decoded": FX_DOUBLE,
            "correct_nonascii": FX_CORRECT,
            "utf8_bom": FX_BOM,
            "invalid_utf8": FX_INVALID,
            "plugin": FX_PLUGIN,
        },
    }
    return {
        "summary": summary,
        "invalid_utf8_all_sample": invalid_all[:40],
        "invalid_utf8_text": invalid_text,
        "bom_rows": bom_rows,
        "mojibake": mojibake,
        "parse_failed": parse_failed[:40],
        "skipped_large": skipped_large[:20],
    }


if __name__ == "__main__":
    data = run_census()
    s = data["summary"]
    slim = {k: s[k] for k in s if k != "controls"}
    print(json.dumps(slim, indent=2, sort_keys=True)[:8000])
    print("SUCCESS:AUD-0085 census")
