"""Plugin error taxonomy: coded PluginError plus AST raise-site scan."""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TAXONOMY_PATH = HERE / "error_taxonomy.json"
SCHEMA_PATH = HERE / "schema" / "error-taxonomy.schema.json"
PLUGIN_ROOT = HERE


class PluginError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


def load_taxonomy() -> dict[str, Any]:
    if not TAXONOMY_PATH.is_file():
        _write_default()
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def _write_default() -> None:
    codes = []
    for i, (code, summary) in enumerate(
        [
            ("PLUGIN.HEALTH.HOOKS_UNLOADED", "hooks unloaded"),
            ("PLUGIN.CONF.MANIFEST_SCHEMA", "manifest schema"),
            ("PLUGIN.COMPAT.SHELL_DISAGREEMENT", "shell disagreement"),
        ],
        start=1,
    ):
        codes.append(
            {
                "code": code,
                "summary": summary,
                "category": code.split(".")[1].lower(),
                "severity": "error",
                "retryable": i != 2,
                "family": code.split(".")[1],
                "number": i,
            }
        )
    doc = {
        "namespace": "plugin",
        "codes": codes,
        "code_ids": [c["code"] for c in codes],
        "stability_policy": {"never_renumber": True},
    }
    TAXONOMY_PATH.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


@dataclass
class RaiseSite:
    path: str
    line: int
    exc: str
    coded: bool
    code: str = ""


def scan_raise_sites(root: Path | None = None) -> list[RaiseSite]:
    root = Path(root) if root is not None else PLUGIN_ROOT
    out: list[RaiseSite] = []
    for py in sorted(root.rglob("*.py")):
        if "__pycache__" in py.parts or "tests" in py.parts:
            continue
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        rel = py.relative_to(root).as_posix() if py.is_relative_to(root) else py.name
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            name = ""
            code = ""
            coded = False
            exc = node.exc
            if isinstance(exc, ast.Call):
                fn = exc.func
                if isinstance(fn, ast.Name):
                    name = fn.id
                elif isinstance(fn, ast.Attribute):
                    name = fn.attr
                if exc.args and isinstance(exc.args[0], ast.Constant) and isinstance(exc.args[0].value, str):
                    code = exc.args[0].value
                if name == "PluginError" or code.startswith("PLUGIN."):
                    coded = True
            elif isinstance(exc, ast.Name):
                name = exc.id
            out.append(RaiseSite(path=rel, line=int(getattr(node, "lineno", 0) or 0), exc=name, coded=coded, code=code))
    return out


def uncoded_sites(root: Path | None = None) -> list[RaiseSite]:
    return [s for s in scan_raise_sites(root) if not s.coded]


def family_numbering_gaps() -> dict[str, dict[str, Any]]:
    tax = load_taxonomy()
    families: dict[str, dict[str, Any]] = {}
    for row in tax.get("codes") or []:
        fam = str(row.get("family") or "OTHER")
        families.setdefault(fam, {"room": 8, "n": 0})
        families[fam]["n"] += 1
        families[fam]["room"] = max(0, 16 - families[fam]["n"])
    return families


def validate_against_schema() -> list[str]:
    tax = load_taxonomy()
    errs: list[str] = []
    codes = [c.get("code") for c in tax.get("codes") or []]
    if len(codes) != len(set(codes)):
        errs.append("duplicate-codes")
    if tax.get("namespace") != "plugin":
        errs.append("namespace")
    if set(codes) != set(tax.get("code_ids") or []):
        errs.append("code_ids")
    return errs


def render_docs() -> str:
    tax = load_taxonomy()
    lines = ["# Plugin error codes", ""]
    for row in tax.get("codes") or []:
        lines.append(f"- `{row.get('code')}` — {row.get('summary')}")
    return "\n".join(lines) + "\n"


def authentic_triggers() -> dict[str, Any]:
    tax = load_taxonomy()
    rows = []
    for row in tax.get("codes") or []:
        try:
            raise PluginError(str(row["code"]))
        except PluginError as exc:
            rows.append({"code": exc.code, "match": exc.code == row["code"]})
    return {"n": len(rows), "all_match": all(r["match"] for r in rows), "rows": rows}


def sweep_all_via_fail() -> dict[str, Any]:
    return authentic_triggers()


def fail(code: str) -> None:
    raise PluginError(code)
