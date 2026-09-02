"""Matched stale-monitor (spec 11315) and no-change-monitor (spec 11316) detectors.

The two failure classes are a pair, not two names for one silence bit:

* 11315 — the monitor dies while remote work continues (STALE_MONITOR).
* 11316 — a live monitor that merely has nothing to report is mistaken for
  dead (NO_CHANGE_MONITOR).

They are distinguishable only when the detector consumes **two independent
streams**:

* a monitor heartbeat JSONL whose token advances while the monitor is alive,
  even when work is silent;
* work **byte-growth** (content length). File mtime is never a liveness
  signal: a stalled process and a long-finished tree are indistinguishable
  from mtimes alone, so an mtime-sourced observation is UNDECIDABLE.

Four-cell truth table (monitor alive/dead × work active/idle):

    alive × active → HEALTHY
    alive × idle   → NO_CHANGE_MONITOR
    dead  × active → STALE_MONITOR
    dead  × idle   → UNDECIDABLE  (do not guess either mixed-cell neighbour)

Collapsing the two signals into one bit (OR: any advance; AND: both must
advance) makes the mixed cells indistinguishable and turns four-cell
distinctness red. That mutation is the proof the production pair is not a
single signal in disguise.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Mapping

HEALTHY = "HEALTHY"
NO_CHANGE_MONITOR = "NO_CHANGE_MONITOR"
STALE_MONITOR = "STALE_MONITOR"
UNDECIDABLE = "UNDECIDABLE"

CELL_ALIVE_ACTIVE = "alive-active"
CELL_ALIVE_IDLE = "alive-idle"
CELL_DEAD_ACTIVE = "dead-active"
CELL_DEAD_IDLE = "dead-idle"

CELL_ORDER: tuple[str, str, str, str] = (
    CELL_ALIVE_ACTIVE,
    CELL_ALIVE_IDLE,
    CELL_DEAD_ACTIVE,
    CELL_DEAD_IDLE,
)

EXPECTED_VERDICT: dict[str, str] = {
    CELL_ALIVE_ACTIVE: HEALTHY,
    CELL_ALIVE_IDLE: NO_CHANGE_MONITOR,
    CELL_DEAD_ACTIVE: STALE_MONITOR,
    CELL_DEAD_IDLE: UNDECIDABLE,
}

PLANTED: dict[str, tuple[bool, bool]] = {
    CELL_ALIVE_ACTIVE: (True, True),
    CELL_ALIVE_IDLE: (True, False),
    CELL_DEAD_ACTIVE: (False, True),
    CELL_DEAD_IDLE: (False, False),
}

ACTIVITY = "ACTIVITY"
SILENCE = "SILENCE"

MONITOR_SOURCE = "heartbeat-jsonl"
WORK_SOURCE = "byte-growth"

# Any of these as an observation source forbids a stall/alive guess.
FORBIDDEN_MTIME_SOURCES = frozenset(
    {
        "mtime",
        "mtime_ns",
        "mtime_age",
        "st_mtime",
        "file_mtime",
        "os.utime",
        "Path.stat().st_mtime",
    }
)

WORK_SEED = b"IMP-0451-WORK-SEED\n"
WORK_DELTA = b"IMP-0451-WORK-PROGRESS\n"
HB_TOKEN_T0 = 1
HB_TOKEN_T1 = 2


def _source_forbidden(*sources: Any) -> bool:
    for src in sources:
        if src is None:
            continue
        token = str(src).strip()
        if token in FORBIDDEN_MTIME_SOURCES:
            return True
        lowered = token.lower()
        if "mtime" in lowered or "st_mtime" in lowered:
            return True
    return False


def last_heartbeat_token(path: Path) -> int | None:
    """Last ``token`` on a heartbeat JSONL stream. Never reads mtime."""
    if not path.is_file():
        return None
    last: int | None = None
    text = path.read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        rec = json.loads(line)
        if not isinstance(rec, dict):
            continue
        if "token" not in rec:
            continue
        last = int(rec["token"])
    return last


def work_nbytes(path: Path) -> int:
    """Content length of the work artifact. Never ``st_mtime``."""
    if not path.is_file():
        return 0
    return len(path.read_bytes())


def append_heartbeat(path: Path, token: int, *, kind: str = "monitor.heartbeat") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"kind": kind, "token": int(token), "seq": int(token)}
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def append_work(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as fh:
        fh.write(payload)


def classify(
    *,
    monitor_t0: int | None,
    monitor_t1: int | None,
    work_t0: int,
    work_t1: int,
    monitor_source: str = MONITOR_SOURCE,
    work_source: str = WORK_SOURCE,
) -> dict[str, Any]:
    """Classify one (monitor, work) observation pair.

    Production never guesses. Both signals frozen → UNDECIDABLE, not a copy
    of NO_CHANGE_MONITOR (quiet-alive neighbour) or STALE_MONITOR
    (dead-active neighbour). An mtime-sourced observation is UNDECIDABLE
    even if the integers look like a mixed cell.
    """
    if _source_forbidden(monitor_source, work_source):
        return {
            "verdict": UNDECIDABLE,
            "guessed": False,
            "reason": "mtime-only-forbidden",
            "monitor_source": monitor_source,
            "work_source": work_source,
            "monitor_t0": monitor_t0,
            "monitor_t1": monitor_t1,
            "work_t0": work_t0,
            "work_t1": work_t1,
            "monitor_advanced": False,
            "work_grew": False,
        }

    monitor_known = monitor_t0 is not None and monitor_t1 is not None
    monitor_advanced = bool(monitor_known and int(monitor_t1) > int(monitor_t0))
    work_grew = int(work_t1) > int(work_t0)

    if not monitor_known:
        return {
            "verdict": UNDECIDABLE,
            "guessed": False,
            "reason": "heartbeat-unreadable-do-not-guess",
            "monitor_source": monitor_source,
            "work_source": work_source,
            "monitor_t0": monitor_t0,
            "monitor_t1": monitor_t1,
            "work_t0": work_t0,
            "work_t1": work_t1,
            "monitor_advanced": False,
            "work_grew": work_grew,
        }

    if monitor_advanced and work_grew:
        verdict = HEALTHY
        reason = "heartbeat-advanced-and-work-grew"
    elif monitor_advanced and not work_grew:
        verdict = NO_CHANGE_MONITOR
        reason = "heartbeat-advanced-work-silent-11316"
    elif (not monitor_advanced) and work_grew:
        verdict = STALE_MONITOR
        reason = "heartbeat-frozen-work-grew-11315"
    else:
        verdict = UNDECIDABLE
        reason = "both-signals-frozen-do-not-guess"

    return {
        "verdict": verdict,
        "guessed": False,
        "reason": reason,
        "monitor_source": monitor_source,
        "work_source": work_source,
        "monitor_t0": monitor_t0,
        "monitor_t1": monitor_t1,
        "work_t0": work_t0,
        "work_t1": work_t1,
        "monitor_advanced": monitor_advanced,
        "work_grew": work_grew,
    }


def collapse_or(monitor_advanced: bool, work_grew: bool) -> str:
    """Single-bit OR mutant: any advancing signal → ACTIVITY."""
    return ACTIVITY if (monitor_advanced or work_grew) else SILENCE


def collapse_and(monitor_advanced: bool, work_grew: bool) -> str:
    """Single-bit AND mutant: both signals must advance → ACTIVITY."""
    return ACTIVITY if (monitor_advanced and work_grew) else SILENCE


def four_verdicts_distinct(mapping: Mapping[str, Any]) -> bool:
    vals = [mapping.get(cell) for cell in CELL_ORDER]
    return all(v is not None for v in vals) and len(set(vals)) == 4


def mixed_cells_indistinguishable(mapping: Mapping[str, Any]) -> bool:
    return mapping.get(CELL_ALIVE_IDLE) == mapping.get(CELL_DEAD_ACTIVE)


def naive_silence_is_dead(monitor_advanced: bool, work_grew: bool) -> str:
    """Idle-read-as-dead mutant: work silence is treated as a dead monitor.

    Fires on alive-idle (11316): a live quiet monitor is labelled STALE.
    """
    del monitor_advanced
    if not work_grew:
        return STALE_MONITOR
    return HEALTHY


def naive_any_activity_is_alive(monitor_advanced: bool, work_grew: bool) -> str:
    """Dead-read-as-idle mutant: any activity is treated as a live monitor.

    Fires on dead-active (11315): work continuing after monitor death is
    labelled HEALTHY.
    """
    if monitor_advanced or work_grew:
        return HEALTHY
    return UNDECIDABLE


def _plant_t0(root: Path, cell: str) -> tuple[Path, Path]:
    cell_dir = root / cell
    hb = cell_dir / "heartbeat.jsonl"
    work = cell_dir / "work.bin"
    append_heartbeat(hb, HB_TOKEN_T0)
    append_work(work, WORK_SEED)
    return hb, work


def _advance(hb: Path, work: Path, monitor_alive: bool, work_active: bool) -> None:
    if monitor_alive:
        append_heartbeat(hb, HB_TOKEN_T1)
    if work_active:
        append_work(work, WORK_DELTA)


def _snapshot(hb: Path, work: Path) -> tuple[int | None, int]:
    return last_heartbeat_token(hb), work_nbytes(work)


def _mtime_control() -> dict[str, Any]:
    """Observation whose declared source is mtime must stay UNDECIDABLE.

    Integers are planted to look like a mixed cell (frozen heartbeat, growing
    work) so a detector that ignored the source tag would guess STALE_MONITOR.
    """
    return classify(
        monitor_t0=HB_TOKEN_T0,
        monitor_t1=HB_TOKEN_T0,
        work_t0=len(WORK_SEED),
        work_t1=len(WORK_SEED) + len(WORK_DELTA),
        monitor_source="mtime",
        work_source="st_mtime",
    )


def four_cell_live(root: Path | None = None) -> dict[str, Any]:
    """Plant four live stream pairs and classify each cell.

    The dead-idle cell is constructed as the hardest adversarial cell: it
    carries the same frozen work bytes as alive-idle and the same frozen
    heartbeat token as dead-active. Copying either neighbour's verdict is a
    defect.
    """
    own = root is None
    tmp: tempfile.TemporaryDirectory[str] | None = None
    if own:
        tmp = tempfile.TemporaryDirectory(prefix="imp0451-four-cell-")
        root = Path(tmp.name)
    assert root is not None
    try:
        rows: list[dict[str, Any]] = []
        verdicts: dict[str, str] = {}
        collapsed_or: dict[str, str] = {}
        collapsed_and: dict[str, str] = {}
        naive_silence: dict[str, str] = {}
        naive_any: dict[str, str] = {}

        for cell in CELL_ORDER:
            monitor_alive, work_active = PLANTED[cell]
            hb, work = _plant_t0(root, cell)
            mon_t0, work_t0 = _snapshot(hb, work)
            _advance(hb, work, monitor_alive, work_active)
            mon_t1, work_t1 = _snapshot(hb, work)
            verdict = classify(
                monitor_t0=mon_t0,
                monitor_t1=mon_t1,
                work_t0=work_t0,
                work_t1=work_t1,
                monitor_source=MONITOR_SOURCE,
                work_source=WORK_SOURCE,
            )
            advanced = bool(verdict["monitor_advanced"])
            grew = bool(verdict["work_grew"])
            collapsed_or[cell] = collapse_or(advanced, grew)
            collapsed_and[cell] = collapse_and(advanced, grew)
            naive_silence[cell] = naive_silence_is_dead(advanced, grew)
            naive_any[cell] = naive_any_activity_is_alive(advanced, grew)
            expected = EXPECTED_VERDICT[cell]
            rows.append(
                {
                    "cell": cell,
                    "planted_monitor_alive": monitor_alive,
                    "planted_work_active": work_active,
                    "verdict": verdict,
                    "match": verdict["verdict"] == expected,
                }
            )
            verdicts[cell] = verdict["verdict"]

        mtime_control = _mtime_control()
        any_guess = any(bool(r["verdict"]["guessed"]) for r in rows)
        all_match = all(bool(r["match"]) for r in rows)
        four_distinct = four_verdicts_distinct(verdicts)
        or_mixed = mixed_cells_indistinguishable(collapsed_or)
        and_mixed = mixed_cells_indistinguishable(collapsed_and)
        production_mixed = mixed_cells_indistinguishable(verdicts)

        idle_read_as_dead = naive_silence[CELL_ALIVE_IDLE] == STALE_MONITOR
        dead_read_as_idle = naive_any[CELL_DEAD_ACTIVE] == HEALTHY

        return {
            "verdicts": verdicts,
            "rows": rows,
            "four_distinct": four_distinct,
            "all_match": all_match,
            "any_guess": any_guess,
            "collapsed_or": collapsed_or,
            "collapsed_and": collapsed_and,
            "or_mixed_indistinguishable": or_mixed,
            "and_mixed_indistinguishable": and_mixed,
            "production_mixed_indistinguishable": production_mixed,
            "naive_silence_is_dead": naive_silence,
            "naive_any_activity_is_alive": naive_any,
            "idle_read_as_dead": idle_read_as_dead,
            "dead_read_as_idle": dead_read_as_idle,
            "mtime_control": mtime_control,
            "mtime_forbidden_undecidable": (
                mtime_control["verdict"] == UNDECIDABLE
                and mtime_control["guessed"] is False
            ),
        }
    finally:
        if tmp is not None:
            tmp.cleanup()


def hardest_cell_undecidable(table: Mapping[str, Any]) -> dict[str, Any]:
    """Adversarial refuter: dead×idle must stay UNDECIDABLE.

    Same frozen work values as the quiet-alive neighbour (11316) and same
    frozen heartbeat values as the stale-monitor neighbour (11315). Inheriting
    either mixed-cell verdict is a guess and a defect.
    """
    rows = list(table.get("rows") or [])
    by_cell = {r.get("cell"): r for r in rows if isinstance(r, dict)}
    hard = by_cell.get(CELL_DEAD_IDLE) or {}
    idle = by_cell.get(CELL_ALIVE_IDLE) or {}
    stale = by_cell.get(CELL_DEAD_ACTIVE) or {}
    hv = hard.get("verdict") if isinstance(hard.get("verdict"), dict) else {}
    iv = idle.get("verdict") if isinstance(idle.get("verdict"), dict) else {}
    sv = stale.get("verdict") if isinstance(stale.get("verdict"), dict) else {}

    verdict = hv.get("verdict")
    guessed = bool(hv.get("guessed"))
    inherited_no_change = verdict == NO_CHANGE_MONITOR
    inherited_stale = verdict == STALE_MONITOR
    same_work = hv.get("work_t0") == iv.get("work_t0") and hv.get("work_t1") == iv.get(
        "work_t1"
    )
    same_monitor = hv.get("monitor_t0") == sv.get("monitor_t0") and hv.get(
        "monitor_t1"
    ) == sv.get("monitor_t1")
    passed = (
        verdict == UNDECIDABLE
        and not guessed
        and not inherited_no_change
        and not inherited_stale
        and same_work is True
        and same_monitor is True
        and hv.get("work_t0") == hv.get("work_t1")
        and hv.get("monitor_t0") == hv.get("monitor_t1")
    )
    return {
        "cell": CELL_DEAD_IDLE,
        "verdict": verdict,
        "guessed": guessed,
        "reason": hv.get("reason"),
        "inherited_no_change_verdict": inherited_no_change,
        "inherited_stale_verdict": inherited_stale,
        "same_work_frozen_as_alive_idle": same_work,
        "same_monitor_frozen_as_dead_active": same_monitor,
        "pass": passed,
        "monitor_t0": hv.get("monitor_t0"),
        "monitor_t1": hv.get("monitor_t1"),
        "work_t0": hv.get("work_t0"),
        "work_t1": hv.get("work_t1"),
    }


def main() -> int:
    table = four_cell_live()
    hard = hardest_cell_undecidable(table)
    print(json.dumps(table["verdicts"], sort_keys=True))
    print(
        "four_distinct={0} all_match={1} any_guess={2}".format(
            table["four_distinct"], table["all_match"], table["any_guess"]
        )
    )
    print("hardest", json.dumps(hard, sort_keys=True))
    ok = (
        table["all_match"]
        and table["four_distinct"]
        and not table["any_guess"]
        and not table["production_mixed_indistinguishable"]
        and table["or_mixed_indistinguishable"]
        and table["and_mixed_indistinguishable"]
        and table["idle_read_as_dead"]
        and table["dead_read_as_idle"]
        and table["mtime_forbidden_undecidable"]
        and hard["pass"]
    )
    print("SUCCESS:monitor_states" if ok else "FAILED:monitor_states")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
