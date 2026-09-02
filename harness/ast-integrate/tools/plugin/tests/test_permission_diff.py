#!/usr/bin/env python3
"""Catalog tests for IMP-0060: permission-diff lattice and consent gate."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

import permission_diff as pd  # noqa: E402


class LatticeTests(unittest.TestCase):
    def test_catalog_triples_agree_on_all_three_signals(self) -> None:
        for name, (inst, cand) in pd.catalog_pairs().items():
            delta = pd.compute_delta(inst, cand)
            self.assertEqual(delta.verdict, name)
            self.assertEqual(delta.lattice_verdict, name)
            self.assertEqual(delta.raw_set_verdict, name)
            self.assertEqual(delta.atom_verdict, name)
            self.assertTrue(delta.lattice_atom_agree)

    def test_unchanged_pair_is_a_real_reorder(self) -> None:
        inst, cand = pd.UNCHANGED_PAIR
        self.assertNotEqual(list(inst), list(cand))
        self.assertEqual(pd.compute_delta(inst, cand).verdict, pd.UNCHANGED)

    def test_covering_pair_splits_lattice_from_raw_set(self) -> None:
        delta = pd.compute_delta(["Write(*)"], ["Write(src/a.py)"])
        self.assertEqual(delta.lattice_verdict, pd.NARROW)
        self.assertEqual(delta.raw_set_verdict, pd.WIDEN)
        self.assertEqual(delta.atom_verdict, pd.NARROW)
        self.assertEqual(delta.added, [])
        self.assertEqual(delta.removed, ["Write"])

    def test_disguised_widen_is_detected_with_bash_added(self) -> None:
        delta = pd.compute_delta(*pd.DISGUISED_WIDEN)
        self.assertEqual(delta.verdict, pd.WIDEN)
        self.assertIn("Bash", delta.added)
        self.assertEqual(delta.removed, [])

    def test_reorder_and_rename_without_new_grant_is_unchanged(self) -> None:
        delta = pd.compute_delta(*pd.REORDER_RENAME_UNCHANGED)
        self.assertEqual(delta.verdict, pd.UNCHANGED)
        self.assertEqual((delta.added, delta.removed), ([], []))

    def test_wildcard_scopes_widen(self) -> None:
        self.assertEqual(pd.compute_delta(*pd.REVIEWER_WILDCARD_WIDEN).verdict, pd.WIDEN)
        star = pd.compute_delta(*pd.REVIEWER_CREDENTIAL_WILDCARD)
        self.assertEqual(star.verdict, pd.WIDEN)
        self.assertEqual(star.added, ["Write"])
        self.assertTrue(star.lattice_atom_agree)

    def test_mixed_delta_fails_closed_as_widen(self) -> None:
        delta = pd.compute_delta(["Read"], ["Bash"])
        self.assertEqual(delta.verdict, pd.WIDEN)
        self.assertEqual(delta.atom_verdict, pd.WIDEN)

    def test_covers_partial_order(self) -> None:
        self.assertTrue(pd.covers("Write(*)", "Write(src/a.py)"))
        self.assertTrue(pd.covers("Write(src/**)", "Write(src/deep/x.py)"))
        self.assertTrue(pd.covers("Bash(git *)", "Bash(git status)"))
        self.assertTrue(pd.covers("net:connect:*", "net:connect:api.example"))
        self.assertFalse(pd.covers("Write(src/a.py)", "Write(*)"))
        self.assertFalse(pd.covers("Write", "Bash"))
        self.assertFalse(pd.covers("Write(src/*.py)", "Write(src/**)"))

    def test_canonicalize_folds_aliases_but_keeps_tools_distinct(self) -> None:
        self.assertEqual(pd.canonicalize(" read "), "Read")
        self.assertEqual(pd.canonicalize("Write(*)"), "Write")
        self.assertNotEqual(pd.canonicalize("Bash"), pd.canonicalize("Write"))
        self.assertEqual(pd.canonicalize("net:connect:*"), "net:connect:*")
        with self.assertRaises(ValueError):
            pd.canonicalize("   ")


class GateTests(unittest.TestCase):
    def test_widen_without_consent_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "pkg.json"
            dest.write_bytes(b"OLD\n")
            res = pd.gate_update("p", "1.0.0", "2.0.0", *pd.DISGUISED_WIDEN, dest=dest, candidate_body=b"NEW\n")
            self.assertFalse(res.proceed)
            self.assertFalse(res.wrote)
            self.assertEqual(res.reason, pd.REASON_REQUIRES_CONSENT)
            self.assertEqual(dest.read_bytes(), b"OLD\n")

    def test_narrow_and_unchanged_proceed_silently(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            for name in ("narrow", "unchanged"):
                inst, cand = pd.catalog_pairs()[name]
                dest = Path(td) / f"{name}.json"
                res = pd.gate_update("p", "1.0.0", "1.1.0", inst, cand, dest=dest, candidate_body=b"OK\n")
                self.assertTrue(res.proceed)
                self.assertTrue(res.wrote)
                self.assertIsNone(res.consent)
                self.assertEqual(dest.read_bytes(), b"OK\n")

    def test_consent_is_persisted_version_specific_and_not_blanket(self) -> None:
        inst, cand = pd.DISGUISED_WIDEN
        with tempfile.TemporaryDirectory() as td:
            store = pd.ConsentStore(Path(td) / "consent.json")
            dest = Path(td) / "c.json"
            granted = pd.gate_update("p", "1.0.0", "2.0.0", inst, cand, consent_store=store, consent_action=True, dest=dest, candidate_body=b"C\n")
            self.assertTrue(granted.proceed and granted.wrote)
            disk = json.loads(store.path.read_text(encoding="utf-8"))
            self.assertIs(disk["blanket"], False)
            self.assertEqual(len(disk["records"]), 1)
            self.assertEqual(disk["records"][0]["widened"], ["Bash"])
            # Same pair again: previously persisted consent authorizes it.
            again = pd.gate_update("p", "1.0.0", "2.0.0", inst, cand, consent_store=pd.ConsentStore(store.path))
            self.assertTrue(again.proceed)
            self.assertEqual(again.reason, "widening-previously-consented")
            # A later version pair is NOT covered.
            later = pd.gate_update("p", "2.0.0", "3.0.0", inst, cand, consent_store=store, dest=Path(td) / "l.json", candidate_body=b"L\n")
            self.assertFalse(later.proceed)
            self.assertFalse((Path(td) / "l.json").exists())

    def test_consent_must_cover_every_added_token(self) -> None:
        store = pd.MemoryConsentStore()
        store.persist(pd.Consent("p", "1.0.0", "2.0.0", widened=("Bash",)))
        self.assertTrue(store.allows("p", "1.0.0", "2.0.0", ["Bash"]))
        self.assertFalse(store.allows("p", "1.0.0", "2.0.0", ["Bash", "Network(*)"]))
        self.assertFalse(store.allows("p", "1.0.0", "2.1.0", ["Bash"]))

    def test_gate_from_manifests(self) -> None:
        installed = {"name": "demo", "version": "1.0.0", "permissions": ["Read"]}
        candidate = {"name": "demo", "version": "1.1.0", "permissions": ["Read", "Bash"]}
        res = pd.gate_from_manifests(installed, candidate)
        self.assertFalse(res.proceed)
        self.assertEqual(res.delta.added, ["Bash"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
