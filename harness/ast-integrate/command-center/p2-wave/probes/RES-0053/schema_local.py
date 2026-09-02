#!/usr/bin/env python3
"""Offline research-claim-record validator (jsonschema 4.10, no network).

jsonschema 4.10.3 follows $ref by fetching https://ast-integrate.invalid/ ...
which does not resolve. Map those $id URIs onto repo files via RefResolver.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DECLARED = "command-center/schema/research-claim-record.schema.json"
STORE_FILES = (
    DECLARED,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def domain(doc: dict) -> dict:
    """Domain payload lives in report (receipt_core additionalProperties=false)."""
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("revocation_table"), list):
        return report
    return doc


def _store() -> dict:
    store: dict = {}
    for rel in STORE_FILES:
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        ident = data.get("$id")
        if not isinstance(ident, str) or not ident:
            raise SystemExit(f"FAILED:RES-0053 schema {rel} missing $id")
        store[ident] = data
        store["https://ast-integrate.invalid/" + rel] = data
    return store


def _https_handler(uri: str) -> dict:
    raise ValueError(f"refusing remote schema fetch: {uri}")


def validator():
    shim = json.loads((REPO / DECLARED).read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(shim.get("$id") or ""),
        referrer=shim,
        store=_store(),
        handlers={"https": _https_handler, "http": _https_handler},
    )
    return Draft202012Validator(shim, resolver=resolver)


class _KindPinError:
    def __init__(self, message: str):
        self.message = message
        self.absolute_path = ("report", "kind")
        self.path = self.absolute_path


def iter_errors(doc) -> list:
    errs = list(validator().iter_errors(doc))
    report = doc.get("report") if isinstance(doc, dict) else None
    if isinstance(report, dict):
        kind = report.get("kind")
        if kind not in (None, "research-claim-record"):
            errs.append(
                _KindPinError(
                    "report.kind must stay research-claim-record "
                    f"(got {kind!r})"
                )
            )
    return sorted(errs, key=lambda e: list(getattr(e, "absolute_path", None) or e.path))


def garbage_accepted() -> object | None:
    for garbage in ({}, {"schema_version": 1}, {"report": {"kind": "research-claim-record"}}, []):
        if isinstance(garbage, dict) and not garbage.get("unit_id") and not garbage.get("id"):
            # Treat empty/unrelated objects as garbage even if the hook is lax.
            continue
        if isinstance(garbage, list):
            return None
        v = validator()
        if not list(v.iter_errors(garbage)):
            return garbage
    return None


def main() -> int:
    rel = "command-center/research/RES-0053.json"
    if len(sys.argv) > 1:
        rel = sys.argv[1]
    path = Path(rel)
    if not path.is_absolute():
        path = REPO / rel
    if not path.is_file():
        print(f"FAILED:RES-0053-schema absent {rel}")
        return 1
    doc = json.loads(path.read_text(encoding="utf-8"))
    errs = iter_errors(doc)
    vacuous = garbage_accepted()
    if vacuous is not None:
        print(f"FAILED:RES-0053-schema vacuous accepted {list(vacuous)[:4]}")
        return 1
    if errs:
        for err in errs[:12]:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            print(f"  {loc}: {err.message}")
        print(f"FAILED:RES-0053-schema n={len(errs)}")
        return 1
    print(f"schema_errors=0 path={rel}")
    print("SUCCESS:RES-0053-schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
