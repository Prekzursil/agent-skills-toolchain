#!/usr/bin/env python3
"""Produce and verify the dedicated completion-condition-11 unit manifest.

The charter manifest intentionally contains only contracted program files.  Unit
outputs therefore need a separately derived registration index.  This gate walks
receipt-shaped JSON under command-center/receipts/, command-center/adversarial/,
and command-center/audit/, hashes artifact bytes after CRLF-to-LF normalization,
and fails closed when discovery is empty, a candidate receipt cannot be read, or
a named artifact is absent.  A receipt is unit_id AND a non-empty artifacts
list; stray unit_id JSON elsewhere is ignored.  Absent files must not receive a
non-hex sha256 sentinel: completion_predicate._c11_manifest skips the digest
check on those.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_REL = "command-center/UNIT-ARTIFACT-MANIFEST.json"
_RECEIPT_DIRS = ("receipts", "adversarial", "audit")


class ManifestError(RuntimeError):
    """Discovery or verification failed closed."""


def _is_scratch(path: Path, corpus: Path) -> bool:
    """Underscore-prefixed trees are probe output, not the receipt corpus."""
    return any(part.startswith("_") for part in path.relative_to(corpus).parts)


def _is_receipt_shape(value: dict[str, Any]) -> bool:
    """Real receipt: non-empty unit_id AND a non-empty artifacts list."""
    unit_id = value.get("unit_id")
    artifacts = value.get("artifacts")
    return (
        isinstance(unit_id, str)
        and bool(unit_id.strip())
        and isinstance(artifacts, list)
        and bool(artifacts)
    )


def _load_receipts(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    corpus = root / "command-center"
    receipts: list[tuple[Path, dict[str, Any]]] = []
    for dirname in _RECEIPT_DIRS:
        base = corpus / dirname
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.json")):
            if _is_scratch(path, corpus) or path.name in {
                "ARTIFACT-MANIFEST.json",
                "UNIT-ARTIFACT-MANIFEST.json",
            }:
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ManifestError(f"unreadable/unparseable JSON {path}: {exc}") from exc
            if not isinstance(value, dict) or not _is_receipt_shape(value):
                continue
            receipts.append((path, value))
    if not receipts:
        raise ManifestError("discovered ZERO receipts (empty walk)")
    return receipts


def derive(root: Path) -> dict[str, Any]:
    """Derive the manifest entirely from receipt claims and filesystem bytes."""
    rows: list[dict[str, Any]] = []
    for receipt_path, receipt in _load_receipts(root):
        for artifact in receipt["artifacts"]:
            if not isinstance(artifact, dict) or not isinstance(
                artifact.get("path"), str
            ):
                raise ManifestError(f"malformed artifact in {receipt_path}")
            rel = artifact["path"].replace("\\", "/")
            target = root / rel
            receipt_rel = receipt_path.relative_to(root).as_posix()
            # Non-hex sentinels skip completion_predicate._c11_manifest digest check.
            if not target.is_file():
                raise ManifestError(
                    f"receipt {receipt_rel} names absent artifact {rel}"
                )
            try:
                raw = target.read_bytes().replace(b"\r\n", b"\n")
            except OSError as exc:
                raise ManifestError(f"artifact unreadable {target}: {exc}") from exc
            digest, length = hashlib.sha256(raw).hexdigest(), len(raw)
            rows.append(
                {
                    "path": rel,
                    "sha256": digest,
                    "bytes": length,
                    "present": True,
                    "unit_id": receipt["unit_id"],
                    "receipt_path": receipt_rel,
                }
            )
    if not rows:
        raise ManifestError("discovered ZERO artifacts (empty walk)")
    rows.sort(key=lambda row: (row["path"], row["receipt_path"], row["unit_id"]))
    return {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "tools/command-center/unit_manifest.py --write",
        "verified_on_disk": all(row["present"] for row in rows),
        "expected": len(rows),
        "present": sum(bool(row["present"]) for row in rows),
        "artifacts": rows,
    }


def _encoded(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True) + "\n"


def write(root: Path) -> int:
    try:
        value = derive(root)
        path = root / MANIFEST_REL
        path.write_text(_encoded(value), encoding="utf-8", newline="\n")
    except (ManifestError, OSError) as exc:
        print(f"FAILED:unit-manifest {exc}")
        return 1
    print(f"SUCCESS:unit-manifest wrote {value['expected']} entries to {MANIFEST_REL}")
    return 0


def check(root: Path) -> int:
    try:
        expected = _encoded(derive(root))
        actual = (root / MANIFEST_REL).read_text(encoding="utf-8")
    except (ManifestError, OSError, UnicodeDecodeError) as exc:
        print(f"FAILED:unit-manifest {exc}")
        return 1
    if actual != expected:
        print(f"FAILED:unit-manifest drift in {MANIFEST_REL}")
        return 1
    print(f"SUCCESS:unit-manifest {MANIFEST_REL} matches derived receipt corpus")
    return 0


def self_test() -> int:
    """Exercise real discovery/write/check paths: red, green, empty, missing, stray."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cc = root / "command-center" / "receipts"
        cc.mkdir(parents=True)
        artifact = root / "out.txt"
        artifact.write_bytes(b"known-good\r\n")
        receipt = {"unit_id": "TST-0001", "artifacts": [{"path": "out.txt"}]}
        (cc / "TST-0001.json").write_text(json.dumps(receipt), encoding="utf-8")
        if write(root) != 0:
            print("FAILED:unit-manifest-self-test could not create clean control")
            return 1
        manifest_path = root / MANIFEST_REL
        written = json.loads(manifest_path.read_text(encoding="utf-8"))
        hexdigits = "0123456789abcdef"
        for row in written["artifacts"]:
            digest = row.get("sha256")
            if not (
                isinstance(digest, str)
                and len(digest) == 64
                and all(c in hexdigits for c in digest)
            ):
                print("FAILED:unit-manifest-self-test clean write emitted non-hex sha256")
                return 1
        bad = written
        bad["artifacts"][0]["sha256"] = "0" * 64
        manifest_path.write_text(_encoded(bad), encoding="utf-8", newline="\n")
        red = check(root)
        if red != 1:
            print("FAILED:unit-manifest-self-test known-bad manifest stayed green")
            return 1
        if write(root) != 0 or check(root) != 0:
            print("FAILED:unit-manifest-self-test clean control did not go green")
            return 1
    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp)
        (empty / "command-center").mkdir()
        closed = check(empty)
        if closed != 1:
            print("FAILED:unit-manifest-self-test empty walk did not fail closed")
            return 1
    with tempfile.TemporaryDirectory() as tmp:
        missing_root = Path(tmp)
        cc = missing_root / "command-center" / "receipts"
        cc.mkdir(parents=True)
        absent_rel = "does-not-exist.txt"
        receipt_name = "TST-MISSING.json"
        receipt = {
            "unit_id": "TST-MISSING",
            "artifacts": [{"path": absent_rel}],
        }
        (cc / receipt_name).write_text(json.dumps(receipt), encoding="utf-8")
        try:
            derive(missing_root)
        except ManifestError as exc:
            msg = str(exc)
            if absent_rel not in msg:
                print("FAILED:unit-manifest-self-test missing-artifact error omitted path")
                return 1
            if receipt_name not in msg:
                print("FAILED:unit-manifest-self-test missing-artifact error omitted receipt")
                return 1
        else:
            print("FAILED:unit-manifest-self-test missing artifact derive() did not raise")
            return 1
        if write(missing_root) != 1:
            print("FAILED:unit-manifest-self-test missing artifact --write stayed green")
            return 1
        if check(missing_root) != 1:
            print("FAILED:unit-manifest-self-test missing artifact --check stayed green")
            return 1
    with tempfile.TemporaryDirectory() as tmp:
        stray_root = Path(tmp)
        receipts_dir = stray_root / "command-center" / "receipts"
        receipts_dir.mkdir(parents=True)
        artifact = stray_root / "out.txt"
        artifact.write_bytes(b"known-good\n")
        receipt = {"unit_id": "TST-0001", "artifacts": [{"path": "out.txt"}]}
        (receipts_dir / "TST-0001.json").write_text(json.dumps(receipt), encoding="utf-8")
        pointer = {"unit_id": "TST-POINTER", "output_path": "out.txt"}
        (receipts_dir / "TST-POINTER.json").write_text(json.dumps(pointer), encoding="utf-8")
        empty_arts = {"unit_id": "TST-EMPTY", "artifacts": []}
        (receipts_dir / "TST-EMPTY.json").write_text(json.dumps(empty_arts), encoding="utf-8")
        probe_dir = stray_root / "command-center" / "p2-wave" / "probes" / "ADV-0008"
        probe_dir.mkdir(parents=True)
        probe = {"unit_id": "ADV-0008", "note": "handoff, not a receipt"}
        (probe_dir / "handoff-measure.json").write_text(json.dumps(probe), encoding="utf-8")
        other_dir = stray_root / "command-center" / "other"
        other_dir.mkdir(parents=True)
        other = {
            "unit_id": "STRAY-0001",
            "artifacts": [{"path": "does-not-exist-stray.txt"}],
        }
        (other_dir / "stray.json").write_text(json.dumps(other), encoding="utf-8")
        try:
            derived = derive(stray_root)
        except ManifestError:
            print("FAILED:unit-manifest-self-test stray unit_id JSON was treated as a receipt")
            return 1
        rows = derived.get("artifacts") or []
        if len(rows) != 1 or rows[0].get("unit_id") != "TST-0001":
            print("FAILED:unit-manifest-self-test stray unit_id JSON leaked into derive")
            return 1
        leaked = [
            row.get("receipt_path", "")
            for row in rows
            if "p2-wave" in row.get("receipt_path", "")
            or "stray.json" in row.get("receipt_path", "")
            or "TST-POINTER" in row.get("receipt_path", "")
            or "TST-EMPTY" in row.get("receipt_path", "")
        ]
        if leaked:
            print("FAILED:unit-manifest-self-test stray receipt_path leaked")
            return 1
        if write(stray_root) != 0 or check(stray_root) != 0:
            print("FAILED:unit-manifest-self-test stray tree did not stay green")
            return 1
    print(
        "SUCCESS:unit-manifest-self-test red on bad, green on clean, "
        "closed on empty, closed on missing, ignored stray unit_id JSON"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="unit_manifest")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--self-test", action="store_true")
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    ns = parser.parse_args(argv)
    if ns.self_test:
        return self_test()
    return write(ns.root) if ns.write else check(ns.root)


if __name__ == "__main__":
    raise SystemExit(main())
