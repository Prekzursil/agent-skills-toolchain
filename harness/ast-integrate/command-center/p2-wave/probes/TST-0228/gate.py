#!/usr/bin/env python3
"""Per-call capability gate (TST-0228 live SUT).

Catalog inputs tools/lib/workspace.mjs and tools/lib/net-allowlist.mjs are
absent on this worktree. This module is the runtime under test: a unit's
granted capabilities are re-evaluated on every tool call, so a mid-run
revoke takes effect on the next invoke of that capability.

StartTimeOnlyGate is the known-broken negative control: it snapshots
grants at unit start and ignores later revokes. OneMoreCallGate is a
second mutant that allows one extra use after revoke, so "denial within
one call" is not vacuously true of every denier.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

CODE_OK = "OK"
CODE_DENIED = "CAPABILITY_DENIED"
CODE_REVOKED = "CAPABILITY_REVOKED"
CODE_UNKNOWN_TOOL = "UNKNOWN_TOOL"

VOCABULARY = ("Read", "Grep", "Bash", "Write")
WRITE_MARKER = "write-side-effect.bin"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_ns() -> int:
    return time.time_ns()


def new_id(prefix: str) -> str:
    # os.urandom: repo-root `platform/` shadows stdlib, so uuid is unusable.
    return f"{prefix}-{os.urandom(8).hex()}"


@dataclass
class CallResult:
    ok: bool
    code: str
    message: str
    tool: str
    seq: int
    t_ns: int
    event_id: str
    wrote: bool
    dest_sha256: str | None
    revocation_event_id: str | None = None
    revocation_t_ns: int | None = None
    observed_error: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "message": self.message,
            "tool": self.tool,
            "seq": self.seq,
            "t_ns": self.t_ns,
            "event_id": self.event_id,
            "wrote": self.wrote,
            "dest_sha256": self.dest_sha256,
            "revocation_event_id": self.revocation_event_id,
            "revocation_t_ns": self.revocation_t_ns,
            "observed_error": self.observed_error,
        }


@dataclass
class Event:
    kind: str
    t_ns: int
    seq: int
    event_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        row = {
            "kind": self.kind,
            "t_ns": self.t_ns,
            "seq": self.seq,
            "event_id": self.event_id,
        }
        row.update(self.payload)
        return row


class CapabilityRevoked(Exception):
    """Typed error the running unit observes on a post-revoke invoke."""

    def __init__(self, result: CallResult) -> None:
        super().__init__(result.message)
        self.result = result
        self.code = result.code


class BaseGate:
    """Shared bookkeeping. Subclasses differ only in when they consult grants."""

    name = "base"

    def __init__(
        self,
        granted: Iterable[str],
        dest: Path,
        unit_id: str = "TST-0228",
        raise_on_deny: bool = False,
    ) -> None:
        unknown = [g for g in granted if g not in VOCABULARY]
        if unknown:
            raise ValueError(f"unknown capabilities: {unknown}")
        self.unit_id = unit_id
        self.dest = Path(dest)
        self.dest.mkdir(parents=True, exist_ok=True)
        self.raise_on_deny = raise_on_deny
        self.start_grants = tuple(dict.fromkeys(granted))
        self.live_grants: set[str] = set(self.start_grants)
        self.revoked: dict[str, Event] = {}
        self.events: list[Event] = []
        self.calls: list[CallResult] = []
        self._seq = 0
        self.started = False
        self.restart_count = 0
        self.run_id = new_id("run")
        t0 = now_ns()
        self.events.append(
            Event(
                kind="unit-start",
                t_ns=t0,
                seq=0,
                event_id=new_id("start"),
                payload={
                    "run_id": self.run_id,
                    "granted": list(self.start_grants),
                    "gate": self.name,
                },
            )
        )
        self.started = True

    def restart(self) -> None:
        """Simulate a new unit start (re-snapshots grants from live set)."""
        self.restart_count += 1
        self.start_grants = tuple(sorted(self.live_grants))
        self._seq = 0
        self.revoked.clear()
        t0 = now_ns()
        self.events.append(
            Event(
                kind="unit-restart",
                t_ns=t0,
                seq=0,
                event_id=new_id("restart"),
                payload={
                    "run_id": self.run_id,
                    "granted": list(self.start_grants),
                    "restart_count": self.restart_count,
                },
            )
        )

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _record(self, kind: str, payload: dict[str, Any], seq: int | None = None) -> Event:
        ev = Event(
            kind=kind,
            t_ns=now_ns(),
            seq=self._seq if seq is None else seq,
            event_id=new_id(kind[:8]),
            payload=payload,
        )
        self.events.append(ev)
        return ev

    def effective_grants(self) -> set[str]:
        raise NotImplementedError

    def revoke(self, capability: str) -> Event:
        if capability not in VOCABULARY:
            raise ValueError(f"unknown capability {capability}")
        if capability not in self.live_grants and capability not in self.revoked:
            raise ValueError(f"{capability} was never granted this run")
        self.live_grants.discard(capability)
        ev = self._record(
            "revoke",
            {
                "capability": capability,
                "gate": self.name,
                "restart_count": self.restart_count,
                "live_after": sorted(self.live_grants),
            },
        )
        self.revoked[capability] = ev
        return ev

    def _write_side_effect(self, tool: str, seq: int) -> tuple[bool, str | None]:
        if tool != "Write":
            return False, None
        marker = self.dest / WRITE_MARKER
        payload = (
            f"unit={self.unit_id}\nrun={self.run_id}\ntool={tool}\nseq={seq}\n"
            f"gate={self.name}\n"
        ).encode("utf-8")
        marker.write_bytes(payload)
        return True, sha256_hex(payload)

    def _dest_sha(self) -> str | None:
        marker = self.dest / WRITE_MARKER
        if not marker.is_file():
            return None
        return sha256_hex(marker.read_bytes())

    def invoke(self, tool: str) -> CallResult:
        if tool not in VOCABULARY:
            seq = self._next_seq()
            result = CallResult(
                ok=False,
                code=CODE_UNKNOWN_TOOL,
                message=f"ERROR: {CODE_UNKNOWN_TOOL}: tool={tool}",
                tool=tool,
                seq=seq,
                t_ns=now_ns(),
                event_id=new_id("call"),
                wrote=False,
                dest_sha256=self._dest_sha(),
                observed_error={
                    "code": CODE_UNKNOWN_TOOL,
                    "tool": tool,
                    "seq": seq,
                },
            )
            self.calls.append(result)
            self._record(
                "deny",
                {"tool": tool, "code": CODE_UNKNOWN_TOOL, "call_event_id": result.event_id},
                seq=seq,
            )
            return result

        seq = self._next_seq()
        t_call = now_ns()
        allowed = tool in self.effective_grants()
        rev_ev = self.revoked.get(tool)
        if allowed:
            wrote, dest_sha = self._write_side_effect(tool, seq)
            result = CallResult(
                ok=True,
                code=CODE_OK,
                message=f"{CODE_OK}: tool={tool} seq={seq} gate={self.name}",
                tool=tool,
                seq=seq,
                t_ns=t_call,
                event_id=new_id("call"),
                wrote=wrote,
                dest_sha256=dest_sha if dest_sha is not None else self._dest_sha(),
            )
            self.calls.append(result)
            self._record(
                "allow",
                {
                    "tool": tool,
                    "code": CODE_OK,
                    "wrote": wrote,
                    "call_event_id": result.event_id,
                    "restart_count": self.restart_count,
                },
                seq=seq,
            )
            return result

        if rev_ev is not None:
            code = CODE_REVOKED
            message = (
                f"ERROR: {CODE_REVOKED}: tool={tool} capability={tool} "
                f"revoked_event={rev_ev.event_id} revoked_at_ns={rev_ev.t_ns} "
                f"call_seq={seq} call_at_ns={t_call} gate={self.name} "
                f"restart_count={self.restart_count}. "
                "Permission was granted at unit start and revoked mid-run; "
                "this call is denied at the next evaluation, not at the next "
                "unit start."
            )
            observed = {
                "code": code,
                "tool": tool,
                "capability": tool,
                "seq": seq,
                "t_ns": t_call,
                "revocation_event_id": rev_ev.event_id,
                "revocation_t_ns": rev_ev.t_ns,
                "restart_count": self.restart_count,
                "gate": self.name,
                "message": message,
            }
        else:
            code = CODE_DENIED
            message = (
                f"ERROR: {CODE_DENIED}: tool={tool} seq={seq} gate={self.name} "
                f"never granted this run (start_grants={list(self.start_grants)})"
            )
            observed = {
                "code": code,
                "tool": tool,
                "seq": seq,
                "t_ns": t_call,
                "gate": self.name,
                "message": message,
            }
        result = CallResult(
            ok=False,
            code=code,
            message=message,
            tool=tool,
            seq=seq,
            t_ns=t_call,
            event_id=new_id("call"),
            wrote=False,
            dest_sha256=self._dest_sha(),
            revocation_event_id=rev_ev.event_id if rev_ev is not None else None,
            revocation_t_ns=rev_ev.t_ns if rev_ev is not None else None,
            observed_error=observed,
        )
        self.calls.append(result)
        self._record(
            "deny",
            {
                "tool": tool,
                "code": code,
                "wrote": False,
                "call_event_id": result.event_id,
                "revocation_event_id": result.revocation_event_id,
                "restart_count": self.restart_count,
            },
            seq=seq,
        )
        if self.raise_on_deny and code == CODE_REVOKED:
            raise CapabilityRevoked(result)
        return result

    def event_log(self) -> list[dict[str, Any]]:
        return [e.as_dict() for e in self.events]

    def marker_bytes(self) -> bytes | None:
        marker = self.dest / WRITE_MARKER
        if not marker.is_file():
            return None
        return marker.read_bytes()


class PerCallGate(BaseGate):
    """Correct SUT: consult the live grant set on every invoke."""

    name = "per-call"

    def effective_grants(self) -> set[str]:
        return set(self.live_grants)


class StartTimeOnlyGate(BaseGate):
    """Negative control: permissions evaluated only at unit start."""

    name = "start-time-only"

    def effective_grants(self) -> set[str]:
        return set(self.start_grants)


class OneMoreCallGate(BaseGate):
    """Mutation: allow exactly one successful use after revoke, then deny.

    A denier that waits one extra call would still emit CAPABILITY_REVOKED
    eventually; TST-0228 requires the next call, so this mutant must fail.
    """

    name = "one-more-call"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._grace: dict[str, int] = {}

    def revoke(self, capability: str) -> Event:
        ev = super().revoke(capability)
        self._grace[capability] = 1
        return ev

    def effective_grants(self) -> set[str]:
        grants = set(self.live_grants)
        for cap, left in list(self._grace.items()):
            if left > 0:
                grants.add(cap)
        return grants

    def invoke(self, tool: str) -> CallResult:
        result = super().invoke(tool)
        if tool in self._grace and result.ok:
            self._grace[tool] = max(0, self._grace[tool] - 1)
        return result


def dump_log(gate: BaseGate) -> str:
    return json.dumps(gate.event_log(), indent=2, sort_keys=True)
