"""Tests for seed.py -- the file its own module docstring has always cited.

seed.py:4 said "That property is what `tests/test_seed.py` uses to prove the committed
catalog was not hand-edited into disagreement with its own source". That file did not
exist: `ls tools/command-center/tests/` on 2026-08-13 returned conftest, test_close,
test_reconcile_delivery, test_registry, test_render, test_validate and nothing else, and
`grep -rn test_seed` found only the docstring pointing at itself. A documented property
with no executable check is NOT-CHECKED, so the two claims it makes are asserted here.

The third test is the regression for a defect that was LIVE, not hypothetical.
"""

from __future__ import annotations

import hashlib

import catalog as cat
import seed
import validate as val

REGISTER = cat.command_center_dir() / "sources" / "REGISTER.md"
OVERLAY = cat.command_center_dir() / "sources" / "overlay.json"

# Fields seed.py's docstring calls DERIVED: recomputable from REGISTER.md alone.
# Deliberately NOT asserted: disposition, disposition_evidence, status, history, defer.
# Those are mutated after seeding by the close/defer tooling (close_round2.py,
# clear_answered_gates.py), so a fresh seed legitimately disagrees with the committed
# catalog on them -- open is 69 at seed time and 58 as committed. Asserting them would
# make this test red for correct work, which is how a tripwire gets deleted.
_DERIVED = (
    "id",
    "title",
    "phase",
    "target",
    "inputs",
    "output_path",
    "completion_sentinel",
    "program",
    "section",
    "effort",
    "sources",
)


def test_seeding_is_deterministic():
    """seed.py's first docstring claim: same inputs -> same bytes, no clock in the output."""
    first = seed.build_catalog(REGISTER, OVERLAY)
    second = seed.build_catalog(REGISTER, OVERLAY)
    assert first == second


def test_derived_fields_agree_with_the_committed_catalog():
    """seed.py's second docstring claim, scoped to what seeding actually derives.

    A hand edit to a derived field of WORK-UNIT-CATALOG.json -- a retitled item, a moved
    section, an invented row -- shows up here as a mismatch against REGISTER.md.
    """
    built = {
        item["id"]: item for item in seed.build_catalog(REGISTER, OVERLAY)["items"]
    }
    committed = {item["id"]: item for item in cat.items(cat.load())}

    assert set(built) == set(committed)
    drift = [
        f"{item_id}.{field}: register={built[item_id][field]!r} catalog={committed[item_id][field]!r}"
        for item_id in sorted(built)
        for field in _DERIVED
        if built[item_id][field] != committed[item_id][field]
    ]
    assert drift == [], drift


def test_register_provenance_is_lf_normalised(tmp_path):
    """REGRESSION. seed.py hashed RAW bytes; validate.py:228 hashes LF-normalised ones.

    A Windows checkout under core.autocrlf=true materialises CRLF, so `seed.py --force`
    there recorded a digest validate.py could never satisfy -- re-creating by hand the
    exact REACH-6 failure that held `gate-tests-coverage (python packages)` red for 98
    commits. Measured 2026-08-13 on two clones of one commit differing only in
    core.autocrlf: autocrlf=true gave `REACH-6 -: register snapshot sha256 721c4e577ca5
    != recorded 60a4d35f822d` and exit 1; autocrlf=false was clean, i.e. the writer
    agreed with the reader only by luck on an LF checkout.

    Red-proof: revert the `.replace(b"\\r\\n", b"\\n")` at seed.py:127 and both asserts
    below fail, because the CRLF register hashes to something else entirely.
    """
    lf = REGISTER.read_bytes().replace(b"\r\n", b"\n")
    crlf_register = tmp_path / "REGISTER.md"
    crlf_register.write_bytes(lf.replace(b"\n", b"\r\n"))
    assert crlf_register.read_bytes().count(b"\r\n") > 0, "fixture is not actually CRLF"

    built = seed.build_catalog(crlf_register, OVERLAY)

    assert built["provenance"]["register_sha256"] == hashlib.sha256(lf).hexdigest()
    assert built["provenance"]["register_bytes"] == len(lf)

    # Second, mechanically different check: hand the catalog to validate.py's OWN reader
    # rather than re-deriving the digest here. A re-implementation that drifts with the
    # code it checks proves nothing; this fails if either side stops normalising.
    violations, _ = val.validate(built, register_path=crlf_register)
    assert [v for v in violations if v.check == "REACH-6"] == []
