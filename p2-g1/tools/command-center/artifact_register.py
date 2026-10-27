#!/usr/bin/env python3
"""Register-on-write into command-center/ARTIFACT-MANIFEST.json (conditions 11 and 12).

Condition 11: an output path is complete only if it is a row in the on-disk
artifact manifest. A file that exists but was never registered fails.

Condition 12: every selected manifest row is opened by the consumer that
claims to read it (or an inferred suffix consumer). A path string, Path.exists,
or a matching sha256 is not readability. Present-but-unparseable fails.
Absent registered paths fail. Currently-valid rows must pass so the gate is
not always-red.

Charter rows (the 14 contracted program files) have no declared consumer.
They are still opened: .json via consume_json, .jsonl via consume_jsonl,
everything else via consume_text. That is more than exists().

This module is the producer. tools/command-center/unit_manifest.py --write is
a different corpus (UNIT-ARTIFACT-MANIFEST.json) and must not be invoked from
here.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MANIFEST_REL = "command-center/ARTIFACT-MANIFEST.json"
JSON_READER = "tools/command-center/artifact_register.py:consume_json"
JSONL_READER = "tools/command-center/artifact_register.py:consume_jsonl"
TEXT_READER = "tools/command-center/artifact_register.py:consume_text"
HEX64 = 64

CHARTER_PATHS = frozenset(
    {
        "command-center/PROGRAM-CHARTER.md",
        "command-center/OWNER-DECISIONS.md",
        "command-center/WORK-UNIT-CATALOG.json",
        "command-center/DEPENDENCY-GRAPH.json",
        "command-center/ARTIFACT-MANIFEST.json",
        "command-center/CLAIM-REGISTRY.json",
        "command-center/TEST-REGISTRY.json",
        "command-center/RISK-REGISTER.md",
        "command-center/UNKNOWNS-REGISTER.md",
        "command-center/RELEASE-CHECKLIST.md",
        "command-center/ROLLBACK-MANIFEST.md",
        "command-center/RUNBOOK.md",
        "command-center/STATUS.md",
        "command-center/events/EVENTS.jsonl",
    }
)


class RegisterError(RuntimeError):
    """Registration refused (missing path, unreadable dest, etc.)."""


@dataclass
class CheckResult:
    ok: bool
    result: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.result = "PASS" if self.ok else "FAIL"


def posix(rel: str) -> str:
    return str(rel or "").replace("\\", "/")


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _dump(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_manifest(repo: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(manifest, dict):
        return manifest
    path = repo / MANIFEST_REL
    if not path.is_file():
        return {
            "schema_version": 1,
            "artifacts": [],
            "contract": "register-on-write",
            "derivation": "tools/command-center/artifact_register.py",
        }
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise RegisterError(f"{MANIFEST_REL} is not a JSON object")
    if not isinstance(doc.get("artifacts"), list):
        doc["artifacts"] = []
    return doc


def save_manifest(repo: Path, doc: dict[str, Any]) -> None:
    _dump(repo / MANIFEST_REL, doc)


def consume_json(path: Path) -> dict[str, Any]:
    """Parse JSON. Existence is not enough: the bytes must decode as an object."""
    reader = JSON_READER
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return {
            "ok": False,
            "reader": reader,
            "error": f"absent:{path.as_posix()}:{type(exc).__name__}",
        }
    try:
        doc = json.loads(raw.replace(b"\r\n", b"\n").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "reader": reader,
            "error": f"json-parse:{type(exc).__name__}:{exc}",
        }
    if not isinstance(doc, dict) or not doc:
        return {
            "ok": False,
            "reader": reader,
            "error": f"json-root-unusable:{type(doc).__name__}",
        }
    key = next(iter(doc))
    val = doc[key]
    if val is None or (isinstance(val, (str, list, dict)) and len(val) == 0):
        return {
            "ok": False,
            "reader": reader,
            "error": f"first-key-empty:{key}",
            "first_parsed_key": key,
            "record_count": len(doc),
        }
    return {
        "ok": True,
        "reader": reader,
        "first_parsed_key": key,
        "second_parsed_key": next(iter(list(doc)[1:]), None),
        "record_count": len(doc),
        "error": "",
    }


def consume_jsonl(path: Path) -> dict[str, Any]:
    reader = JSONL_READER
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "ok": False,
            "reader": reader,
            "error": f"absent:{path.as_posix()}:{type(exc).__name__}",
        }
    except UnicodeDecodeError as exc:
        return {
            "ok": False,
            "reader": reader,
            "error": f"json-parse:{type(exc).__name__}:{exc}",
        }
    records = 0
    first_key = None
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            doc = json.loads(line)
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "reader": reader,
                "error": f"json-parse:{type(exc).__name__}:line {i}:{exc}",
            }
        records += 1
        if first_key is None and isinstance(doc, dict) and doc:
            first_key = next(iter(doc))
    if records == 0:
        return {"ok": False, "reader": reader, "error": "jsonl-empty"}
    return {
        "ok": True,
        "reader": reader,
        "first_parsed_key": first_key,
        "record_count": records,
        "error": "",
    }


def consume_text(path: Path) -> dict[str, Any]:
    reader = TEXT_READER
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "ok": False,
            "reader": reader,
            "error": f"absent:{path.as_posix()}:{type(exc).__name__}",
        }
    except UnicodeDecodeError as exc:
        return {
            "ok": False,
            "reader": reader,
            "error": f"json-parse:{type(exc).__name__}:{exc}",
        }
    if not text.strip():
        return {"ok": False, "reader": reader, "error": "empty-text"}
    lines = text.splitlines()
    heading = next((ln.strip() for ln in lines if ln.strip()), "text")
    return {
        "ok": True,
        "reader": reader,
        "first_parsed_key": heading[:120],
        "record_count": len(lines),
        "error": "",
    }


def _load_py(repo: Path, rel: str):
    path = repo / posix(rel)
    if not path.is_file():
        raise RegisterError(f"consumer module missing: {rel}")
    spec = importlib.util.spec_from_file_location(
        "cc_declared_consumer_" + hashlib.sha256(rel.encode()).hexdigest()[:12],
        path,
    )
    if spec is None or spec.loader is None:
        raise RegisterError(f"cannot import consumer {rel}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def inferred_consumer(rel: str, row: dict[str, Any]) -> str:
    declared = row.get("consumer")
    if isinstance(declared, str) and declared.strip():
        return declared.strip()
    p = posix(rel).lower()
    if p.endswith(".json"):
        return "json"
    if p.endswith(".jsonl"):
        return "jsonl"
    return "text"


def read_with_consumer(
    repo: Path,
    rel: str,
    consumer: str | None = None,
    record_type: str | None = None,
) -> dict[str, Any]:
    rel = posix(rel)
    path = repo / rel
    kind = (consumer or "json").strip()
    if not path.is_file():
        reader = JSON_READER if kind in {"json", "application/json"} else kind
        return {
            "ok": False,
            "reader": reader,
            "error": f"absent:{rel}",
            "path": rel,
        }
    if kind in {"json", "application/json"}:
        out = consume_json(path)
    elif kind == "jsonl":
        out = consume_jsonl(path)
    elif kind == "text":
        out = consume_text(path)
    elif kind.endswith(".py") or ".py:" in kind:
        mod_rel, _, func_name = kind.partition(":")
        if not mod_rel.endswith(".py"):
            mod_rel, func_name = kind, ""
        mod = _load_py(repo, mod_rel)
        if func_name and hasattr(mod, func_name):
            fn = getattr(mod, func_name)
            if func_name in {"consume", "consume_registered"}:
                out = fn(path, record_type or "unknown")
            else:
                out = fn(path)
        elif record_type and hasattr(mod, "consume"):
            out = mod.consume(path, record_type)
        elif hasattr(mod, "consume_json"):
            out = mod.consume_json(path)
        else:
            out = consume_json(path)
    else:
        out = consume_json(path)
    out = dict(out)
    out["path"] = rel
    return out


def _rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for row in manifest.get("artifacts") or []:
        if isinstance(row, dict) and isinstance(row.get("path"), str) and row["path"]:
            out.append(row)
    return out


def _select_rows(
    manifest: dict[str, Any],
    *,
    unit_id: str | None = None,
    output_path: str | None = None,
) -> list[dict[str, Any]]:
    rows = _rows(manifest)
    if output_path:
        want = posix(output_path)
        return [r for r in rows if posix(r["path"]) == want]
    if unit_id:
        return [r for r in rows if r.get("unit_id") == unit_id]
    return rows


def _reading(rel: str, consumed: dict[str, Any]) -> dict[str, Any]:
    err = str(consumed.get("error") or "")
    return {
        "path": rel,
        "ok": bool(consumed.get("ok")),
        "reader": consumed.get("reader"),
        "first_parsed_key": consumed.get("first_parsed_key"),
        "record_count": consumed.get("record_count"),
        "error": err,
    }


def evaluate_rows(repo: Path, rows: list[dict[str, Any]]) -> CheckResult:
    readings: list[dict[str, Any]] = []
    bad: list[str] = []
    for row in rows:
        rel = posix(row["path"])
        kind = inferred_consumer(rel, row)
        record_type = row.get("record_type") if isinstance(row.get("record_type"), str) else None
        consumed = read_with_consumer(repo, rel, consumer=kind, record_type=record_type)
        item = _reading(rel, consumed)
        readings.append(item)
        if not item["ok"]:
            err = item["error"] or "unreadable"
            bad.append(f"{rel}:{err}")
    evidence = {"readings": readings, "unreadable": bad}
    n = len(rows)
    if n == 0:
        return CheckResult(
            False,
            "FAIL",
            "no manifest entries to open (a vacuous pass is always-red)",
            evidence,
        )
    if bad:
        return CheckResult(
            False,
            "FAIL",
            f"{len(bad)}/{n} entries unreadable: {'; '.join(bad)}",
            evidence,
        )
    return CheckResult(
        True,
        "PASS",
        f"{n} manifest entries opened by declared consumers",
        evidence,
    )


def evaluate_manifest(
    repo: Path,
    manifest: dict[str, Any] | None = None,
) -> CheckResult:
    doc = load_manifest(repo, manifest)
    return evaluate_rows(repo, _select_rows(doc))


def check_condition_12(
    repo: Path,
    *,
    unit_id: str | None = None,
    output_path: str | None = None,
    manifest: dict[str, Any] | None = None,
) -> CheckResult:
    doc = load_manifest(repo, manifest)
    rows = _select_rows(doc, unit_id=unit_id, output_path=output_path)
    return evaluate_rows(repo, rows)


def check_condition_11(
    repo: Path,
    *,
    unit_id: str | None = None,
    output_path: str,
    manifest: dict[str, Any] | None = None,
) -> CheckResult:
    rel = posix(output_path)
    path = repo / rel
    doc = load_manifest(repo, manifest)
    index = {posix(r["path"]): r for r in _rows(doc)}
    entry = index.get(rel)
    evidence: dict[str, Any] = {
        "path": rel,
        "unit_id": unit_id,
        "manifest_path": MANIFEST_REL,
        "in_manifest": entry is not None,
        "exists": path.is_file(),
    }
    if entry is None:
        if path.is_file():
            reason = (
                f"artifact {rel} exists on disk but is not in {MANIFEST_REL}"
            )
        else:
            reason = f"artifact {rel} is not in {MANIFEST_REL}"
        return CheckResult(False, "FAIL", reason, evidence)
    if path.is_file():
        sha, n = digest_file(path)
        evidence["sha256"] = sha
        evidence["bytes"] = n
        recorded = entry.get("sha256")
        if isinstance(recorded, str) and len(recorded) == HEX64:
            if recorded != sha:
                evidence["recorded_sha256"] = recorded
                return CheckResult(
                    False,
                    "FAIL",
                    f"manifest digest drift for {rel}: recorded {recorded} != live {sha}",
                    evidence,
                )
        return CheckResult(
            True,
            "PASS",
            f"registered {rel} sha256={sha} bytes={n}",
            evidence,
        )
    return CheckResult(
        False,
        "FAIL",
        f"artifact {rel} is registered in {MANIFEST_REL} but absent on disk",
        evidence,
    )


def _upsert_row(doc: dict[str, Any], row: dict[str, Any]) -> None:
    arts = doc.setdefault("artifacts", [])
    rel = posix(row["path"])
    for i, existing in enumerate(arts):
        if isinstance(existing, dict) and posix(existing.get("path") or "") == rel:
            merged = dict(existing)
            merged.update(row)
            arts[i] = merged
            return
    arts.append(row)


def register_path(
    repo: Path,
    rel: str,
    *,
    unit_id: str,
    consumer: str = "json",
    record_type: str | None = None,
) -> dict[str, Any]:
    rel = posix(rel)
    path = repo / rel
    if not path.is_file():
        raise RegisterError(f"cannot register absent path {rel}")
    sha, n = digest_file(path)
    consumed = read_with_consumer(
        repo, rel, consumer=consumer, record_type=record_type
    )
    row: dict[str, Any] = {
        "path": rel,
        "sha256": sha,
        "bytes": n,
        "present": True,
        "unit_id": unit_id,
        "consumer": consumer,
        "consumer_reader": consumed.get("reader") or JSON_READER,
        "first_parsed_key": consumed.get("first_parsed_key"),
        "record_count": consumed.get("record_count"),
        "read_ok": bool(consumed.get("ok")),
    }
    if record_type:
        row["record_type"] = record_type
    doc = load_manifest(repo)
    _upsert_row(doc, row)
    unit_n = sum(
        1
        for r in _rows(doc)
        if posix(r["path"]) not in CHARTER_PATHS
    )
    doc["unit_register_on_write"] = (
        "tools/command-center/artifact_register.py:register_path"
    )
    doc["unit_artifacts_registered"] = unit_n
    save_manifest(repo, doc)
    row["sha256"] = sha
    return row


def write_registered(
    repo: Path,
    rel: str,
    payload: str | bytes | dict[str, Any],
    *,
    unit_id: str,
    consumer: str = "json",
) -> dict[str, Any]:
    path = repo / posix(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, dict):
        text = json.dumps(payload, indent=1, sort_keys=True) + "\n"
        path.write_text(text, encoding="utf-8", newline="\n")
    elif isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(payload, encoding="utf-8", newline="\n")
    return register_path(repo, rel, unit_id=unit_id, consumer=consumer)


def self_test() -> int:
    """Both-states: unregistered/absent/unparseable fail; a valid row passes."""
    flags = {
        "unregistered_fail": False,
        "absent_fail": False,
        "unparseable_fail": False,
        "valid_pass": False,
        "both_states_pass": False,
        "phantom_rejected": False,
        "first_key": None,
        "second_key": None,
    }
    with tempfile.TemporaryDirectory(prefix="cc0009-ar-") as tmp:
        repo = Path(tmp)
        art = "command-center/receipts/T-0001.json"
        valid = {"unit_id": "T-0001", "k": "present"}
        (repo / art).parent.mkdir(parents=True)
        (repo / MANIFEST_REL).parent.mkdir(parents=True, exist_ok=True)
        save_manifest(
            repo,
            {
                "schema_version": 1,
                "artifacts": [],
                "contract": "self-test",
            },
        )
        (repo / art).write_text(
            json.dumps(valid, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        c11_unreg = check_condition_11(repo, unit_id="T-0001", output_path=art)
        flags["unregistered_fail"] = (not c11_unreg.ok) and "not in" in c11_unreg.reason

        registered = register_path(repo, art, unit_id="T-0001", consumer="json")
        flags["first_key"] = registered.get("first_parsed_key")
        flags["second_key"] = consume_json(repo / art).get("second_parsed_key")
        c11_ok = check_condition_11(repo, unit_id="T-0001", output_path=art)
        c12_ok = check_condition_12(repo, unit_id="T-0001", output_path=art)
        flags["valid_pass"] = (
            c11_ok.ok
            and c12_ok.ok
            and flags["first_key"] == "unit_id"
            and flags["second_key"] == "k"
            and bool((c12_ok.evidence.get("readings") or [{}])[0].get("first_parsed_key"))
        )

        mutated = load_manifest(repo)
        mutated = json.loads(json.dumps(mutated))
        mutated.setdefault("artifacts", []).append(
            {
                "path": "command-center/receipts/ABSENT.json",
                "sha256": "a" * 64,
                "bytes": 1,
                "present": True,
                "unit_id": "T-ABSENT",
                "consumer": "json",
            }
        )
        c12_abs = check_condition_12(repo, manifest=mutated)
        flags["absent_fail"] = (not c12_abs.ok) and "absent:" in c12_abs.reason

        garbage_rel = "command-center/receipts/GARBAGE.json"
        (repo / garbage_rel).write_text("{not-json", encoding="utf-8")
        gsha, gn = digest_file(repo / garbage_rel)
        gdoc = load_manifest(repo)
        gdoc = json.loads(json.dumps(gdoc))
        gdoc.setdefault("artifacts", []).append(
            {
                "path": garbage_rel,
                "sha256": gsha,
                "bytes": gn,
                "present": True,
                "unit_id": "T-GARBAGE",
                "consumer": "json",
            }
        )
        c12_bad = check_condition_12(repo, manifest=gdoc)
        flags["unparseable_fail"] = (not c12_bad.ok) and "json-parse" in c12_bad.reason

        phantom_rel = "command-center/receipts/PHANTOM.json"
        pdoc = load_manifest(repo)
        pdoc = json.loads(json.dumps(pdoc))
        pdoc.setdefault("artifacts", []).append(
            {
                "path": phantom_rel,
                "sha256": "b" * 64,
                "bytes": 9,
                "present": True,
                "unit_id": "T-PHANTOM",
                "consumer": "json",
            }
        )
        c12_ph = check_condition_12(repo, manifest=pdoc)
        flags["phantom_rejected"] = (not c12_ph.ok) and (
            phantom_rel in c12_ph.reason or "absent:" in c12_ph.reason
        )

        flags["both_states_pass"] = (
            flags["valid_pass"]
            and flags["unregistered_fail"]
            and flags["absent_fail"]
            and flags["unparseable_fail"]
            and flags["phantom_rejected"]
        )

    line = (
        "SUCCESS:artifact-register-self-test "
        f"unregistered_fail={flags['unregistered_fail']} "
        f"absent_fail={flags['absent_fail']} "
        f"unparseable_fail={flags['unparseable_fail']} "
        f"valid_pass={flags['valid_pass']} "
        f"both_states_pass={flags['both_states_pass']} "
        f"phantom_rejected={flags['phantom_rejected']} "
        f"first_key={flags['first_key']} "
        f"second_key={flags['second_key']}"
    )
    ok = bool(flags["both_states_pass"])
    if ok:
        print(line)
        return 0
    print("FAILED:artifact-register-self-test " + json.dumps(flags, sort_keys=True))
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--register", dest="register_rel")
    parser.add_argument("--unit-id", dest="unit_id")
    parser.add_argument("--consumer", default="json")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.register_rel:
        if not args.unit_id:
            print("FAILED:artifact-register --register needs --unit-id")
            return 2
        repo = Path(__file__).resolve().parents[2]
        row = register_path(
            repo, args.register_rel, unit_id=args.unit_id, consumer=args.consumer
        )
        print(json.dumps(row, indent=2, sort_keys=True))
        print(f"SUCCESS:registered {row['path']}")
        return 0
    print("FAILED:artifact-register pass --self-test or --register")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
