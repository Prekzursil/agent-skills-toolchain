"""Dead-MCP detector — per-server health with GRADED, citable evidence.

Extends mcp-manager rather than duplicating it: config discovery reuses the same
plane layout as core/inventory.py and core/claude_adapter.py, and this module
adds the two things they lack — historical failure rates mined from the session
corpus, and a reachability probe that never spawns a server.

Three design rules, each earned from a measured failure:

1.  EVIDENCE IS GRADED.  "the command resolves on PATH" (ProbeGrade.COMMAND) and
    "the endpoint completed a TCP handshake" (ProbeGrade.ENDPOINT) are different
    strengths of claim.  Every verdict records the grade it rests on so a weak
    KEEP is never mistaken for a strong one.

2.  ABSENCE IS NOT HEALTH.  corpus.json caps its own lists (error_fingerprints
    is a top-N, failures_by_tool is a top-N), so a server with no row has NO
    EVIDENCE — not a clean record.  error_rate/dead_rate return None, never 0.0,
    and the verdict is INSUFFICIENT_EVIDENCE rather than KEEP.

3.  READ THE UNION, NOT ONE SOURCE.  The two corpus sections disagree about
    which servers they name: on the real corpus error_fingerprints carries
    "claude.ai Biomni Lab" and failures_by_tool carries "firecrawl", and neither
    carries both.  Reading either alone silently loses servers.

The module is read-only.  It never writes config and never starts a server.
"""

from __future__ import annotations

import json
import re
import shutil
import socket
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from .models import AuthStatus

# The literal error string Claude Code emits for an unreachable MCP server.
# It carries the EXACT configured id (e.g. "claude.ai Tavily"), which is what
# makes a corpus->config join possible without guessing at name mangling.
_NOT_CONNECTED = re.compile(r'MCP server "([^"]+)" is not connected')

# MCP tool names are "mcp__<server>__<tool>" with the server segment restricted
# to [A-Za-z0-9_-]; every other byte in the configured id becomes "_".
_UNSAFE_IN_TOOL_NAME = re.compile(r"[^A-Za-z0-9_-]")

_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})

# A server is "historically damaging" only above BOTH floors: a high rate on a
# handful of calls is a reconnect blip, not a dead server.  Both were chosen
# against the measured distribution: the two real offenders sit at 37% / 55%
# with 275 / 212 dead calls, while every transient blip sits under 1.5%.
DEAD_RATE_FLOOR = 0.20
DEAD_COUNT_FLOOR = 25

# A server can be perfectly REACHABLE and still fail most calls — "not connected"
# and "connected but erroring" are different axes needing different repairs, and
# a dead-rate-only view grades the second one KEEP.  Measured on this box: codex
# answers on PATH yet fails 36 of 52 calls (69.2%) with ZERO dead signals.
# The volume floor keeps a 1-call-1-error server from crying wolf.
ERROR_RATE_FLOOR = 0.25
VOLUME_FLOOR = 25


class ProbeGrade(str, Enum):
    """How strong the reachability evidence is.  Ordered, and never conflated."""

    NOT_PROBED = "not_probed"  # nothing was measured
    COMMAND = "command"  # the binary resolves on PATH / exists on disk
    ENDPOINT = "endpoint"  # a TCP connection to the endpoint completed
    HANDSHAKE = "handshake"  # an MCP initialize round-trip succeeded

    @property
    def strength(self) -> int:
        return _GRADE_STRENGTH[self.value]


_GRADE_STRENGTH = {"not_probed": 0, "command": 1, "endpoint": 2, "handshake": 3}


class Reach(str, Enum):
    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"  # not measured — distinct from "measured as dead"


class Verdict(str, Enum):
    KEEP = "keep"
    FIX = "fix"
    RETIRE = "retire"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class ReachResult:
    reach: Reach
    grade: ProbeGrade
    detail: str = ""

    @property
    def is_strong(self) -> bool:
        """True only for evidence at ENDPOINT grade or above.

        COMMAND grade means "a file with that name exists".  It says nothing
        about whether the server starts, speaks MCP, or has valid credentials,
        so it must never be reported as proof a server is alive.
        """
        return self.grade.strength >= ProbeGrade.ENDPOINT.strength


@dataclass(frozen=True)
class CorpusHistory:
    """What the session corpus recorded about one server.

    `sources` names the corpus sections that reported this server NOT CONNECTED.
    Every count is a LOWER BOUND: the corpus caps its own lists, so a count of 5
    means "at least 5", and a count of 0 means "no row found", never "zero
    failures happened".
    """

    server_id: str
    calls: int = 0
    errors: int = 0
    not_connected: int = 0
    sources: tuple[str, ...] = ()

    @property
    def has_data(self) -> bool:
        return bool(self.sources) or self.calls > 0

    @property
    def lower_bound(self) -> bool:
        return True

    @property
    def error_rate(self) -> float | None:
        """None when there is no call volume — NOT 0.0.

        Returning 0.0 here is the false-absence bug: it renders an unmeasured
        server as a perfect one.
        """
        return self.errors / self.calls if self.calls else None

    @property
    def dead_rate(self) -> float | None:
        return self.not_connected / self.calls if self.calls else None

    @property
    def answered_error_rate(self) -> float | None:
        """Failure rate EXCLUDING 'not connected' — errors that followed an answer.

        The two axes need different repairs and must not be pooled: Tavily's 277
        errors are 275 dead + 2 real, so its answered-error rate is 0.3%, not
        37.5%.  Pooling them produces the claim "this server answers and then
        fails" about a server that was never reachable.
        """
        if not self.calls:
            return None
        return max(self.errors - self.not_connected, 0) / self.calls


@dataclass(frozen=True)
class ConfiguredServer:
    """One server as declared in config, with every plane that declares it."""

    id: str
    transport: str = "stdio"
    command: str = ""
    url: str = ""
    sources: tuple[str, ...] = ()


@dataclass
class ServerHealth:
    id: str
    configured_in: tuple[str, ...]
    reach: ReachResult
    history: CorpusHistory
    verdict: Verdict
    rests_on: ProbeGrade
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "configured_in": list(self.configured_in),
            "reachable": self.reach.reach.value,
            "probe_grade": self.reach.grade.value,
            "probe_detail": self.reach.detail,
            "calls": self.history.calls,
            "errors": self.history.errors,
            "not_connected": self.history.not_connected,
            "error_rate": self.history.error_rate,
            "dead_rate": self.history.dead_rate,
            "answered_error_rate": self.history.answered_error_rate,
            "history_sources": list(self.history.sources),
            "history_is_lower_bound": self.history.lower_bound,
            "verdict": self.verdict.value,
            "rests_on": self.rests_on.value,
            "evidence": list(self.evidence),
        }


def normalize_server_id(server_id: str) -> str:
    """Map a configured server id to its MCP tool-name segment.

    'claude.ai Tavily' -> 'claude_ai_Tavily'   (dots and spaces are unsafe)
    'basic-memory'     -> 'basic-memory'       (hyphens are safe, kept as-is)
    """
    return _UNSAFE_IN_TOOL_NAME.sub("_", server_id)


# ── corpus ────────────────────────────────────────────────────────────────────


def _call_volume(data: dict[str, Any]) -> dict[str, tuple[int, int]]:
    """Aggregate tool_usage into per-server (calls, errors), keyed by tool segment."""
    volume: dict[str, list[int]] = {}
    for row in cast("list[dict[str, Any]]", data.get("tool_usage") or []):
        tool = str(row.get("tool", ""))
        if not tool.startswith("mcp__"):
            continue
        parts = tool.split("__")
        if len(parts) < 3:
            continue
        agg = volume.setdefault(parts[1], [0, 0])
        agg[0] += int(row.get("calls", 0) or 0)
        agg[1] += int(row.get("errors", 0) or 0)
    return {k: (v[0], v[1]) for k, v in volume.items()}


def _dead_signal(data: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Per-server 'not connected' counts, unioned across BOTH corpus sections.

    Both sections are top-N truncated and they truncate DIFFERENTLY, so the
    union recovers servers that either one alone would drop.  Where both name a
    server the larger count wins: they count the same underlying events, and the
    per-tool section loses some to its own per-tool cap.
    """
    per_source: dict[str, dict[str, int]] = {}

    for entry in cast("list[dict[str, Any]]", data.get("error_fingerprints") or []):
        match = _NOT_CONNECTED.search(str(entry.get("fingerprint", "")))
        if match:
            bucket = per_source.setdefault(match.group(1), {})
            count = int(entry.get("count", 0) or 0)
            bucket["error_fingerprints"] = bucket.get("error_fingerprints", 0) + count

    failures = cast("dict[str, Any]", data.get("failures_by_tool") or {})
    for entry_value in failures.values():
        tool_block = cast("dict[str, Any]", entry_value)
        for failure in cast(
            "list[dict[str, Any]]", tool_block.get("top_failures") or []
        ):
            match = _NOT_CONNECTED.search(str(failure.get("fingerprint", "")))
            if match:
                bucket = per_source.setdefault(match.group(1), {})
                count = int(failure.get("count", 0) or 0)
                bucket["failures_by_tool"] = bucket.get("failures_by_tool", 0) + count

    return per_source


def load_corpus_history(corpus_path: Path) -> dict[str, CorpusHistory]:
    """Read corpus.json into per-server history keyed by the EXACT configured id.

    Returns a row for every server with either a dead signal or call volume.
    Servers absent from the result have no corpus evidence at all — which is not
    the same as having a clean record.
    """
    try:
        data = cast(
            "dict[str, Any]",
            json.loads(Path(corpus_path).read_text(encoding="utf-8")),
        )
    except (OSError, json.JSONDecodeError):
        return {}

    volume = _call_volume(data)
    dead = _dead_signal(data)

    out: dict[str, CorpusHistory] = {}
    for server_id, per_source in dead.items():
        calls, errors = volume.get(normalize_server_id(server_id), (0, 0))
        out[server_id] = CorpusHistory(
            server_id=server_id,
            calls=calls,
            errors=errors,
            not_connected=max(per_source.values()),
            sources=tuple(sorted(per_source)),
        )

    # Servers seen in tool_usage but never reported dead still carry evidence:
    # a real call volume with no dead signal is what a healthy server looks like.
    seen = {normalize_server_id(k) for k in out}
    for segment, (calls, errors) in volume.items():
        if segment not in seen:
            out[segment] = CorpusHistory(
                server_id=segment, calls=calls, errors=errors, sources=()
            )
    return out


# ── reachability probes (never spawn a server) ───────────────────────────────


def probe_command(command: str) -> ReachResult:
    """Weakest useful check: does the stdio command resolve to a real file?

    shutil.which honours PATHEXT, so it finds the .CMD/.EXE shims that a
    hand-rolled PATH walk (or Git-Bash `which`) silently misses.  Verified in
    both directions against PowerShell Get-Command on this box.

    This does NOT start the server.  A COMMAND-grade REACHABLE means only that
    a launchable file exists — not that it speaks MCP or has credentials.
    """
    if not command:
        return ReachResult(
            Reach.UNKNOWN, ProbeGrade.NOT_PROBED, "no command configured"
        )
    resolved = shutil.which(command)
    if resolved:
        return ReachResult(
            Reach.REACHABLE, ProbeGrade.COMMAND, f"resolves to {resolved}"
        )
    return ReachResult(
        Reach.UNREACHABLE, ProbeGrade.COMMAND, f"{command!r} does not resolve on PATH"
    )


def probe_endpoint(
    url: str, *, timeout: float = 2.0, allow_remote: bool = False
) -> ReachResult:
    """Bounded TCP connect to an http/sse endpoint.  No payload, no HTTP request.

    Remote hosts are NOT probed unless allow_remote is set: reaching out to
    someone else's host is a side effect, and — more importantly — a firewalled
    or rate-limited remote would read UNREACHABLE and earn a false RETIRE.  An
    unprobed endpoint is UNKNOWN, which is honest about having measured nothing.
    """
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return ReachResult(
            Reach.UNKNOWN, ProbeGrade.NOT_PROBED, f"unparseable url {url!r}"
        )

    if host not in _LOOPBACK and not allow_remote:
        return ReachResult(
            Reach.UNKNOWN,
            ProbeGrade.NOT_PROBED,
            f"remote host {host} not probed (pass allow_remote to enable)",
        )

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return ReachResult(
                Reach.REACHABLE, ProbeGrade.ENDPOINT, f"tcp connect {host}:{port} ok"
            )
    except OSError as exc:
        return ReachResult(
            Reach.UNREACHABLE,
            ProbeGrade.ENDPOINT,
            f"tcp connect {host}:{port} failed: {exc}",
        )


def reach_from_mcp_list(output: str) -> dict[str, ReachResult]:
    """Borrow HANDSHAKE-grade evidence from a pasted `claude mcp list` dump.

    That command really connects to every server, so its glyphs are the
    strongest evidence available — and the spawn cost was already paid by the
    human who ran it, so reusing the output costs this tool nothing.

    Parsing is delegated to claude_adapter.parse_mcp_list (the same parser the
    rest of mcp-manager uses) rather than reimplemented here.

    'Needs authentication' maps to UNREACHABLE: the transport is up but the
    server cannot answer, which is a credential FIX, not a retirement.
    """
    from . import claude_adapter  # deferred: keeps core.health import-light

    out: dict[str, ReachResult] = {}
    for row in claude_adapter.parse_mcp_list(output):
        if row.status is AuthStatus.CONNECTED:
            out[row.id] = ReachResult(
                Reach.REACHABLE, ProbeGrade.HANDSHAKE, f"claude mcp list: {row.auth}"
            )
        elif row.status in (AuthStatus.FAILED, AuthStatus.NEEDS_AUTH):
            out[row.id] = ReachResult(
                Reach.UNREACHABLE, ProbeGrade.HANDSHAKE, f"claude mcp list: {row.auth}"
            )
        else:
            out[row.id] = ReachResult(
                Reach.UNKNOWN, ProbeGrade.NOT_PROBED, f"claude mcp list: {row.auth}"
            )
    return out


# ── verdict ───────────────────────────────────────────────────────────────────


def _is_damaging(history: CorpusHistory) -> bool:
    """Historically DEAD: called at volume and answered 'not connected'."""
    rate = history.dead_rate
    if rate is None:
        return False  # no denominator -> no rate -> no retirement on rate
    return rate >= DEAD_RATE_FLOOR and history.not_connected >= DEAD_COUNT_FLOOR


def _is_erroring(history: CorpusHistory) -> bool:
    """Historically BROKEN: answered at volume, then failed anyway.

    Uses answered_error_rate, NOT error_rate: a dead server's errors are all
    'not connected', and counting them here would label it "answers then fails".
    """
    rate = history.answered_error_rate
    if rate is None:
        return False
    return rate >= ERROR_RATE_FLOOR and history.calls >= VOLUME_FLOOR


def assess(
    *,
    server_id: str,
    configured_in: tuple[str, ...],
    reach: ReachResult,
    history: CorpusHistory,
) -> ServerHealth:
    """Combine current reachability with historical damage into one verdict.

    Reachability dominates history: a server that answers NOW is KEEP even if it
    was dead for months, otherwise the report nags forever about a fixed problem.
    History only decides how an UNREACHABLE/UNKNOWN server is graded — RETIRE if
    it burned real call volume, FIX if it is merely down.
    """
    damaging = _is_damaging(history)
    erroring = _is_erroring(history)
    evidence: list[str] = [
        f"reachability={reach.reach.value} "
        f"(grade={reach.grade.value}, strength={reach.grade.strength}): {reach.detail}"
    ]

    if reach.reach is Reach.REACHABLE:
        verdict = Verdict.FIX if erroring else Verdict.KEEP
    elif reach.reach is Reach.UNREACHABLE:
        verdict = Verdict.RETIRE if damaging else Verdict.FIX
    else:
        verdict = Verdict.RETIRE if damaging else Verdict.INSUFFICIENT_EVIDENCE

    if history.has_data:
        rate = history.dead_rate
        rate_text = "n/a (no call volume)" if rate is None else f"{rate:.1%}"
        evidence.append(
            f"corpus: {history.calls} calls, {history.errors} errors, "
            f"{history.not_connected} 'not connected' (dead-rate {rate_text}); "
            f"sources={list(history.sources) or ['tool_usage']}; counts are a LOWER BOUND"
        )
    else:
        evidence.append(
            "corpus: NO ROW — the corpus caps its own lists, so this is absence of "
            "evidence, not evidence of health"
        )

    if erroring:
        answered = history.answered_error_rate or 0.0
        evidence.append(
            f"answered-error-rate {answered:.1%} over {history.calls} calls "
            f"({history.errors} errors, only {history.not_connected} of them "
            "'not connected') — this server ANSWERS and then fails, so the repair is "
            "credentials/args/quota, NOT reconnection"
        )

    if history.not_connected and history.dead_rate is None:
        evidence.append(
            f"WARNING: {history.not_connected} dead calls recorded but no call volume "
            "joined — dead-rate not computable, so no RETIRE can rest on it"
        )

    if not configured_in:
        evidence.append(
            "not present in any config plane read here — if this is a RETIRE it is "
            "already executed; no action required"
        )

    if verdict is Verdict.KEEP and not reach.is_strong:
        evidence.append(
            f"NOTE: this KEEP rests on {reach.grade.value} grade only — the server "
            "was never asked to respond, so 'alive' is unproven"
        )

    if verdict is Verdict.INSUFFICIENT_EVIDENCE:
        evidence.append(
            "nothing was measured in either axis; do NOT read this as healthy"
        )

    return ServerHealth(
        id=server_id,
        configured_in=configured_in,
        reach=reach,
        history=history,
        verdict=verdict,
        rests_on=reach.grade,
        evidence=evidence,
    )


# ── config discovery ──────────────────────────────────────────────────────────


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return {}


def _absorb(
    out: dict[str, ConfiguredServer], servers: dict[str, Any], source: str
) -> None:
    for server_id, raw in servers.items():
        spec = cast("dict[str, Any]", raw or {})
        url = str(spec.get("url") or "")
        transport = str(spec.get("type") or ("http" if url else "stdio"))
        existing = out.get(server_id)
        if existing is None:
            out[server_id] = ConfiguredServer(
                id=server_id,
                transport=transport,
                command=str(spec.get("command") or ""),
                url=url,
                sources=(source,),
            )
        elif source not in existing.sources:
            out[server_id] = ConfiguredServer(
                id=existing.id,
                transport=existing.transport or transport,
                command=existing.command or str(spec.get("command") or ""),
                url=existing.url or url,
                sources=(*existing.sources, source),
            )


def discover_configured(home: Path) -> dict[str, ConfiguredServer]:
    """Every MCP server declared in any config plane on this box.

    Deliberately EXCLUDES ~/.claude.json's claudeAiMcpEverConnected: that key is
    an ever-connected HISTORY list, not the current roster.  Two servers the
    owner has already removed still appear in it, and treating it as config
    would resurrect them as live findings.  A consequence worth stating: the
    current claude.ai remote-connector roster is held server-side and is NOT
    readable from local config, so remote connectors are invisible to this
    function unless they also appear in a local file.
    """
    out: dict[str, ConfiguredServer] = {}

    claude_json = _read_json(home / ".claude.json")
    _absorb(
        out,
        cast("dict[str, Any]", claude_json.get("mcpServers") or {}),
        "~/.claude.json",
    )
    _absorb(
        out,
        cast("dict[str, Any]", _read_json(home / ".mcp.json").get("mcpServers") or {}),
        "~/.mcp.json",
    )

    projects = cast("dict[str, Any]", claude_json.get("projects") or {})
    for project_path, raw_block in projects.items():
        block = cast("dict[str, Any]", raw_block or {})
        _absorb(
            out,
            cast("dict[str, Any]", block.get("mcpServers") or {}),
            f"~/.claude.json:projects[{project_path}]",
        )
    return out


# ── report ────────────────────────────────────────────────────────────────────


def build_report(
    *,
    home: Path,
    corpus_path: Path,
    allow_remote: bool = False,
    include_unconfigured: bool = True,
    mcp_list_output: str | None = None,
) -> list[ServerHealth]:
    """Full per-server health report.  Read-only; starts no server.

    include_unconfigured adds rows for historically-damaging servers that are no
    longer in any config plane, so a completed retirement is visible as such
    instead of silently vanishing from the report.

    mcp_list_output accepts a pasted `claude mcp list` dump.  It does two things
    no local config file can: it upgrades those rows to HANDSHAKE grade, and it
    reveals plugin-provided servers and claude.ai remote connectors, whose
    rosters live outside every file on disk.
    """
    history = load_corpus_history(corpus_path)
    configured = discover_configured(home)
    handshakes = reach_from_mcp_list(mcp_list_output) if mcp_list_output else {}
    rows: list[ServerHealth] = []

    for server_id, cfg in configured.items():
        # Handshake evidence outranks both cheap probes when it is available.
        reach = handshakes.get(server_id)
        if reach is None:
            if cfg.url:
                reach = probe_endpoint(cfg.url, allow_remote=allow_remote)
            else:
                reach = probe_command(cfg.command)
        rows.append(
            assess(
                server_id=server_id,
                configured_in=cfg.sources,
                reach=reach,
                history=history.get(server_id, CorpusHistory(server_id=server_id)),
            )
        )

    for server_id, reach in handshakes.items():
        if server_id in configured:
            continue
        rows.append(
            assess(
                server_id=server_id,
                configured_in=("claude mcp list",),
                reach=reach,
                history=history.get(server_id, CorpusHistory(server_id=server_id)),
            )
        )

    if include_unconfigured:
        for server_id, hist in history.items():
            if server_id in configured or server_id in handshakes:
                continue
            if not _is_damaging(hist):
                continue
            rows.append(
                assess(
                    server_id=server_id,
                    configured_in=(),
                    reach=ReachResult(
                        Reach.UNKNOWN, ProbeGrade.NOT_PROBED, "not in any config plane"
                    ),
                    history=hist,
                )
            )

    _ORDER = {
        Verdict.RETIRE: 0,
        Verdict.FIX: 1,
        Verdict.INSUFFICIENT_EVIDENCE: 2,
        Verdict.KEEP: 3,
    }
    rows.sort(key=lambda r: (_ORDER[r.verdict], -r.history.not_connected, r.id))
    return rows
