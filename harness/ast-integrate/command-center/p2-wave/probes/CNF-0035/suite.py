#!/usr/bin/env python3
"""One-invocation suite: three negative fixtures + valid control.

Also feeds live plugin/marketplace/hook/settings documents through the same reader.
"""
from __future__ import annotations

import copy
import json
import sys
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import document_schemas as D  # noqa: E402
import strict_reader as R  # noqa: E402

FIX = HERE / "fixtures"
CONTROL_PLUGIN = (
    REPO
    / "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/typed/plugin.json"
)
REGISTRY = REPO / "command-center/p2-wave/probes/ARC-0010/registry.json"


def parser_identity() -> dict[str, str]:
    py = sys.version.split()[0]
    js = pkg_version("jsonschema")
    return {
        "name": "cnf-0035-strict-reader",
        "path": "command-center/p2-wave/probes/CNF-0035/strict_reader.py",
        "python": py,
        "jsonschema": js,
        "draft": "draft-07",
        "json_module": "json (CPython decoder with object_pairs_hook)",
        "version": f"python-{py}+jsonschema-{js}+cnf-0035-strict-reader",
    }


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def plant_duplicate_name(text: str) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    inserted = False
    for line in lines:
        out.append(line)
        stripped = line.lstrip()
        if not inserted and stripped.startswith('"name"'):
            indent = line[: len(line) - len(stripped)]
            out.append(f'{indent}"name": "last-wins-if-permissive",\n')
            inserted = True
    if not inserted:
        raise RuntimeError("could not plant duplicate name key")
    return "".join(out)


def write_negative_fixtures() -> dict[str, Path]:
    FIX.mkdir(parents=True, exist_ok=True)
    control_text = CONTROL_PLUGIN.read_text(encoding="utf-8")
    control_obj = json.loads(control_text)
    control_path = FIX / "control.valid-plugin.json"
    control_path.write_text(_dump(control_obj), encoding="utf-8")

    unknown = copy.deepcopy(control_obj)
    unknown["cnf0035_unknown_field"] = True
    unknown_path = FIX / "negative.unknown-field.json"
    unknown_path.write_text(_dump(unknown), encoding="utf-8")

    case_obj = copy.deepcopy(control_obj)
    case_obj["Name"] = "harness-casefold-twin"
    case_path = FIX / "negative.case-distinct.json"
    case_path.write_text(_dump(case_obj), encoding="utf-8")

    dup_path = FIX / "negative.duplicate-key.json"
    dup_path.write_text(plant_duplicate_name(_dump(control_obj)), encoding="utf-8")
    return {
        "control": control_path,
        "unknown-field": unknown_path,
        "case-distinct": case_path,
        "duplicate-key": dup_path,
    }


def attempt(path: Path, schema: dict[str, Any]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path)
    try:
        obj = R.read_strict(text, schema)
    except R.StrictParseError as exc:
        return {
            "path": rel,
            "parsed": False,
            "errored": True,
            "classification": exc.classification,
            "error_text": str(exc),
            "error_key": exc.key,
            "keys_if_lenient": None,
        }
    keys = sorted(obj.keys()) if isinstance(obj, dict) else []
    return {
        "path": rel,
        "parsed": True,
        "errored": False,
        "classification": None,
        "error_text": None,
        "error_key": None,
        "keys": keys,
    }


def permissive_duplicate_last_wins(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    obj = R.lenient_loads(text)
    return {
        "parsed": True,
        "name": obj.get("name") if isinstance(obj, dict) else None,
        "note": "CPython json.loads last-wins; this is the dangerous overwrite the strict reader must refuse",
    }


def mutation_unknown_accepted(path: Path) -> bool:
    """Relax additionalProperties; unknown-field fixture must then parse.

    Proves the rejection is the additionalProperties rule, not a broken decoder.
    """
    schema = copy.deepcopy(D.PLUGIN)
    schema["additionalProperties"] = True
    try:
        R.read_strict(path.read_text(encoding="utf-8"), schema)
        return True
    except R.StrictParseError:
        return False


def live_subjects() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spec in D.LIVE_SUBJECTS:
        path = REPO / spec["path"]
        row = {
            "kind": spec["kind"],
            "role": spec["role"],
            "path": spec["path"],
            "present": path.is_file(),
        }
        if not path.is_file():
            row["parsed"] = False
            row["errored"] = True
            row["error_text"] = "absent"
            out.append(row)
            continue
        result = attempt(path, D.schema_for(spec["kind"]))
        row.update(result)
        out.append(row)
    reg = attempt(REGISTRY, D.registry_schema())
    reg.update(
        {
            "kind": "registry",
            "role": "typed-ssot-registry",
            "present": True,
        }
    )
    out.append(reg)
    return out


def run_suite() -> dict[str, Any]:
    paths = write_negative_fixtures()
    plugin_schema = D.PLUGIN
    order = (
        ("unknown-field", "unknown-field fixture must be rejected"),
        ("case-distinct", "case-distinct key fixture must be reported as a collision"),
        ("duplicate-key", "duplicate-key fixture must error rather than last-wins"),
        ("control", "valid manifest must parse cleanly in the same run"),
    )
    results: list[dict[str, Any]] = []
    for fid, required in order:
        row = attempt(paths[fid], plugin_schema)
        row["id"] = fid
        row["required"] = required
        if fid == "control":
            row["expect_error"] = False
            row["ok"] = row["parsed"] is True and row["errored"] is False
        else:
            row["expect_error"] = True
            row["ok"] = row["errored"] is True
        results.append(row)

    negatives = [r for r in results if r["id"] != "control"]
    control = next(r for r in results if r["id"] == "control")
    all_neg_errored = all(r["errored"] for r in negatives)
    control_clean = control["parsed"] is True and control["errored"] is False
    same_invocation = True
    live = live_subjects()
    live_ok = all(s.get("parsed") is True and s.get("errored") is False for s in live)

    dup_path = paths["duplicate-key"]
    unknown_path = paths["unknown-field"]
    case_row = next(r for r in results if r["id"] == "case-distinct")
    unk_row = next(r for r in results if r["id"] == "unknown-field")
    dup_row = next(r for r in results if r["id"] == "duplicate-key")

    detector_ok = (
        all_neg_errored
        and control_clean
        and unk_row["classification"] == "unknown-field"
        and case_row["classification"] == "case-collision"
        and dup_row["classification"] == "duplicate-key"
    )
    return {
        "parser": parser_identity(),
        "same_invocation": same_invocation,
        "all_three_negatives_errored": all_neg_errored,
        "control_parsed_clean": control_clean,
        "detector_ok": detector_ok,
        "live_manifests_ok": live_ok,
        "pass": detector_ok and live_ok,
        "results": results,
        "live": live,
        "permissive_duplicate": permissive_duplicate_last_wins(dup_path),
        "mutation_unknown_accepted_when_additional_properties_true": mutation_unknown_accepted(
            unknown_path
        ),
        "fixture_paths": {k: v.relative_to(REPO).as_posix() for k, v in paths.items()},
    }


def main() -> int:
    report = run_suite()
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    if not report["pass"]:
        print("FAILED:CNF-0035-suite")
        return 1
    print(
        "SUCCESS:CNF-0035-suite negatives_errored="
        f"{report['all_three_negatives_errored']} "
        f"control_clean={report['control_parsed_clean']} "
        f"live_ok={report['live_manifests_ok']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
