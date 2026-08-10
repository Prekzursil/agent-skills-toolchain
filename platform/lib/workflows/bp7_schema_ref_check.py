"""Resolve-and-compile check for every ``schema_ref`` / ``output_schema`` a blueprint declares.

A blueprint that points ``schema_ref`` at a path which does not exist on disk is a dangling
contract: the DSL validator does not open the file, so the document is "schema-valid" while no
receipt it produces could ever be validated. This module is the missing check.

For one reference it asserts, in order:
  1. the repo-relative ``.json`` file exists,
  2. it parses as JSON,
  3. the optional ``#/json/pointer`` fragment resolves inside it,
  4. the resolved subschema COMPILES as draft 2020-12 against the local registry.

Both-states control: :func:`self_check` runs the same resolver over a KNOWN-PRESENT reference
(must pass) and over four KNOWN-BROKEN ones - missing file, bad pointer, non-schema body, and a
path escaping the repo - each of which must FAIL with the expected reason. A resolver that is
silent on all five measures nothing.

Usage::

    python platform/lib/workflows/schema_ref_check.py            # check every blueprint
    python platform/lib/workflows/schema_ref_check.py --self-check
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = REPO_ROOT / "platform" / "workflows"


class RefError(Exception):
    """A schema reference that cannot be resolved. ``reason`` is a stable token."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def _resolve_pointer(doc: Any, pointer: str) -> Any:
    """RFC-6901 JSON pointer walk. Raises RefError('pointer-unresolved')."""
    if pointer in ("", "/"):
        return doc
    if not pointer.startswith("/"):
        raise RefError("pointer-malformed", f"{pointer!r} does not start with '/'")
    node = doc
    for raw in pointer.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if token not in node:
                raise RefError("pointer-unresolved", f"{token!r} absent from {pointer!r}")
            node = node[token]
        elif isinstance(node, list):
            try:
                node = node[int(token)]
            except (ValueError, IndexError) as exc:
                raise RefError("pointer-unresolved", f"{token!r} in {pointer!r}: {exc}") from exc
        else:
            raise RefError("pointer-unresolved", f"{token!r} walks into a scalar")
    return node


def resolve_ref(ref: str, *, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Resolve one schema reference. Returns a row; raises RefError on any failure."""
    if ref.startswith(("http://", "https://")):
        # An absolute URI is legal per the schema_reference pattern but cannot be opened offline.
        return {"ref": ref, "kind": "absolute-uri", "resolved": False, "reason": "not-checked-offline"}
    path_part, _, pointer = ref.partition("#")
    if ".." in path_part:
        raise RefError("path-escape", f"{ref!r} contains '..'")
    if not path_part.endswith(".json"):
        raise RefError("not-json", f"{ref!r} does not name a .json document")
    target = repo_root / path_part
    if not target.is_file():
        raise RefError("file-missing", f"{path_part} is not a file under {repo_root}")
    try:
        doc = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RefError("json-invalid", f"{path_part}: {exc}") from exc
    sub = _resolve_pointer(doc, pointer) if pointer else doc
    if not isinstance(sub, (dict, bool)):
        raise RefError("not-a-schema", f"{ref!r} resolves to {type(sub).__name__}, not a schema")
    try:
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(sub)
    except Exception as exc:  # noqa: BLE001 - any compile failure is the finding
        raise RefError("schema-uncompilable", f"{ref!r}: {str(exc)[:160]}") from exc
    return {
        "ref": ref,
        "kind": "repo-relative",
        "resolved": True,
        "file": path_part,
        "pointer": pointer or None,
        "bytes": target.stat().st_size,
    }


def collect_refs(doc: Any, path: str = "") -> list[tuple[str, str]]:
    """Every ``schema_ref`` / ``output_schema`` / ``predicate_ref`` / ``validate_against`` string."""
    keys = {"schema_ref", "output_schema", "predicate_ref", "validate_against", "council_spec_ref"}
    out: list[tuple[str, str]] = []
    if isinstance(doc, dict):
        for k, v in doc.items():
            if k in keys and isinstance(v, str):
                out.append((f"{path}/{k}", v))
            out.extend(collect_refs(v, f"{path}/{k}"))
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            out.extend(collect_refs(v, f"{path}/{i}"))
    return out


def check_document(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for where, ref in collect_refs(doc):
        try:
            row = resolve_ref(ref)
        except RefError as exc:
            failures.append({"where": where, "ref": ref, "reason": exc.reason, "detail": exc.detail})
        else:
            rows.append({"where": where, **row})
    distinct = sorted({r["ref"] for r in rows} | {f["ref"] for f in failures})
    return {
        "document": path.name,
        "id": doc.get("id"),
        "references": len(rows) + len(failures),
        "distinct_references": len(distinct),
        "resolved": len([r for r in rows if r.get("resolved")]),
        "failures": failures,
        "ok": not failures,
    }


def check_all(paths: Iterable[Path]) -> dict[str, Any]:
    results = [check_document(p) for p in sorted(paths)]
    return {
        "documents": len(results),
        "references": sum(r["references"] for r in results),
        "resolved": sum(r["resolved"] for r in results),
        "failures": [f for r in results for f in r["failures"]],
        "results": results,
        "ok": all(r["ok"] for r in results),
    }


# --------------------------------------------------------------------- both-states control


def self_check(tmp: Path) -> dict[str, Any]:
    """Prove the resolver fires on known-broken refs and stays silent on a known-present one."""
    tmp.mkdir(parents=True, exist_ok=True)
    good = "platform/schema/receipt.schema.json"
    (tmp / "not-a-schema.json").write_text(json.dumps({"$defs": {"leaf": 7}}), encoding="utf-8")
    (tmp / "broken.json").write_text("{not json", encoding="utf-8")
    rel = tmp.relative_to(REPO_ROOT).as_posix()

    cases: list[tuple[str, str, str | None]] = [
        ("known-present", good, None),
        ("known-present-pointer", f"{good}#/$defs/receipt_core", None),
        ("missing-file", "command-center/schema/definitely-not-here.schema.json", "file-missing"),
        ("bad-pointer", f"{good}#/$defs/no_such_def", "pointer-unresolved"),
        ("not-a-schema", f"{rel}/not-a-schema.json#/$defs/leaf", "not-a-schema"),
        ("json-invalid", f"{rel}/broken.json", "json-invalid"),
        ("path-escape", "../../etc/passwd.json", "path-escape"),
        ("not-json", "platform/schema/receipt.schema.yaml", "not-json"),
    ]
    rows = []
    try:
        for name, ref, expect in cases:
            try:
                resolve_ref(ref)
                got = None
            except RefError as exc:
                got = exc.reason
            rows.append({"case": name, "ref": ref, "expected": expect, "got": got, "ok": got == expect})
    finally:
        # The two known-broken fixtures must live UNDER the repo, because resolve_ref joins
        # repo-relative paths against REPO_ROOT - a tempfile outside the tree could not be
        # addressed by a repo-relative reference at all. So they are cleaned up here instead of
        # being left behind for someone else to commit.
        shutil.rmtree(tmp, ignore_errors=True)
    return {
        "cases": len(rows),
        "passed": sum(1 for r in rows if r["ok"]),
        "rows": rows,
        "fixture_dir_removed": not tmp.exists(),
        "ok": all(r["ok"] for r in rows) and not tmp.exists(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bp7_schema_ref_check")
    ap.add_argument("paths", nargs="*", help="blueprint json files (default: every bp-*.json)")
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args(argv)

    if args.self_check:
        report = self_check(REPO_ROOT / "platform" / "lib" / "workflows" / "_tmp_refcheck")
        print(json.dumps(report, indent=1))
        print("SUCCESS:schema-ref-selfcheck" if report["ok"] else "FAILED:schema-ref-selfcheck")
        return 0 if report["ok"] else 1

    paths = [Path(p) for p in args.paths] or sorted(WORKFLOW_DIR.glob("bp-*.json"))
    if not paths:
        print("FAILED:schema-ref-check no blueprint documents found")
        return 1
    report = check_all(paths)
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")
    for r in report["results"]:
        print(f"{'OK ' if r['ok'] else 'BAD'} {r['document']:<52} refs={r['references']:<4} distinct={r['distinct_references']:<4} resolved={r['resolved']}")
        for f in r["failures"]:
            print(f"      {f['reason']:<20} {f['ref']}  @{f['where']}")
    print(f"documents={report['documents']} references={report['references']} resolved={report['resolved']} failures={len(report['failures'])}")
    print("SUCCESS:schema-ref-check" if report["ok"] else "FAILED:schema-ref-check")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
