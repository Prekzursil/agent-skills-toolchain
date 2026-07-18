"""Unit tests for the qdx-rush charge / energy parsers.

Scope: the pure-Python result parsers in ``qdx_mcp_server`` — ``_parse_charge_exports``
(and its shared vs strict behaviour), ``_parse_exess``, and ``_parse_charges``.  All input
is a STUB ``res`` object with a hand-built ``.exports`` dict; nothing here touches the
network, a RUSH token, or rush-py's native extension (see ``conftest.py`` for the stubs).

Expected charge-export shapes are taken from ``QDX_REFERENCE.md`` §12 ("Common accessors"):
``result.exports["chelpg_charges"]`` (ESP fit, the primary ``charges``) and
``result.exports["mulliken_charges"]`` (population analysis, diagnostic).

Two robustness behaviours are asserted here (post-review hardening, PR #89 follow-up):
  * Fix 1 — an exess/energy/qmmm result with NO ``.exports`` attribute must not raise.
  * Fix 2 — a malformed-but-present charge array in the SHARED/auto energy path must not
    flip an otherwise-complete energy result to non-done; it is swallowed + warned. The
    explicit ``charges`` path stays strict (still raises).
"""

from __future__ import annotations

import json
import logging
import types

import pytest

import qdx_mcp_server as srv

# Reference-shaped 3-atom charge arrays (values are illustrative, ordering = input topology).
CHELPG = [-0.42, 0.21, 0.21]
MULLIKEN = [-0.50, 0.25, 0.25]

_UNSET = object()


# ----------------------------------------------------------------- stub result builders
def _make_qmmbe(**overrides: object) -> types.SimpleNamespace:
    base: dict[str, object] = {
        "expanded_hf_energy": -76.02,
        "expanded_mp2_ss_correction": -0.05,
        "expanded_mp2_os_correction": -0.15,
        "reference_fragment": None,
        "num_iters": 11,
    }
    base.update(overrides)
    return types.SimpleNamespace(**base)


def _make_res(
    *, exports: object = _UNSET, method: object = _UNSET, qmmbe: object = None
) -> types.SimpleNamespace:
    mbe = qmmbe if qmmbe is not None else _make_qmmbe()
    if method is not _UNSET:
        mbe.method = method
    res = types.SimpleNamespace(calc=types.SimpleNamespace(qmmbe=mbe))
    if exports is not _UNSET:
        res.exports = exports
    return res


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, res: object) -> None:
    """Make ``exess.ResultRef.from_raw_output(raw).fetch()`` return ``res``."""

    class _Ref:
        @staticmethod
        def from_raw_output(raw: object) -> object:
            return types.SimpleNamespace(fetch=lambda: res)

    monkeypatch.setattr(srv.exess, "ResultRef", _Ref)


# ================================================================= _parse_charge_exports
def test_non_dict_exports_returns_empty() -> None:
    assert srv._parse_charge_exports(None) == {}
    assert srv._parse_charge_exports("not-a-dict") == {}
    assert srv._parse_charge_exports([1, 2, 3]) == {}


def test_missing_charge_keys_returns_empty() -> None:
    assert srv._parse_charge_exports({"energy": -1.0, "other": [1, 2, 3]}) == {}


def test_happy_path_prefers_chelpg_as_primary() -> None:
    out = srv._parse_charge_exports(
        {"chelpg_charges": CHELPG, "mulliken_charges": MULLIKEN}
    )
    assert out["charges"] == CHELPG
    assert out["charge_model"] == "CHELPG"
    assert out["n_atoms"] == 3
    assert out["units"] == "elementary_charge"
    assert out["atom_order"] == "input_topology"
    assert out["chelpg_charges"] == CHELPG
    assert out["mulliken_charges"] == MULLIKEN
    assert out["chelpg_charge_sum"] == round(sum(CHELPG), 10)
    assert out["mulliken_charge_sum"] == round(sum(MULLIKEN), 10)


def test_mulliken_only_is_selected_as_primary() -> None:
    out = srv._parse_charge_exports({"mulliken_charges": MULLIKEN})
    assert out["charge_model"] == "Mulliken"
    assert out["charges"] == MULLIKEN
    assert out["n_atoms"] == 3
    assert "chelpg_charge_sum" not in out
    assert out["mulliken_charge_sum"] == round(sum(MULLIKEN), 10)


@pytest.mark.parametrize(
    ("bad_exports", "match"),
    [
        ({"chelpg_charges": 42}, "non-empty charge array"),  # non-list charges
        ({"chelpg_charges": []}, "non-empty charge array"),  # empty charges
        (
            {"mulliken_charges": [0.1, "x", 0.2]},
            "non-numeric charge",
        ),  # non-numeric elem
        (
            {"chelpg_charges": [0.1, 0.2], "mulliken_charges": [0.1]},
            "different atom counts",
        ),  # length mismatch
    ],
)
def test_strict_mode_raises_on_malformed(bad_exports: dict, match: str) -> None:
    # The explicit charges-kind path passes strict=True and must surface the malformation.
    with pytest.raises(ValueError, match=match):
        srv._parse_charge_exports(bad_exports, strict=True)


@pytest.mark.parametrize(
    "bad_exports",
    [
        {"chelpg_charges": 42},
        {"chelpg_charges": []},
        {"mulliken_charges": [0.1, "x", 0.2]},
        {"chelpg_charges": [0.1, 0.2], "mulliken_charges": [0.1]},
    ],
)
def test_shared_path_swallows_malformed_and_warns(
    bad_exports: dict, caplog: pytest.LogCaptureFixture
) -> None:
    # Default (shared/auto energy path) must NOT raise on a malformed-but-present array.
    with caplog.at_level(logging.WARNING):
        assert srv._parse_charge_exports(bad_exports) == {}
    assert any("malformed" in rec.getMessage().lower() for rec in caplog.records)


# ================================================================= _parse_exess
def test_parse_exess_without_exports_attribute_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fix 1: a normal exess/interaction/calculate/qmmm result has no `.exports`; the
    # unconditional `res.exports` access would AttributeError before the getattr guard.
    res = _make_res(exports=_UNSET)
    assert not hasattr(res, "exports")
    _patch_fetch(monkeypatch, res)

    out = srv._parse_exess(b"raw")

    assert out["total_hartree"] == pytest.approx(-76.02 + -0.05 + -0.15)
    assert out["total_kcal_per_mol"] is not None
    assert out["is_interaction_energy"] is False
    assert "charges" not in out
    assert "charge_model" not in out


def test_parse_exess_malformed_exports_preserves_energy_and_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Fix 2: malformed-but-present charges must not flip a completed energy to non-done.
    res = _make_res(exports={"chelpg_charges": [0.1, "bad", 0.2]})
    _patch_fetch(monkeypatch, res)

    with caplog.at_level(logging.WARNING):
        out = srv._parse_exess(b"raw")

    assert out["total_hartree"] == pytest.approx(-76.02 + -0.05 + -0.15)
    assert "charges" not in out
    assert "charge_model" not in out
    assert any("malformed" in rec.getMessage().lower() for rec in caplog.records)


def test_parse_exess_merges_valid_charges(monkeypatch: pytest.MonkeyPatch) -> None:
    res = _make_res(exports={"chelpg_charges": CHELPG, "mulliken_charges": MULLIKEN})
    _patch_fetch(monkeypatch, res)

    out = srv._parse_exess(b"raw")

    assert out["charge_model"] == "CHELPG"
    assert out["charges"] == CHELPG
    assert out["n_atoms"] == 3
    assert out["total_hartree"] == pytest.approx(-76.22)


def test_parse_exess_interaction_energy_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    res = _make_res(qmmbe=_make_qmmbe(reference_fragment=0), exports={})
    _patch_fetch(monkeypatch, res)

    out = srv._parse_exess(b"raw")

    assert out["is_interaction_energy"] is True
    assert out["reference_fragment"] == 0


# ================================================================= _parse_charges (strict)
def test_parse_charges_returns_arrays_and_method(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    res = _make_res(
        exports={"chelpg_charges": CHELPG, "mulliken_charges": MULLIKEN},
        method="RestrictedKSDFT",
    )
    _patch_fetch(monkeypatch, res)

    out = srv._parse_charges(b"raw")

    assert out["method"] == "RestrictedKSDFT"
    assert out["charges"] == CHELPG
    assert out["chelpg_charges"] == CHELPG
    assert out["mulliken_charges"] == MULLIKEN
    assert out["n_atoms"] == 3


def test_parse_charges_stays_strict_on_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Explicit charges path keeps raising (strictness retained after the shared-path fix).
    res = _make_res(
        exports={"chelpg_charges": [0.1, "x"], "mulliken_charges": [0.2, 0.3]}
    )
    _patch_fetch(monkeypatch, res)

    with pytest.raises(ValueError, match="non-numeric charge"):
        srv._parse_charges(b"raw")


def test_parse_charges_raises_when_exports_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    res = _make_res(exports={})
    _patch_fetch(monkeypatch, res)

    with pytest.raises(ValueError, match="missing charge exports"):
        srv._parse_charges(b"raw")


# ================================================================= run_collect (end-to-end)
def test_run_collect_energy_stays_done_with_malformed_charges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The reviewer's concrete concern: a valid energy whose charge export is malformed
    # must still collect as status='done' with the parsed energy (not the "could not
    # parse" fallback envelope).
    res = _make_res(exports={"chelpg_charges": [0.1, "bad"]})
    _patch_fetch(monkeypatch, res)
    monkeypatch.setattr(srv, "_with_retry", lambda fn, *a, **k: b"raw")

    out = json.loads(srv.run_collect("run-123", kind="energy"))

    assert out["status"] == "done"
    assert out["result"]["total_hartree"] == pytest.approx(-76.22)
    assert "charges" not in out["result"]
