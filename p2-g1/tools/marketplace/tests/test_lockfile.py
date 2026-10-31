"""Lockfile verify-on-install tests used by IMP-0084 named probes."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from marketplace.lockfile import (
    DigestMismatch,
    MissingLockfileEntry,
    ResolvedPackage,
    filesystem_census,
    generate_lockfile,
    install_verified,
    load_lockfile,
)


def _packages() -> list[ResolvedPackage]:
    return [
        ResolvedPackage("alpha", "1.0.0", "mem://alpha-1.0.0", b"alpha-payload"),
        ResolvedPackage("beta", "2.0.0", "mem://beta-2.0.0", b"beta-payload"),
    ]


class TestLockfile(unittest.TestCase):
    def test_generate_and_load_roundtrip(self) -> None:
        data = generate_lockfile(_packages())
        doc = load_lockfile(data)
        self.assertEqual(doc["resolver_version"], "1")
        rows = doc["packages"]
        self.assertEqual(
            [(r["name"], r["version"]) for r in rows],
            [("alpha", "1.0.0"), ("beta", "2.0.0")],
        )
        self.assertEqual(rows[0]["sha256"], ResolvedPackage("a", "1", "", b"alpha-payload").digest_hex)
        self.assertEqual(rows[0]["bytes"], len(b"alpha-payload"))

    def test_lockfile_is_deterministic(self) -> None:
        reordered = list(reversed(_packages()))
        self.assertEqual(
            generate_lockfile(_packages()),
            generate_lockfile(reordered),
            "same index must regenerate byte-identical lockfile",
        )

    def test_match_installs(self) -> None:
        lock = generate_lockfile(_packages())
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            got = install_verified(
                lock,
                name="alpha",
                dest=dest,
                fetch=lambda url: b"alpha-payload",
            )
            self.assertEqual(got.name, "alpha")
            self.assertTrue(Path(got.dest).is_file())
            self.assertEqual(Path(got.dest).read_bytes(), b"alpha-payload")
            self.assertEqual(got.warnings, [])

    def test_mismatch_refused_before_any_write(self) -> None:
        lock = generate_lockfile(_packages())
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            before = filesystem_census(dest)
            with self.assertRaises(DigestMismatch) as ctx:
                install_verified(
                    lock,
                    name="alpha",
                    dest=dest,
                    fetch=lambda url: b"alpha-payload-MUTATED",
                )
            msg = str(ctx.exception)
            self.assertIn(ctx.exception.expected_hex, msg)
            self.assertIn(ctx.exception.actual_hex, msg)
            after = filesystem_census(dest)
            self.assertEqual(before, after, "refusal must occur before any write")

    def test_missing_entry_refused(self) -> None:
        lock = generate_lockfile(_packages())
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            before = filesystem_census(dest)
            with self.assertRaises(MissingLockfileEntry):
                install_verified(
                    lock,
                    name="gamma",
                    dest=dest,
                    fetch=lambda url: b"whatever",
                )
            self.assertEqual(before, filesystem_census(dest))

    def test_stale_resolver_version_warns_but_installs(self) -> None:
        doc = load_lockfile(generate_lockfile(_packages()))
        doc["resolver_version"] = "0"
        stale = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
        with tempfile.TemporaryDirectory() as tmp:
            got = install_verified(
                stale,
                name="beta",
                dest=Path(tmp),
                fetch=lambda url: b"beta-payload",
            )
            self.assertEqual(len(got.warnings), 1)
            self.assertIn("stale resolver version", got.warnings[0])

    def test_unmutated_installs_in_same_run_after_refusal(self) -> None:
        # NEGATIVE CONTROL: the unmutated blob installs right after a refusal.
        lock = generate_lockfile(_packages())
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            with self.assertRaises(DigestMismatch):
                install_verified(
                    lock,
                    name="alpha",
                    dest=dest,
                    fetch=lambda url: b"alpha-payload-MUTATED",
                )
            got = install_verified(
                lock,
                name="alpha",
                dest=dest,
                fetch=lambda url: b"alpha-payload",
            )
            self.assertTrue(Path(got.dest).is_file())


if __name__ == "__main__":
    unittest.main()
