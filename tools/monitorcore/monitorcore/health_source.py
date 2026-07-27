"""``health_source`` — a :class:`~monitorcore.contract.MonitorSource` over the system sentinel.

The sentinel (``~/.local/opt/memguard/sentinel.ps1``) appends one NDJSON sample per tick to
``~/.claude/system-health/events.ndjson``. This adapter tails that file and surfaces it on the
existing cockpit, so workstation liveness is a row on the board people already watch rather than
a fifth place to look.

WHY THIS EXISTS — measured 2026-07-21. ``memguard`` bands on COMMIT ALONE. At the moment this
was written the box read commit 57.1% (band ``OK``) while physical sat at 96.4% and ``Taskmgr``
was pinned at GDI 9999 against a per-process cap of 10000 — i.e. the tool the owner diagnoses
freezes *with* was itself GUI-object starved, and the watchdog said everything was fine. A
single-signal detector cannot see a multi-mechanism failure, so the sentinel bands every signal
independently and names the driver; this adapter carries that verdict through unchanged.

THE DEAD-MAN RULE IS THE POINT. If the sentinel process dies, the file simply stops growing and
its last sample stays readable forever. An adapter that kept rendering that frame would show a
healthy board for a machine nobody is watching — the exact "reports success while dead" class
this program exists to eliminate. So freshness is computed from the sample's own timestamp and a
feed older than ``dead_man_s`` becomes ``STALLED`` + ``stale=True``, never a green row.

``SourceState`` is modelled for work-executing sources, so the mapping here is deliberate rather
than natural, and is stated plainly instead of being left implicit:

    band ``green``            -> ``IDLE``    (reachable, nothing wrong)
    band ``yellow``           -> ``RUNNING`` (elevated pressure, not yet failing)
    band ``orange`` / ``red`` -> ``ERROR``   (a signal is in breach)
    feed older than dead-man  -> ``STALLED``
    file absent / unreadable  -> ``UNREACHABLE``

A sample is UNTRUSTED INPUT, not merely a reading. The feed is a world-writable-by-the-user
file whose fields carry OS-supplied strings (a process name in ``gui.gdi_max_proc``, the orphan
names, the census keys), so every string is funnelled through the package's shared
:func:`monitorcore.redact.scrub` ingest floor — control bytes stripped FIRST, then secrets
masked. Without it a crafted sample paints raw ESC/BEL straight onto the operator's terminal
through the headline (OSC title-set, OSC-8 link spoof, OSC-52 clipboard hijack); that was
reproduced against this adapter before the floor was added, and ``test_no_escape_byte_*`` pins
each sink.

Stdlib-only, so it vendors into the skill copy unchanged (CI enforces the dual write).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .contract import Alert, Snapshot, SourceState
from .redact import redact, scrub
from .report_doc import KV, Block, ReportDoc, Section, Table, Text
from .textsafe import strip_controls

__all__ = ["HealthPayload", "SystemHealthSource"]

# Read this much from the tail. Comfortably more than one sample (~1 KB) so a truncated final
# line always has at least one complete predecessor to fall back to.
_TAIL_BYTES = 65536

# Bands the sentinel emits, ordered. Kept as a tuple rather than an enum so an unknown future
# band degrades to "unknown" instead of raising inside poll().
_BAND_RANK = {"green": 0, "yellow": 1, "orange": 2, "red": 3}


@dataclass(frozen=True)
class HealthPayload:
    """One sentinel sample — the domain's own model, never flattened to a shared dict.

    Every ``str`` field here is ALREADY scrubbed at ingest by :func:`_to_payload` (the shared
    :func:`monitorcore.redact.scrub` floor: control bytes stripped, then secrets masked), so a
    consumer may render any of them directly. The ONE exception is ``raw``, which is the
    untouched sample dict kept for debugging — it is NOT render-safe and must pass ``scrub``
    before any of it reaches a frame.
    """

    band: str = "unknown"
    driver: str = ""
    commit_pct: float = 0.0
    phys_pct: float = 0.0
    procs: int = 0
    handles: int = 0
    threads: int = 0
    gdi_max: int | None = None
    gdi_max_proc: str | None = None
    usr_max: int | None = None
    orphan_count: int = 0
    orphan_top: tuple[str, ...] = ()
    census: tuple[tuple[str, int], ...] = ()
    sample_ts: float = 0.0
    raw: dict[str, object] = field(default_factory=dict)


def _parse_ts(value: object) -> float:
    """ISO-8601 -> epoch seconds. Returns 0.0 on anything unparseable (never raises)."""
    if not isinstance(value, str):
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _last_complete_sample(path: Path) -> dict[str, object] | None:
    """Return the newest fully-parseable NDJSON object in the file's tail, or ``None``.

    A live tailing reader WILL sometimes catch a half-written final line — the writer appends
    and flushes per tick, so a read can land mid-line. Scanning backwards for the first line
    that parses tolerates that instead of crashing or, worse, mis-parsing it into a wrong
    reading. Only the tail is read, so file growth does not make polling more expensive.
    """
    with path.open("rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - _TAIL_BYTES))
        blob = fh.read()
    text = blob.decode("utf-8", errors="replace")
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # truncated or mid-write; try the previous line
        if isinstance(obj, dict):
            return obj
    return None


def _to_payload(obj: dict[str, object]) -> HealthPayload:
    def sub(key: str) -> dict[str, object]:
        v = obj.get(key)
        return v if isinstance(v, dict) else {}

    commit, phys, proc, gui, orph = (
        sub("commit"),
        sub("phys"),
        sub("proc"),
        sub("gui"),
        sub("orphans"),
    )
    census_raw = sub("census")
    top = orph.get("top")
    orphan_top: tuple[str, ...] = ()
    if isinstance(top, list):
        orphan_top = tuple(
            scrub(
                f"{t.get('name')}:{t.get('pid')} (ppid {t.get('ppid')}, {t.get('rss_mb')} MB)"
            )
            for t in top
            if isinstance(t, dict)
        )

    def num(d: dict[str, object], k: str, default: float = 0.0) -> float:
        v = d.get(k)
        return float(v) if isinstance(v, (int, float)) else default

    def opt_int(d: dict[str, object], k: str) -> int | None:
        v = d.get(k)
        return int(v) if isinstance(v, (int, float)) else None

    gdi_proc = gui.get("gdi_max_proc")
    return HealthPayload(
        band=scrub(obj.get("band", "unknown")),
        driver=scrub(obj.get("driver", "")),
        commit_pct=num(commit, "pct"),
        phys_pct=num(phys, "pct"),
        procs=int(num(proc, "count")),
        handles=int(num(proc, "handles")),
        threads=int(num(proc, "threads")),
        gdi_max=opt_int(gui, "gdi_max"),
        gdi_max_proc=(scrub(gdi_proc) if isinstance(gdi_proc, str) else None),
        usr_max=opt_int(gui, "usr_max"),
        orphan_count=int(num(orph, "count")),
        orphan_top=orphan_top,
        census=tuple(
            (scrub(k), int(v))
            for k, v in census_raw.items()
            if isinstance(v, (int, float))
        ),
        sample_ts=_parse_ts(obj.get("ts")),
        raw=obj,
    )


class SystemHealthSource:
    """Tails the sentinel's NDJSON and reports workstation liveness on the shared board."""

    def __init__(
        self,
        events_path: Path | str | None = None,
        *,
        source_id: str = "health",
        dead_man_s: float = 45.0,
        redact_enabled: bool = True,
    ) -> None:
        self.id = source_id
        # 45s = 4.5 sentinel ticks. Long enough that one slow tick (measured max 2.22s) never
        # trips it; short enough that a dead sentinel is visible inside a minute.
        self._dead_man_s = dead_man_s
        self._redact = redact_enabled
        self._path = Path(
            events_path
            if events_path is not None
            else Path.home() / ".claude" / "system-health" / "events.ndjson"
        )
        self._last_good: HealthPayload | None = None

    def poll(self) -> Snapshot[HealthPayload]:
        """Read the newest sample. MUST NOT raise — every failure degrades this row only."""
        now = time.time()
        try:
            if not self._path.exists():
                return self._degraded(
                    now, "sentinel event log not found: is sentinel.ps1 running?"
                )
            obj = _last_complete_sample(self._path)
            if obj is None:
                return self._degraded(now, "no parseable sample in event-log tail")

            payload = _to_payload(obj)
            self._last_good = payload
            age = max(0.0, now - payload.sample_ts) if payload.sample_ts else None

            # Dead-man: a readable file is NOT a live feed. If the newest sample has aged past
            # the window, the sentinel is gone and this row must say so rather than keep
            # rendering a stale-but-green frame.
            if age is not None and age > self._dead_man_s:
                return Snapshot(
                    source_id=self.id,
                    ts=now,
                    reachable=True,
                    stale=True,
                    state=SourceState.STALLED,
                    headline=self._line(payload, stalled_age=age),
                    payload=payload,
                    age_s=age,
                    error=f"sentinel feed stale: newest sample is {age:.0f}s old",
                )

            rank = _BAND_RANK.get(payload.band, 0)
            state = (
                SourceState.ERROR
                if rank >= 2
                else SourceState.RUNNING
                if rank == 1
                else SourceState.IDLE
            )
            return Snapshot(
                source_id=self.id,
                ts=now,
                reachable=True,
                stale=False,
                state=state,
                headline=self._line(payload),
                payload=payload,
                age_s=age,
            )
        except Exception as exc:  # noqa: BLE001 — contract: poll never raises
            return self._degraded(now, f"{type(exc).__name__}: {exc}")

    def _safe(self, text: str) -> str:
        """Strip control bytes, THEN mask secrets. The ONLY way text leaves this adapter.

        The control-byte strip is UNCONDITIONAL and deliberately sits outside ``redact_enabled``:
        an ESC/BEL reaching the operator's terminal is a code-execution-adjacent hazard
        (OSC-8 link spoof, OSC-52 clipboard hijack), not a privacy preference, so it must not
        share an off switch with secret masking. ``redact_enabled`` continues to govern only
        the secret/home-path masking, matching the exporters' ``--no-redact``.
        """
        return redact(strip_controls(text), enabled=self._redact)[0]

    def _degraded(self, now: float, why: str) -> Snapshot[HealthPayload]:
        payload = self._last_good or HealthPayload()
        text = self._safe(why)
        return Snapshot(
            source_id=self.id,
            ts=now,
            reachable=False,
            stale=self._last_good is not None,
            state=SourceState.UNREACHABLE,
            headline=f"health: unreachable — {text}",
            payload=payload,
            age_s=None,
            error=text,
        )

    def _line(self, p: HealthPayload, *, stalled_age: float | None = None) -> str:
        if stalled_age is not None:
            return f"health: SENTINEL DEAD — no sample for {stalled_age:.0f}s (last band {p.band})"
        bits = [
            f"{p.band.upper()}",
            f"phys {p.phys_pct:.0f}%",
            f"commit {p.commit_pct:.0f}%",
            f"{p.procs} procs",
        ]
        if p.gdi_max is not None and p.gdi_max >= 6000:
            bits.append(f"GDI {p.gdi_max}/10000 {p.gdi_max_proc or ''}".strip())
        if p.orphan_count:
            bits.append(f"{p.orphan_count} orphan")
        if p.driver:
            bits.append(f"driver {p.driver}")
        return self._safe("health: " + " · ".join(bits))

    def headline(self, snap: Snapshot[HealthPayload]) -> str:
        return snap.headline

    def render_native(self, snap: Snapshot[HealthPayload]) -> object:
        return snap.payload

    def alert(self, snap: Snapshot[HealthPayload]) -> Alert | None:
        p = snap.payload
        # A dead sentinel is itself alertable: losing the observer is worse than a yellow band,
        # because everything downstream then reads as healthy by default.
        if snap.state is SourceState.STALLED:
            head = self._safe(f"sentinel feed dead ({snap.age_s:.0f}s)")
            return Alert(
                source_id=self.id,
                level="critical",
                headline=head,
                detail=self._safe(snap.error or ""),
                ts=snap.ts,
            )
        rank = _BAND_RANK.get(p.band, 0)
        if rank < 2:
            return None
        head = self._safe(f"workstation {p.band}: {p.driver}")
        detail = self._safe(
            f"phys {p.phys_pct}% · commit {p.commit_pct}% · {p.procs} procs · "
            f"{p.handles} handles · gdi_max {p.gdi_max} · orphans {p.orphan_count}"
        )
        return Alert(
            source_id=self.id,
            level="critical" if rank >= 3 else "warn",
            headline=head,
            detail=detail,
            ts=snap.ts,
        )

    def export_model(self, snap: Snapshot[HealthPayload]) -> ReportDoc:
        """Map the snapshot onto the generic ``ReportDoc``.

        ``generated_at`` derives deterministically from the snapshot's own poll epoch, matching
        ``CodexSource``, so identical snapshots export byte-identically through the shared
        renderers.

        ``rollup`` is EMPTY, matching :class:`~monitorcore.mcp_source.McpSource`. One workstation
        is not a unit queue, so the work-execution keys (total/done/running/idle/tokens) would be
        meaningless here — but the shared renderers do not treat ``rollup`` as an open mapping:
        ``render_md._rollup_line`` and ``render_html`` both index those keys DIRECTLY, so any
        non-empty rollup carrying domain keys raises ``KeyError`` and takes the whole export down
        (measured: ``KeyError: 'total'`` in Markdown, ``KeyError: 'running'`` in HTML). An empty
        rollup is the only correct value for a non-queue source, and it costs nothing here: the
        four counts a rollup would have carried (processes / handles / threads / orphans) are
        already rendered verbatim in the KV block below.
        """
        p = snap.payload
        generated = datetime.fromtimestamp(snap.ts, tz=timezone.utc).isoformat()

        pairs: tuple[tuple[str, str], ...] = (
            ("band", p.band),
            ("driver", p.driver or "none"),
            ("commit %", f"{p.commit_pct}"),
            ("physical %", f"{p.phys_pct}"),
            ("processes", f"{p.procs}"),
            ("handles", f"{p.handles}"),
            ("threads", f"{p.threads}"),
            ("gdi_max", f"{p.gdi_max} ({p.gdi_max_proc or '-'})"),
            ("usr_max", f"{p.usr_max}"),
            ("orphaned MCP runtimes", f"{p.orphan_count}"),
        )
        children: list[Block] = [KV(pairs=pairs)]
        if p.orphan_top:
            children.append(
                Table(
                    headers=("orphaned runtime",),
                    rows=tuple((o,) for o in p.orphan_top),
                )
            )
        if p.census:
            children.append(KV(pairs=tuple((k, str(v)) for k, v in p.census)))
        if snap.error:
            children.append(Text(text=f"error: {snap.error}"))

        return ReportDoc(
            title=f"system health — {p.band}",
            generated_at=generated,
            subtitle=snap.headline,
            rollup=(),
            active=snap.state in (SourceState.ERROR, SourceState.STALLED),
            blocks=(
                # NOT ``card=True``. A card is the work-unit ENTITY renderer: ``render_md._card``
                # (and its HTML twin) emit model / tokens / tool-calls / task / output and never
                # look at ``children``, so a card here rendered an empty "0 tokens - 0 tool calls"
                # shell and silently dropped every KV and Table below it. A plain group section
                # renders its children inline, which is what this domain needs — the same choice
                # ``McpSource`` makes, and for the same reason.
                Section(
                    title="workstation liveness",
                    anchor="health",
                    badge=p.band,
                    children=tuple(children),
                ),
            ),
        )
