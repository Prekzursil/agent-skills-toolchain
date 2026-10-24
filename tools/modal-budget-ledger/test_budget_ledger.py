#!/usr/bin/env python
"""Tests for modal-budget-ledger. Run: python test_budget_ledger.py (or pytest).

Everything runs in a temp dir and touches no real config, no real ledger and no
network. Pure logic, so it is cheap to run on a thermally limited machine.
"""

from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import budget_ledger as bl  # noqa: E402


def _write(tmp: Path, name: str, payload: object) -> Path:
    p = tmp / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _cfg(tmp: Path, **over: object) -> Path:
    base: dict[str, object] = {
        "global_ceiling_usd": 100.0,
        "min_headroom_usd": 5.0,
        "accounts": [
            {"profile": "acct-a", "cap_usd": 30.0, "funded": True},
            {"profile": "acct-b", "cap_usd": 50.0, "funded": True},
        ],
    }
    base.update(over)
    return _write(tmp, "config.json", base)


def _entries(*pairs: tuple[str, float]) -> list[bl.Entry]:
    return [bl.Entry(ts=1.0, profile=p, usd=u, job_id="", note="") for p, u in pairs]


# --------------------------------------------------------------------------- #
# Config validation                                                           #
# --------------------------------------------------------------------------- #


def test_loads_valid_config() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(_cfg(Path(d)))
        assert len(cfg.accounts) == 2
        assert cfg.accounts[0].profile == "acct-a"
        assert cfg.global_ceiling_usd == 100.0
        assert cfg.min_headroom_usd == 5.0


def test_missing_config_is_an_error() -> None:
    try:
        bl.load_config(Path("nope") / "missing.json")
    except bl.ConfigError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("expected ConfigError")


def test_funded_must_be_explicit() -> None:
    """Omitting `funded` must fail rather than defaulting to usable."""
    with tempfile.TemporaryDirectory() as d:
        p = _cfg(Path(d), accounts=[{"profile": "acct-a", "cap_usd": 30.0}])
        try:
            bl.load_config(p)
        except bl.ConfigError as exc:
            assert "funded" in str(exc)
        else:
            raise AssertionError("expected ConfigError for missing funded")


def test_duplicate_profile_rejected() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = _cfg(
            Path(d),
            accounts=[
                {"profile": "dup", "cap_usd": 10.0, "funded": True},
                {"profile": "dup", "cap_usd": 20.0, "funded": True},
            ],
        )
        try:
            bl.load_config(p)
        except bl.ConfigError as exc:
            assert "duplicate" in str(exc)
        else:
            raise AssertionError("expected ConfigError for duplicate profile")


def test_nan_cap_rejected() -> None:
    """NaN must be refused: every comparison against it is False, so a NaN cap
    would silently pass or fail every threshold check instead of erroring."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        p.write_text(
            '{"accounts":[{"profile":"a","cap_usd":NaN,"funded":true}]}',
            encoding="utf-8",
        )
        try:
            bl.load_config(p)
        except bl.ConfigError as exc:
            assert "finite" in str(exc)
        else:
            raise AssertionError("expected ConfigError for NaN cap")


def test_zero_and_negative_caps_rejected() -> None:
    with tempfile.TemporaryDirectory() as d:
        for cap in (0.0, -5.0):
            p = _cfg(
                Path(d),
                accounts=[{"profile": "a", "cap_usd": cap, "funded": True}],
            )
            try:
                bl.load_config(p)
            except bl.ConfigError:
                pass
            else:
                raise AssertionError(f"expected ConfigError for cap {cap}")


# --------------------------------------------------------------------------- #
# Ledger arithmetic                                                           #
# --------------------------------------------------------------------------- #


def test_spent_and_remaining() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(_cfg(Path(d)))
        rows = bl.account_status(cfg, _entries(("acct-a", 10.0), ("acct-a", 2.5)))
        a = next(r for r in rows if r.profile == "acct-a")
        assert a.spent_usd == 12.5
        assert a.remaining_usd == 17.5
        b = next(r for r in rows if r.profile == "acct-b")
        assert b.spent_usd == 0.0
        assert b.remaining_usd == 50.0


def test_corrupt_ledger_line_is_fatal() -> None:
    """Skipping a bad line would under-report spend, the one thing this must
    never do, so it raises instead."""
    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "spend.jsonl"
        led.write_text('{"profile":"a","usd":1.0}\nnot json\n', encoding="utf-8")
        try:
            bl.read_entries(led)
        except bl.ConfigError as exc:
            assert "corrupt" in str(exc)
        else:
            raise AssertionError("expected ConfigError for corrupt line")


def test_missing_ledger_means_nothing_spent() -> None:
    with tempfile.TemporaryDirectory() as d:
        assert bl.read_entries(Path(d) / "absent.jsonl") == []


# --------------------------------------------------------------------------- #
# Selection and thresholds                                                    #
# --------------------------------------------------------------------------- #


def test_order_strategy_drains_first_account_then_moves_on() -> None:
    """The "spend A down, then move to B" shape."""
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(_cfg(Path(d)))
        picked, _ = bl.select_account(cfg, [], strategy="order")
        assert picked is not None and picked.profile == "acct-a"
        # a has $4 left, under the $5 min headroom, so it is skipped.
        picked, _ = bl.select_account(cfg, _entries(("acct-a", 26.0)))
        assert picked is not None and picked.profile == "acct-b"


def test_most_remaining_strategy_spreads() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(_cfg(Path(d)))
        picked, _ = bl.select_account(cfg, [], strategy="most-remaining")
        assert picked is not None and picked.profile == "acct-b"


def test_min_headroom_threshold_is_exclusive_at_the_boundary() -> None:
    """remaining == min_headroom stays eligible; a cent less does not."""
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(_cfg(Path(d)))
        at = bl.account_status(cfg, _entries(("acct-a", 25.0)))[0]
        assert at.remaining_usd == 5.0
        assert at.eligible, "exactly at the threshold must remain usable"
        below = bl.account_status(cfg, _entries(("acct-a", 25.01)))[0]
        assert below.remaining_usd == 4.99
        assert not below.eligible
        assert "below min headroom" in below.reason


def test_cap_reached_is_not_eligible() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(_cfg(Path(d)))
        row = bl.account_status(cfg, _entries(("acct-a", 30.0)))[0]
        assert row.remaining_usd == 0.0
        assert not row.eligible and row.reason == "cap reached"


def test_unfunded_account_is_refused_with_a_reason() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = _cfg(
            Path(d),
            accounts=[
                {"profile": "free-tier", "cap_usd": 30.0, "funded": False},
                {"profile": "mine", "cap_usd": 40.0, "funded": True},
            ],
        )
        cfg = bl.load_config(p)
        rows = bl.account_status(cfg, [])
        unfunded = next(r for r in rows if r.profile == "free-tier")
        assert not unfunded.eligible
        assert unfunded.reason == "not marked funded in config"
        picked, _ = bl.select_account(cfg, [])
        assert picked is not None and picked.profile == "mine"


def test_no_eligible_account_returns_a_refusal() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(_cfg(Path(d)))
        picked, reason = bl.select_account(
            cfg, _entries(("acct-a", 30.0), ("acct-b", 50.0))
        )
        assert picked is None
        assert "headroom" in reason


def test_unknown_strategy_rejected() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(_cfg(Path(d)))
        try:
            bl.select_account(cfg, [], strategy="cheapest")
        except bl.ConfigError as exc:
            assert "unknown strategy" in str(exc)
        else:
            raise AssertionError("expected ConfigError")


# --------------------------------------------------------------------------- #
# Global ceiling                                                              #
# --------------------------------------------------------------------------- #


def test_global_ceiling_beats_per_account_headroom() -> None:
    """The ceiling must win even while an account still has room, otherwise it
    is decorative.

    AMENDED 2026-10-24: this test previously asserted ``b.eligible`` here, which
    encoded the very bug the lead's review found — eligibility was computed from
    the account's own cap and the ceiling was a separate end-stop. An account
    the ceiling cannot fund is now ineligible at source, so the assertion is
    inverted. Its untouched cap is still reported, which is the point: the two
    figures differ and the spendable one governs.
    """
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(_cfg(Path(d), global_ceiling_usd=20.0))
        entries = _entries(("acct-a", 20.0))
        b = next(r for r in bl.account_status(cfg, entries) if r.profile == "acct-b")
        assert b.remaining_usd == 50.0, "its own cap is untouched"
        assert b.effective_remaining_usd == 0.0, "but the ceiling funds none of it"
        assert not b.eligible
        assert b.reason == "global ceiling reached"
        picked, reason = bl.select_account(cfg, entries)
        assert picked is None
        assert "global ceiling reached" in reason


def test_ceiling_clips_remaining_room_not_just_the_end() -> None:
    """REGRESSION (lead review, 2026-10-24). The ceiling used to be enforced
    only once reached, so with $2 of global room left an account showing $8 was
    still offered and a launcher could overshoot the "hard total" by $6.

    These are the exact numbers from the review: ceiling $60, headroom $5,
    a=$30 cap spent $26, b=$40 cap spent $32, total $58.
    """
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(
            _cfg(
                Path(d),
                global_ceiling_usd=60.0,
                accounts=[
                    {"profile": "a", "cap_usd": 30.0, "funded": True},
                    {"profile": "b", "cap_usd": 40.0, "funded": True},
                ],
            )
        )
        entries = _entries(("a", 26.0), ("b", 32.0))
        assert bl.total_spent(entries) == 58.0
        assert bl.ceiling_remaining(cfg, entries) == 2.0

        b = next(r for r in bl.account_status(cfg, entries) if r.profile == "b")
        assert b.remaining_usd == 8.0, "its own cap really does leave $8"
        assert b.effective_remaining_usd == 2.0, "but only $2 is spendable"
        assert not b.eligible, "$2 is under the $5 min headroom, so refuse"
        assert "global ceiling" in b.reason, "and say which limit bound"

        picked, reason = bl.select_account(cfg, entries)
        assert picked is None, "must not hand out an account it cannot fund"
        assert "global ceiling" in reason


def test_effective_remaining_tracks_the_binding_limit() -> None:
    """Whichever of cap or ceiling binds first is the one reported."""
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(_cfg(Path(d), global_ceiling_usd=1000.0))
        # Ceiling is far away, so the account cap binds.
        row = bl.account_status(cfg, _entries(("acct-a", 10.0)))[0]
        assert row.remaining_usd == 20.0
        assert row.effective_remaining_usd == 20.0
        assert row.eligible

        # Now the ceiling is the tighter limit.
        tight = bl.load_config(_cfg(Path(d), global_ceiling_usd=25.0))
        row = bl.account_status(tight, _entries(("acct-a", 10.0)))[0]
        assert row.remaining_usd == 20.0
        assert row.effective_remaining_usd == 15.0
        assert row.eligible, "$15 still clears the $5 headroom"


def test_most_remaining_ranks_on_effective_not_account_remaining() -> None:
    """A clipped account must not win the ranking on its unclipped figure."""
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(
            _cfg(
                Path(d),
                global_ceiling_usd=1000.0,
                min_headroom_usd=1.0,
                accounts=[
                    {"profile": "small", "cap_usd": 20.0, "funded": True},
                    {"profile": "big", "cap_usd": 900.0, "funded": True},
                ],
            )
        )
        picked, _ = bl.select_account(cfg, [], strategy="most-remaining")
        assert picked is not None and picked.profile == "big"

        # With only $10 of ceiling room left, both clip to $10 and the tie
        # breaks on name, so the pick stays deterministic rather than
        # following the now-meaningless per-account figure.
        tight = bl.load_config(
            _cfg(
                Path(d),
                global_ceiling_usd=10.0,
                min_headroom_usd=1.0,
                accounts=[
                    {"profile": "small", "cap_usd": 20.0, "funded": True},
                    {"profile": "big", "cap_usd": 900.0, "funded": True},
                ],
            )
        )
        picked, _ = bl.select_account(tight, [], strategy="most-remaining")
        assert picked is not None
        assert picked.effective_remaining_usd == 10.0
        assert picked.profile == "big", "ties break on name, deterministically"


def test_ceiling_remaining_never_negative() -> None:
    """An already-recorded overshoot reads as zero room, not negative room."""
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(_cfg(Path(d), global_ceiling_usd=10.0))
        assert bl.ceiling_remaining(cfg, _entries(("acct-a", 25.0))) == 0.0


def test_absent_ceiling_means_unlimited_total() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = bl.load_config(_cfg(Path(d), global_ceiling_usd=None))
        assert cfg.global_ceiling_usd is None
        assert bl.ceiling_blocked(cfg, _entries(("acct-a", 29.0))) == ""


# --------------------------------------------------------------------------- #
# Recording spend                                                             #
# --------------------------------------------------------------------------- #


def test_record_appends_and_accumulates() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = bl.load_config(_cfg(tmp))
        led = tmp / "spend.jsonl"
        bl.record_spend(led, cfg, "acct-a", 1.5, job_id="j1", now=1.0)
        bl.record_spend(led, cfg, "acct-a", 2.25, job_id="j2", now=2.0)
        entries = bl.read_entries(led)
        assert len(entries) == 2
        assert bl.spent_by_account(entries)["acct-a"] == 3.75
        assert [e.job_id for e in entries] == ["j1", "j2"]


def test_dry_run_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = bl.load_config(_cfg(tmp))
        led = tmp / "spend.jsonl"
        entry = bl.record_spend(led, cfg, "acct-a", 7.0, dry_run=True, now=1.0)
        assert entry.usd == 7.0
        assert not led.exists(), "dry run must not create the ledger"


def test_record_against_unenrolled_account_refused() -> None:
    """A typo must not silently open an uncapped shadow account."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = bl.load_config(_cfg(tmp))
        try:
            bl.record_spend(tmp / "spend.jsonl", cfg, "acct-typo", 1.0)
        except bl.ConfigError as exc:
            assert "not enrolled" in str(exc)
        else:
            raise AssertionError("expected ConfigError")


def test_negative_spend_refused() -> None:
    """Negative spend would manufacture headroom; corrections are out of scope
    for v1 and documented as such in the README."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = bl.load_config(_cfg(tmp))
        try:
            bl.record_spend(tmp / "spend.jsonl", cfg, "acct-a", -5.0)
        except bl.ConfigError as exc:
            assert "negative" in str(exc)
        else:
            raise AssertionError("expected ConfigError")


# --------------------------------------------------------------------------- #
# CLI surface                                                                 #
# --------------------------------------------------------------------------- #


def test_cli_select_prints_bare_profile() -> None:
    with tempfile.TemporaryDirectory() as d:
        rc = bl.main(["--config", str(_cfg(Path(d))), "select"])
        assert rc == bl.EXIT_OK


def test_cli_select_exit_3_when_exhausted() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = _cfg(tmp)
        led = tmp / "spend.jsonl"
        cfg = bl.load_config(cfg_path)
        bl.record_spend(led, cfg, "acct-a", 30.0, now=1.0)
        bl.record_spend(led, cfg, "acct-b", 50.0, now=2.0)
        rc = bl.main(["--config", str(cfg_path), "select"])
        assert rc == bl.EXIT_NO_ACCOUNT, "exhaustion is exit 3, not a crash"


def test_cli_bad_config_is_exit_2() -> None:
    rc = bl.main(["--config", "definitely-missing.json", "status"])
    assert rc == bl.EXIT_USAGE


def test_cli_requires_a_config_path() -> None:
    saved = os.environ.pop("MODAL_BUDGET_CONFIG", None)
    try:
        rc = bl.main(["status"])
        assert rc == bl.EXIT_USAGE
    finally:
        if saved is not None:
            os.environ["MODAL_BUDGET_CONFIG"] = saved


def test_cli_status_json_shape() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rc = bl.main(["--config", str(_cfg(tmp)), "status", "--json"])
        assert rc == bl.EXIT_OK


# Every module budget_ledger.py is allowed to import. This allowlist IS the
# reviewable surface: adding an import here is a deliberate, visible act, and
# anything absent fails the test below. Replaces an earlier substring grep that
# would have waved through `from urllib.request import urlopen`, `os.system`,
# `importlib`, and `subprocess`.
ALLOWED_IMPORTS = frozenset(
    {
        "__future__",
        "argparse",
        "dataclasses",
        "json",
        "math",
        "os",
        "pathlib",
        "sys",
        "time",
    }
)


def test_imports_match_the_allowlist() -> None:
    """No network, no subprocess, no dynamic import — checked structurally.

    Walks the AST rather than grepping strings, so an aliased or from-import
    cannot slip past, and the failure names the offending module.
    """
    tree = ast.parse((HERE / "budget_ledger.py").read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            # level > 0 is a relative import; there is no package here, so the
            # module would be None. Record it as "." to fail loudly.
            found.add(node.module.split(".")[0] if node.module else ".")
    unexpected = found - ALLOWED_IMPORTS
    assert not unexpected, (
        f"budget_ledger.py imports {sorted(unexpected)}, which is not in the "
        f"allowlist. If that is intended, add it to ALLOWED_IMPORTS and say in "
        f"the README what it changes about the no-network property."
    )


def test_allowlist_excludes_the_dangerous_modules() -> None:
    """Guards the guard: the allowlist itself must stay free of the modules
    that would let the no-network property quietly lapse."""
    for banned in (
        "socket",
        "urllib",
        "http",
        "requests",
        "httpx",
        "subprocess",
        "importlib",
        "modal",
        "ftplib",
        "telnetlib",
        "asyncio",
    ):
        assert banned not in ALLOWED_IMPORTS, f"{banned} must not be allowlisted"


# Floor, not just "no failures": a discovery break (a rename, a decorator that hides
# the test_ functions) would otherwise report PASS on 0/0 and gate nothing in CI.
# Raise it when tests are added; a drop below it is a lost test, not a pass.
MIN_TESTS = 33


def main() -> int:
    tests = [
        (name, obj)
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    if len(tests) < MIN_TESTS:
        print(f"RESULT: FAIL  (collected {len(tests)} tests, floor is {MIN_TESTS})")
        return 1
    failures: list[str] = []
    for name, fn in tests:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - test runner reports everything
            failures.append(f"{name}: {exc}")
            print(f"  BAD  {name}: {exc}")
        else:
            print(f"  OK   {name}")
    print(
        f"\nRESULT: {'PASS' if not failures else 'FAIL'}  "
        f"({len(tests) - len(failures)}/{len(tests)} passed)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
