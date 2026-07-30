#!/usr/bin/env python3
"""Mechanical plan-lint stage-0 + cross-session resume manifest (gem G.6).

Two cheap, deterministic, *no-LLM* facilities that run BEFORE the expensive
Opus/Fable reviewer fan-out of the ``/plan-gate`` Workflow:

1. ``lint(plan)`` -- a mechanical stage-0 sanity pass over a decomposed plan:

     * WU-size ceiling  -- every work unit touches <= ``MAX_FILES`` files
       (default 5); a fat WU means the scope was not decomposed and one
       subagent will fight itself over a broad ``git add``.
     * no overlapping scopes -- no two work units may target the same file
       (or a file matched by another WU's glob); overlapping scopes are the
       recorded root cause of "parallel worktree agents contaminate the shared
       index" (feedback_parallel_agent_worktree).
     * DAG check -- the ``deps`` graph must be acyclic, self-loop-free, and
       reference only declared work units; a cycle deadlocks the barrier.
     * one-level nesting -- if a WU declares a ``parent`` its chain depth must
       be <= 1 (workflow-authoring forbids deep nesting).

   Running this FIRST is the cheap gate: a dirty plan is caught by ~1 ms of
   Python instead of by N parallel Opus reviewers (the G.6 "plan-lint stage-0
   BEFORE spawning Opus reviewers" find).

2. A cross-session **resume manifest** -- ``done.jsonl`` plus write-ahead
   ``partial`` records. Native Claude resume is same-session only; when a
   teammate subagent dies on a session cut the cohort re-does completed work.
   The manifest retires that: mark a WU ``partial`` (write-ahead) *before* it
   runs, ``done`` after it commits, and on resume replay ``done.jsonl`` to skip
   finished WUs and re-drive only the ``pending`` + crashed-``partial`` ones.

Design constraints (gem-hunt council C5, BUILD-CHARTER anti-overfit):

  * SHADOW MODE ONLY. This module observes, lints and records; it NEVER blocks,
    nags, or raises to the caller. Every entry point returns a structured
    result and the CLI always exits 0. The verdict lives in the marker + a
    bounded rotating shadow sink, never in an exit code. Promoting stage-0 to
    an ENFORCE gate that *skips* the reviewers on ``dirty`` is a separate,
    deferred step.
  * Rides the existing bus: pure stdlib, reuses the harness ``EventLedger`` when
    importable, and writes its shadow log to a bounded auto-rotating jsonl sink
    (never the main ledger, per C5 (iii)). No new runtime, no trained critic,
    no vector store.
  * Inert until invoked. Nothing imports or runs this unless the ``/plan-gate``
    Workflow (or the CLI) calls it explicitly.

Evidence: MASTER-DECISION-QUEUE G.6 (workflow-improve #7/#10); COUNCIL-VERDICT
C5 (shadow ladder + bounded rotating sink); feedback_parallel_agent_worktree;
feedback_workflow_orchestration (barrier-deadlock + teammates-die-redo).

Usage (from the /plan-gate Workflow or a shell)::

    python plan_lint_stage0.py --plan plan.json
    python plan_lint_stage0.py --plan .beads/plans/active-plan.md --json
    python plan_lint_stage0.py --plan plan.json --max-files 5

    # resume manifest
    python plan_lint_stage0.py --manifest .beads/context/resume --resume
    python plan_lint_stage0.py --manifest .beads/context/resume --mark-partial WU3
    python plan_lint_stage0.py --manifest .beads/context/resume --mark-done WU3

    # resume manifest -- work-list supplied inline (a saved Workflow's unit list is
    # a JS array, NOT a plan file, so --plan cannot name its units)
    python plan_lint_stage0.py --manifest R --ids WU1,WU2,WU3 --resume --json
    python plan_lint_stage0.py --manifest R --ids WU1,WU2,WU3 --next   # to-run ids only

Importable API::

    from plan_lint_stage0 import lint, ResumeManifest
    result = lint(plan)                 # dict; result["verdict"] in {clean,dirty,na}
    mani = ResumeManifest(base)
    mani.mark_partial("WU3")            # write-ahead, before the WU runs
    mani.mark_done("WU3")              # after it commits
    state = mani.resume(all_wu_ids)     # {done, partial, failed, pending}
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

VERDICT_CLEAN = "clean"
VERDICT_DIRTY = "dirty"
VERDICT_NA = "na"

MAX_FILES_DEFAULT = 5
MAX_NEST_DEPTH = 1  # one-level nesting only

# Liberal key aliases so the linter reads plans written by different authors.
_ID_KEYS = ("id", "wu", "wu_id", "name", "key")
_FILE_KEYS = ("files", "scope", "targets", "target_files", "paths", "file_scope")
_DEP_KEYS = ("deps", "depends_on", "dependencies", "after", "needs")
_PARENT_KEYS = ("parent", "parent_id", "of")
_UNIT_KEYS = ("work_units", "units", "wus", "workunits", "tasks", "plan")

_GLOB_CHARS = re.compile(r"[*?\[\]]")

# Shadow sink: bounded + auto-rotating (C5 (iii)). Never the main ledger.
_SHADOW_MAX_BYTES = 512 * 1024
_SHADOW_ROTATE_KEEP = 3


# --------------------------------------------------------------------------- #
# Result dataclasses
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Violation:
    """One mechanical lint failure. ``kind`` is a stable machine slug."""

    kind: str
    wu: str
    detail: str
    related: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["related"] = list(self.related)
        return d


@dataclass
class LintResult:
    verdict: str
    marker: str
    wu_count: int
    max_files: int
    violations: list[Violation] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "marker": self.marker,
            "wu_count": self.wu_count,
            "max_files": self.max_files,
            "violations": [v.to_dict() for v in self.violations],
            "reason": self.reason,
            "shadow": True,
        }


# --------------------------------------------------------------------------- #
# Plan parsing (liberal)
# --------------------------------------------------------------------------- #


def _first(d: dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                # a dep expressed as {"id": "WU1"} or a file as {"path": "x"}
                nested = _first(item, _ID_KEYS + ("path", "file"))
                if isinstance(nested, str):
                    out.append(nested)
        return out
    return []


def _norm_path(p: str) -> str:
    """Normalise a scope entry for comparison (forward slashes, no ./)."""
    p = p.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


@dataclass
class WorkUnit:
    id: str
    files: list[str]
    deps: list[str]
    parent: str | None = None


def normalise_plan(plan: Any) -> list[WorkUnit]:
    """Coerce a variety of plan shapes into a list of ``WorkUnit``.

    Accepts: a list of unit dicts; a dict with a ``work_units``/``units``/...
    key; or a dict mapping id -> unit-dict. Returns ``[]`` for anything with no
    recognisable work units (caller maps that to verdict ``na``).
    """
    units_raw: Any = None
    if isinstance(plan, list):
        units_raw = plan
    elif isinstance(plan, dict):
        units_raw = _first(plan, _UNIT_KEYS)
        if units_raw is None:
            # maybe an id -> unit mapping, but only if the values look like units
            if plan and all(isinstance(v, dict) for v in plan.values()):
                units_raw = [{**v, "id": v.get("id", k)} for k, v in plan.items()]
    if not isinstance(units_raw, list):
        return []

    units: list[WorkUnit] = []
    for idx, raw in enumerate(units_raw):
        if not isinstance(raw, dict):
            continue
        wid = _first(raw, _ID_KEYS)
        if not isinstance(wid, str) or not wid.strip():
            wid = f"WU{idx + 1}"
        files = [_norm_path(f) for f in _as_list(_first(raw, _FILE_KEYS)) if f.strip()]
        deps = [d.strip() for d in _as_list(_first(raw, _DEP_KEYS)) if d.strip()]
        parent = _first(raw, _PARENT_KEYS)
        parent = parent.strip() if isinstance(parent, str) and parent.strip() else None
        units.append(WorkUnit(id=wid.strip(), files=files, deps=deps, parent=parent))
    return units


def load_plan(path: str | os.PathLike[str]) -> Any:
    """Load a plan from a ``.json`` file, or extract an embedded JSON plan
    block from a markdown file. Returns the parsed object, or ``None``.

    Markdown extraction looks for a fenced ```` ```json ```` / ```` ```plan ````
    block that parses to a plan (list, or dict with a recognised units key).
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    # Straight JSON first.
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    # Fenced code blocks in markdown.
    for match in re.finditer(r"```(?:json|plan)?\s*\n(.*?)```", text, re.DOTALL):
        try:
            obj = json.loads(match.group(1))
        except (ValueError, TypeError):
            continue
        if normalise_plan(obj):
            return obj
    return None


# --------------------------------------------------------------------------- #
# The mechanical checks
# --------------------------------------------------------------------------- #


def _scopes_conflict(a: str, b: str) -> bool:
    """Do two scope entries collide?

    Sound for the common concrete-path case (no false negatives): identical
    entries collide, and a literal path colliding with a glob is caught via
    ``fnmatch`` in both directions. Glob-vs-glob only collides when identical
    (full glob-intersection is undecidable; we never *miss* a literal clash,
    which is the real worktree-contamination risk).
    """
    if a == b:
        return True
    a_glob = bool(_GLOB_CHARS.search(a))
    b_glob = bool(_GLOB_CHARS.search(b))
    if a_glob and not b_glob:
        return fnmatch.fnmatch(b, a)
    if b_glob and not a_glob:
        return fnmatch.fnmatch(a, b)
    return False


def _check_overlaps(units: Sequence[WorkUnit]) -> list[Violation]:
    violations: list[Violation] = []
    for i in range(len(units)):
        for j in range(i + 1, len(units)):
            ua, ub = units[i], units[j]
            clashes: set[str] = set()
            for fa in ua.files:
                for fb in ub.files:
                    if _scopes_conflict(fa, fb):
                        clashes.add(fa if fa == fb else f"{fa} ~ {fb}")
            if clashes:
                violations.append(
                    Violation(
                        kind="overlapping_scope",
                        wu=ua.id,
                        detail=(
                            f"scope overlaps {ub.id}: " + ", ".join(sorted(clashes))
                        ),
                        related=(ub.id,),
                    )
                )
    return violations


def _check_sizes(units: Sequence[WorkUnit], max_files: int) -> list[Violation]:
    out: list[Violation] = []
    for u in units:
        if len(u.files) > max_files:
            out.append(
                Violation(
                    kind="oversized_scope",
                    wu=u.id,
                    detail=f"{len(u.files)} files > max {max_files}: decompose further",
                )
            )
    return out


def _check_dag(units: Sequence[WorkUnit]) -> list[Violation]:
    out: list[Violation] = []
    ids = {u.id for u in units}

    # duplicate ids
    seen: set[str] = set()
    for u in units:
        if u.id in seen:
            out.append(
                Violation(kind="duplicate_id", wu=u.id, detail="work-unit id repeated")
            )
        seen.add(u.id)

    # missing / self deps
    graph: dict[str, list[str]] = {}
    for u in units:
        clean_deps: list[str] = []
        for d in u.deps:
            if d == u.id:
                out.append(
                    Violation(kind="self_dep", wu=u.id, detail="depends on itself")
                )
                continue
            if d not in ids:
                out.append(
                    Violation(
                        kind="missing_dep",
                        wu=u.id,
                        detail=f"depends on undeclared work unit '{d}'",
                        related=(d,),
                    )
                )
                continue
            clean_deps.append(d)
        graph.setdefault(u.id, []).extend(clean_deps)

    # cycle detection over the clean (existing-only) edges via DFS colouring
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {u.id: WHITE for u in units}

    def _visit(node: str, stack: list[str]) -> None:
        colour[node] = GREY
        for nxt in graph.get(node, ()):  # noqa: B007
            if colour.get(nxt) == GREY:
                cyc = stack[stack.index(nxt) :] + [nxt] if nxt in stack else [node, nxt]
                out.append(
                    Violation(
                        kind="cycle",
                        wu=node,
                        detail="dependency cycle: " + " -> ".join(cyc),
                        related=tuple(cyc),
                    )
                )
            elif colour.get(nxt) == WHITE:
                _visit(nxt, stack + [nxt])
        colour[node] = BLACK

    for u in units:
        if colour[u.id] == WHITE:
            _visit(u.id, [u.id])

    # dedupe cycle violations (a cycle is discovered once per entry node)
    seen_cycles: set[frozenset[str]] = set()
    deduped: list[Violation] = []
    for v in out:
        if v.kind == "cycle":
            key = frozenset(v.related)
            if key in seen_cycles:
                continue
            seen_cycles.add(key)
        deduped.append(v)
    return deduped


def _check_nesting(units: Sequence[WorkUnit]) -> list[Violation]:
    out: list[Violation] = []
    by_id = {u.id: u for u in units}
    for u in units:
        depth = 0
        cur = u.parent
        guard = 0
        while cur is not None and guard <= len(units) + 1:
            depth += 1
            if depth > MAX_NEST_DEPTH:
                out.append(
                    Violation(
                        kind="deep_nesting",
                        wu=u.id,
                        detail=f"nesting depth {depth} > {MAX_NEST_DEPTH} (one-level only)",
                    )
                )
                break
            nxt = by_id.get(cur)
            cur = nxt.parent if nxt else None
            guard += 1
    return out


def lint(plan: Any, *, max_files: int = MAX_FILES_DEFAULT) -> LintResult:
    """Run every mechanical stage-0 check over ``plan``. SHADOW: never raises.

    ``plan`` may be a normalised list of ``WorkUnit``, a raw list/dict plan, or
    already-parsed JSON. Returns a ``LintResult`` whose ``verdict`` is one of
    ``clean`` / ``dirty`` / ``na``.
    """
    try:
        # Fast-path only for a non-empty list already made of WorkUnit objects;
        # anything else (dict / list-of-dicts / None) goes through normalise.
        if (
            isinstance(plan, list)
            and plan
            and all(isinstance(u, WorkUnit) for u in plan)
        ):
            units = list(plan)
        else:
            units = normalise_plan(plan)
    except Exception as exc:  # pragma: no cover - defensive, shadow never raises
        return LintResult(
            VERDICT_NA, "PLAN_LINT:na", 0, max_files, reason=f"parse error: {exc}"
        )

    if not units:
        return LintResult(
            VERDICT_NA,
            "PLAN_LINT:na",
            0,
            max_files,
            reason="no recognisable work units",
        )

    try:
        violations: list[Violation] = []
        violations += _check_sizes(units, max_files)
        violations += _check_overlaps(units)
        violations += _check_dag(units)
        violations += _check_nesting(units)
    except Exception as exc:  # pragma: no cover - defensive, shadow never raises
        return LintResult(
            VERDICT_NA,
            "PLAN_LINT:na",
            len(units),
            max_files,
            reason=f"lint error: {exc}",
        )

    if violations:
        verdict = VERDICT_DIRTY
        marker = "PLAN_LINT:dirty"
        reason = f"{len(violations)} violation(s) across {len(units)} work unit(s)"
    else:
        verdict = VERDICT_CLEAN
        marker = "PLAN_LINT:clean"
        reason = f"{len(units)} work unit(s) passed stage-0"
    return LintResult(verdict, marker, len(units), max_files, violations, reason)


# --------------------------------------------------------------------------- #
# Cross-session resume manifest (done.jsonl + write-ahead partials)
# --------------------------------------------------------------------------- #

STATE_PARTIAL = "partial"
STATE_DONE = "done"
STATE_FAILED = "failed"
_TERMINAL_STATES = {STATE_DONE, STATE_FAILED}


@dataclass
class ResumeState:
    done: list[str] = field(default_factory=list)
    partial: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResumeManifest:
    """Append-only, durable, cross-session work-unit manifest.

    Records are one JSON object per line in ``<base>/done.jsonl``. Each write
    is flushed + ``fsync``-ed so a mid-WU crash still leaves the write-ahead
    ``partial`` marker on disk (the whole point: never silently redo).
    """

    def __init__(
        self, base: str | os.PathLike[str], filename: str = "done.jsonl"
    ) -> None:
        self.base = Path(base)
        self.path = self.base / filename

    # -- writing --------------------------------------------------------- #

    def _append(
        self, wu_id: str, state: str, meta: dict[str, Any] | None
    ) -> dict[str, Any]:
        self.base.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": time.time(),
            "wu_id": wu_id,
            "state": state,
            "meta": meta or {},
        }
        line = json.dumps(record, ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:  # pragma: no cover - fsync may be unavailable
                pass
        return record

    def mark_partial(self, wu_id: str, **meta: Any) -> dict[str, Any]:
        """WRITE-AHEAD: call *before* the WU runs so a crash is recoverable."""
        return self._append(wu_id, STATE_PARTIAL, meta or None)

    def mark_done(self, wu_id: str, **meta: Any) -> dict[str, Any]:
        """Call after the WU committed successfully."""
        return self._append(wu_id, STATE_DONE, meta or None)

    def mark_failed(self, wu_id: str, **meta: Any) -> dict[str, Any]:
        return self._append(wu_id, STATE_FAILED, meta or None)

    # -- reading --------------------------------------------------------- #

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except (ValueError, TypeError):
                continue  # tolerate a torn last line from a crash mid-write
            if isinstance(obj, dict) and obj.get("wu_id"):
                out.append(obj)
        return out

    def latest_state(self) -> dict[str, str]:
        """Fold the log to the most-recent state per work unit."""
        state: dict[str, str] = {}
        for rec in self.records():
            wu = rec.get("wu_id")
            st = rec.get("state")
            if isinstance(wu, str) and isinstance(st, str):
                state[wu] = st
        return state

    def resume(self, all_wu_ids: Iterable[str] | None = None) -> ResumeState:
        """Classify work units for a resuming session.

        * ``done``     -- completed; skip.
        * ``partial``  -- started (write-ahead) but never reached a terminal
          state -> a crashed WU that must be re-driven (roll back + redo).
        * ``failed``   -- explicitly failed; caller decides retry.
        * ``pending``  -- declared in ``all_wu_ids`` but never seen in the log.
        """
        latest = self.latest_state()
        done = sorted(w for w, s in latest.items() if s == STATE_DONE)
        partial = sorted(w for w, s in latest.items() if s == STATE_PARTIAL)
        failed = sorted(w for w, s in latest.items() if s == STATE_FAILED)
        pending: list[str] = []
        if all_wu_ids is not None:
            seen = set(latest)
            pending = sorted(w for w in dict.fromkeys(all_wu_ids) if w not in seen)
        return ResumeState(done=done, partial=partial, failed=failed, pending=pending)


# --------------------------------------------------------------------------- #
# Shadow sink (bounded, auto-rotating) + best-effort ledger
# --------------------------------------------------------------------------- #


def _shadow_sink_path() -> Path:
    base = os.environ.get("PLAN_LINT_SHADOW_DIR")
    if base:
        return Path(base) / "plan_lint_shadow.jsonl"
    return Path(__file__).resolve().parent / "logs" / "plan_lint_shadow.jsonl"


def _rotate(path: Path) -> None:
    try:
        if path.exists() and path.stat().st_size > _SHADOW_MAX_BYTES:
            for i in range(_SHADOW_ROTATE_KEEP - 1, 0, -1):
                older = path.with_suffix(path.suffix + f".{i}")
                newer = path.with_suffix(path.suffix + f".{i - 1}") if i > 1 else path
                if newer.exists():
                    older.unlink(missing_ok=True)
                    newer.rename(older)
    except OSError:  # pragma: no cover - rotation is best-effort
        pass


def shadow_log(record: dict[str, Any]) -> bool:
    """Append one record to the bounded, auto-rotating shadow sink. Best-effort."""
    path = _shadow_sink_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate(path)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def _load_ledger():  # pragma: no cover - environment-dependent
    """Best-effort import of the shared harness EventLedger. None if unavailable."""
    for cand in (
        os.environ.get("AGENT_HARNESS_DIR"),
        str(Path.home() / ".agents" / "harness"),
    ):
        if not cand:
            continue
        parent = str(Path(cand).parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)
    try:
        from harness.ledger import EventLedger  # type: ignore

        return EventLedger()
    except Exception:
        return None


def emit(
    result: LintResult, *, cwd: str | None = None, to_ledger: bool = True
) -> dict[str, bool]:
    """Record the lint verdict to the shadow sink and (best-effort) ledger.

    SHADOW: log only; returns which sinks accepted the record. Never blocks.
    """
    record = {
        "ts": time.time(),
        "event": "plan_lint",
        "cwd": cwd or os.getcwd(),
        **result.to_dict(),
    }
    sink_ok = shadow_log(record)
    ledger_ok = False
    if to_ledger:
        ledger = _load_ledger()
        if ledger is not None:  # pragma: no cover - environment-dependent
            try:
                ledger.append(
                    cwd or os.getcwd(),
                    "plan_lint",
                    marker=result.marker,
                    verdict=result.verdict,
                    shadow=True,
                    wu_count=result.wu_count,
                    violations=[v.kind for v in result.violations],
                    reason=result.reason,
                )
                ledger_ok = True
            except Exception:
                ledger_ok = False
    return {"shadow_sink": sink_ok, "ledger": ledger_ok}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _format_human(result: LintResult, sinks: dict[str, bool]) -> str:
    lines = [result.marker, f"  {result.reason}"]
    for v in result.violations:
        rel = f" [{', '.join(v.related)}]" if v.related else ""
        lines.append(f"  [{v.kind}] {v.wu}: {v.detail}{rel}")
    written = "written" if sinks.get("shadow_sink") else "skipped"
    lines.append(
        f"  shadow-sink: {written}; ledger: {'written' if sinks.get('ledger') else 'n/a'}"
        " (SHADOW - non-blocking)"
    )
    return "\n".join(lines)


def _run_lint(args: argparse.Namespace) -> int:
    plan = load_plan(args.plan)
    if plan is None:
        result = LintResult(
            VERDICT_NA,
            "PLAN_LINT:na",
            0,
            args.max_files,
            reason=f"no plan at {args.plan}",
        )
    else:
        result = lint(plan, max_files=args.max_files)
    sinks = emit(result, to_ledger=not args.no_ledger)
    if args.json:
        payload = result.to_dict()
        payload["sinks"] = sinks
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_format_human(result, sinks))
    return 0  # SHADOW: always exit 0


def _split_ids(raw: str | None) -> list[str] | None:
    """Parse ``--ids`` into a work-list. Comma- and/or whitespace-separated.

    Returns ``None`` for an absent/blank value so ``resume()`` keeps its
    "no work-list declared -> pending is empty" contract instead of being handed
    an empty list that looks like "zero declared units".
    """
    if raw is None:
        return None
    ids = [tok for tok in re.split(r"[,\s]+", raw.strip()) if tok]
    return ids or None


def _wu_ids(args: argparse.Namespace) -> list[str] | None:
    """The declared work-list: ``--ids`` wins, else the ids inside ``--plan``."""
    ids = _split_ids(getattr(args, "ids", None))
    if ids is not None:
        return ids
    if args.plan:
        plan = load_plan(args.plan)
        units = normalise_plan(plan) if plan is not None else []
        return [u.id for u in units] or None
    return None


def _run_manifest(args: argparse.Namespace) -> int:
    mani = ResumeManifest(args.manifest)
    if args.next:
        # THE ONE-COMMAND RESUME CONTRACT: stdout is exactly the ids still to run
        # (crashed-partial + failed + never-seen-pending), one per line, nothing
        # else -- so a caller can consume it without parsing JSON. Still SHADOW:
        # always exit 0, an empty work-list simply prints nothing.
        state = mani.resume(_wu_ids(args))
        for wu in state.partial + state.failed + state.pending:
            print(wu)
        return 0
    if args.mark_partial:
        mani.mark_partial(args.mark_partial)
        print(f"PLAN_RESUME:partial {args.mark_partial}")
    elif args.mark_done:
        mani.mark_done(args.mark_done)
        print(f"PLAN_RESUME:done {args.mark_done}")
    elif args.mark_failed:
        mani.mark_failed(args.mark_failed)
        print(f"PLAN_RESUME:failed {args.mark_failed}")
    elif args.resume:
        state = mani.resume(_wu_ids(args))
        if args.json:
            print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2))
        else:
            print("PLAN_RESUME:state")
            print(f"  done:    {', '.join(state.done) or '-'}")
            print(
                f"  partial: {', '.join(state.partial) or '-'}  (crashed -> re-drive)"
            )
            print(f"  failed:  {', '.join(state.failed) or '-'}")
            print(f"  pending: {', '.join(state.pending) or '-'}")
    else:
        print(
            "PLAN_RESUME:noop (pass --resume / --mark-partial / --mark-done / --mark-failed)"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="plan_lint_stage0",
        description="Mechanical plan-lint stage-0 + resume manifest (SHADOW; never blocks).",
    )
    parser.add_argument("--plan", default=None, help="path to a JSON or markdown plan")
    parser.add_argument(
        "--max-files", type=int, default=MAX_FILES_DEFAULT, help="per-WU file ceiling"
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument(
        "--no-ledger", action="store_true", help="do not write to the ledger"
    )
    # resume-manifest sub-surface (flag-based to keep one entrypoint)
    parser.add_argument(
        "--manifest", default=None, help="resume-manifest base directory"
    )
    parser.add_argument(
        "--resume", action="store_true", help="print resume classification"
    )
    parser.add_argument(
        "--mark-partial", default=None, metavar="WU", help="write-ahead a WU start"
    )
    parser.add_argument(
        "--mark-done", default=None, metavar="WU", help="record a WU completion"
    )
    parser.add_argument(
        "--mark-failed", default=None, metavar="WU", help="record a WU failure"
    )
    parser.add_argument(
        "--ids",
        default=None,
        metavar="WU1,WU2",
        help="declared work-list, comma/space separated. A saved Workflow's unit "
        "list is a JS array, not a plan file, so --plan cannot name its units",
    )
    parser.add_argument(
        "--next",
        action="store_true",
        help="print ONLY the ids still to run (partial+failed+pending), one per "
        "line -- the one-command resume contract for a fan-out driver",
    )
    args = parser.parse_args(argv)

    if args.manifest:
        return _run_manifest(args)
    if args.plan:
        return _run_lint(args)
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
