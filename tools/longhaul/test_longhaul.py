#!/usr/bin/env python
"""Tests for longhaul's budget, measure, watch and CLI parts. Run: python test_longhaul.py
(or pytest). The checkpoint part has its own suite and spec.

Everything runs in a temp dir: no real config, no real ledger, no network and no
provider CLI (the billing runner and the Modal backend are injected fakes).
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

import longhaul as lh  # noqa: E402
import longhaul_budget as lb  # noqa: E402
import longhaul_measure as lm  # noqa: E402
import longhaul_watch as lw  # noqa: E402

ACCTS = [
    {"profile": "acct-a", "cap_usd": 42.5, "funded": True},
    {"profile": "acct-b", "cap_usd": 42.5, "funded": True},
    {"profile": "acct-c", "cap_usd": 42.5, "funded": True, "closed": True},
]


def _write(tmp: Path, name: str, payload: object) -> Path:
    p = tmp / name
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _cfg_file(tmp: Path, **over: object) -> Path:
    base: dict[str, object] = {
        "pause_margin_usd": 3.0,
        "global_ceiling_usd": 126.0,
        "accounts": [dict(a) for a in ACCTS],
    }
    base.update(over)
    return _write(tmp, "longhaul.json", base)


def _cfg(**over: object) -> lb.Config:
    with tempfile.TemporaryDirectory() as t:
        return lb.load_config(_cfg_file(Path(t), **over))


def _entries(*pairs: tuple[str, float]) -> list[lb.Entry]:
    return [lb.Entry(ts=1.0, profile=p, usd=u, job_id="", note="") for p, u in pairs]


def _refused(fn: object, needle: str) -> None:
    try:
        fn()  # type: ignore[operator]
    except lb.ConfigError as exc:
        assert needle in str(exc), f"{needle!r} not in {exc}"
    else:
        raise AssertionError(f"expected ConfigError mentioning {needle!r}")


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = lh.main(argv)
    return rc, out.getvalue(), err.getvalue()


def _payload(metered: str, billed: str = "0E-8", credits: str = "-30.00000000") -> str:
    return json.dumps(
        {
            "metered_cost": metered,
            "billed_cost": billed,
            "adjustments": {"credits": credits},
        }
    )


def _runner(stdout: str, rc: int = 0, seen: list | None = None):
    def run(argv: list[str], timeout: float) -> tuple[int, str, str]:
        if seen is not None:
            seen.append((argv, timeout))
        return rc, stdout, "boom" if rc else ""

    return run


# --------------------------------------------------------------------------- #
# Config                                                                      #
# --------------------------------------------------------------------------- #


def test_loads_a_valid_config_with_lines_and_ceiling() -> None:
    cfg = _cfg()
    assert [a.profile for a in cfg.accounts] == ["acct-a", "acct-b", "acct-c"]
    assert cfg.accounts[0].line(cfg) == 39.5
    assert cfg.global_line() == 123.0
    assert cfg.accounts[2].closed and not cfg.accounts[0].closed
    assert cfg.spend_source == "ledger" and cfg.meter == "metered"


def test_an_account_hopper_config_loads_unchanged() -> None:
    """Migration: an account-hopper config is a valid longhaul config."""
    with tempfile.TemporaryDirectory() as t:
        p = _write(
            Path(t),
            "cfg.json",
            {
                "global_ceiling_usd": 240.0,
                "min_headroom_usd": 2.0,
                "accounts": [
                    {"profile": "x", "cap_usd": 30.0, "funded": True, "note": "n"}
                ],
            },
        )
        cfg = lb.load_config(p)
        assert cfg.pause_margin_usd == 0.0 and cfg.accounts[0].line(cfg) == 30.0


def test_funded_must_be_explicit() -> None:
    _refused(lambda: _cfg(accounts=[{"profile": "x", "cap_usd": 5.0}]), "funded")


def test_duplicate_profile_rejected() -> None:
    dup = [ACCTS[0], ACCTS[0]]
    _refused(lambda: _cfg(accounts=dup), "duplicate")


def test_bad_money_rejected() -> None:
    for cap, needle in (
        (float("nan"), "finite"),
        (0, "greater than 0"),
        (-1, "negative"),
        ("5", "number"),
        (True, "number"),
    ):
        acct = {"profile": "x", "cap_usd": cap, "funded": True}
        _refused(
            lambda acct=acct: _cfg(accounts=[acct], global_ceiling_usd=None), needle
        )


def test_margin_must_stay_below_the_cap_and_the_ceiling() -> None:
    _refused(lambda: _cfg(pause_margin_usd=50.0), "pause margin must be below")
    _refused(lambda: _cfg(global_ceiling_usd=3.0), "above pause_margin_usd")
    acct = {"profile": "x", "cap_usd": 5.0, "funded": True, "pause_margin_usd": 5.0}
    _refused(lambda: _cfg(accounts=[acct]), "pause margin must be below")


def test_closed_must_be_a_bool_and_options_validated() -> None:
    acct = {"profile": "x", "cap_usd": 5.0, "funded": True, "closed": "yes"}
    _refused(lambda: _cfg(accounts=[acct]), "closed")
    _refused(lambda: _cfg(spend_source="psychic"), "spend_source")
    _refused(lambda: _cfg(meter="gross"), "meter")
    acct = {"profile": "x", "cap_usd": 5.0, "funded": True, "meter": "gross"}
    _refused(lambda: _cfg(accounts=[acct]), "meter")


def test_config_shape_errors() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        _refused(lambda: lb.load_config(tmp / "absent.json"), "not found")
        (tmp / "bad.json").write_text("{nope", encoding="utf-8")
        _refused(lambda: lb.load_config(tmp / "bad.json"), "not valid JSON")
        _refused(lambda: lb.load_config(_write(tmp, "l.json", [1])), "JSON object")
    _refused(lambda: _cfg(accounts=[]), "non-empty list")
    _refused(lambda: _cfg(accounts=[3]), "must be an object")
    _refused(
        lambda: _cfg(accounts=[{"profile": " ", "cap_usd": 1, "funded": True}]),
        "profile",
    )


# --------------------------------------------------------------------------- #
# Lines, ceiling and the per-invocation check                                 #
# --------------------------------------------------------------------------- #


def test_line_is_cap_minus_margin_and_room_is_measured_to_it() -> None:
    cfg = _cfg(global_ceiling_usd=None)
    row = lb.account_status(cfg, _entries(("acct-a", 30.0)))[0]
    assert row.line_usd == 39.5 and row.line_room_usd == 9.5
    assert row.effective_remaining_usd == 9.5 and row.eligible


def test_ceiling_clips_the_spendable_room_not_just_the_end() -> None:
    """The account-hopper regression, kept: $60 ceiling, $58 spent in total, an
    account with $8 of its own room has only $2 really available."""
    cfg = _cfg(
        pause_margin_usd=0.0,
        global_ceiling_usd=60.0,
        accounts=[
            {"profile": "a", "cap_usd": 50.0, "funded": True},
            {"profile": "b", "cap_usd": 30.0, "funded": True},
        ],
    )
    rows = lb.account_status(cfg, _entries(("a", 36.0), ("b", 22.0)))
    b = next(r for r in rows if r.profile == "b")
    assert b.line_room_usd == 8.0 and b.effective_remaining_usd == 2.0
    _st, why = lb.check_profile(cfg, _entries(("a", 36.0), ("b", 22.0)), "b", 5.0)
    assert "cannot fund a $5.00 job" in why


def test_check_refuses_each_way_with_a_reason() -> None:
    cfg = _cfg()
    entries = _entries(("acct-a", 39.5))
    assert "at its line" in lb.check_profile(cfg, entries, "acct-a")[1]
    assert "closed" in lb.check_profile(cfg, entries, "acct-c")[1]
    _status, why = lb.check_profile(cfg, entries, "acct-b", projected_usd=40.0)
    assert "cannot fund" in why
    assert lb.check_profile(cfg, entries, "acct-b", projected_usd=10.0)[1] == ""
    unfunded = _cfg(accounts=[{"profile": "u", "cap_usd": 5.0, "funded": False}])
    assert "not marked funded" in lb.check_profile(unfunded, [], "u")[1]
    _refused(lambda: lb.check_profile(cfg, entries, "nobody"), "not enrolled")


def test_global_line_refuses_every_account() -> None:
    cfg = _cfg()
    entries = _entries(("acct-a", 39.0), ("acct-b", 39.0), ("acct-c", 45.0))
    for profile in ("acct-a", "acct-b"):
        assert "global line reached" in lb.check_profile(cfg, entries, profile)[1]


def test_min_headroom_names_the_binding_limit() -> None:
    cfg = _cfg(min_headroom_usd=5.0, global_ceiling_usd=None)
    assert (
        "bound by account line"
        in lb.check_profile(cfg, _entries(("acct-a", 36.0)), "acct-a")[1]
    )
    cfg = _cfg(min_headroom_usd=5.0)
    entries = _entries(("acct-a", 10.0), ("acct-b", 39.0), ("acct-c", 72.0))
    assert "bound by global line" in lb.check_profile(cfg, entries, "acct-a")[1]


def test_measured_spend_replaces_recorded_per_account_only() -> None:
    cfg = _cfg()
    spent = lb.spent_by_account(
        cfg, _entries(("acct-a", 1.0), ("acct-b", 2.0)), {"acct-a": 38.31}
    )
    assert spent == {"acct-a": 38.31, "acct-b": 2.0, "acct-c": 0.0}
    rows = lb.account_status(cfg, [], {"acct-a": 38.31})
    assert rows[0].measured and not rows[1].measured


def test_pause_targets_fire_at_the_line_and_at_the_global_line() -> None:
    cfg = _cfg()
    assert lb.pause_targets(cfg, _entries(("acct-a", 39.49))) == {}
    hit = lb.pause_targets(cfg, _entries(("acct-a", 39.5)))
    assert list(hit) == ["acct-a"] and "line $39.50" in hit["acct-a"]
    allhit = lb.pause_targets(
        cfg, _entries(("acct-a", 38.0), ("acct-b", 38.0), ("acct-c", 47.0))
    )
    assert sorted(allhit) == ["acct-a", "acct-b", "acct-c"]
    assert "global line $123.00" in allhit["acct-b"]


def test_no_selection_and_no_hop_exist() -> None:
    """Scope guard: the next account is always the user's explicit choice."""
    for mod in (lb, lw, lh):
        for name in ("select_account", "hop", "pick_account", "rotate"):
            assert not hasattr(mod, name), f"{mod.__name__}.{name} must not exist"
    parser_cmds = lh.build_parser()._subparsers._group_actions[0].choices  # type: ignore[union-attr]
    assert "select" not in parser_cmds and "hop" not in parser_cmds


# --------------------------------------------------------------------------- #
# Ledger                                                                      #
# --------------------------------------------------------------------------- #


def test_record_appends_dry_run_writes_nothing_and_unknown_is_refused() -> None:
    cfg = _cfg()
    with tempfile.TemporaryDirectory() as t:
        led = Path(t) / "spend.jsonl"
        lb.record_spend(led, cfg, "acct-a", 1.234, job_id="j1", now=5.0)
        lb.record_spend(led, cfg, "acct-a", 2.0, dry_run=True)
        entries = lb.read_entries(led)
        assert (
            len(entries) == 1 and entries[0].usd == 1.23 and entries[0].job_id == "j1"
        )
        _refused(lambda: lb.record_spend(led, cfg, "acct-x", 1.0), "not enrolled")
        _refused(lambda: lb.record_spend(led, cfg, "acct-a", -1.0), "negative")


def test_ledger_corruption_is_fatal_and_blanks_are_skipped() -> None:
    with tempfile.TemporaryDirectory() as t:
        led = Path(t) / "spend.jsonl"
        assert lb.read_entries(led) == []
        led.write_text('{"profile": "a", "usd": 1}\n\n', encoding="utf-8")
        assert len(lb.read_entries(led)) == 1
        for bad, needle in (
            ("{x", "corrupt"),
            ("[1]", "object"),
            ('{"usd": 1}', "profile"),
        ):
            led.write_text(bad + "\n", encoding="utf-8")
            _refused(lambda: lb.read_entries(led), needle)


# --------------------------------------------------------------------------- #
# Measure                                                                     #
# --------------------------------------------------------------------------- #


def test_parse_summary_reads_decimal_strings_and_credit_magnitude() -> None:
    r = lm.parse_summary(
        json.loads(_payload("38.08001548", "8.08", "-30.00000000")),
        "p",
        "this month",
        1.0,
    )
    assert (r.metered_usd, r.billed_usd, r.credits_applied_usd) == (38.08, 8.08, 30.0)
    assert (
        lm.parse_summary(
            json.loads(_payload("0E-8")), "p", "this month", 1.0
        ).metered_usd
        == 0.0
    )
    assert r.by_meter("billed") == 8.08
    try:
        r.by_meter("gross")
    except lm.SpendError:
        pass
    else:
        raise AssertionError("unknown meter must raise")


def test_fetch_spend_argv_is_exact_and_tolerates_noise() -> None:
    seen: list = []
    noisy = "DeprecationWarning: blah\n" + _payload("19.36") + "\ntrailing"
    r = lm.fetch_spend("acct-b", runner=_runner(noisy, seen=seen), now=7.0)
    assert r.metered_usd == 19.36 and r.fetched_at == 7.0
    argv = seen[0][0]
    assert argv == [
        "modal",
        "billing",
        "summary",
        "--json",
        "--profile",
        "acct-b",
        "--for",
        "this month",
    ]


def test_fetch_spend_failures_raise_never_zero() -> None:
    for runner, needle in (
        (_runner("", rc=1), "billing query failed"),
        (_runner("no json here"), "no JSON object"),
        (_runner("{bad json}"), "not valid JSON"),
        (_runner(json.dumps({"billed_cost": "1"})), "metered_cost: missing"),
    ):
        try:
            lm.fetch_spend("acct-a", runner=runner)
        except lm.SpendError as exc:
            assert needle in str(exc), f"{needle!r} not in {exc}"
        else:
            raise AssertionError(f"expected SpendError: {needle}")

    def timeout(_argv: list[str], _t: float):
        raise lm.subprocess.TimeoutExpired("modal", 1)

    def missing(_argv: list[str], _t: float):
        raise FileNotFoundError

    for runner, needle in ((timeout, "timed out"), (missing, "not found on PATH")):
        try:
            lm.fetch_spend("acct-a", runner=runner)
        except lm.SpendError as exc:
            assert needle in str(exc)
        else:
            raise AssertionError(needle)


def test_profile_names_are_validated_and_tokens_stripped() -> None:
    for bad in ("", "-x", "a b", "a/b", None, "x" * 65):
        try:
            lm.validate_profile(bad)
        except lm.SpendError:
            pass
        else:
            raise AssertionError(f"accepted {bad!r}")
    env = lm.child_env(
        {
            "MODAL_TOKEN_ID": "a",
            "MODAL_TOKEN_SECRET": "b",
            "MODAL_PROFILE": "c",
            "PATH": "p",
        }
    )
    assert env == {"PATH": "p"}
    scoped = lh.scoped_env("acct-a", {"MODAL_TOKEN_ID": "a", "PATH": "p"})
    assert scoped == {"PATH": "p", "MODAL_PROFILE": "acct-a"}


def test_cycle_keys_name_the_month() -> None:
    jan = 1767225600.0 + 86400 * 10  # 2026-01-11 UTC
    assert lm.cycle_key("this month", jan) == "2026-01"
    assert lm.cycle_key("last month", jan) == "2025-12"
    assert lm.cycle_key("2026-10") == "2026-10"
    for bad in ("next month", "2026-13", "26-10"):
        try:
            lm.cycle_key(bad)
        except lm.SpendError:
            pass
        else:
            raise AssertionError(bad)


def test_high_water_never_goes_down_and_resets_per_month() -> None:
    """Measured 2026-10-30: one account read 38.31, then 38.08."""
    with tempfile.TemporaryDirectory() as t:
        hw = Path(t) / "highwater.json"
        assert lm.raise_highwater(hw, "2026-10", {"a/metered": 38.31}) == {
            "a/metered": 38.31
        }
        assert lm.raise_highwater(hw, "2026-10", {"a/metered": 38.08}) == {
            "a/metered": 38.31
        }
        assert lm.raise_highwater(hw, "2026-11", {"a/metered": 0.5}) == {
            "a/metered": 0.5
        }
        assert lm.read_highwater(hw)["2026-10"]["a/metered"] == 38.31


def test_corrupt_high_water_store_is_refused() -> None:
    with tempfile.TemporaryDirectory() as t:
        hw = Path(t) / "highwater.json"
        for bad in ("{x", "[1]", '{"2026-10": 3}', '{"2026-10": {"a/metered": -1}}'):
            hw.write_text(bad, encoding="utf-8")
            try:
                lm.read_highwater(hw)
            except lm.SpendError:
                pass
            else:
                raise AssertionError(bad)


def test_cache_reuses_within_ttl_and_drops_damage() -> None:
    with tempfile.TemporaryDirectory() as t:
        cache = Path(t) / "cache.json"
        seen: list = []
        run = _runner(_payload("5.00"), seen=seen)
        lm.fetch_spend_cached("a", cache, ttl=100, now=1000.0, runner=run)
        lm.fetch_spend_cached("a", cache, ttl=100, now=1050.0, runner=run)
        assert len(seen) == 1, "second read within the TTL comes from the cache"
        lm.fetch_spend_cached("a", cache, ttl=100, now=1200.0, runner=run)
        assert len(seen) == 2
        cache.write_text("{damaged", encoding="utf-8")
        assert (
            lm.fetch_spend_cached(
                "a", cache, ttl=100, now=1201.0, runner=run
            ).metered_usd
            == 5.0
        )


def test_measure_accounts_returns_high_water_figures() -> None:
    with tempfile.TemporaryDirectory() as t:
        hw = Path(t) / "hw.json"
        month = lm.cycle_key("this month")
        lm.raise_highwater(hw, month, {"a/metered": 38.31})
        marks, readings = lm.measure_accounts(
            [("a", "metered")], "this month", hw, runner=_runner(_payload("38.08"))
        )
        assert readings["a"].metered_usd == 38.08 and marks == {"a": 38.31}


# --------------------------------------------------------------------------- #
# Watch                                                                       #
# --------------------------------------------------------------------------- #


class FakeCalls:
    def __init__(self, states: dict[str, lw.CallState]) -> None:
        self.states = dict(states)
        self.cancelled: list[str] = []
        self.spawned: list[dict] = []

    def state(self, call_id: str) -> lw.CallState:
        return self.states.get(call_id, lw.CallState(lw.RUNNING))

    def cancel(self, call_id: str) -> None:
        self.cancelled.append(call_id)

    def spawn(self, recipe: dict) -> str:
        self.spawned.append(recipe)
        return f"fc-new-{len(self.spawned)}"


RECIPE = {"app": "app", "function": "fn", "args": [1], "options": {"cpu": 2.0}}


def _row(cid: str, label: str = "L", profile: str = "acct-a", **kw: object) -> dict:
    return {"group": "G", "label": label, "call_id": cid, "profile": profile, **kw}


def test_running_calls_are_left_alone_even_if_they_look_failed() -> None:
    """Modal's own restart after a preemption reads as running here."""
    plan = lw.plan_tick(
        [_row("c1", spawn=RECIPE, max_respawn=3)],
        {"c1": lw.CallState(lw.RUNNING)},
        "acct-a",
        "",
    )
    assert plan.actions == () and plan.pending == 1


def test_finished_errors_respawn_only_when_opted_in_and_within_max() -> None:
    err = {"c1": lw.CallState(lw.ERROR, "Boom")}
    assert (
        lw.plan_tick([_row("c1", spawn=RECIPE)], err, "acct-a", "").actions[0].kind
        == "give-up"
    )
    assert (
        lw.plan_tick([_row("c1", max_respawn=2)], err, "acct-a", "").actions[0].kind
        == "give-up"
    )
    plan = lw.plan_tick([_row("c1", spawn=RECIPE, max_respawn=2)], err, "acct-a", "")
    assert plan.actions[0].kind == "respawn" and plan.pending == 1
    rows = [_row(c, spawn=RECIPE, max_respawn=2) for c in ("c0", "cx", "c1")]
    assert lw.plan_tick(rows, err, "acct-a", "").actions[0].kind == "give-up"


def test_a_paused_profile_pauses_running_and_respawns_nothing() -> None:
    rows = [_row("c1"), _row("c2", label="M", spawn=RECIPE, max_respawn=3)]
    states = {"c1": lw.CallState(lw.RUNNING), "c2": lw.CallState(lw.ERROR, "Boom")}
    plan = lw.plan_tick(rows, states, "acct-a", "spend $39.50 >= line $39.50")
    kinds = sorted(a.kind for a in plan.actions)
    assert kinds == ["give-up", "pause"] and plan.pending == 0


def test_done_stopped_and_other_profiles_are_ignored() -> None:
    rows = [
        _row("c1"),
        _row("c2", label="M"),
        {
            "group": "G",
            "label": "M",
            "profile": "acct-a",
            "stopped": True,
            "last_call": "c2",
        },
        _row("c3", label="N", profile="acct-b"),
    ]
    plan = lw.plan_tick(rows, {"c1": lw.CallState(lw.DONE)}, "acct-a", "x")
    assert plan.actions == () and plan.pending == 0


def test_run_tick_acts_and_records_on_the_same_profile() -> None:
    with tempfile.TemporaryDirectory() as t:
        calls = Path(t) / "calls.jsonl"
        lw.append_call(calls, _row("c1", spawn=RECIPE, max_respawn=1))
        lw.append_call(calls, _row("c2", label="M"))
        fake = FakeCalls(
            {"c1": lw.CallState(lw.ERROR, "Preempted"), "c2": lw.CallState(lw.RUNNING)}
        )
        log: list[str] = []
        plan = lw.run_tick(calls, "acct-a", "", fake, say=log.append)
        assert fake.spawned == [RECIPE] and fake.cancelled == [] and plan.pending == 2
        rows = lw.read_calls(calls)
        assert rows[-1]["replaces"] == "c1" and rows[-1]["profile"] == "acct-a"
        assert any("RESPAWN acct-a" in line for line in log)
        fake.states["fc-new-1"] = lw.CallState(lw.RUNNING)
        plan = lw.run_tick(
            calls,
            "acct-a",
            "total $123.00 >= global line $123.00",
            fake,
            say=log.append,
        )
        assert sorted(fake.cancelled) == ["c2", "fc-new-1"] and plan.pending == 0
        plan = lw.run_tick(calls, "acct-a", "", fake, say=log.append)
        assert plan.actions == () and plan.pending == 0, "paused chains stay stopped"


class _Status:
    def __init__(self, name: str) -> None:
        self.name = name


class _Info:
    def __init__(self, status: str) -> None:
        self.status = _Status(status)


def _fake_modal(get_exc: BaseException | None, graph: object):
    """A stand-in for the modal module: one FunctionCall with scripted outcomes."""

    class FakeCall:
        def get(self, timeout: float = 0) -> None:
            if get_exc is not None:
                raise get_exc

        def get_call_graph(self) -> list:
            if isinstance(graph, BaseException):
                raise graph
            return [_Info(s) for s in graph]  # type: ignore[union-attr]

    class FunctionCall:
        @staticmethod
        def from_id(_cid: str) -> FakeCall:
            return FakeCall()

    return type("FakeModal", (), {"FunctionCall": FunctionCall})


def test_modal_state_needs_two_signals_before_calling_a_call_failed() -> None:
    """A network blip on get() must never read as a failed job (it would respawn)."""
    cases = [
        (None, [], lw.DONE),
        (TimeoutError(), ["FAILURE"], lw.RUNNING),  # Modal restarting after preemption
        (RuntimeError("job raised"), ["FAILURE"], lw.ERROR),
        (RuntimeError("job raised"), ["TIMEOUT"], lw.ERROR),
        (ConnectionError("dns"), OSError("dns"), lw.RUNNING),  # unknown is running
        (ConnectionError("dns"), ["PENDING"], lw.RUNNING),
        (ConnectionError("blip"), [], lw.RUNNING),
        (KeyError("output expired"), ["SUCCESS"], lw.DONE),
    ]
    for get_exc, graph, want in cases:
        got = lw.ModalCalls(_fake_modal(get_exc, graph)).state("fc-1")
        assert got.kind == want, f"{get_exc!r} + {graph!r}: {got} (want {want})"


def test_cli_watch_survives_a_failed_measurement_on_stored_marks() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        cfg = str(_cfg_file(tmp, spend_source="measured"))
        calls = tmp / "calls.jsonl"
        lw.append_call(calls, _row("c1"))
        month = lm.cycle_key("this month")
        lm.raise_highwater(tmp / "highwater.json", month, {"acct-a/metered": 40.0})

        def failing(*_a: object, **_k: object):
            raise lm.SpendError("dns down")

        real = lm.measure_accounts
        lm.measure_accounts = failing  # type: ignore[assignment]
        try:
            ns = lh.build_parser().parse_args(
                [
                    "--config",
                    cfg,
                    "watch",
                    "--profile",
                    "acct-a",
                    "--calls",
                    str(calls),
                    "--once",
                ]
            )
            fake = FakeCalls({"c1": lw.CallState(lw.RUNNING)})
            ns.backend = fake
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = lh._cmd_watch(ns)
            assert rc == 3 and fake.cancelled == ["c1"], (
                "stored $40 >= line $39.50 pauses"
            )
            assert "MEASURE-FAILED" in out.getvalue()
            (tmp / "highwater.json").unlink()
            lw.append_call(calls, _row("c2", label="M"))
            ns.backend = FakeCalls({"c2": lw.CallState(lw.RUNNING)})
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    lh._cmd_watch(ns)
            except lb.ConfigError as exc:
                assert "no high-water marks" in str(exc), (
                    "a blind first tick fails closed"
                )
            else:
                raise AssertionError("expected ConfigError with no stored marks")
        finally:
            lm.measure_accounts = real  # type: ignore[assignment]


def test_call_ledger_corruption_is_fatal() -> None:
    with tempfile.TemporaryDirectory() as t:
        calls = Path(t) / "calls.jsonl"
        assert lw.read_calls(calls) == []
        for bad in ("{x", "[1]"):
            calls.write_text(bad + "\n", encoding="utf-8")
            try:
                lw.read_calls(calls)
            except ValueError:
                pass
            else:
                raise AssertionError(bad)


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def test_cli_check_status_record_and_exit_codes() -> None:
    with tempfile.TemporaryDirectory() as t:
        cfg = str(_cfg_file(Path(t)))
        assert _run(["--config", cfg, "check", "--profile", "acct-a"])[:2] == (
            0,
            "acct-a\n",
        )
        assert (
            _run(["--config", cfg, "record", "--profile", "acct-a", "--usd", "39.5"])[0]
            == 0
        )
        rc, out, err = _run(["--config", cfg, "check", "--profile", "acct-a"])
        assert rc == 3 and out == "" and "at its line" in err and "yourself" in err
        rc, out, _ = _run(["--config", cfg, "status"])
        assert rc == 0 and "PAUSE acct-a" in out and "global line $123.00" in out
        rc, out, _ = _run(["--config", cfg, "status", "--json"])
        blob = json.loads(out)
        assert blob["pause"]["acct-a"].startswith("spend $39.50")
        assert _run(["--config", cfg, "check", "--profile", "nobody"])[0] == 2
        assert _run(["check", "--profile", "acct-a"])[0] == 2, "no config is exit 2"


def test_cli_config_from_environment() -> None:
    with tempfile.TemporaryDirectory() as t:
        cfg = str(_cfg_file(Path(t)))
        old = os.environ.get("LONGHAUL_CONFIG")
        os.environ["LONGHAUL_CONFIG"] = cfg
        try:
            assert _run(["check", "--profile", "acct-b"])[0] == 0
        finally:
            if old is None:
                os.environ.pop("LONGHAUL_CONFIG", None)
            else:
                os.environ["LONGHAUL_CONFIG"] = old


def test_cli_measured_source_uses_high_water_marks() -> None:
    with tempfile.TemporaryDirectory() as t:
        cfg = str(_cfg_file(Path(t), spend_source="measured"))
        real = lm.measure_accounts
        lm.measure_accounts = lambda pairs, *a, **k: ({p: 39.6 for p, _m in pairs}, {})  # type: ignore[assignment]
        try:
            rc, _out, err = _run(["--config", cfg, "check", "--profile", "acct-b"])
        finally:
            lm.measure_accounts = real  # type: ignore[assignment]
        assert rc == 3 and "at its line" in err
        assert (
            _run(["--config", cfg, "--no-measure", "check", "--profile", "acct-b"])[0]
            == 0
        )


def test_cli_run_scopes_the_child_to_the_chosen_profile() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        cfg = str(_cfg_file(tmp))
        out = tmp / "env.json"
        code = (
            "import json, os, sys; json.dump({k: os.environ.get(k) for k in "
            "('MODAL_PROFILE', 'MODAL_TOKEN_ID')}, open(sys.argv[1], 'w'))"
        )
        os.environ["MODAL_TOKEN_ID"] = "must-not-leak"
        try:
            argv = [
                "--config",
                cfg,
                "run",
                "--profile",
                "acct-b",
                "--",
                sys.executable,
                "-c",
                code,
                str(out),
            ]
            rc, _o, _e = _run(argv)
        finally:
            os.environ.pop("MODAL_TOKEN_ID", None)
        assert rc == 0
        assert json.loads(out.read_text(encoding="utf-8")) == {
            "MODAL_PROFILE": "acct-b",
            "MODAL_TOKEN_ID": None,
        }
        marker = tmp / "ran"
        argv = [
            "--config",
            cfg,
            "run",
            "--profile",
            "acct-c",
            "--",
            sys.executable,
            "-c",
            f"open({str(marker)!r}, 'w')",
        ]
        assert _run(argv)[0] == 3 and not marker.exists(), "a refused run never starts"


def test_cli_watch_exits_0_when_done_and_3_when_paused() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        cfg = str(_cfg_file(tmp))
        calls = tmp / "calls.jsonl"
        lw.append_call(calls, _row("c1"))
        ns = lh.build_parser().parse_args(
            [
                "--config",
                cfg,
                "watch",
                "--profile",
                "acct-a",
                "--calls",
                str(calls),
                "--period",
                "0",
            ]
        )
        ns.backend = FakeCalls({"c1": lw.CallState(lw.DONE)})
        with contextlib.redirect_stdout(io.StringIO()):
            assert lh._cmd_watch(ns) == 0
        lw.append_call(calls, _row("c2", label="M"))
        lb.record_spend(tmp / "spend.jsonl", lb.load_config(cfg), "acct-a", 40.0)
        fake = FakeCalls({"c1": lw.CallState(lw.DONE), "c2": lw.CallState(lw.RUNNING)})
        ns.backend = fake
        with contextlib.redirect_stdout(io.StringIO()):
            assert lh._cmd_watch(ns) == 3
        assert fake.cancelled == ["c2"]


def test_cli_checkpoint_mirror_verify_resume() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        work, durable = tmp / "w", tmp / "d"
        work.mkdir()
        (work / "a.txt").write_text("alpha", encoding="utf-8")
        assert (
            _run(
                ["checkpoint", "mirror", "--work", str(work), "--durable", str(durable)]
            )[0]
            == 0
        )
        rc, out, _ = _run(["checkpoint", "verify", "--durable", str(durable)])
        assert rc == 0 and out.startswith("ok: generation 1")
        rc, out, _ = _run(
            [
                "checkpoint",
                "resume",
                "--work",
                str(tmp / "w2"),
                "--durable",
                str(durable),
            ]
        )
        assert rc == 0 and (tmp / "w2" / "a.txt").read_text(encoding="utf-8") == "alpha"
        assert _run(["checkpoint", "verify", "--durable", str(tmp / "none")])[0] == 3
        assert _run(["checkpoint", "mirror", "--durable", str(durable)])[0] == 2


# --------------------------------------------------------------------------- #
# Structure: what each module may import                                      #
# --------------------------------------------------------------------------- #

BANNED_EVERYWHERE = {
    "socket",
    "urllib",
    "http",
    "requests",
    "httpx",
    "importlib",
    "boto3",
}
ALLOWED = {
    "longhaul_budget.py": {
        "__future__",
        "dataclasses",
        "json",
        "math",
        "pathlib",
        "time",
    },
    "longhaul_measure.py": {
        "__future__",
        "dataclasses",
        "decimal",
        "json",
        "os",
        "pathlib",
        "re",
        "subprocess",
        "time",
    },
    "longhaul_watch.py": {
        "__future__",
        "dataclasses",
        "json",
        "pathlib",
        "time",
        "modal",
    },
}


def _imports(name: str) -> tuple[set[str], set[str]]:
    """(all imports, imports at module level)."""
    tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module.split(".")[0] if node.module else ".")
    top: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            top.add(node.module.split(".")[0] if node.module else ".")
    return found, top


def test_imports_match_the_allowlists() -> None:
    for name, allowed in ALLOWED.items():
        found, _top = _imports(name)
        assert found <= allowed, f"{name}: unexpected imports {sorted(found - allowed)}"
        assert not found & BANNED_EVERYWHERE, name


def test_only_measure_and_the_cli_start_processes_and_modal_loads_lazily() -> None:
    for name in ("longhaul_budget.py", "longhaul_watch.py", "longhaul_checkpoint.py"):
        assert "subprocess" not in _imports(name)[0], name
    _found, top = _imports("longhaul_watch.py")
    assert "modal" not in top, (
        "modal is imported inside ModalCalls, never at module level"
    )
    for name in (
        "longhaul.py",
        "longhaul_budget.py",
        "longhaul_measure.py",
        "longhaul_checkpoint.py",
    ):
        assert "modal" not in _imports(name)[0], name


# Floor, not just "no failures": a discovery break would otherwise report PASS on
# 0/0 and gate nothing. Raise it when tests are added.
MIN_TESTS = 43


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
        except Exception as exc:  # noqa: BLE001 - the runner reports everything
            failures.append(name)
            print(f"  BAD  {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"  OK   {name}")
    print(
        f"\nRESULT: {'PASS' if not failures else 'FAIL'}  "
        f"({len(tests) - len(failures)}/{len(tests)} passed)"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
