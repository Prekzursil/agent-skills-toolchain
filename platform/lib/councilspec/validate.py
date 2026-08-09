"""CouncilSpec validator + conformance runner.

Two layers, both required for a spec to be conformant:

1. JSON Schema (Draft 2020-12) - shapes, enums, typed metric leaves, conditionals.
2. Semantic rules (semantics.py) - cross-field coherence JSON Schema cannot express.

CLI
---
    python -m councilspec.validate FILE [FILE ...]
    python -m councilspec.validate --conformance [--examples DIR]
    python -m councilspec.validate --evaluate METRICS.json FILE

Terminal state (AGENTS.md Sec.4): the last line is SUCCESS:<id> or FAILED:<id> <reason>.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Mapping, Tuple

try:  # allow both `python -m councilspec.validate` and `python validate.py`
    from .expression import evaluate, parse, unparse
    from .registry import SCHEMA_PATH, load_schema
    from .semantics import Finding, check, errors
except ImportError:  # pragma: no cover - direct-script fallback
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from councilspec.expression import evaluate, parse, unparse  # type: ignore
    from councilspec.registry import SCHEMA_PATH, load_schema  # type: ignore
    from councilspec.semantics import Finding, check, errors  # type: ignore

import jsonschema

EXAMPLES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "schema", "examples")
)


def _validator(schema_path: str = SCHEMA_PATH):
    schema = load_schema(schema_path)
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


def schema_errors(instance: Mapping[str, Any], schema_path: str = SCHEMA_PATH) -> List[str]:
    validator = _validator(schema_path)
    out = []
    for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        loc = "$" + "".join(f"[{p!r}]" if isinstance(p, str) else f"[{p}]"
                            for p in err.absolute_path)
        out.append(f"{loc}: {err.message}")
    return out


def validate_spec(instance: Mapping[str, Any], schema_path: str = SCHEMA_PATH) -> Dict[str, Any]:
    serr = schema_errors(instance, schema_path)
    findings: List[Finding] = [] if serr else check(instance)
    serious = errors(findings)
    return {
        "schema_ok": not serr,
        "schema_errors": serr,
        "findings": [f.__dict__ for f in findings],
        "semantic_errors": [str(f) for f in serious],
        "warnings": [str(f) for f in findings if f.severity == "WARN"],
        "ok": not serr and not serious,
    }


def validate_file(path: str, schema_path: str = SCHEMA_PATH) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            instance = json.load(fh)
    except json.JSONDecodeError as exc:
        return {"schema_ok": False, "schema_errors": [f"invalid JSON: {exc}"], "findings": [],
                "semantic_errors": [], "warnings": [], "ok": False}
    result = validate_spec(instance, schema_path)
    result["file"] = path
    return result


# ------------------------------------------------------------------- conformance


def _load_expectations(examples_dir: str) -> Dict[str, Any]:
    with open(os.path.join(examples_dir, "EXPECTATIONS.json"), "r", encoding="utf-8") as fh:
        return json.load(fh)


def run_conformance(examples_dir: str = EXAMPLES_DIR,
                    schema_path: str = SCHEMA_PATH) -> Tuple[bool, List[str]]:
    """Assert every declared example lands on its declared side of the gate."""
    manifest = _load_expectations(examples_dir)
    lines: List[str] = []
    ok = True
    seen = set()

    for entry in manifest["cases"]:
        rel = entry["file"]
        seen.add(os.path.normcase(rel.replace("/", os.sep)))
        path = os.path.join(examples_dir, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            lines.append(f"MISSING  {rel}")
            ok = False
            continue
        res = validate_file(path, schema_path)
        blob = " | ".join(res["schema_errors"] + res["semantic_errors"])
        expect_pass = entry["expect"] == "pass"

        if expect_pass and not res["ok"]:
            lines.append(f"FAIL     {rel}: expected to validate, got -> {blob}")
            ok = False
            continue
        if not expect_pass and res["ok"]:
            lines.append(f"FAIL     {rel}: expected REJECTION ({entry.get('reason')}) but it validated")
            ok = False
            continue
        if not expect_pass:
            detector = entry.get("detector")
            if detector == "schema" and not res["schema_errors"]:
                lines.append(f"FAIL     {rel}: expected a SCHEMA rejection, got semantic only")
                ok = False
                continue
            if detector == "semantic" and not res["semantic_errors"]:
                lines.append(f"FAIL     {rel}: expected a SEMANTIC rejection, got schema only")
                ok = False
                continue
            needle = entry.get("contains")
            if needle and needle not in blob:
                lines.append(f"FAIL     {rel}: rejection message lacks {needle!r}; got -> {blob}")
                ok = False
                continue
            lines.append(f"REJECTED {rel}  <- {blob[:150]}")
            continue

        # positive case: also prove the stopping rule round-trips and executes
        with open(path, "r", encoding="utf-8") as fh:
            spec = json.load(fh)
        extra = ""
        src = spec.get("stopping", {}).get("source_expression")
        tree = spec.get("stopping", {}).get("expression")
        if src:
            if parse(src) != tree:
                lines.append(f"FAIL     {rel}: source_expression does not parse to expression")
                ok = False
                continue
            if parse(unparse(tree)) != tree:
                lines.append(f"FAIL     {rel}: unparse/parse is not tree-idempotent")
                ok = False
                continue
            extra = "  roundtrip=OK"
        for probe_name in ("metrics_satisfying", "metrics_not_satisfying"):
            probe = entry.get(probe_name)
            if probe is None:
                continue
            want = probe_name == "metrics_satisfying"
            got = evaluate(tree, probe)
            if got is not want:
                lines.append(f"FAIL     {rel}: {probe_name} evaluated {got}, expected {want}")
                ok = False
                break
        else:
            if entry.get("metrics_satisfying") is not None:
                extra += " eval=BOTH-STATES-OK"
            lines.append(f"PASS     {rel}{extra}")
            continue
        ok = False

    # A manifest that silently skips an on-disk example would hide an untested file.
    # Scope: only the subdirectories this manifest claims (valid/, invalid/). The examples
    # root is shared with sibling Phase-4 contracts (e.g. receipt.*.example.json), and those
    # files are not ours to gate.
    owned_dirs = {os.path.dirname(c["file"].replace("/", os.sep)) for c in manifest["cases"]}
    owned_dirs.discard("")
    on_disk = set()
    for sub in sorted(owned_dirs):
        for root, _dirs, files in os.walk(os.path.join(examples_dir, sub)):
            for name in files:
                if name.endswith(".json") and name != "EXPECTATIONS.json":
                    rel = os.path.relpath(os.path.join(root, name), examples_dir)
                    on_disk.add(os.path.normcase(rel))
    unlisted = sorted(on_disk - seen)
    if unlisted:
        lines.append(f"FAIL     example files present but not in EXPECTATIONS.json: {unlisted}")
        ok = False

    return ok, lines


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="councilspec.validate")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--schema", default=SCHEMA_PATH)
    ap.add_argument("--conformance", action="store_true")
    ap.add_argument("--examples", default=EXAMPLES_DIR)
    ap.add_argument("--evaluate", metavar="METRICS_JSON")
    args = ap.parse_args(argv)

    if args.conformance:
        ok, lines = run_conformance(args.examples, args.schema)
        for line in lines:
            print(line)
        total = len(lines)
        print(f"-- {total} conformance cases checked")
        print(("SUCCESS:councilspec-conformance" if ok
               else "FAILED:councilspec-conformance one or more cases landed on the wrong side"))
        return 0 if ok else 1

    if not args.files:
        ap.error("give at least one FILE, or --conformance")

    all_ok = True
    for path in args.files:
        res = validate_file(path, args.schema)
        status = "OK" if res["ok"] else "REJECTED"
        print(f"{status}  {path}")
        for msg in res["schema_errors"]:
            print(f"   schema   {msg}")
        for msg in res["semantic_errors"]:
            print(f"   semantic {msg}")
        for msg in res["warnings"]:
            print(f"   warn     {msg}")
        if res["ok"] and args.evaluate:
            with open(args.evaluate, "r", encoding="utf-8") as fh:
                metrics = json.load(fh)
            with open(path, "r", encoding="utf-8") as fh:
                spec = json.load(fh)
            tree = spec["stopping"]["expression"]
            print(f"   expr     {unparse(tree)}")
            print(f"   stop?    {evaluate(tree, metrics)}")
        all_ok &= res["ok"]

    print("SUCCESS:councilspec-validate" if all_ok
          else "FAILED:councilspec-validate at least one instance was rejected")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
