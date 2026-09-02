#!/usr/bin/env python3
"""Standalone six-case gate for RegisteringWriter (not pytest).

Run as ``python3 -B tools/command-center/tests/test_registering_writer.py``.
A later sweep must not be what produces rows, and must not register a
direct-open bypass.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from registering_writer import (  # noqa: E402
    EmitError,
    RegisteringWriter,
    digest_file,
    reconcile,
)

UNIT = "IMP-0454"


def _sandbox() -> tuple[Path, Path, Path]:
    tmp = Path(tempfile.mkdtemp(prefix="rw-test-"))
    root = tmp / "out"
    man = tmp / "ARTIFACT-MANIFEST.json"
    return tmp, root, man


def test_full_run_set_difference_empty() -> None:
    _, root, man = _sandbox()
    writer = RegisteringWriter(root, man)
    payloads = [
        ("alpha.json", '{"n":1}\n'),
        ("beta/gamma.txt", "gamma-body\n"),
        ("delta.md", "# delta\n"),
    ]
    for rel, body in payloads:
        writer.emit(rel, body, unit_id=UNIT, role="fixture")
        fresh = json.loads(man.read_text(encoding="utf-8"))
        paths = [row["path"] for row in fresh["artifacts"]]
        if rel not in paths:
            raise AssertionError(f"row missing immediately after emit: {rel}")
    report = reconcile(root, man)
    if report.unregistered_count != 0 or not report.set_difference_empty:
        raise AssertionError(f"full-run set difference not empty: {report.as_dict()}")
    if set(writer.emitted_paths) != {p[0] for p in payloads}:
        raise AssertionError(f"emitted_paths drifted: {writer.emitted_paths}")


def test_bypass_direct_open_is_unregistered() -> None:
    _, root, man = _sandbox()
    writer = RegisteringWriter(root, man)
    writer.emit("kept.json", '{"kept":true}\n', unit_id=UNIT)
    before = reconcile(root, man)
    if not before.set_difference_empty:
        raise AssertionError("writer-only state was not empty")
    sneak = root / "sneak-bypass.txt"
    with open(sneak, "w", encoding="utf-8") as fh:
        fh.write("direct-open bypass of RegisteringWriter.emit\n")
    after = reconcile(root, man)
    if "sneak-bypass.txt" not in after.unregistered:
        raise AssertionError(f"bypass not unregistered: {after.unregistered}")
    if after.unregistered_count != 1:
        raise AssertionError(f"expected one unregistered path, got {after.as_dict()}")


def test_reconcile_does_not_register() -> None:
    _, root, man = _sandbox()
    writer = RegisteringWriter(root, man)
    writer.emit("kept.json", "k\n", unit_id=UNIT)
    (root / "sneak-bypass.txt").write_text("bypass\n", encoding="utf-8")
    before = man.read_bytes()
    first = reconcile(root, man)
    second = reconcile(root, man)
    after = man.read_bytes()
    if after != before:
        raise AssertionError("reconcile mutated the manifest")
    if "sneak-bypass.txt" not in first.unregistered:
        raise AssertionError("bypass missing from first reconcile")
    if first.unregistered != second.unregistered:
        raise AssertionError("reconcile was not stable")


def test_emit_row_sha_matches_file() -> None:
    _, root, man = _sandbox()
    writer = RegisteringWriter(root, man)
    body = "hash-me\r\nplease\n"
    row = writer.emit("hashed.txt", body, unit_id=UNIT, role="primary")
    dest = root / "hashed.txt"
    sha, size = digest_file(dest)
    if row["sha256"] != sha or row["bytes"] != size:
        raise AssertionError(f"row {row} != digest_file {sha} {size}")
    if not dest.is_file():
        raise AssertionError("dest missing after emit")


def test_in_memory_claim_misses_bypass() -> None:
    _, root, man = _sandbox()
    writer = RegisteringWriter(root, man)
    writer.emit("kept.json", "k\n", unit_id=UNIT)
    sneak_rel = "sneak-bypass.txt"
    (root / sneak_rel).write_text("bypass\n", encoding="utf-8")
    if sneak_rel in writer.emitted_paths:
        raise AssertionError("in-memory writer claim already listed the bypass")
    if sneak_rel not in reconcile(root, man).unregistered:
        raise AssertionError("disk reconcile missed the bypass the memory claim missed")


def test_failed_emit_is_noop() -> None:
    _, root, man = _sandbox()
    writer = RegisteringWriter(root, man)
    writer.emit("kept.json", "keep-me\n", unit_id=UNIT)
    before_man = man.read_bytes()
    before_files = sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )
    before_mem = list(writer.emitted_paths)
    raised = False
    try:
        writer.emit("../escape.txt", "nope\n", unit_id=UNIT)
    except EmitError:
        raised = True
    if not raised:
        raise AssertionError("escaping emit did not raise")
    nested_raised = False
    try:
        writer.emit("kept.json/nested.txt", "nope\n", unit_id=UNIT)
    except (EmitError, OSError):
        nested_raised = True
    if not nested_raised:
        raise AssertionError("emit over a file-as-parent did not fail")
    after_man = man.read_bytes()
    after_files = sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )
    if after_man != before_man:
        raise AssertionError("failed emit mutated the manifest")
    if after_files != before_files:
        raise AssertionError(f"failed emit left files {after_files} vs {before_files}")
    if writer.emitted_paths != before_mem:
        raise AssertionError("failed emit mutated in-memory emitted_paths")
    if (root.parent / "escape.txt").exists():
        raise AssertionError("escaped file was written outside the root")


def main() -> int:
    tests = [
        test_full_run_set_difference_empty,
        test_bypass_direct_open_is_unregistered,
        test_reconcile_does_not_register,
        test_emit_row_sha_matches_file,
        test_in_memory_claim_misses_bypass,
        test_failed_emit_is_noop,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
        except Exception as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
            continue
        print(f"PASS {fn.__name__}")
    total = len(tests)
    passed = total - failed
    if failed:
        print(f"FAILED:registering_writer {passed}/{total}")
        return 1
    print(f"SUCCESS:registering_writer {passed}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
