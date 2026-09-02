#!/usr/bin/env python3
"""YAML 1.1 scalar-coercion probe for TST-0059.

Compares PyYAML SafeLoader (YAML 1.1 implicit typing — the loader this repo
calls) against a string-preserving loader, key by key.

Hazard classes (meaning-changing, per the catalog row):
  * YAML 1.1 extra boolean words: NO / OFF / ON / YES (and y/n case variants)
  * mapping keys that become bool True/False (GitHub Actions `on:`)
  * version-like dotted scalars whose lexical form is not the float repr (3.10)
  * empty / ~ scalars that become None
Canonical YAML 1.2 true/false/null and ordinary ints are recorded, not hazards.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLANTED = HERE / "fixtures" / "planted-coercion.yaml"
QUOTED = HERE / "fixtures" / "quoted-safe.yaml"
QUALITY_REL = ".github/workflows/quality.yml"

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".cache",
        "vendor",
        "deps",
        "site-packages",
    }
)
SKIP_PATH_PARTS = (
    "/p2-wave/probes/",
    "/probes/TST-0250/runtime/",
)

YAML11_BOOL_CF = frozenset(
    {"y", "yes", "n", "no", "on", "off"}
)
DOTTED_NUMBER = re.compile(r"^[0-9]+\.[0-9]+$")
READER_CALL = re.compile(r"yaml\.(safe_load|load|unsafe_load)\s*\(")


class StringLoader(yaml.SafeLoader):
    """SafeLoader with implicit resolvers stripped so every scalar stays a str."""


StringLoader.yaml_implicit_resolvers = {}


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def py_type(value: Any) -> str:
    if value is None:
        return "null"
    if value is True or value is False:
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def jsonable(value: Any) -> Any:
    if value is True or value is False or value is None:
        return value
    if isinstance(value, (int, float, str)):
        return value
    return repr(value)


def hazard_for_scalar(token: str, loaded: Any) -> str | None:
    if loaded is True or loaded is False:
        if token.casefold() in YAML11_BOOL_CF:
            return "yaml11-bool-word"
        return None
    if loaded is None:
        if token.strip() in {"", "~"}:
            return "empty-to-null"
        return None
    if isinstance(loaded, float) and not isinstance(loaded, bool):
        if DOTTED_NUMBER.fullmatch(token):
            frac = token.split(".", 1)[1]
            if token != str(loaded) or frac.endswith("0"):
                return "version-like-float"
        return None
    return None


def hazard_for_key(declared: str, loaded_key: Any) -> str | None:
    if loaded_key is True or loaded_key is False:
        if declared.casefold() in YAML11_BOOL_CF:
            return "yaml11-bool-key"
    return None


def join_path(prefix: str, key: str) -> str:
    if not prefix:
        return key
    if key.startswith("["):
        return prefix + key
    return f"{prefix}.{key}"


def walk(coerced: Any, literal: Any, prefix: str, rows: list[dict]) -> None:
    if isinstance(coerced, dict) or isinstance(literal, dict):
        c = coerced if isinstance(coerced, dict) else {}
        lit = literal if isinstance(literal, dict) else {}
        used_c: set[Any] = set()
        used_l: set[Any] = set()
        for k in list(c.keys()):
            if k in lit:
                used_c.add(k)
                used_l.add(k)
                walk(c[k], lit[k], join_path(prefix, str(k)), rows)
        remain_c = [k for k in c.keys() if k not in used_c]
        remain_l = [k for k in lit.keys() if k not in used_l]
        for ck in remain_c:
            matched = None
            for lk in remain_l:
                try:
                    coerced_lk = yaml.safe_load(lk) if isinstance(lk, str) else lk
                except Exception:
                    coerced_lk = None
                if coerced_lk == ck or (lk == "" and ck is None):
                    matched = lk
                    break
            path_key = str(matched) if matched is not None else repr(ck)
            path = join_path(prefix, path_key)
            hz = (
                hazard_for_key(matched, ck)
                if isinstance(matched, str)
                else "unpaired-key"
            )
            rows.append(
                {
                    "kind": "key",
                    "path": path,
                    "declared_token": matched if isinstance(matched, str) else repr(matched),
                    "loaded_type": py_type(ck),
                    "loaded_value": jsonable(ck),
                    "hazard": hz,
                }
            )
            if matched is not None:
                remain_l.remove(matched)
                walk(c[ck], lit[matched], path, rows)
        for lk in remain_l:
            rows.append(
                {
                    "kind": "key",
                    "path": join_path(prefix, str(lk)),
                    "declared_token": lk if isinstance(lk, str) else repr(lk),
                    "loaded_type": "absent-in-coerced",
                    "loaded_value": None,
                    "hazard": "unpaired-key",
                }
            )
        return
    if isinstance(coerced, list) and isinstance(literal, list):
        n = max(len(coerced), len(literal))
        for i in range(n):
            a = coerced[i] if i < len(coerced) else None
            b = literal[i] if i < len(literal) else None
            walk(a, b, f"{prefix}[{i}]", rows)
        return
    token = literal if isinstance(literal, str) else "" if literal is None else str(literal)
    hz = hazard_for_scalar(literal, coerced) if isinstance(literal, str) else None
    rows.append(
        {
            "kind": "value",
            "path": prefix or "$",
            "declared_token": token,
            "loaded_type": py_type(coerced),
            "loaded_value": jsonable(coerced),
            "hazard": hz,
        }
    )


def probe_document(text: str, source: str) -> dict:
    sha = digest_text(text)
    try:
        coerced = yaml.safe_load(text)
        literal = yaml.load(text, Loader=StringLoader)
    except Exception as exc:
        return {
            "source": source,
            "sha256": sha,
            "bytes": len(text.encode("utf-8")),
            "parse_ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "rows": [],
            "hazards": [],
            "hazard_count": 0,
            "row_count": 0,
        }
    rows: list[dict] = []
    walk(coerced, literal, "", rows)
    hazards = [r for r in rows if r.get("hazard")]
    return {
        "source": source,
        "sha256": sha,
        "bytes": len(text.encode("utf-8")),
        "parse_ok": True,
        "error": None,
        "rows": rows,
        "hazards": hazards,
        "hazard_count": len(hazards),
        "row_count": len(rows),
    }


def should_skip(path: Path) -> bool:
    posix = path.as_posix().replace("\\", "/")
    for part in path.parts:
        if part in SKIP_DIR_NAMES or part.endswith(".egg-info"):
            return True
    for needle in SKIP_PATH_PARTS:
        if needle in posix:
            return True
    return False


def _pruned_walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES and not d.endswith(".egg-info")
        ]
        posix = Path(dirpath).as_posix().replace("\\", "/")
        if any(needle in posix for needle in SKIP_PATH_PARTS):
            dirnames[:] = []
            continue
        yield Path(dirpath), filenames


def iter_yaml_files() -> list[Path]:
    found: list[Path] = []
    for directory, filenames in _pruned_walk(REPO):
        for name in filenames:
            if Path(name).suffix.lower() not in {".yml", ".yaml"}:
                continue
            path = directory / name
            if should_skip(path):
                continue
            found.append(path)
    return sorted(found, key=rel)


def live_corpus() -> list[dict]:
    docs = []
    for path in iter_yaml_files():
        text = path.read_text(encoding="utf-8")
        docs.append(probe_document(text, rel(path)))
    return docs


def adjacent_probe_yaml() -> dict:
    """Sibling probe YAML is not product config; GitHub `on:` still shows up there."""
    root = REPO / "command-center" / "p2-wave" / "probes"
    docs = []
    if root.is_dir():
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in SKIP_DIR_NAMES and not d.endswith(".egg-info")
            ]
            posix = Path(dirpath).as_posix().replace("\\", "/")
            if "/TST-0250/runtime/" in posix:
                dirnames[:] = []
                continue
            for name in filenames:
                if Path(name).suffix.lower() not in {".yml", ".yaml"}:
                    continue
                path = Path(dirpath) / name
                posix_f = path.as_posix().replace("\\", "/")
                if "/probes/TST-0059/fixtures/" in posix_f:
                    continue
                text = path.read_text(encoding="utf-8")
                docs.append(probe_document(text, rel(path)))
    hazards = []
    for doc in docs:
        for h in doc["hazards"]:
            hazards.append({"source": doc["source"], **h})
    return {
        "file_count": len(docs),
        "hazard_count": len(hazards),
        "hazards": hazards,
        "note": (
            "Not in the live product-config corpus. Recorded because these "
            "GitHub-Actions-shaped fixtures are the same `on:` key hazard "
            "quality.yml would hit under PyYAML YAML 1.1."
        ),
    }


def reader_call_sites() -> list[dict]:
    sites = []
    found: list[Path] = []
    for directory, filenames in _pruned_walk(REPO):
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = directory / name
            if should_skip(path):
                continue
            found.append(path)
    for path in sorted(found, key=rel):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "yaml." not in text or not READER_CALL.search(text):
            continue
        lines = []
        for i, line in enumerate(text.splitlines(), 1):
            if READER_CALL.search(line) and "READER_CALL" not in line:
                lines.append({"line": i, "text": line.strip()[:220]})
        if lines:
            sites.append({"path": rel(path), "calls": lines})
    return sites


def matrix_fixture_demo() -> dict:
    """AUD-0041 in-code YAML is loaded with yaml.safe_load; `on:` becomes True."""
    src = REPO / "command-center" / "p2-wave" / "_build_AUD0041.py"
    if not src.is_file():
        return {"present": False, "extracted": False, "hazards": []}
    text = src.read_text(encoding="utf-8")
    tree = ast.parse(text)
    blob = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "MATRIX_FIXTURE":
                    blob = ast.literal_eval(node.value)
    if not isinstance(blob, str):
        return {"present": True, "extracted": False, "hazards": []}
    doc = probe_document(blob, "command-center/p2-wave/_build_AUD0041.py:MATRIX_FIXTURE")
    return {
        "present": True,
        "extracted": True,
        "source": doc["source"],
        "hazard_count": doc["hazard_count"],
        "hazards": doc["hazards"],
        "note": (
            "In-code fixture, not a repo config file. Live yaml.safe_load call "
            "site exposed to YAML 1.1 key coercion of `on:`."
        ),
    }


def _has_token(hazards: list[dict], token: str, kind: str) -> bool:
    for row in hazards:
        if str(row.get("declared_token")) == token and row.get("hazard") == kind:
            return True
    return False


def required_planted_checks(hazards: list[dict]) -> dict[str, bool]:
    return {
        "country_NO_bool": _has_token(hazards, "NO", "yaml11-bool-word"),
        "switch_OFF_bool": _has_token(hazards, "OFF", "yaml11-bool-word"),
        "feature_ON_bool": _has_token(hazards, "ON", "yaml11-bool-word"),
        "accept_YES_bool": _has_token(hazards, "YES", "yaml11-bool-word"),
        "python_3_10_float": _has_token(hazards, "3.10", "version-like-float"),
        "release_1_10_float": _has_token(hazards, "1.10", "version-like-float"),
        "blank_empty_null": any(
            h.get("hazard") == "empty-to-null"
            and str(h.get("path", "")).endswith("blank")
            for h in hazards
        ),
        "on_key_bool": any(h.get("hazard") == "yaml11-bool-key" for h in hazards),
    }


def planted_control() -> dict:
    text = PLANTED.read_text(encoding="utf-8")
    doc = probe_document(text, rel(PLANTED))
    checks = required_planted_checks(doc["hazards"])
    fired = all(checks.values()) and doc["hazard_count"] >= 7
    return {
        "source": doc["source"],
        "parse_ok": doc["parse_ok"],
        "hazard_count": doc["hazard_count"],
        "hazards": doc["hazards"],
        "required_checks": checks,
        "fired": fired,
    }


def quoted_control() -> dict:
    text = QUOTED.read_text(encoding="utf-8")
    doc = probe_document(text, rel(QUOTED))
    silent = doc["parse_ok"] and doc["hazard_count"] == 0
    return {
        "source": doc["source"],
        "parse_ok": doc["parse_ok"],
        "hazard_count": doc["hazard_count"],
        "hazards": doc["hazards"],
        "silent": silent,
    }


def missing_catalog_inputs() -> list[dict]:
    quality = REPO / QUALITY_REL
    prompts = REPO / "_USER-PROMPTS.md"
    return [
        {
            "input": QUALITY_REL,
            "exists": quality.is_file(),
            "role": "catalog-named-yaml-config",
        },
        {
            "input": "_USER-PROMPTS.md",
            "exists": prompts.is_file(),
            "role": "catalog-named-spec-anchor",
            "anchor": ":11014",
        },
    ]


def quality_on_key_listed(live_hazards: list[dict]) -> bool:
    for row in live_hazards:
        if row.get("source") != QUALITY_REL:
            continue
        if row.get("hazard") != "yaml11-bool-key":
            continue
        if str(row.get("declared_token") or "").casefold() == "on":
            return True
    return False


def run_suite() -> dict:
    live = live_corpus()
    live_hazards = []
    for doc in live:
        for h in doc["hazards"]:
            live_hazards.append({"source": doc["source"], **h})
    planted = planted_control()
    quoted = quoted_control()
    readers = reader_call_sites()
    demo = matrix_fixture_demo()
    missing = missing_catalog_inputs()
    adjacent = adjacent_probe_yaml()
    quality_exists = (REPO / QUALITY_REL).is_file()
    quality_in_corpus = any(d.get("source") == QUALITY_REL for d in live)
    quality_on = quality_on_key_listed(live_hazards)
    scan_ok = bool(live) and all(
        d.get("parse_ok") or d.get("error") for d in live
    )
    # "Silently coerced" means a meaning-changing YAML 1.1 load that this probe
    # does not list. Catalog input quality.yml has unquoted `on:`; t1 passes only
    # when that key is listed (live positive instance), not when the corpus is
    # claimed empty by skipping the file.
    t1_pass = scan_ok and (quality_in_corpus and quality_on if quality_exists else True)
    t1 = {
        "id": "test_no_key_is_silently_coerced",
        "pass": t1_pass,
        "scope": (
            "product/config YAML on disk (.github including quality.yml, "
            "seed-stage, tools excluding vendor/, skills). Sibling "
            "p2-wave/probes fixtures excluded from this pass and reported "
            "under adjacent_probe_yaml."
        ),
        "live_hazard_count": len(live_hazards),
        "quality_yml_exists": quality_exists,
        "quality_yml_scanned": quality_in_corpus,
        "quality_on_key_listed": quality_on,
    }
    t2 = {
        "id": "test_probe_detects_a_planted_coercion",
        "pass": bool(planted["fired"]) and bool(quoted["silent"]),
        "planted_fired": planted["fired"],
        "quoted_silent": quoted["silent"],
        "required_checks": planted["required_checks"],
    }
    return {
        "loader": {
            "coercing": "yaml.SafeLoader (PyYAML YAML 1.1 implicit resolvers)",
            "literal": "StringLoader = SafeLoader with yaml_implicit_resolvers={}",
            "pyyaml_version": getattr(yaml, "__version__", "unknown"),
        },
        "live_yaml_files": live,
        "live_file_count": len(live),
        "live_hazards": live_hazards,
        "live_hazard_count": len(live_hazards),
        "test_no_key_is_silently_coerced": t1,
        "test_probe_detects_a_planted_coercion": t2,
        "planted_control": planted,
        "quoted_control": quoted,
        "reader_call_sites": readers,
        "inline_matrix_fixture": demo,
        "missing_catalog_inputs": missing,
        "adjacent_probe_yaml": adjacent,
        "exposed_keys_live": live_hazards,
        "pass": bool(t1["pass"] and t2["pass"]),
    }


def main() -> int:
    result = run_suite()
    print(
        json.dumps(
            {
                "live_file_count": result["live_file_count"],
                "live_hazard_count": result["live_hazard_count"],
                "planted_fired": result["planted_control"]["fired"],
                "quoted_silent": result["quoted_control"]["silent"],
                "pass": result["pass"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
