#!/usr/bin/env python
"""Tests for account-hopper. Run: python test_account_hopper.py (or pytest).

Everything runs in a temp dir and touches no real config, no real ledger and no
network. Pure logic, so it is cheap to run on a thermally limited machine.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import account_hopper as ah  # noqa: E402


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


def _entries(*pairs: tuple[str, float]) -> list[ah.Entry]:
    return [ah.Entry(ts=1.0, profile=p, usd=u, job_id="", note="") for p, u in pairs]


def _run(argv: list[str]) -> tuple[int, str, str]:
    """Run the CLI, capture both streams, return (rc, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = ah.main(argv)
    return rc, out.getvalue(), err.getvalue()


# --------------------------------------------------------------------------- #
# Config validation                                                           #
# --------------------------------------------------------------------------- #


def test_loads_valid_config() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = ah.load_config(_cfg(Path(d)))
        assert len(cfg.accounts) == 2
        assert cfg.accounts[0].profile == "acct-a"
        assert cfg.global_ceiling_usd == 100.0
        assert cfg.min_headroom_usd == 5.0


def test_missing_config_is_an_error() -> None:
    try:
        ah.load_config(Path("nope") / "missing.json")
    except ah.ConfigError as exc:
        assert "not found" in str(exc)
    else:
        raise AssertionError("expected ConfigError")


def test_invalid_json_config_is_an_error() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        p.write_text("{not json", encoding="utf-8")
        try:
            ah.load_config(p)
        except ah.ConfigError as exc:
            assert "not valid JSON" in str(exc)
        else:
            raise AssertionError("expected ConfigError for invalid JSON")


def test_funded_must_be_explicit() -> None:
    """Omitting `funded` must fail rather than defaulting to usable."""
    with tempfile.TemporaryDirectory() as d:
        p = _cfg(Path(d), accounts=[{"profile": "acct-a", "cap_usd": 30.0}])
        try:
            ah.load_config(p)
        except ah.ConfigError as exc:
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
            ah.load_config(p)
        except ah.ConfigError as exc:
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
            ah.load_config(p)
        except ah.ConfigError as exc:
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
                ah.load_config(p)
            except ah.ConfigError:
                pass
            else:
                raise AssertionError(f"expected ConfigError for cap {cap}")


def test_non_numeric_cap_rejected() -> None:
    """A string cap must be refused at the boundary, not compared."""
    with tempfile.TemporaryDirectory() as d:
        p = _cfg(
            Path(d), accounts=[{"profile": "a", "cap_usd": "thirty", "funded": True}]
        )
        try:
            ah.load_config(p)
        except ah.ConfigError as exc:
            assert "expected a number, got str" in str(exc)
        else:
            raise AssertionError("expected ConfigError for string cap")


def test_bool_cap_rejected() -> None:
    """A bool is not a number here: True would silently act as 1.0."""
    with tempfile.TemporaryDirectory() as d:
        p = _cfg(Path(d), accounts=[{"profile": "a", "cap_usd": True, "funded": True}])
        try:
            ah.load_config(p)
        except ah.ConfigError as exc:
            assert "expected a number, got bool" in str(exc)
        else:
            raise AssertionError("expected ConfigError for bool cap")


def test_note_must_be_a_string() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = _cfg(
            Path(d),
            accounts=[{"profile": "a", "cap_usd": 10.0, "funded": True, "note": 42}],
        )
        try:
            ah.load_config(p)
        except ah.ConfigError as exc:
            assert "must be a string" in str(exc)
        else:
            raise AssertionError("expected ConfigError for non-string note")


def test_config_must_be_a_json_object() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.json"
        p.write_text("[]", encoding="utf-8")
        try:
            ah.load_config(p)
        except ah.ConfigError as exc:
            assert "JSON object" in str(exc)
        else:
            raise AssertionError("expected ConfigError for non-object config")


def test_accounts_must_be_a_non_empty_list() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = _cfg(Path(d), accounts=[])
        try:
            ah.load_config(p)
        except ah.ConfigError as exc:
            assert "non-empty list" in str(exc)
        else:
            raise AssertionError("expected ConfigError for empty accounts")


def test_account_entry_must_be_an_object() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = _cfg(Path(d), accounts=["acct-a"])
        try:
            ah.load_config(p)
        except ah.ConfigError as exc:
            assert "must be an object" in str(exc)
        else:
            raise AssertionError("expected ConfigError for non-object account")


def test_blank_profile_rejected() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = _cfg(
            Path(d), accounts=[{"profile": "   ", "cap_usd": 10.0, "funded": True}]
        )
        try:
            ah.load_config(p)
        except ah.ConfigError as exc:
            assert "non-empty string" in str(exc)
        else:
            raise AssertionError("expected ConfigError for blank profile")


def test_zero_ceiling_rejected() -> None:
    """A ceiling must buy something; 0 would block everything by accident."""
    with tempfile.TemporaryDirectory() as d:
        p = _cfg(Path(d), global_ceiling_usd=0.0)
        try:
            ah.load_config(p)
        except ah.ConfigError as exc:
            assert "must be greater than 0" in str(exc)
        else:
            raise AssertionError("expected ConfigError for zero ceiling")


# --------------------------------------------------------------------------- #
# Ledger arithmetic                                                           #
# --------------------------------------------------------------------------- #


def test_spent_and_remaining() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = ah.load_config(_cfg(Path(d)))
        rows = ah.account_status(cfg, _entries(("acct-a", 10.0), ("acct-a", 2.5)))
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
            ah.read_entries(led)
        except ah.ConfigError as exc:
            assert "corrupt" in str(exc)
        else:
            raise AssertionError("expected ConfigError for corrupt line")


def test_ledger_line_that_is_not_an_object_is_fatal() -> None:
    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "spend.jsonl"
        led.write_text("[1, 2]\n", encoding="utf-8")
        try:
            ah.read_entries(led)
        except ah.ConfigError as exc:
            assert "ledger line must be an object" in str(exc)
        else:
            raise AssertionError("expected ConfigError for non-object ledger line")


def test_ledger_line_without_a_profile_is_fatal() -> None:
    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "spend.jsonl"
        led.write_text('{"usd":1.0}\n', encoding="utf-8")
        try:
            ah.read_entries(led)
        except ah.ConfigError as exc:
            assert "entry.profile missing" in str(exc)
        else:
            raise AssertionError("expected ConfigError for profile-less ledger line")


def test_ledger_blank_lines_are_skipped() -> None:
    with tempfile.TemporaryDirectory() as d:
        led = Path(d) / "spend.jsonl"
        led.write_text('\n   \n{"profile":"acct-a","usd":1.0}\n', encoding="utf-8")
        entries = ah.read_entries(led)
        assert len(entries) == 1
        assert entries[0].profile == "acct-a"


def test_missing_ledger_means_nothing_spent() -> None:
    with tempfile.TemporaryDirectory() as d:
        assert ah.read_entries(Path(d) / "absent.jsonl") == []


# --------------------------------------------------------------------------- #
# Selection and thresholds                                                    #
# --------------------------------------------------------------------------- #


def test_order_strategy_drains_first_account_then_moves_on() -> None:
    """The "spend A down, then move to B" shape."""
    with tempfile.TemporaryDirectory() as d:
        cfg = ah.load_config(_cfg(Path(d)))
        picked, _ = ah.select_account(cfg, [], strategy="order")
        assert picked is not None and picked.profile == "acct-a"
        # a has $4 left, under the $5 min headroom, so it is skipped.
        picked, _ = ah.select_account(cfg, _entries(("acct-a", 26.0)))
        assert picked is not None and picked.profile == "acct-b"


def test_most_remaining_strategy_spreads() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = ah.load_config(_cfg(Path(d)))
        picked, _ = ah.select_account(cfg, [], strategy="most-remaining")
        assert picked is not None and picked.profile == "acct-b"


def test_min_headroom_threshold_is_exclusive_at_the_boundary() -> None:
    """remaining == min_headroom stays eligible; a cent less does not."""
    with tempfile.TemporaryDirectory() as d:
        cfg = ah.load_config(_cfg(Path(d)))
        at = ah.account_status(cfg, _entries(("acct-a", 25.0)))[0]
        assert at.remaining_usd == 5.0
        assert at.eligible, "exactly at the threshold must remain usable"
        below = ah.account_status(cfg, _entries(("acct-a", 25.01)))[0]
        assert below.remaining_usd == 4.99
        assert not below.eligible
        assert "below min headroom" in below.reason


def test_cap_reached_is_not_eligible() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = ah.load_config(_cfg(Path(d)))
        row = ah.account_status(cfg, _entries(("acct-a", 30.0)))[0]
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
        cfg = ah.load_config(p)
        rows = ah.account_status(cfg, [])
        unfunded = next(r for r in rows if r.profile == "free-tier")
        assert not unfunded.eligible
        assert unfunded.reason == "not marked funded in config"
        picked, _ = ah.select_account(cfg, [])
        assert picked is not None and picked.profile == "mine"


def test_no_eligible_account_returns_a_refusal() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = ah.load_config(_cfg(Path(d)))
        picked, reason = ah.select_account(
            cfg, _entries(("acct-a", 30.0), ("acct-b", 50.0))
        )
        assert picked is None
        assert "headroom" in reason


def test_unknown_strategy_rejected() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = ah.load_config(_cfg(Path(d)))
        try:
            ah.select_account(cfg, [], strategy="cheapest")
        except ah.ConfigError as exc:
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
        cfg = ah.load_config(_cfg(Path(d), global_ceiling_usd=20.0))
        entries = _entries(("acct-a", 20.0))
        b = next(r for r in ah.account_status(cfg, entries) if r.profile == "acct-b")
        assert b.remaining_usd == 50.0, "its own cap is untouched"
        assert b.effective_remaining_usd == 0.0, "but the ceiling funds none of it"
        assert not b.eligible
        assert b.reason == "global ceiling reached"
        picked, reason = ah.select_account(cfg, entries)
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
        cfg = ah.load_config(
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
        assert ah.total_spent(entries) == 58.0
        assert ah.ceiling_remaining(cfg, entries) == 2.0

        b = next(r for r in ah.account_status(cfg, entries) if r.profile == "b")
        assert b.remaining_usd == 8.0, "its own cap really does leave $8"
        assert b.effective_remaining_usd == 2.0, "but only $2 is spendable"
        assert not b.eligible, "$2 is under the $5 min headroom, so refuse"
        assert "global ceiling" in b.reason, "and say which limit bound"

        picked, reason = ah.select_account(cfg, entries)
        assert picked is None, "must not hand out an account it cannot fund"
        assert "global ceiling" in reason


def test_effective_remaining_tracks_the_binding_limit() -> None:
    """Whichever of cap or ceiling binds first is the one reported."""
    with tempfile.TemporaryDirectory() as d:
        cfg = ah.load_config(_cfg(Path(d), global_ceiling_usd=1000.0))
        # Ceiling is far away, so the account cap binds.
        row = ah.account_status(cfg, _entries(("acct-a", 10.0)))[0]
        assert row.remaining_usd == 20.0
        assert row.effective_remaining_usd == 20.0
        assert row.eligible

        # Now the ceiling is the tighter limit.
        tight = ah.load_config(_cfg(Path(d), global_ceiling_usd=25.0))
        row = ah.account_status(tight, _entries(("acct-a", 10.0)))[0]
        assert row.remaining_usd == 20.0
        assert row.effective_remaining_usd == 15.0
        assert row.eligible, "$15 still clears the $5 headroom"


def test_most_remaining_picks_maximal_spendable_room() -> None:
    """`most-remaining` hands out the account with the most SPENDABLE room.

    CORRECTED 2026-10-24 after review. This test used to be called
    "...ranks_on_effective_not_account_remaining" and claimed "a clipped account
    must not win the ranking on its unclipped figure". That scenario cannot
    arise, so the claim was an overclaim:

    the ceiling room C is global, so every account is clipped by the SAME C, and
    `min(r, C)` is monotone in r. Sorting by `-r` therefore always picks an
    account of maximal spendable room too — the two keys differ only in WHICH of
    several equally-spendable accounts is named. Brute-forced over 905 eligible
    configurations: the spendable amount differed in 0 of them, the identity in
    60. So ranking on the effective figure is a clarity and determinism choice,
    NOT a correctness fix, and a mutant reverting the sort key survives this
    suite legitimately.

    What is worth pinning, and is pinned below: the account handed out really
    does have maximal spendable room, and ties resolve deterministically by name
    rather than by whatever order the config happened to list.
    """
    with tempfile.TemporaryDirectory() as d:
        cfg = ah.load_config(
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
        picked, _ = ah.select_account(cfg, [], strategy="most-remaining")
        assert picked is not None and picked.profile == "big"

        # With only $10 of ceiling room left both clip to $10, so the pick is a
        # tie on spendable room and the name breaks it deterministically.
        tight = ah.load_config(
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
        picked, _ = ah.select_account(tight, [], strategy="most-remaining")
        assert picked is not None
        assert picked.effective_remaining_usd == 10.0
        assert picked.profile == "big", "ties break on name, deterministically"


def test_ceiling_remaining_never_negative() -> None:
    """An already-recorded overshoot reads as zero room, not negative room."""
    with tempfile.TemporaryDirectory() as d:
        cfg = ah.load_config(_cfg(Path(d), global_ceiling_usd=10.0))
        assert ah.ceiling_remaining(cfg, _entries(("acct-a", 25.0))) == 0.0


def test_absent_ceiling_means_unlimited_total() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = ah.load_config(_cfg(Path(d), global_ceiling_usd=None))
        assert cfg.global_ceiling_usd is None
        assert ah.ceiling_blocked(cfg, _entries(("acct-a", 29.0))) == ""


# --------------------------------------------------------------------------- #
# Recording spend                                                             #
# --------------------------------------------------------------------------- #


def test_record_appends_and_accumulates() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = ah.load_config(_cfg(tmp))
        led = tmp / "spend.jsonl"
        ah.record_spend(led, cfg, "acct-a", 1.5, job_id="j1", now=1.0)
        ah.record_spend(led, cfg, "acct-a", 2.25, job_id="j2", now=2.0)
        entries = ah.read_entries(led)
        assert len(entries) == 2
        assert ah.spent_by_account(entries)["acct-a"] == 3.75
        assert [e.job_id for e in entries] == ["j1", "j2"]


def test_dry_run_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = ah.load_config(_cfg(tmp))
        led = tmp / "spend.jsonl"
        entry = ah.record_spend(led, cfg, "acct-a", 7.0, dry_run=True, now=1.0)
        assert entry.usd == 7.0
        assert not led.exists(), "dry run must not create the ledger"


def test_record_against_unenrolled_account_refused() -> None:
    """A typo must not silently open an uncapped shadow account."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = ah.load_config(_cfg(tmp))
        try:
            ah.record_spend(tmp / "spend.jsonl", cfg, "acct-typo", 1.0)
        except ah.ConfigError as exc:
            assert "not enrolled" in str(exc)
        else:
            raise AssertionError("expected ConfigError")


def test_negative_spend_refused() -> None:
    """Negative spend would manufacture headroom; corrections are out of scope
    for v1 and documented as such in the README."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg = ah.load_config(_cfg(tmp))
        try:
            ah.record_spend(tmp / "spend.jsonl", cfg, "acct-a", -5.0)
        except ah.ConfigError as exc:
            assert "negative" in str(exc)
        else:
            raise AssertionError("expected ConfigError")


# --------------------------------------------------------------------------- #
# CLI surface                                                                 #
# --------------------------------------------------------------------------- #


def test_cli_select_prints_bare_profile() -> None:
    with tempfile.TemporaryDirectory() as d:
        rc = ah.main(["--config", str(_cfg(Path(d))), "select"])
        assert rc == ah.EXIT_OK


def test_cli_select_exit_3_when_exhausted() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = _cfg(tmp)
        led = tmp / "spend.jsonl"
        cfg = ah.load_config(cfg_path)
        ah.record_spend(led, cfg, "acct-a", 30.0, now=1.0)
        ah.record_spend(led, cfg, "acct-b", 50.0, now=2.0)
        rc = ah.main(["--config", str(cfg_path), "select"])
        assert rc == ah.EXIT_NO_ACCOUNT, "exhaustion is exit 3, not a crash"


def test_cli_bad_config_is_exit_2() -> None:
    rc = ah.main(["--config", "definitely-missing.json", "status"])
    assert rc == ah.EXIT_USAGE


def test_cli_requires_a_config_path() -> None:
    saved = os.environ.pop("ACCOUNT_HOPPER_CONFIG", None)
    try:
        rc = ah.main(["status"])
        assert rc == ah.EXIT_USAGE
    finally:
        if saved is not None:
            os.environ["ACCOUNT_HOPPER_CONFIG"] = saved


def test_cli_status_json_shape() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rc = ah.main(["--config", str(_cfg(tmp)), "status", "--json"])
        assert rc == ah.EXIT_OK


def test_config_and_ledger_can_come_from_the_environment() -> None:
    """Both paths have env-var fallbacks; this exercises them end to end."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = _cfg(tmp)
        env_ledger = tmp / "env-ledger.jsonl"
        saved_cfg = os.environ.pop("ACCOUNT_HOPPER_CONFIG", None)
        saved_led = os.environ.pop("ACCOUNT_HOPPER_LEDGER", None)
        try:
            os.environ["ACCOUNT_HOPPER_CONFIG"] = str(cfg_path)
            os.environ["ACCOUNT_HOPPER_LEDGER"] = str(env_ledger)
            rc, out, _err = _run(["record", "--account", "acct-a", "--usd", "2.0"])
            assert rc == ah.EXIT_OK
            assert env_ledger.is_file(), "the ledger env var must be honoured"
            assert "recorded $2.00 on acct-a" in out
        finally:
            if saved_cfg is not None:
                os.environ["ACCOUNT_HOPPER_CONFIG"] = saved_cfg
            else:
                os.environ.pop("ACCOUNT_HOPPER_CONFIG", None)
            if saved_led is not None:
                os.environ["ACCOUNT_HOPPER_LEDGER"] = saved_led
            else:
                os.environ.pop("ACCOUNT_HOPPER_LEDGER", None)


def test_status_text_renders_clipping_and_the_refusal() -> None:
    """The text `status` view must show the spendable figure when the ceiling
    clips an account, and must print the REFUSING line when it is spent."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = _cfg(tmp, global_ceiling_usd=20.0)
        led = tmp / "spend.jsonl"
        cfg = ah.load_config(cfg_path)
        ah.record_spend(led, cfg, "acct-a", 20.0, now=1.0)
        rc, out, _err = _run(["--config", str(cfg_path), "status"])
        assert rc == ah.EXIT_OK
        assert "(spendable $0.00)" in out, "clipped room must show the effective figure"
        assert "global ceiling reached" in out
        assert "$20.00 of $20.00 ceiling" in out
        assert "REFUSING: global ceiling reached" in out


def test_status_text_without_a_ceiling_names_it() -> None:
    with tempfile.TemporaryDirectory() as d:
        rc, out, _err = _run(
            ["--config", str(_cfg(Path(d), global_ceiling_usd=None)), "status"]
        )
        assert rc == ah.EXIT_OK
        assert "(no global ceiling set)" in out
        assert "REFUSING" not in out
        assert "(spendable" not in out, "nothing is clipped when no ceiling exists"


def test_select_verbose_reports_spendable_and_names_the_clip() -> None:
    """--verbose leads with the spendable figure and says when the ceiling
    clipped it — the two numbers differ exactly when the ceiling binds."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rc, out, err = _run(["--config", str(_cfg(tmp)), "select", "--verbose"])
        assert rc == ah.EXIT_OK
        assert out.strip() == "acct-a"
        assert "spendable $30.00 (account remaining $30.00 of $30.00)" in err
        assert "clipped by" not in err

        rc, _out, err = _run(
            ["--config", str(_cfg(tmp, global_ceiling_usd=10.0)), "select", "--verbose"]
        )
        assert rc == ah.EXIT_OK
        assert "spendable $10.00" in err
        assert "clipped by the global ceiling" in err


def test_cli_record_dry_run_reports_without_writing() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = _cfg(tmp)
        led = tmp / "spend.jsonl"
        rc, out, _err = _run(
            [
                "--config",
                str(cfg_path),
                "--ledger",
                str(led),
                "record",
                "--account",
                "acct-a",
                "--usd",
                "7.0",
                "--dry-run",
            ]
        )
        assert rc == ah.EXIT_OK
        assert out.startswith("would record $7.00 on acct-a")
        assert "remaining $23.00 of $30.00" in out
        assert "$93.00 under the global ceiling" in out
        assert not led.exists(), "dry run must not create the ledger"


def test_cli_record_without_a_ceiling_omits_the_ceiling_note() -> None:
    """With no global ceiling the record tail must not mention one."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rc, out, _err = _run(
            [
                "--config",
                str(_cfg(tmp, global_ceiling_usd=None)),
                "--ledger",
                str(tmp / "spend.jsonl"),
                "record",
                "--account",
                "acct-a",
                "--usd",
                "7.0",
            ]
        )
        assert rc == ah.EXIT_OK
        assert out.startswith("recorded $7.00 on acct-a")
        assert "remaining $23.00 of $30.00" in out
        assert "global ceiling" not in out


# --------------------------------------------------------------------------- #
# hop — the rotation step                                                     #
# --------------------------------------------------------------------------- #


def test_hop_records_then_hands_over_the_next_account() -> None:
    """hop = record + select in one rotation step; stdout is the bare next
    profile so the launcher can compose it."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = _cfg(tmp)
        led = tmp / "spend.jsonl"
        rc, out, err = _run(
            [
                "--config",
                str(cfg_path),
                "--ledger",
                str(led),
                "hop",
                "--account",
                "acct-a",
                "--usd",
                "28.0",
                "--job-id",
                "j1",
            ]
        )
        assert rc == ah.EXIT_OK
        assert out.strip() == "acct-b", "$2 left is under the $5 headroom"
        entries = ah.read_entries(led)
        assert [(e.profile, e.usd, e.job_id) for e in entries] == [
            ("acct-a", 28.0, "j1")
        ]
        assert "recorded $28.00 on acct-a" in err
        assert "next: acct-b" in err


def test_hop_stays_on_an_account_that_still_has_headroom() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = _cfg(tmp)
        led = tmp / "spend.jsonl"
        cfg = ah.load_config(cfg_path)
        ah.record_spend(led, cfg, "acct-a", 10.0, now=1.0)
        rc, out, _err = _run(
            [
                "--config",
                str(cfg_path),
                "--ledger",
                str(led),
                "hop",
                "--account",
                "acct-a",
                "--usd",
                "5.0",
            ]
        )
        assert rc == ah.EXIT_OK
        assert out.strip() == "acct-a", "$15 left still clears the headroom"
        assert len(ah.read_entries(led)) == 2


def test_hop_exit_3_when_the_rotation_is_out_of_budget() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = _cfg(tmp)
        led = tmp / "spend.jsonl"
        cfg = ah.load_config(cfg_path)
        ah.record_spend(led, cfg, "acct-a", 30.0, now=1.0)
        ah.record_spend(led, cfg, "acct-b", 50.0, now=2.0)
        rc, out, err = _run(
            [
                "--config",
                str(cfg_path),
                "--ledger",
                str(led),
                "hop",
                "--account",
                "acct-b",
                "--usd",
                "0.0",
            ]
        )
        assert rc == ah.EXIT_NO_ACCOUNT, "a dry rotation is exit 3, not a crash"
        assert out == "", "no profile may be printed when nothing has headroom"
        assert "nothing left to hop to" in err


def test_hop_without_account_is_a_pure_first_hop() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = _cfg(tmp)
        led = tmp / "spend.jsonl"
        rc, out, err = _run(["--config", str(cfg_path), "--ledger", str(led), "hop"])
        assert rc == ah.EXIT_OK
        assert out.strip() == "acct-a"
        assert not led.exists(), "a pure first hop writes nothing"
        assert "recorded" not in err


def test_hop_pure_form_exit_3_when_exhausted() -> None:
    """The note-less exhaustion path: a pure hop (no --account) on a drained
    rotation exits 3 with no stdout and no hop note on stderr."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = _cfg(tmp)
        led = tmp / "spend.jsonl"
        cfg = ah.load_config(cfg_path)
        ah.record_spend(led, cfg, "acct-a", 30.0, now=1.0)
        ah.record_spend(led, cfg, "acct-b", 50.0, now=2.0)
        rc, out, err = _run(["--config", str(cfg_path), "--ledger", str(led), "hop"])
        assert rc == ah.EXIT_NO_ACCOUNT
        assert out == ""
        assert "no account available" in err
        assert "nothing left to hop to" not in err


def test_hop_refuses_an_unenrolled_account() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rc, _out, err = _run(
            [
                "--config",
                str(_cfg(tmp)),
                "--ledger",
                str(tmp / "spend.jsonl"),
                "hop",
                "--account",
                "acct-typo",
                "--usd",
                "1.0",
            ]
        )
        assert rc == ah.EXIT_USAGE
        assert "not enrolled" in err


def test_hop_requires_usd_with_account() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rc, _out, err = _run(
            [
                "--config",
                str(_cfg(tmp)),
                "--ledger",
                str(tmp / "spend.jsonl"),
                "hop",
                "--account",
                "acct-a",
            ]
        )
        assert rc == ah.EXIT_USAGE
        assert "required with --account" in err


def test_hop_refuses_usd_without_account() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rc, _out, err = _run(
            [
                "--config",
                str(_cfg(tmp)),
                "--ledger",
                str(tmp / "spend.jsonl"),
                "hop",
                "--usd",
                "5.0",
            ]
        )
        assert rc == ah.EXIT_USAGE
        assert "only makes sense together with --account" in err


def test_hop_dry_run_previews_the_real_hop_without_writing() -> None:
    """Under --dry-run the pending spend COUNTS in the preview: with $3 left and
    a $3 pending spend the real hop would drain the account, so the preview must
    hand over the next one — while writing nothing."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = _cfg(tmp, min_headroom_usd=0.0)
        led = tmp / "spend.jsonl"
        cfg = ah.load_config(cfg_path)
        ah.record_spend(led, cfg, "acct-a", 27.0, now=1.0)
        rc, out, err = _run(
            [
                "--config",
                str(cfg_path),
                "--ledger",
                str(led),
                "hop",
                "--account",
                "acct-a",
                "--usd",
                "3.0",
                "--dry-run",
            ]
        )
        assert rc == ah.EXIT_OK
        assert out.strip() == "acct-b", "the preview must count the pending spend"
        assert [e.usd for e in ah.read_entries(led)] == [27.0], "dry run wrote nothing"
        assert "would record $3.00 on acct-a" in err
        assert "[dry-run: nothing written]" in err


def test_hop_respects_the_global_ceiling() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfg_path = _cfg(tmp, global_ceiling_usd=20.0)
        led = tmp / "spend.jsonl"
        cfg = ah.load_config(cfg_path)
        ah.record_spend(led, cfg, "acct-a", 20.0, now=1.0)
        rc, out, err = _run(
            [
                "--config",
                str(cfg_path),
                "--ledger",
                str(led),
                "hop",
                "--account",
                "acct-a",
                "--usd",
                "0.0",
            ]
        )
        assert rc == ah.EXIT_NO_ACCOUNT
        assert out == ""
        assert "global ceiling" in err


# Every module account_hopper.py is allowed to import. This allowlist IS the
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
    tree = ast.parse((HERE / "account_hopper.py").read_text(encoding="utf-8"))
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
        f"account_hopper.py imports {sorted(unexpected)}, which is not in the "
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
MIN_TESTS = 61


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
