#!/usr/bin/env python
"""longhaul watch — a preemption-safe watchdog that also pauses work before the cap.

One watch process looks after the calls of ONE profile, the one the user chose,
recorded in an append-only call ledger (``calls.jsonl``). Each tick it:

1. pauses: if the profile is at its line, or the total is at the global line
   (``longhaul_budget.pause_targets``), every still-running call on it is
   cancelled with its containers terminated, so the job stops at a checkpoint
   before the provider's hard stop. A ``stopped`` marker is appended so the
   paused calls are never respawned;
2. respawns: a call that FINISHED WITH AN ERROR is spawned again from its
   recorded recipe, on the SAME profile, at most ``max_respawn`` times. The
   default is 0, so respawning is something a launcher opts into per call;
3. leaves everything else alone.

WHY "RUNNING" INCLUDES "LOOKS FAILED". After a preemption Modal restarts the
input itself; its status can read FAILURE for 13-20 minutes while
``FunctionCall.get(timeout=0)`` still raises ``TimeoutError``. Cancelling or
respawning then kills a live restart and throws away the work it was about to
resume (measured 2026-10-24, when exactly that happened). So a call is only
"error" once ``get()`` raises something other than ``TimeoutError`` AND the
input's own status in the call graph is terminal. One signal is not enough: a
machine that loses DNS (it happened twice on 2026-10-29/30) makes ``get()`` raise
too, and respawning then would duplicate live work. An unreadable state counts
as running.

WHAT IT NEVER DOES. It never moves work to another account: a call on a paused
profile is not respawned anywhere, and there is no code here that names a
different profile. It never cancels a live call except to pause before the cap.

The decision function ``plan_tick`` is pure; ``ModalCalls`` is the thin adapter
over the Modal SDK, imported lazily so the rest of the module (and its tests)
never load it.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

RUNNING = "running"
DONE = "done"
ERROR = "error"
# Input statuses (modal.call_graph.InputStatus) that end a call without success.
_TERMINAL_FAILURES = frozenset({"FAILURE", "INIT_FAILURE", "TERMINATED", "TIMEOUT"})


@dataclass(frozen=True)
class CallState:
    kind: str  # RUNNING (includes Modal's own restart window) | DONE | ERROR
    detail: str = ""


@dataclass(frozen=True)
class Action:
    kind: str  # "pause" | "respawn" | "give-up"
    key: tuple[str, str]
    row: dict
    reason: str


@dataclass(frozen=True)
class Plan:
    actions: tuple[Action, ...]
    pending: int


def read_calls(path: str | Path) -> list[dict]:
    """The call ledger, one JSON object per line. A corrupt line is fatal:
    skipping it could hide a running call from the pause."""
    p = Path(path)
    if not p.is_file():
        return []
    rows: list[dict] = []
    for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"{p}:{lineno}: corrupt call-ledger line: {exc}") from None
        if not isinstance(row, dict):
            raise ValueError(f"{p}:{lineno}: call-ledger line must be an object")
        rows.append(row)
    return rows


def append_call(path: str | Path, row: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _key(row: dict) -> tuple[str, str]:
    return str(row.get("group", "")), str(row.get("label", ""))


def chains(rows: list[dict], profile: str) -> dict[tuple[str, str], tuple[dict, int]]:
    """Latest row and attempt count per (group, label) for one profile.

    A chain whose latest row is a ``stopped`` marker was ended on purpose and is
    skipped by every later tick.
    """
    latest: dict[tuple[str, str], dict] = {}
    count: dict[tuple[str, str], int] = {}
    for row in rows:
        if row.get("profile") != profile:
            continue
        key = _key(row)
        latest[key] = row
        if row.get("call_id") and not row.get("stopped"):
            count[key] = count.get(key, 0) + 1
    return {k: (r, count.get(k, 0)) for k, r in latest.items()}


def plan_tick(
    rows: list[dict],
    states: dict[str, CallState],
    profile: str,
    pause_reason: str,
) -> Plan:
    """What to do this tick for ``profile``. Pure.

    ``states`` maps call_id -> CallState for the latest live call of each chain.
    ``pause_reason`` is non-empty when the profile must pause now.
    """
    actions: list[Action] = []
    pending = 0
    for key, (row, attempts) in sorted(chains(rows, profile).items()):
        if row.get("stopped") or not row.get("call_id"):
            continue
        state = states.get(str(row["call_id"]), CallState(RUNNING, "unknown"))
        if state.kind == DONE:
            continue
        if state.kind == RUNNING:
            if pause_reason:
                actions.append(Action("pause", key, row, pause_reason))
            else:
                pending += 1
            continue
        # Finished with an error.
        allowed = int(row.get("max_respawn") or 0)
        if pause_reason:
            actions.append(
                Action(
                    "give-up",
                    key,
                    row,
                    f"{state.detail}; not respawned: {pause_reason}",
                )
            )
        elif not isinstance(row.get("spawn"), dict) or attempts > allowed:
            actions.append(
                Action(
                    "give-up",
                    key,
                    row,
                    f"{state.detail}; {attempts} attempt(s), max_respawn {allowed}",
                )
            )
        else:
            actions.append(Action("respawn", key, row, state.detail))
            pending += 1
    return Plan(tuple(actions), pending)


def stamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ModalCalls:
    """Adapter over modal.FunctionCall / modal.Function for the current profile.

    The caller scopes the process to one profile first (``MODAL_PROFILE`` set,
    ``MODAL_TOKEN_*`` removed), so the default client IS that profile and no
    credential handling lives here.
    """

    def __init__(self, modal_module: object = None) -> None:
        if modal_module is None:
            import modal  # noqa: PLC0415 - deliberate: only the watch loop loads the SDK

            modal_module = modal
        self.modal = modal_module

    def state(self, call_id: str) -> CallState:
        """Classify a call, needing TWO signals before calling it a finished error.

        ``get(timeout=0)`` raising ``TimeoutError`` means running (or restarting).
        Any other exception might be the job's own failure, or might be this
        machine losing the network; respawning on the latter would duplicate
        live work. So an exception is only an ERROR once the input's own status
        in the call graph is terminal and not successful. If that cannot be
        read, the call is treated as running: nothing is cancelled or respawned
        on an unknown state.
        """
        call = self.modal.FunctionCall.from_id(call_id)  # type: ignore[attr-defined]
        try:
            call.get(timeout=0)
        except TimeoutError:
            return CallState(RUNNING)
        except Exception as exc:  # noqa: BLE001 - classified below
            first = f"{type(exc).__name__}: {str(exc)[:160]}"
        else:
            return CallState(DONE)
        try:
            graph = call.get_call_graph()
            statuses = {
                str(getattr(info.status, "name", info.status)) for info in graph
            }
        except Exception as exc:  # noqa: BLE001 - unknown is treated as running
            return CallState(
                RUNNING,
                f"unconfirmed ({first}); call graph unreadable: {type(exc).__name__}",
            )
        if "PENDING" in statuses or not statuses:
            return CallState(RUNNING, f"unconfirmed ({first}); input pending")
        if statuses & _TERMINAL_FAILURES:
            return CallState(ERROR, first)
        if statuses <= {"SUCCESS"}:
            return CallState(DONE, f"finished; output unreadable ({first})")
        return CallState(
            RUNNING, f"unconfirmed ({first}); input status {sorted(statuses)}"
        )

    def cancel(self, call_id: str) -> None:
        self.modal.FunctionCall.from_id(call_id).cancel(terminate_containers=True)

    def spawn(self, recipe: dict) -> str:
        fn = self.modal.Function.from_name(str(recipe["app"]), str(recipe["function"]))
        options = recipe.get("options") or {}
        if options:
            fn = fn.with_options(**options)
        call = fn.spawn(*(recipe.get("args") or []), **(recipe.get("kwargs") or {}))
        return str(call.object_id)


def run_tick(
    calls_path: str | Path,
    profile: str,
    pause_reason: str,
    backend: object,
    say: object = print,
) -> Plan:
    """One tick: read the ledger, probe live calls, act, and record what was done."""
    rows = read_calls(calls_path)
    live = [
        r
        for r, _n in chains(rows, profile).values()
        if r.get("call_id") and not r.get("stopped")
    ]
    states = {str(r["call_id"]): backend.state(str(r["call_id"])) for r in live}  # type: ignore[attr-defined]
    plan = plan_tick(rows, states, profile, pause_reason)
    for act in plan.actions:
        group, label = act.key
        old = str(act.row["call_id"])
        if act.kind == "pause":
            backend.cancel(old)  # type: ignore[attr-defined]
            append_call(
                calls_path,
                {
                    "group": group,
                    "label": label,
                    "profile": profile,
                    "stopped": True,
                    "last_call": old,
                    "reason": f"paused: {act.reason}",
                    "at": stamp(),
                },
            )
            say(f"{stamp()} PAUSE {profile} {group} {label} {old}: {act.reason}")  # type: ignore[operator]
        elif act.kind == "respawn":
            new = backend.spawn(act.row["spawn"])  # type: ignore[attr-defined]
            row = {
                k: v
                for k, v in act.row.items()
                if k not in ("call_id", "replaces", "reason")
            }
            row.update(
                {
                    "call_id": new,
                    "replaces": old,
                    "reason": f"watchdog: {act.reason}",
                    "spawned_at": stamp(),
                }
            )
            append_call(calls_path, row)
            say(f"{stamp()} RESPAWN {profile} {group} {label}: {act.reason} -> {new}")  # type: ignore[operator]
        else:
            append_call(
                calls_path,
                {
                    "group": group,
                    "label": label,
                    "profile": profile,
                    "stopped": True,
                    "last_call": old,
                    "reason": f"gave up: {act.reason}",
                    "at": stamp(),
                },
            )
            say(f"{stamp()} GIVE-UP {profile} {group} {label} {old}: {act.reason}")  # type: ignore[operator]
    return plan
