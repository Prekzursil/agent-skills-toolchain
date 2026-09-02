#!/usr/bin/env python3
"""Disposition evidence gate (WFA-0073).

Rejects a disposition whose record lacks the evidence its own class demands:
  ADOPT-AS-IS / ADOPT-WITH-WRAPPER  -> passing smoke run (artifact on disk)
  RETIRE                           -> preservation proof (retrieved hash match)
  UNKNOWN-NEEDS-PROBE / UNKNOWN    -> named executed probe (command + result)
  TRANSLATE                        -> named target adapter

Default invocation ENFORCES. Enforcement is not an optional extra argument.
`--json` only changes stdout shape.

CI form (no extra flags):
  PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/WFA-0073/gate.py [registry.json]

Exit 1 when any gated record fails. A high failure count on the current 284
is data, not a reason to disarm the gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

# Default is enforce. Do not add an opt-in argument that turns this on.
DEFAULT_ENFORCE = True

GATED = {
    "ADOPT-AS-IS": "smoke_run",
    "ADOPT-WITH-WRAPPER": "smoke_run",
    "RETIRE": "preservation_proof",
    "UNKNOWN-NEEDS-PROBE": "named_executed_probe",
    "UNKNOWN": "named_executed_probe",
    "TRANSLATE": "target_adapter",
}

SMOKE_SIZE_FLOOR_DEFAULT = 16


def lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def resolve_repo_path(raw: str) -> Path:
    text = str(raw or "").strip().replace("\\", "/")
    p = Path(text)
    if p.is_absolute():
        return p
    return REPO / text


def _evidence_obj(record: dict[str, Any]) -> dict[str, Any]:
    ev = record.get("evidence")
    return ev if isinstance(ev, dict) else {}


def check_smoke_run(record: dict[str, Any]) -> tuple[bool, str]:
    """Exit 0 alone is never success. Artifact must exist, clear a size floor, and parse."""
    ev = _evidence_obj(record)
    smoke = ev.get("smoke_run") or ev.get("smoke") or record.get("smoke_run")
    if not isinstance(smoke, dict):
        return False, "smoke-run-absent-or-not-object"
    try:
        rc = int(smoke.get("exit_code"))
    except (TypeError, ValueError):
        return False, "smoke-run-exit-code-missing"
    if rc != 0:
        return False, f"smoke-run-exit-nonzero:{rc}"
    art = smoke.get("artifact") or smoke.get("artifact_path") or smoke.get("output_path")
    if not isinstance(art, str) or not art.strip():
        return False, "smoke-run-artifact-path-absent"
    path = resolve_repo_path(art)
    if not path.is_file():
        return False, "smoke-run-artifact-missing-on-disk"
    size = path.stat().st_size
    try:
        floor = int(smoke.get("size_floor") or SMOKE_SIZE_FLOOR_DEFAULT)
    except (TypeError, ValueError):
        floor = SMOKE_SIZE_FLOOR_DEFAULT
    if size < floor or size <= 0:
        return False, f"smoke-run-artifact-below-size-floor:{size}<{floor}"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "smoke-run-artifact-unparseable"
    return True, "ok"


def check_preservation(record: dict[str, Any]) -> tuple[bool, str]:
    """A manifest entry is a claim. Only a successful retrieval + hash match is a receipt."""
    ev = _evidence_obj(record)
    pres = ev.get("preservation") or ev.get("preservation_proof") or record.get("preservation")
    if not isinstance(pres, dict):
        return False, "preservation-proof-absent-or-not-object"
    loc = pres.get("location") or pres.get("path")
    claimed = str(pres.get("content_sha256") or pres.get("sha256") or "").strip().lower()
    if not isinstance(loc, str) or not loc.strip():
        return False, "preservation-location-absent"
    if not claimed:
        return False, "preservation-content-hash-absent"
    path = resolve_repo_path(loc)
    if not path.is_file():
        return False, "preservation-location-unretrievable"
    live = lf_sha256(path)
    if live != claimed:
        return False, "preservation-hash-mismatch"
    return True, "ok"


def check_named_probe(record: dict[str, Any]) -> tuple[bool, str]:
    ev = _evidence_obj(record)
    probe = (
        ev.get("probe")
        or ev.get("named_probe")
        or ev.get("executed_probe")
        or record.get("probe")
    )
    if not isinstance(probe, dict):
        return False, "named-probe-absent-or-not-object"
    name = str(probe.get("id") or probe.get("name") or "").strip()
    cmd = str(probe.get("command") or "").strip()
    result = probe.get("result")
    if result is None:
        result = probe.get("output")
    if result is None:
        result = probe.get("raw_output")
    if not name:
        return False, "probe-unnamed"
    if not cmd:
        return False, "probe-command-absent"
    if probe.get("executed") is False:
        return False, "probe-not-executed"
    if result is None:
        return False, "probe-result-absent"
    if isinstance(result, str) and not result.strip():
        return False, "probe-result-absent"
    return True, "ok"


def check_target_adapter(record: dict[str, Any]) -> tuple[bool, str]:
    ev = _evidence_obj(record)
    adapter = ev.get("target_adapter") or ev.get("adapter") or ev.get("adapter_id")
    if adapter is None:
        adapter = record.get("target_adapter")
    if isinstance(adapter, dict):
        adapter = adapter.get("id") or adapter.get("name")
    if not isinstance(adapter, str) or not adapter.strip():
        return False, "target-adapter-absent"
    return True, "ok"


CHECKERS = {
    "smoke_run": check_smoke_run,
    "preservation_proof": check_preservation,
    "named_executed_probe": check_named_probe,
    "target_adapter": check_target_adapter,
}


def classify(record: dict[str, Any]) -> str:
    return str(
        record.get("classification")
        or record.get("disposition")
        or record.get("class")
        or ""
    ).strip()


def evaluate_record(record: dict[str, Any]) -> dict[str, Any]:
    cls = classify(record)
    rid = str(record.get("id") or record.get("name") or "")
    required = GATED.get(cls)
    if not required:
        return {
            "id": rid,
            "classification": cls,
            "required": None,
            "gated": False,
            "ok": True,
            "verdict": "PASS",
            "reason": "class-not-gated-by-WFA-0073",
        }
    checker = CHECKERS[required]
    ok, reason = checker(record)
    return {
        "id": rid,
        "classification": cls,
        "required": required,
        "gated": True,
        "ok": ok,
        "verdict": "PASS" if ok else "FAIL",
        "reason": reason,
    }


def evaluate_registry(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [evaluate_record(r) for r in records]
    fails = [r for r in rows if r["verdict"] == "FAIL"]
    passes = [r for r in rows if r["verdict"] == "PASS"]
    by_class = Counter(classify(r) for r in records)
    fail_by_class = Counter(r["classification"] for r in fails)
    pass_by_class = Counter(r["classification"] for r in passes)
    gated_n = sum(1 for r in rows if r["gated"])
    return {
        "n": len(records),
        "gated_n": gated_n,
        "fail_n": len(fails),
        "pass_n": len(passes),
        "by_class": dict(sorted(by_class.items())),
        "fail_by_class": dict(sorted(fail_by_class.items())),
        "pass_by_class": dict(sorted(pass_by_class.items())),
        "failing_ids": [r["id"] for r in fails],
        "rows": rows,
    }


def load_records_from_path(path: Path) -> list[dict[str, Any]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, dict) and isinstance(doc.get("candidates"), list):
        return [r for r in doc["candidates"] if isinstance(r, dict)]
    if isinstance(doc, list):
        return [r for r in doc if isinstance(r, dict)]
    raise SystemExit(f"FAILED:WFA-0073-gate unreadable-registry {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "WFA-0073 disposition evidence gate. Default invocation enforces; "
            "missing evidence is a failure, never a silence."
        )
    )
    parser.add_argument(
        "registry",
        nargs="?",
        default=None,
        help="Registry JSON (candidates[]). Default: current 284-row corpus.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the evaluation object as JSON (still exits 1 on violations).",
    )
    args = parser.parse_args(argv)

    if args.registry:
        recs = load_records_from_path(Path(args.registry))
        source = args.registry
    else:
        # Imported lazily so `python3 gate.py fixtures/x.json` does not need registry.py path hacks
        # beyond this file's directory.
        sys.path.insert(0, str(HERE))
        import registry as R  # noqa: E402

        loaded = R.load_registry()
        recs = loaded["records"]
        source = loaded.get("rel") or loaded.get("source")

    report = evaluate_registry(recs)
    report["source"] = source
    report["enforce"] = DEFAULT_ENFORCE
    if args.json:
        slim = {k: v for k, v in report.items() if k != "rows"}
        slim["fail_sample"] = report["failing_ids"][:12]
        print(json.dumps(slim, indent=2, sort_keys=True))
    else:
        print(
            f"WFA-0073-gate source={source} n={report['n']} "
            f"fail={report['fail_n']} pass={report['pass_n']} "
            f"fail_by_class={json.dumps(report['fail_by_class'], sort_keys=True)}"
        )
        for row in report["rows"]:
            if row["verdict"] == "FAIL":
                print(f"  FAIL {row['id']} {row['classification']} {row['reason']}")
    if report["fail_n"]:
        print(f"FAILED:WFA-0073-gate violations={report['fail_n']}")
        return 1
    print(f"SUCCESS:WFA-0073-gate records={report['n']} violations=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
