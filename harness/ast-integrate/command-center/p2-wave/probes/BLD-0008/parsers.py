"""Product parser wrappers. Each wrapper takes raw bytes and uses the shipped call path."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS_CC = REPO / "tools" / "command-center"
TOOLS_ROUTER = REPO / "tools" / "router"
TOOLS_SPEC = REPO / "tools" / "agentspec" / "agentspec"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_register = None
_frontmatter = None
_oracle = None


def register_mod():
    global _register
    if _register is None:
        sys.path.insert(0, str(TOOLS_CC))
        _register = _load("bld0008_register_parse", TOOLS_CC / "register_parse.py")
    return _register


def frontmatter_fn() -> Callable[[str], dict]:
    global _frontmatter
    if _frontmatter is None:
        mod = _load("bld0008_index_cache", TOOLS_ROUTER / "index_cache.py")
        _frontmatter = mod._parse_frontmatter
    return _frontmatter


def oracle_mod():
    global _oracle
    if _oracle is None:
        _oracle = _load("bld0008_oracle", TOOLS_SPEC / "oracle.py")
    return _oracle


def product_utf8_decode(raw: bytes) -> str:
    """catalog.load / parse_file / unit_manifest: Path.read_text(encoding='utf-8')."""
    return raw.decode("utf-8")


def canonical(value: Any) -> str:
    if hasattr(value, "rows") and hasattr(value, "owner_questions"):
        rows = [
            {
                "id": r.row_id,
                "section": r.section,
                "program": r.program,
                "title": r.title,
            }
            for r in value.rows
        ]
        return json.dumps(
            {"rows": rows, "owner_questions": list(value.owner_questions)},
            sort_keys=True,
            default=str,
        )
    if hasattr(value, "ok") and hasattr(value, "reason"):
        return json.dumps(
            {
                "ok": value.ok,
                "reason": value.reason,
                "schema_validated": value.schema_validated,
                "progress_stream": value.progress_stream,
            },
            sort_keys=True,
            default=str,
        )
    return json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)


@dataclass(frozen=True)
class ParseAttempt:
    outcome: str
    error: str | None
    canonical: str | None
    keys: list[str]
    notes: str


def _named(err: BaseException, notes: str = "") -> ParseAttempt:
    return ParseAttempt(
        outcome="NAMED-REJECT" if not isinstance(err, UnicodeDecodeError) else "DECODE-REJECT",
        error=type(err).__name__,
        canonical=None,
        keys=[],
        notes=notes or f"{type(err).__name__}: {err}"[:240],
    )


def parse_json_catalog(raw: bytes) -> ParseAttempt:
    """tools/command-center/catalog.py load(): json.loads(read_text utf-8)."""
    try:
        text = product_utf8_decode(raw)
    except UnicodeDecodeError as exc:
        return _named(exc, "catalog.load never reaches json.loads: utf-8 decode fails")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return _named(exc)
    keys: list[str] = []
    if isinstance(obj, dict):
        keys = [str(k) for k in obj.keys()]
        if any(k.startswith("\ufeff") for k in keys):
            return ParseAttempt(
                "SILENT-BOM-KEY",
                None,
                canonical(obj),
                keys,
                "BOM survived into a JSON object key",
            )
    return ParseAttempt("PARSE-OK", None, canonical(obj), keys, "json.loads after utf-8")


def parse_jsonl_events(raw: bytes) -> ParseAttempt:
    """tools/command-center/tests/test_close.py: json.loads per events line."""
    try:
        text = product_utf8_decode(raw)
    except UnicodeDecodeError as exc:
        return _named(exc)
    recs = []
    try:
        for line in text.splitlines():
            if not line.strip():
                continue
            recs.append(json.loads(line))
    except json.JSONDecodeError as exc:
        return _named(exc, "jsonl line json.loads")
    return ParseAttempt("PARSE-OK", None, canonical(recs), [], "jsonl json.loads per line")


def parse_yaml(raw: bytes) -> ParseAttempt:
    try:
        import yaml  # type: ignore
    except ImportError:
        return ParseAttempt(
            "PARSER-ABSENT",
            "ImportError",
            None,
            [],
            "no tools/ call site; PyYAML not importable on this runtime",
        )
    try:
        text = product_utf8_decode(raw)
    except UnicodeDecodeError as exc:
        return _named(exc)
    try:
        obj = yaml.safe_load(text)
    except Exception as exc:  # yaml.YAMLError and variants
        return _named(exc, "yaml.safe_load (not a tools/ call site; runtime family)")
    return ParseAttempt(
        "PARSE-OK",
        None,
        canonical(obj),
        list(obj) if isinstance(obj, dict) else [],
        "yaml.safe_load; no tools/ import of yaml — runtime family only",
    )


def parse_toml(raw: bytes) -> ParseAttempt:
    try:
        import tomllib
    except ImportError:
        return ParseAttempt("PARSER-ABSENT", "ImportError", None, [], "tomllib missing")
    try:
        text = product_utf8_decode(raw)
    except UnicodeDecodeError as exc:
        return _named(exc)
    try:
        obj = tomllib.loads(text)
    except Exception as exc:
        return _named(exc, "tomllib.loads — stdlib; no tools/ product call site")
    return ParseAttempt(
        "PARSE-OK",
        None,
        canonical(obj),
        list(obj) if isinstance(obj, dict) else [],
        "tomllib.loads stdlib; no tools/ call site found",
    )


def parse_frontmatter(raw: bytes) -> ParseAttempt:
    try:
        text = product_utf8_decode(raw)
    except UnicodeDecodeError as exc:
        return _named(exc)
    fn = frontmatter_fn()
    fields = fn(text)
    return ParseAttempt(
        "PARSE-OK",
        None,
        canonical(fields),
        list(fields),
        "tools/router/index_cache.py _parse_frontmatter",
    )


def parse_env_file(raw: bytes) -> ParseAttempt:
    del raw
    return ParseAttempt(
        "PARSER-ABSENT",
        None,
        None,
        [],
        "tools/ has no .env file reader; env_allowlist.py reads os.environ and security.mjs",
    )


def parse_manifest_json(raw: bytes) -> ParseAttempt:
    """unit_manifest.py: json.loads(path.read_text(encoding='utf-8'))."""
    return parse_json_catalog(raw)


def parse_receipt_oracle(raw: bytes) -> ParseAttempt:
    try:
        text = product_utf8_decode(raw)
    except UnicodeDecodeError as exc:
        return _named(exc)
    result = oracle_mod().classify_producer_body(text)
    return ParseAttempt(
        "PARSE-OK",
        None,
        canonical(result),
        [],
        "tools/agentspec/agentspec/oracle.py classify_producer_body",
    )


def parse_register_md(raw: bytes) -> ParseAttempt:
    try:
        text = product_utf8_decode(raw)
    except UnicodeDecodeError as exc:
        return _named(exc)
    parsed = register_mod().parse_text(text)
    return ParseAttempt(
        "PARSE-OK",
        None,
        canonical(parsed),
        [r.row_id for r in parsed.rows],
        "tools/command-center/register_parse.py parse_text",
    )


PARSERS: dict[str, Callable[[bytes], ParseAttempt]] = {
    "json-catalog": parse_json_catalog,
    "jsonl-events": parse_jsonl_events,
    "yaml": parse_yaml,
    "toml": parse_toml,
    "md-frontmatter": parse_frontmatter,
    "env-file": parse_env_file,
    "manifest-json": parse_manifest_json,
    "receipt-oracle": parse_receipt_oracle,
    "register-md": parse_register_md,
}

PARSER_PATHS = {
    "json-catalog": "tools/command-center/catalog.py:load",
    "jsonl-events": "tools/command-center/tests/test_close.py (EVENTS.jsonl json.loads per line)",
    "yaml": "ABSENT-in-tools (runtime yaml.safe_load if installed)",
    "toml": "ABSENT-in-tools (stdlib tomllib.loads)",
    "md-frontmatter": "tools/router/index_cache.py:_parse_frontmatter",
    "env-file": "ABSENT (tools/lib/env_allowlist.py does not parse .env files)",
    "manifest-json": "tools/command-center/unit_manifest.py json.loads(read_text utf-8)",
    "receipt-oracle": "tools/agentspec/agentspec/oracle.py:classify_producer_body",
    "register-md": "tools/command-center/register_parse.py:parse_text",
}
