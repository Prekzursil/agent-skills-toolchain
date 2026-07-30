"""Unit tests for e2e/watch.py — the merged live fan-out monitor.

Neither pre-merge copy of watch.py had ANY test, so every case here is new. The suite is
scoped to the behaviours the merge actually reconciled, because those are the ones a future
edit is most likely to silently revert:

  * the receipt predicate — lifecycle TERMINATED is NOT success (a TERMINATED/FAILED run must
    exit 1, and so must SUCCESS with a short artifact count);
  * the three-tier landed filter (exact expected set > prefix > every .md) and its fail-closed
    behaviour on a `databricks fs ls` error;
  * the rich render extras (percent, rate/min, the `<- +N` delta, `eta pending first unit`,
    the terminal `[landed]` roster);
  * BOTH CLI call forms — flags and the positional form the governed-run orchestrator template
    invokes with six arguments.

No live Databricks and no real clock: `watch.sh` is monkeypatched and `watch.time` is replaced
by a deterministic 60s-per-tick stub, so the poll loop runs instantly and ETA/rate are exact.
"""

import io
import json

from e2e import watch as W

LS = "dbfs:/tmp/r/{}"


def _ls(*names):
    return "\n".join(LS.format(n) for n in names) + "\n"


def _payload(life, result="", msg=""):
    return json.dumps(
        {
            "state": {
                "life_cycle_state": life,
                "result_state": result,
                "state_message": msg,
            }
        }
    )


def _fake_sh(get_run_out="", ls_out="", get_run_rc=0, ls_rc=0):
    calls = []

    def sh(argv):
        calls.append(argv)
        if argv[1] == "jobs":
            return get_run_rc, get_run_out, ""
        return ls_rc, ls_out, ""

    sh.calls = calls
    return sh


class _Clock:
    """Deterministic stand-in for the `time` module: every read advances 60s."""

    def __init__(self, step=60.0):
        self.step = step
        self.t = -step
        self.slept = []

    def time(self):
        self.t += self.step
        return self.t

    def sleep(self, seconds):
        self.slept.append(seconds)


def _drive(monkeypatch, states, landings, **kw):
    """Run watch() against scripted (life, result, msg) and (landed, names) sequences."""
    s_iter, l_iter = iter(states), iter(landings)
    clock = _Clock()
    monkeypatch.setattr(W, "run_state", lambda *a, **k: next(s_iter))
    monkeypatch.setattr(W, "count_landed", lambda *a, **k: next(l_iter))
    monkeypatch.setattr(W, "time", clock)
    buf = io.StringIO()
    rc = W.watch("42", "dbfs:/tmp/r", out=buf, interval=7, **kw)
    return rc, buf.getvalue(), clock


# --------------------------------------------------------------------- helpers


def test_fmt_minutes_and_hours():
    assert W.fmt(0) == "0m00s"
    assert W.fmt(61) == "1m01s"
    assert W.fmt(3661) == "1h01m01s"


def test_sh_runs_a_real_process_and_returns_the_triple():
    import sys

    rc, out, err = W.sh([sys.executable, "-c", "print('hi')"])
    assert rc == 0
    assert out.strip() == "hi"
    assert err == ""


def test_pre_merge_aliases_still_resolve():
    assert W._run is W.sh
    assert W._fmt is W.fmt
    assert W._state is W.run_state


def test_profile_default_comes_from_the_rail_contract():
    from harness.contract import RAIL

    assert W.PROFILE_DEFAULT == RAIL["profile"]


# ------------------------------------------------------------------ run_state


def test_run_state_reports_result_state_and_strips_the_message(monkeypatch):
    monkeypatch.setattr(W, "sh", _fake_sh(_payload("TERMINATED", "FAILED", "  boom  ")))
    assert W.run_state("42") == ("TERMINATED", "FAILED", "boom")


def test_run_state_missing_result_state_is_empty_not_none(monkeypatch):
    monkeypatch.setattr(W, "sh", _fake_sh(json.dumps({"state": {}})))
    assert W.run_state("42") == ("?", "", "")


def test_run_state_fails_closed_on_cli_error(monkeypatch):
    monkeypatch.setattr(W, "sh", _fake_sh(_payload("RUNNING"), get_run_rc=1))
    assert W.run_state("42") == ("?", "", "")


def test_run_state_fails_closed_on_unparseable_payload(monkeypatch):
    monkeypatch.setattr(W, "sh", _fake_sh("not json at all"))
    assert W.run_state("42") == ("?", "", "")


def test_run_state_passes_the_profile_through(monkeypatch):
    fake = _fake_sh(_payload("RUNNING"))
    monkeypatch.setattr(W, "sh", fake)
    W.run_state(99, profile="other-profile")
    assert fake.calls[0] == [
        "databricks",
        "jobs",
        "get-run",
        "99",
        "--profile",
        "other-profile",
    ]


# --------------------------------------------------------------- count_landed


def test_prefix_filter_ignores_a_stale_sibling_artifact(monkeypatch):
    # The "2/1 landed" bug: a previous batch left other-unit.md in the shared result dir.
    monkeypatch.setattr(W, "sh", _fake_sh(ls_out=_ls("other-unit.md", "cov-1.md")))
    assert W.count_landed("dbfs:/tmp/r", "cov-") == (1, ["cov-1.md"])


def test_expected_set_beats_prefix_and_is_exact(monkeypatch):
    monkeypatch.setattr(W, "sh", _fake_sh(ls_out=_ls("cov-1.md", "cov-2.md")))
    got = W.count_landed("dbfs:/tmp/r", "cov-", expected={"cov-2.md", "cov-9.md"})
    assert got == (1, ["cov-2.md"])


def test_no_filter_counts_every_md_and_sorts(monkeypatch):
    monkeypatch.setattr(W, "sh", _fake_sh(ls_out=_ls("b.md", "a.md", "notes.txt")))
    assert W.count_landed("dbfs:/tmp/r") == (2, ["a.md", "b.md"])


def test_count_landed_fails_closed_on_ls_error(monkeypatch):
    monkeypatch.setattr(W, "sh", _fake_sh(ls_out=_ls("cov-1.md"), ls_rc=1))
    assert W.count_landed("dbfs:/tmp/r", "cov-") == (0, [])


def test_count_landed_passes_the_profile_through(monkeypatch):
    fake = _fake_sh(ls_out="")
    monkeypatch.setattr(W, "sh", fake)
    W.count_landed("dbfs:/tmp/r", profile="other-profile")
    assert fake.calls[0] == [
        "databricks",
        "fs",
        "ls",
        "dbfs:/tmp/r",
        "--profile",
        "other-profile",
    ]


# ----------------------------------------------------------- receipt predicate


def test_terminated_but_failed_result_exits_nonzero(monkeypatch):
    # The merge-critical case: lifecycle alone would have called this a success.
    rc, out, _ = _drive(
        monkeypatch,
        [("TERMINATED", "FAILED", "task failed")],
        [(2, ["u1.md", "u2.md"])],
        total=2,
    )
    assert rc == 1
    assert "=== TERMINAL TERMINATED/FAILED" in out


def test_success_with_a_short_artifact_count_exits_nonzero(monkeypatch):
    rc, out, _ = _drive(
        monkeypatch, [("TERMINATED", "SUCCESS", "")], [(1, ["u1.md"])], total=2
    )
    assert rc == 1
    assert "1/2 landed (50%)" in out


def test_success_with_every_artifact_landed_exits_zero(monkeypatch):
    rc, out, _ = _drive(
        monkeypatch,
        [("TERMINATED", "SUCCESS", "")],
        [(2, ["u1.md", "u2.md"])],
        total=2,
    )
    assert rc == 0
    assert "=== TERMINAL TERMINATED/SUCCESS · 2/2 landed · 1m00s ===" in out
    assert "[landed] u1.md, u2.md" in out


def test_unknown_result_state_renders_a_question_mark_and_fails(monkeypatch):
    rc, out, _ = _drive(monkeypatch, [("SKIPPED", "", "")], [(0, [])], total=1)
    assert rc == 1
    assert "=== TERMINAL SKIPPED/? · 0/1 landed" in out


def test_internal_error_is_terminal(monkeypatch):
    rc, out, _ = _drive(monkeypatch, [("INTERNAL_ERROR", "FAILED", "")], [(0, [])])
    assert rc == 1
    assert "=== TERMINAL INTERNAL_ERROR/FAILED" in out


def test_no_total_still_succeeds_on_success(monkeypatch):
    rc, out, _ = _drive(monkeypatch, [("TERMINATED", "SUCCESS", "")], [(3, ["a.md"])])
    assert rc == 0
    assert "3/? landed ·" in out  # no percent when the total is unknown


# ------------------------------------------------------------------- rendering


def test_pending_phase_rate_and_eta_pending_first_unit(monkeypatch):
    rc, out, _ = _drive(
        monkeypatch,
        [("PENDING", "", ""), ("RUNNING", "", ""), ("TERMINATED", "SUCCESS", "")],
        [(0, []), (0, []), (1, ["u1.md"])],
        total=1,
    )
    lines = out.strip().splitlines()
    assert "spinning up cluster" in lines[0]
    assert "eta pending first unit" in lines[1]
    assert rc == 0


def test_state_message_wins_over_the_phase_default_and_truncates_at_48(monkeypatch):
    _, out, _ = _drive(
        monkeypatch,
        [("TERMINATED", "SUCCESS", "M" * 80)],
        [(1, ["u1.md"])],
        total=1,
    )
    assert "M" * 48 in out
    assert "M" * 49 not in out


def test_delta_marker_eta_and_rate_on_the_second_poll(monkeypatch):
    rc, out, _ = _drive(
        monkeypatch,
        [("RUNNING", "", ""), ("TERMINATED", "SUCCESS", "")],
        [(1, ["u1.md"]), (2, ["u1.md", "u2.md"])],
        total=2,
    )
    lines = out.strip().splitlines()
    # poll 1: 60s elapsed, 1 of 2 landed -> 1.0/min and a 1m00s ETA for the remaining unit.
    assert "1/2 landed (50%) · 1m00s · eta ~1m00s · 1.0/min" in lines[0]
    assert lines[1].endswith("<- +1")
    assert rc == 0


def test_default_label_is_the_run_id_and_label_overrides_it(monkeypatch):
    _, out, _ = _drive(monkeypatch, [("TERMINATED", "SUCCESS", "")], [(0, [])])
    assert out.startswith("[watch 42] ")
    _, out2, _ = _drive(
        monkeypatch, [("TERMINATED", "SUCCESS", "")], [(0, [])], label="R-wave"
    )
    assert out2.startswith("[R-wave] ")


# --------------------------------------------------------------- poll cadence


_CADENCE_STATES = [
    ("RUNNING", "", ""),
    ("RUNNING", "", ""),
    ("TERMINATED", "SUCCESS", ""),
]
_CADENCE_LANDED = [(1, ["u1.md"]), (1, ["u1.md"]), (1, ["u1.md"])]


def test_default_cadence_prints_a_heartbeat_every_poll(monkeypatch):
    rc, out, clock = _drive(monkeypatch, _CADENCE_STATES, _CADENCE_LANDED, total=1)
    assert rc == 0
    # 3 status lines + the terminal line + the landed roster.
    assert len(out.strip().splitlines()) == 5
    assert clock.slept == [7, 7]


def test_on_change_suppresses_the_unchanged_poll(monkeypatch):
    rc, out, clock = _drive(
        monkeypatch, _CADENCE_STATES, _CADENCE_LANDED, total=1, on_change=True
    )
    assert rc == 0
    # The middle poll changed nothing, so only 2 status lines survive.
    assert len(out.strip().splitlines()) == 4
    assert clock.slept == [7, 7]


# ---------------------------------------------------------------------- CLI


def _record_watch(monkeypatch):
    seen = {}

    def fake_watch(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return 0

    monkeypatch.setattr(W, "watch", fake_watch)
    return seen


def test_positional_form_matches_the_orchestrator_template_call(monkeypatch):
    seen = _record_watch(monkeypatch)
    # governed-run-orchestrator.md passes: RUN_ID RESULTS N 15 RUN_TAG '' (empty prefix).
    assert W.main(["77", "dbfs:/tmp/R/results", "12", "15", "R-wave", ""]) == 0
    assert seen["args"] == (
        "77",
        "dbfs:/tmp/R/results",
        12,
        W.PROFILE_DEFAULT,
        None,
        None,
        15,
        "R-wave",
        False,
    )


def test_positional_form_defaults_interval_to_15(monkeypatch):
    seen = _record_watch(monkeypatch)
    assert W.main(["77", "dbfs:/tmp/R/results"]) == 0
    assert seen["args"][2] == 0  # no expected total
    assert seen["args"][6] == 15


def test_positional_form_keeps_a_real_prefix(monkeypatch):
    seen = _record_watch(monkeypatch)
    W.main(["77", "dbfs:/r", "3", "20", "lbl", "cov-"])
    assert seen["args"][4] == "cov-"


def test_positional_form_without_a_result_dir_is_a_usage_error(monkeypatch, capsys):
    _record_watch(monkeypatch)
    assert W.main(["77"]) == 2
    assert "usage: watch.py <run_id> <result_dir>" in capsys.readouterr().err


def test_flag_form_defaults_interval_to_30(monkeypatch):
    seen = _record_watch(monkeypatch)
    assert W.main(["--run-id", "77", "--result-dir", "dbfs:/r"]) == 0
    assert seen["args"][6] == 30


def test_flag_form_expect_file_builds_the_exact_set_and_the_total(
    monkeypatch, tmp_path
):
    seen = _record_watch(monkeypatch)
    f = tmp_path / "expected.txt"
    f.write_text("u1.md\n\n  u2.md  \nu3.md\n", encoding="utf-8")
    W.main(["--run-id", "77", "--result-dir", "dbfs:/r", "--expect-file", str(f)])
    assert seen["args"][2] == 3
    assert seen["args"][5] == {"u1.md", "u2.md", "u3.md"}


def test_flag_form_explicit_expect_overrides_the_file_length(monkeypatch, tmp_path):
    seen = _record_watch(monkeypatch)
    f = tmp_path / "expected.txt"
    f.write_text("u1.md\n", encoding="utf-8")
    W.main(
        [
            "--run-id",
            "7",
            "--result-dir",
            "dbfs:/r",
            "--expect-file",
            str(f),
            "--expect",
            "9",
        ]
    )
    assert seen["args"][2] == 9


def test_flag_form_passes_profile_label_and_on_change(monkeypatch):
    seen = _record_watch(monkeypatch)
    W.main(
        [
            "--run-id",
            "7",
            "--result-dir",
            "dbfs:/r",
            "--profile",
            "other",
            "--label",
            "L",
            "--on-change",
        ]
    )
    assert seen["args"][3] == "other"
    assert seen["args"][7] == "L"
    assert seen["args"][8] is True


def test_main_reads_sys_argv_when_no_argv_is_passed(monkeypatch):
    seen = _record_watch(monkeypatch)
    monkeypatch.setattr(W.sys, "argv", ["watch.py", "88", "dbfs:/r"])
    assert W.main() == 0
    assert seen["args"][0] == "88"


def test_cli_to_shell_end_to_end_with_a_prefix_filter(monkeypatch):
    """One wiring test: flags -> watch -> run_state/count_landed -> the databricks CLI."""
    fake = _fake_sh(
        _payload("TERMINATED", "SUCCESS", ""),
        _ls("stale-other.md", "cov-1.md"),
    )
    monkeypatch.setattr(W, "sh", fake)
    monkeypatch.setattr(W, "time", _Clock())
    assert (
        W.main(
            [
                "--run-id",
                "77",
                "--result-dir",
                "dbfs:/tmp/r",
                "--expect",
                "1",
                "--prefix",
                "cov-",
            ]
        )
        == 0
    )
    assert [c[1] for c in fake.calls] == ["jobs", "fs"]
