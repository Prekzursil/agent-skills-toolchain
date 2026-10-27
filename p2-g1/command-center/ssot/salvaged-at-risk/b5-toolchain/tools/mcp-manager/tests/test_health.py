"""Tests for core/health.py — dead-MCP detection with GRADED evidence.

Contract enforced here, and the reason each test exists:

1.  Every verdict names the evidence grade it rests on.  "the command exists on
    PATH" and "the endpoint answered" are different strengths of claim and the
    report must never conflate them.
2.  Every detector is validated in BOTH directions — a known-alive thing must
    read alive AND a known-dead thing must read dead.  A one-directional
    detector is how "0 results" got believed seven times in one session.
3.  Absence of corpus data is NOT a 0% failure rate.  The corpus is a capped
    distillation; a server with no row has NO EVIDENCE, not a clean record.
4.  The reachability probe never spawns a configured server.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.health import (  # noqa: E402
    CorpusHistory,
    ProbeGrade,
    Reach,
    ReachResult,
    Verdict,
    assess,
    build_report,
    discover_configured,
    load_corpus_history,
    normalize_server_id,
    probe_command,
    probe_endpoint,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

# A corpus shaped like the real one, in which the two sources DISAGREE:
#   - error_fingerprints (a top-N list) carries "alpha" but not "beta"
#   - failures_by_tool   (a top-N list) carries "beta"  but not "alpha"
# This mirrors the real corpus, where error_fingerprints has "claude.ai Biomni
# Lab" and failures_by_tool has "firecrawl", and neither source has both.
SPLIT_CORPUS: dict[str, object] = {
    "_meta": {"stamp": "test", "files_failed": 0},
    "tool_usage": [
        {"tool": "mcp__alpha__search", "calls": 100, "errors": 40},
        {"tool": "mcp__beta__fetch", "calls": 50, "errors": 3},
        {"tool": "mcp__gamma__ping", "calls": 10, "errors": 0},
        {"tool": "Bash", "calls": 999, "errors": 1},
    ],
    "error_fingerprints": [
        {"fingerprint": 'MCP server "alpha" is not connected', "count": 40},
    ],
    "failures_by_tool": {
        "mcp__beta__fetch": {
            "errors": 3,
            "calls": 50,
            "top_failures": [
                {"fingerprint": 'MCP server "beta" is not connected', "count": 3}
            ],
        }
    },
}


def _naive_single_source_history(corpus: dict[str, object]) -> set[str]:
    """The obvious-but-wrong reader: trust error_fingerprints alone.

    Kept in the test suite deliberately.  It documents the defect the union
    reader fixes, and test_naive_reader_misses_a_server proves the defect is
    real rather than hypothetical.
    """
    import re

    pattern = re.compile(r'MCP server "([^"]+)" is not connected')
    entries: list[dict[str, object]] = corpus["error_fingerprints"]  # type: ignore[assignment]
    found: set[str] = set()
    for entry in entries:
        match = pattern.search(str(entry["fingerprint"]))
        if match:
            found.add(match.group(1))
    return found


def _write_corpus(tmp_path: Path, data: dict[str, object]) -> Path:
    path = tmp_path / "corpus.json"
    _ = path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _fake_home(tmp_path: Path) -> Path:
    """A synthetic ~ with every MCP config plane the real box uses."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    _ = (home / ".claude.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "root-stdio": {"type": "stdio", "command": "root-cmd"},
                },
                "claudeAiMcpEverConnected": ["claude.ai Ghost"],
                "projects": {
                    "C:/proj": {
                        "mcpServers": {"proj-stdio": {"command": "proj-cmd"}},
                        "disabledMcpServers": ["root-stdio"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    _ = (home / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "canonical-http": {"type": "http", "url": "http://127.0.0.1:1/mcp"},
                    "root-stdio": {"type": "stdio", "command": "root-cmd"},
                }
            }
        ),
        encoding="utf-8",
    )
    return home


def _free_port() -> int:
    """A port that is definitely NOT listening (bound, then released)."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


# ── 1. Name normalisation (live config id <-> corpus tool-name segment) ───────


def test_normalize_maps_live_id_to_corpus_tool_segment() -> None:
    # KNOWN-POSITIVE: these exact pairs are present in the real corpus.
    assert normalize_server_id("claude.ai Tavily") == "claude_ai_Tavily"
    assert normalize_server_id("claude.ai Exa") == "claude_ai_Exa"
    # Hyphens and underscores survive; only out-of-charset bytes are replaced.
    assert normalize_server_id("basic-memory") == "basic-memory"
    assert (
        normalize_server_id("plugin:local-mcp-bridge:cheatengine")
        == "plugin_local-mcp-bridge_cheatengine"
    )


# ── 2. Corpus history: the union, and the defect it fixes ────────────────────


def test_history_unions_both_corpus_sources(tmp_path: Path) -> None:
    """The union must find servers that live in EITHER source."""
    history = load_corpus_history(_write_corpus(tmp_path, SPLIT_CORPUS))
    assert "alpha" in history, "server present only in error_fingerprints was lost"
    assert "beta" in history, "server present only in failures_by_tool was lost"
    assert history["alpha"].not_connected == 40
    assert history["beta"].not_connected == 3
    assert set(history["alpha"].sources) == {"error_fingerprints"}
    assert set(history["beta"].sources) == {"failures_by_tool"}


def test_naive_reader_misses_a_server(tmp_path: Path) -> None:
    """Control: prove the single-source defect is REAL, not hypothetical.

    If this ever passes trivially (naive == union) the fixture has stopped
    exercising the disagreement and the union test is no longer load-bearing.
    """
    naive = _naive_single_source_history(SPLIT_CORPUS)
    union = set(load_corpus_history(_write_corpus(tmp_path, SPLIT_CORPUS)))
    assert "beta" not in naive, "fixture no longer reproduces the single-source defect"
    assert "beta" in union
    assert naive < union


def test_call_volume_joins_via_normalised_tool_names(tmp_path: Path) -> None:
    history = load_corpus_history(_write_corpus(tmp_path, SPLIT_CORPUS))
    assert history["alpha"].calls == 100
    assert history["alpha"].errors == 40
    assert history["alpha"].error_rate == pytest.approx(0.40)


# ── 3. Absence of data is NOT a clean record (anti-false-absence) ─────────────


def test_no_corpus_row_is_not_a_zero_percent_failure_rate() -> None:
    empty = CorpusHistory(server_id="never-seen")
    assert empty.has_data is False
    assert empty.error_rate is None, "0.0 would read as 'perfect record'"
    assert empty.dead_rate is None


def test_history_is_labelled_a_lower_bound(tmp_path: Path) -> None:
    """The corpus caps its own lists, so every count is a floor, never a total."""
    history = load_corpus_history(_write_corpus(tmp_path, SPLIT_CORPUS))
    assert history["alpha"].lower_bound is True


# ── 4. Reachability probes — BOTH directions, at each grade ──────────────────


def test_probe_command_known_positive_and_known_negative() -> None:
    alive = probe_command(sys.executable)  # certainly exists: we are running it
    assert alive.reach is Reach.REACHABLE
    assert alive.grade is ProbeGrade.COMMAND

    dead = probe_command("definitely-not-a-real-binary-xyz-123")
    assert dead.reach is Reach.UNREACHABLE
    assert dead.grade is ProbeGrade.COMMAND


def test_probe_command_resolves_windows_shims() -> None:
    """Guard against the Git-Bash `which` blind spot that misses .cmd shims.

    shutil.which honours PATHEXT; a hand-rolled PATH walk would not.
    """
    name = Path(sys.executable).name  # e.g. python.exe
    assert probe_command(name).reach is Reach.REACHABLE


def test_probe_endpoint_known_positive_and_known_negative() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port: int = listener.getsockname()[1]
        alive = probe_endpoint(f"http://127.0.0.1:{port}/mcp", timeout=2.0)
        assert alive.reach is Reach.REACHABLE
        assert alive.grade is ProbeGrade.ENDPOINT

    dead = probe_endpoint(f"http://127.0.0.1:{_free_port()}/mcp", timeout=2.0)
    assert dead.reach is Reach.UNREACHABLE
    assert dead.grade is ProbeGrade.ENDPOINT


def test_remote_endpoints_are_not_probed_by_default() -> None:
    """Egress to someone else's host is a side effect; it must be opt-in.

    An unprobed remote must read UNKNOWN, never UNREACHABLE — otherwise a
    healthy remote server gets a false RETIRE.
    """
    result = probe_endpoint("https://mcp.example.com/mcp", allow_remote=False)
    assert result.reach is Reach.UNKNOWN
    assert result.grade is ProbeGrade.NOT_PROBED


def test_command_grade_is_weaker_evidence_than_endpoint() -> None:
    assert ProbeGrade.COMMAND.strength < ProbeGrade.ENDPOINT.strength
    assert ProbeGrade.ENDPOINT.strength < ProbeGrade.HANDSHAKE.strength
    assert probe_command(sys.executable).is_strong is False
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port: int = listener.getsockname()[1]
        assert probe_endpoint(f"http://127.0.0.1:{port}/x", timeout=2.0).is_strong


# ── 5. Verdicts ──────────────────────────────────────────────────────────────


def _hist(**kw: int) -> CorpusHistory:
    return CorpusHistory(server_id="s", sources=("error_fingerprints",), **kw)


def test_verdict_retire_needs_damaging_history_and_no_reachability() -> None:
    health = assess(
        server_id="claude.ai Tavily",
        configured_in=(),
        reach=probe_command("definitely-not-a-real-binary-xyz-123"),
        history=_hist(calls=738, errors=277, not_connected=275),
    )
    assert health.verdict is Verdict.RETIRE


def test_verdict_keep_when_reachable_and_history_clean() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port: int = listener.getsockname()[1]
        health = assess(
            server_id="healthy",
            configured_in=("~/.mcp.json",),
            reach=probe_endpoint(f"http://127.0.0.1:{port}/mcp", timeout=2.0),
            history=_hist(calls=1259, errors=29, not_connected=2),
        )
    assert health.verdict is Verdict.KEEP


def test_verdict_fix_when_configured_but_unreachable() -> None:
    health = assess(
        server_id="angr",
        configured_in=("~/.mcp.json",),
        reach=probe_endpoint(f"http://127.0.0.1:{_free_port()}/sse", timeout=2.0),
        history=CorpusHistory(server_id="angr"),
    )
    assert health.verdict is Verdict.FIX


def test_verdict_is_insufficient_evidence_when_nothing_was_measured() -> None:
    """The anti-false-absence verdict: no probe + no history != healthy."""
    health = assess(
        server_id="unknown-server",
        configured_in=("~/.mcp.json",),
        reach=probe_endpoint("https://remote.example.com/mcp", allow_remote=False),
        history=CorpusHistory(server_id="unknown-server"),
    )
    assert health.verdict is Verdict.INSUFFICIENT_EVIDENCE


def test_a_historically_dead_server_that_now_answers_is_not_retired() -> None:
    """Recovery must beat history — otherwise the report never stops nagging."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port: int = listener.getsockname()[1]
        health = assess(
            server_id="recovered",
            configured_in=("~/.mcp.json",),
            reach=probe_endpoint(f"http://127.0.0.1:{port}/mcp", timeout=2.0),
            history=_hist(calls=738, errors=277, not_connected=275),
        )
    assert health.verdict is not Verdict.RETIRE


def test_a_reachable_server_that_fails_most_calls_is_not_a_silent_keep() -> None:
    """Measured on this box: codex = 52 calls, 36 errors (69.2%), ZERO dead.

    Dead-rate alone reads 0.0% and grades it KEEP.  A server that answers but
    fails two calls in three is a FIX, and the evidence must name WHICH axis
    failed — "not connected" and "connected but erroring" need different repairs.
    """
    health = assess(
        server_id="codex",
        configured_in=("~/.claude.json",),
        reach=probe_command(sys.executable),
        history=CorpusHistory(server_id="codex", calls=52, errors=36),
    )
    assert health.verdict is Verdict.FIX
    assert any("error-rate" in line for line in health.evidence)


def test_dead_calls_are_not_counted_as_answered_then_failed() -> None:
    """Tavily: 277 errors of which 275 ARE the 'not connected' kind.

    Only 2 errors happened after the server answered, so the "answers and then
    fails" narrative is false — and printing it produces an evidence line that
    contradicts the reachability line directly above it.  Measured on the real
    corpus, which is how this defect was found.
    """
    health = assess(
        server_id="claude.ai Tavily",
        configured_in=(),
        reach=ReachResult(Reach.UNKNOWN, ProbeGrade.NOT_PROBED, "not in any config"),
        history=CorpusHistory(
            server_id="claude.ai Tavily",
            calls=738,
            errors=277,
            not_connected=275,
            sources=("error_fingerprints",),
        ),
    )
    assert health.verdict is Verdict.RETIRE
    assert not any("ANSWERS" in line for line in health.evidence), (
        "claimed the server answers while reporting its reachability as unknown"
    )


def test_low_volume_does_not_trigger_the_error_rate_rule() -> None:
    """1 call / 1 error is 100% but proves nothing — do not cry wolf."""
    health = assess(
        server_id="tiny",
        configured_in=("~/.mcp.json",),
        reach=probe_command(sys.executable),
        history=CorpusHistory(server_id="tiny", calls=1, errors=1),
    )
    assert health.verdict is Verdict.KEEP


def test_every_verdict_cites_the_grade_it_rests_on() -> None:
    health = assess(
        server_id="s",
        configured_in=("~/.mcp.json",),
        reach=probe_command(sys.executable),
        history=CorpusHistory(server_id="s"),
    )
    assert health.rests_on is ProbeGrade.COMMAND
    assert health.evidence, "a verdict with no evidence is an opinion"
    assert ProbeGrade.COMMAND.value in " ".join(health.evidence)


# ── 6. Config discovery across planes ────────────────────────────────────────


def test_discover_reads_every_configured_plane(tmp_path: Path) -> None:
    found = discover_configured(_fake_home(tmp_path))
    assert "root-stdio" in found
    assert "canonical-http" in found
    assert "proj-stdio" in found
    # Same server in two files -> both planes recorded, not deduplicated away.
    assert set(found["root-stdio"].sources) == {"~/.claude.json", "~/.mcp.json"}
    assert found["canonical-http"].transport == "http"


def test_ever_connected_remotes_are_not_reported_as_configured(
    tmp_path: Path,
) -> None:
    """claudeAiMcpEverConnected is a HISTORY list, not the current roster.

    Treating it as current config would resurrect servers the owner removed.
    """
    found = discover_configured(_fake_home(tmp_path))
    assert "claude.ai Ghost" not in found


# ── 7. Read-only + no eager spawn ────────────────────────────────────────────


def test_report_never_spawns_a_configured_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Requirement (b): 65 servers spawned to check health is itself an outage.

    Poison every process-creation entry point; the report must still complete.
    """

    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("health check spawned a subprocess")

    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "check_output", _boom)
    monkeypatch.setattr(os, "system", _boom)

    rows = build_report(
        home=_fake_home(tmp_path),
        corpus_path=_write_corpus(tmp_path, SPLIT_CORPUS),
    )
    assert rows, "known-positive control: the fake home has servers to report"


def test_report_does_not_modify_any_config_file(tmp_path: Path) -> None:
    home = _fake_home(tmp_path)
    targets = [home / ".claude.json", home / ".mcp.json"]
    before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in targets}
    _ = build_report(home=home, corpus_path=_write_corpus(tmp_path, SPLIT_CORPUS))
    for path in targets:
        mtime, blob = before[path]
        assert path.stat().st_mtime_ns == mtime, f"{path.name} mtime changed"
        assert path.read_bytes() == blob, f"{path.name} content changed"


def test_report_grades_an_unresolvable_stdio_command_as_fix(tmp_path: Path) -> None:
    """End-to-end: 'root-cmd' is not on PATH, so the row is FIX at COMMAND grade.

    It must NOT be RETIRE — a missing binary is a repair, not a retirement, and
    COMMAND is too weak a grade to justify retiring anything.
    """
    rows = {
        r.id: r
        for r in build_report(
            home=_fake_home(tmp_path),
            corpus_path=_write_corpus(tmp_path, SPLIT_CORPUS),
        )
    }
    assert rows["root-stdio"].verdict is Verdict.FIX
    assert rows["root-stdio"].rests_on is ProbeGrade.COMMAND


# ── 7b. Degraded inputs must degrade to UNKNOWN, never to "dead" ─────────────


def test_missing_corpus_is_no_history_not_a_crash(tmp_path: Path) -> None:
    """The default case on a box that has never run the miner."""
    assert load_corpus_history(tmp_path / "absent.json") == {}


def test_corrupt_corpus_is_no_history_not_a_crash(tmp_path: Path) -> None:
    bad = tmp_path / "corpus.json"
    _ = bad.write_text("{not json at all", encoding="utf-8")
    assert load_corpus_history(bad) == {}


def test_missing_config_files_yield_no_servers(tmp_path: Path) -> None:
    assert discover_configured(tmp_path / "no-such-home") == {}


def test_stdio_server_with_no_command_is_unknown_not_unreachable() -> None:
    """A malformed entry is unmeasurable, not dead.

    Reporting UNREACHABLE here would manufacture a FIX for a config typo the
    probe never actually tested.
    """
    result = probe_command("")
    assert result.reach is Reach.UNKNOWN
    assert result.grade is ProbeGrade.NOT_PROBED


def test_unparseable_url_is_unknown_not_unreachable() -> None:
    result = probe_endpoint("not-a-url", allow_remote=True)
    assert result.reach is Reach.UNKNOWN
    assert result.grade is ProbeGrade.NOT_PROBED


def test_dead_signal_without_call_volume_is_flagged_not_retired() -> None:
    """Dead calls recorded but no call volume joined -> no computable rate.

    Real case: a server named in error_fingerprints whose tool rows never made
    the capped tool_usage list.  Retiring on an uncomputable rate would be a
    guess; the tool must say so out loud instead.
    """
    health = assess(
        server_id="orphan",
        configured_in=("~/.mcp.json",),
        reach=ReachResult(Reach.UNKNOWN, ProbeGrade.NOT_PROBED, "not probed"),
        history=CorpusHistory(
            server_id="orphan", not_connected=99, sources=("error_fingerprints",)
        ),
    )
    assert health.verdict is not Verdict.RETIRE
    assert any("not computable" in line for line in health.evidence)


def test_to_dict_is_json_serialisable_and_keeps_the_grade(tmp_path: Path) -> None:
    """--json output must carry the evidence grade, not just the verdict."""
    rows = build_report(
        home=_fake_home(tmp_path), corpus_path=_write_corpus(tmp_path, SPLIT_CORPUS)
    )
    blob = json.loads(json.dumps([r.to_dict() for r in rows]))
    assert blob
    first = blob[0]
    for key in ("id", "verdict", "rests_on", "probe_grade", "evidence", "dead_rate"):
        assert key in first, f"{key} missing from --json output"


# ── 7c. Borrowed handshake evidence from a pasted `claude mcp list` ──────────

# Real shape of `claude mcp list` output, including the two server families that
# NO local config file exposes: plugin-provided servers and claude.ai remote
# connectors (whose roster is held server-side).
MCP_LIST_DUMP = """\
Checking MCP server health...

canonical-http: http://127.0.0.1:1/mcp - ✔ Connected
plugin:semgrep:semgrep: semgrep mcp - ✔ Connected
plugin:local-mcp-bridge:sonarqube: docker run sonar - ✘ Failed to connect
claude.ai Figma: https://mcp.figma.com/mcp - ! Needs authentication
"""


def test_pasted_mcp_list_is_handshake_grade() -> None:
    """`claude mcp list` really connects, so its glyphs are the STRONGEST grade.

    The spawn cost was paid by the human who ran the command; borrowing the
    result costs this tool nothing and is far better evidence than 'the binary
    exists'.
    """
    from core.health import reach_from_mcp_list

    reaches = reach_from_mcp_list(MCP_LIST_DUMP)
    assert reaches["plugin:semgrep:semgrep"].reach is Reach.REACHABLE
    assert reaches["plugin:semgrep:semgrep"].grade is ProbeGrade.HANDSHAKE
    assert reaches["plugin:local-mcp-bridge:sonarqube"].reach is Reach.UNREACHABLE
    assert reaches["plugin:local-mcp-bridge:sonarqube"].grade is ProbeGrade.HANDSHAKE


def test_needs_authentication_is_a_fix_not_a_retire() -> None:
    """A server that connects but is unauthorised needs a credential, not a grave."""
    from core.health import reach_from_mcp_list

    reach = reach_from_mcp_list(MCP_LIST_DUMP)["claude.ai Figma"]
    health = assess(
        server_id="claude.ai Figma",
        configured_in=("claude mcp list",),
        reach=reach,
        history=CorpusHistory(server_id="claude.ai Figma"),
    )
    assert health.verdict is Verdict.FIX
    assert any("auth" in line.lower() for line in health.evidence)


def test_pasted_list_adds_servers_no_local_config_file_exposes(
    tmp_path: Path,
) -> None:
    """Closes the measured coverage gap: 13 servers from files vs 43 from the CLI.

    Plugin-provided servers and claude.ai remote connectors appear in NO local
    config file, so a file-only report silently under-reports the fleet.
    """
    rows = {
        r.id: r
        for r in build_report(
            home=_fake_home(tmp_path),
            corpus_path=_write_corpus(tmp_path, SPLIT_CORPUS),
            mcp_list_output=MCP_LIST_DUMP,
        )
    }
    assert "plugin:semgrep:semgrep" in rows
    assert "claude.ai Figma" in rows
    assert rows["plugin:local-mcp-bridge:sonarqube"].verdict is Verdict.FIX
    # Servers from local files must survive the merge, not be replaced by it.
    assert "root-stdio" in rows


def test_an_unrecognised_glyph_is_unknown_not_dead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract pin: if the parser ever yields UNKNOWN, we must not call it dead.

    No glyph in today's parser maps to UNKNOWN, so this branch is defensive.
    Forcing it here documents the invariant instead of leaving a future parser
    change free to turn "I could not tell" into "it is dead".
    """
    from core import claude_adapter
    from core.health import reach_from_mcp_list
    from core.models import AuthStatus, ServerRow

    monkeypatch.setattr(
        claude_adapter,
        "parse_mcp_list",
        lambda _output: [
            ServerRow(id="mystery", name="mystery", status=AuthStatus.UNKNOWN, auth="?")
        ],
    )
    result = reach_from_mcp_list("irrelevant")["mystery"]
    assert result.reach is Reach.UNKNOWN
    assert result.grade is ProbeGrade.NOT_PROBED


def test_a_configured_server_with_damaging_history_is_not_duplicated(
    tmp_path: Path,
) -> None:
    """The unconfigured-retirement sweep must not re-emit an already-reported row."""
    corpus: dict[str, object] = {
        "tool_usage": [{"tool": "mcp__root-stdio__go", "calls": 100, "errors": 90}],
        "error_fingerprints": [
            {"fingerprint": 'MCP server "root-stdio" is not connected', "count": 90}
        ],
        "failures_by_tool": {},
    }
    ids = [
        r.id
        for r in build_report(
            home=_fake_home(tmp_path), corpus_path=_write_corpus(tmp_path, corpus)
        )
    ]
    assert ids.count("root-stdio") == 1, "server reported twice"


def test_handshake_evidence_outranks_the_command_probe(tmp_path: Path) -> None:
    """canonical-http is in both the fake home and the dump; handshake must win."""
    rows = {
        r.id: r
        for r in build_report(
            home=_fake_home(tmp_path),
            corpus_path=_write_corpus(tmp_path, SPLIT_CORPUS),
            mcp_list_output=MCP_LIST_DUMP,
        )
    }
    row = rows["canonical-http"]
    assert row.rests_on is ProbeGrade.HANDSHAKE
    assert row.verdict is Verdict.KEEP
    assert row.reach.is_strong


# ── 8. Live-corpus known-positive control ────────────────────────────────────

_LIVE_CORPUS = (
    Path.home() / ".claude" / "harness-sota-2026-07-18" / "corpus" / "corpus.json"
)
_REQUIRE_LIVE = os.environ.get("MCP_HEALTH_REQUIRE_LIVE_CORPUS") == "1"


def test_live_corpus_is_present_when_required() -> None:
    """Escalation so the skip below cannot silently disarm the control.

    A bare skipif on a known-positive control is the silent-disarm failure the
    control exists to prevent; run with MCP_HEALTH_REQUIRE_LIVE_CORPUS=1 to make
    absence a failure rather than a skip.
    """
    if _REQUIRE_LIVE:
        assert _LIVE_CORPUS.is_file(), f"live corpus missing at {_LIVE_CORPUS}"


@pytest.mark.skipif(
    not _LIVE_CORPUS.is_file() and not _REQUIRE_LIVE,
    reason="live corpus not on this box",
)
def test_live_corpus_known_positive_control() -> None:
    """Prove the parser finds items that are KNOWN to be present.

    Independently measured from the real corpus:
      claude.ai Tavily  738 calls / 277 errors / 275 'not connected'
      claude.ai Exa     385 calls / 213 errors / 212 'not connected'
    If these ever read zero, the parser is broken — not the servers healthy.
    """
    history = load_corpus_history(_LIVE_CORPUS)

    tavily = history["claude.ai Tavily"]
    assert tavily.calls == 738
    assert tavily.errors == 277
    assert tavily.not_connected == 275

    exa = history["claude.ai Exa"]
    assert exa.calls == 385
    assert exa.not_connected == 212

    # The union must beat either source alone on the REAL corpus too.
    assert "firecrawl" in history, "failures_by_tool-only server lost"
    assert "claude.ai Biomni Lab" in history, "error_fingerprints-only server lost"
