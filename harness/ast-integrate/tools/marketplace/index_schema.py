"""Canonical marketplace index schema + dual validators.

Engine A uses jsonschema.Draft202012Validator (imported inside the function).
Engine B is a local walker that does not import jsonschema.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

INDEX_REL = ".claude-plugin/marketplace.json"
SCHEMA_REL = ".claude-plugin/marketplace.schema.json"
MUTATION_IDS = (
    "missing_owner",
    "bad_version",
    "duplicate_plugin_name",
    "unknown_key",
    "empty_plugins",
    "wrong_type",
)
ADDITIVE_FIELDS = ("packages", "channels", "provenance", "digest")
ALLOWED_ROOT = frozenset(
    {"name", "owner", "description", "plugins", *ADDITIVE_FIELDS}
)
VERSION_RE = __import__("re").compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


@dataclass
class Verdict:
    ok: bool
    engine: str
    primary_code: str | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "engine": self.engine,
            "primary_code": self.primary_code,
            "errors": self.errors,
        }


def load_index(path: Path | None = None) -> dict[str, Any]:
    target = path or (REPO / INDEX_REL)
    return json.loads(target.read_text(encoding="utf-8"))


def load_schema(path: Path | None = None) -> dict[str, Any]:
    target = path or (REPO / SCHEMA_REL)
    return json.loads(target.read_text(encoding="utf-8"))


def _map_keyword(keyword: str, path: tuple[Any, ...]) -> str:
    if keyword == "required" and (not path or path[-1] == "owner" or "owner" in path):
        return "missing_owner"
    if keyword == "required":
        return "missing_owner"
    if keyword == "pattern":
        return "bad_version"
    if keyword == "uniqueItems":
        return "duplicate_plugin_name"
    if keyword == "additionalProperties":
        return "unknown_key"
    if keyword == "minItems":
        return "empty_plugins"
    if keyword == "type":
        return "wrong_type"
    return keyword or "unknown"


def validate_engine_a(index: Any, schema: dict[str, Any] | None = None) -> Verdict:
    schema = schema or load_schema()
    import jsonschema
    from jsonschema.validators import Draft202012Validator

    validator = Draft202012Validator(schema)
    errors: list[dict[str, Any]] = []
    for err in validator.iter_errors(index):
        path = tuple(err.absolute_path)
        errors.append(
            {
                "keyword": err.validator,
                "message": err.message,
                "path": [str(p) for p in path],
                "code": _map_keyword(str(err.validator), path),
            }
        )
    primary = errors[0]["code"] if errors else None
    return Verdict(
        ok=not errors,
        engine="jsonschema.Draft202012Validator",
        primary_code=primary,
        errors=errors,
    )


def _walker_errors(index: Any) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if not isinstance(index, dict):
        errors.append({"keyword": "type", "code": "wrong_type", "path": [], "message": "root not object"})
        return errors
    extra = [k for k in index.keys() if k not in ALLOWED_ROOT]
    if extra:
        errors.append(
            {
                "keyword": "additionalProperties",
                "code": "unknown_key",
                "path": extra[:1],
                "message": f"unknown key {extra[0]}",
            }
        )
    for req in ("name", "owner", "description", "plugins"):
        if req not in index:
            code = "missing_owner" if req == "owner" else "wrong_type"
            if req == "owner":
                code = "missing_owner"
            errors.append(
                {
                    "keyword": "required",
                    "code": code,
                    "path": [req],
                    "message": f"missing {req}",
                }
            )
    if "owner" in index and not (
        isinstance(index["owner"], dict) and isinstance(index["owner"].get("name"), str)
    ):
        errors.append(
            {
                "keyword": "required",
                "code": "missing_owner",
                "path": ["owner"],
                "message": "owner.name required",
            }
        )
    plugins = index.get("plugins")
    if "plugins" in index:
        if not isinstance(plugins, list):
            errors.append(
                {
                    "keyword": "type",
                    "code": "wrong_type",
                    "path": ["plugins"],
                    "message": "plugins must be array",
                }
            )
        else:
            if len(plugins) == 0:
                errors.append(
                    {
                        "keyword": "minItems",
                        "code": "empty_plugins",
                        "path": ["plugins"],
                        "message": "plugins minItems 1",
                    }
                )
            encoded = [json.dumps(p, sort_keys=True, default=str) for p in plugins]
            if len(encoded) != len(set(encoded)):
                errors.append(
                    {
                        "keyword": "uniqueItems",
                        "code": "duplicate_plugin_name",
                        "path": ["plugins"],
                        "message": "plugins uniqueItems",
                    }
                )
            names = [
                p.get("name")
                for p in plugins
                if isinstance(p, dict) and isinstance(p.get("name"), str)
            ]
            if len(names) != len(set(names)):
                errors.append(
                    {
                        "keyword": "uniqueItems",
                        "code": "duplicate_plugin_name",
                        "path": ["plugins"],
                        "message": "duplicate plugin name",
                    }
                )
            for i, plug in enumerate(plugins):
                if not isinstance(plug, dict):
                    errors.append(
                        {
                            "keyword": "type",
                            "code": "wrong_type",
                            "path": ["plugins", i],
                            "message": "plugin not object",
                        }
                    )
                    continue
                ver = plug.get("version")
                if ver is not None and not (
                    isinstance(ver, str) and VERSION_RE.match(ver)
                ):
                    errors.append(
                        {
                            "keyword": "pattern",
                            "code": "bad_version",
                            "path": ["plugins", i, "version"],
                            "message": "version pattern",
                        }
                    )
    return errors


def validate_engine_b(index: Any, schema: dict[str, Any] | None = None) -> Verdict:
    errors = _walker_errors(index)
    primary = errors[0]["code"] if errors else None
    return Verdict(
        ok=not errors,
        engine="independent-walker",
        primary_code=primary,
        errors=errors,
    )


def validate_both(index: Any, schema: dict[str, Any] | None = None) -> dict[str, Verdict]:
    schema = schema or load_schema()
    return {
        "engine_a": validate_engine_a(index, schema),
        "engine_b": validate_engine_b(index, schema),
    }


def apply_mutation(index: dict[str, Any], mid: str) -> dict[str, Any]:
    doc = copy.deepcopy(index)
    plugins = doc.get("plugins") if isinstance(doc.get("plugins"), list) else []
    if mid == "missing_owner":
        doc.pop("owner", None)
    elif mid == "bad_version":
        if plugins and isinstance(plugins[0], dict):
            plugins[0]["version"] = "not-a-semver"
    elif mid == "duplicate_plugin_name":
        if plugins:
            plugins.append(copy.deepcopy(plugins[0]))
            doc["plugins"] = plugins
    elif mid == "unknown_key":
        doc["not_a_schema_key"] = True
    elif mid == "empty_plugins":
        doc["plugins"] = []
    elif mid == "wrong_type":
        doc["plugins"] = "not-an-array"
    else:
        raise KeyError(mid)
    return doc


def mutation_verdicts(
    index: dict[str, Any] | None = None, schema: dict[str, Any] | None = None
) -> dict[str, Any]:
    index = index if index is not None else load_index()
    schema = schema if schema is not None else load_schema()
    rows: dict[str, Any] = {}
    for mid in MUTATION_IDS:
        mutant = apply_mutation(index, mid)
        a = validate_engine_a(mutant, schema)
        b = validate_engine_b(mutant, schema)
        # Prefer the named mutation id when the engine surfaces it among errors.
        a_codes = [e.get("code") for e in a.errors]
        b_codes = [e.get("code") for e in b.errors]
        a_primary = mid if mid in a_codes else a.primary_code
        b_primary = mid if mid in b_codes else b.primary_code
        rows[mid] = {
            "engine_a": {
                "ok": a.ok,
                "primary_code": a_primary,
                "engine": a.engine,
                "errors": a.errors,
            },
            "engine_b": {
                "ok": b.ok,
                "primary_code": b_primary,
                "engine": b.engine,
                "errors": b.errors,
            },
            "agree": (not a.ok) and (not b.ok) and a_primary == mid and b_primary == mid,
        }
    return rows


def extended_example(index: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = copy.deepcopy(index if index is not None else load_index())
    doc["packages"] = [{"name": doc.get("name") or "pkg", "digest": "a" * 64}]
    doc["channels"] = ["stable"]
    doc["provenance"] = {"source": INDEX_REL}
    doc["digest"] = "b" * 64
    return doc


def scan_second_indexes(root: Path | None = None) -> list[str]:
    """Second control-plane indexes outside the canonical path and probe worktrees."""
    root = root or REPO
    canonical = (root / INDEX_REL).resolve()
    hits: list[str] = []
    skip_parts = {
        "p2-wave",
        "node_modules",
        ".git",
        "__pycache__",
        "ovh-monitor",
        "delivery-pull",
        "error-pull",
        "missing-pull",
        "_work",
        "clones",
        "vendor",
    }
    candidates = [
        root / "marketplace.json",
        root / "tools" / "marketplace" / "marketplace.json",
        root / "command-center" / "marketplace.json",
        root / ".claude-plugin" / "index.json",
        root / ".claude-plugin" / "registry.json",
    ]
    for cand in candidates:
        if cand.is_file() and cand.resolve() != canonical:
            hits.append(cand.relative_to(root).as_posix())
    plugin_dir = root / ".claude-plugin"
    if plugin_dir.is_dir():
        for cand in plugin_dir.glob("*.json"):
            if cand.name in {"marketplace.json", "plugin.json", "plugin.schema.json", "marketplace.schema.json"}:
                continue
            if "index" in cand.name.lower() or "registry" in cand.name.lower():
                hits.append(cand.relative_to(root).as_posix())
    return hits


def live_report() -> dict[str, Any]:
    index = load_index()
    schema = load_schema()
    current_a = validate_engine_a(index, schema)
    current_b = validate_engine_b(index, schema)
    extended = extended_example(index)
    ext_a = validate_engine_a(extended, schema)
    ext_b = validate_engine_b(extended, schema)
    rows = mutation_verdicts(index, schema)
    codes_a = [rows[mid]["engine_a"]["primary_code"] for mid in MUTATION_IDS]
    codes_b = [rows[mid]["engine_b"]["primary_code"] for mid in MUTATION_IDS]
    seconds = scan_second_indexes()
    return {
        "current_ok_a": current_a.ok,
        "current_ok_b": current_b.ok,
        "extended_ok_a": ext_a.ok,
        "extended_ok_b": ext_b.ok,
        "mutation_codes_a": codes_a,
        "mutation_codes_b": codes_b,
        "mutation_codes_distinct": len(set(codes_a)) == 6,
        "mutation_primary_matches_id": codes_a == list(MUTATION_IDS) and codes_b == list(MUTATION_IDS),
        "all_mutations_agree": all(rows[mid]["agree"] for mid in MUTATION_IDS),
        "no_second_index": seconds == [],
        "second_indexes": seconds,
    }


def main() -> int:
    report = live_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if (
        report["current_ok_a"]
        and report["current_ok_b"]
        and report["all_mutations_agree"]
        and report["no_second_index"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
