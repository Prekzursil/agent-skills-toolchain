from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Action = Literal["allow", "block", "inject", "continue"]

# Identity strings that name NO single session or turn. adapters.normalize_event
# defaults a missing turn_id to "" and a missing session_id to "unknown", so every
# unidentified event shares them. ledger._session_isolatable applies the same rule
# to per-session goal files; evidence_turn_id below applies it to receipts.
UNIDENTIFIED_IDS = frozenset({"", "unknown"})


def _identifies(value: str) -> bool:
    """Whether `value` names one session/turn rather than a shared placeholder."""
    return str(value).strip().lower() not in UNIDENTIFIED_IDS


@dataclass(frozen=True)
class ToolEnvelope:
    name: str = ""
    id: str = ""
    input: Any = field(default_factory=dict)
    result: Any = None


@dataclass(frozen=True)
class AgentEnvelope:
    id: str = ""
    type: str = ""
    transcript_path: str = ""
    # D17-F4 · the spawning task/agent, when the host names one. Without it a
    # TaskCompleted/SubagentStop fact cannot be joined back to what spawned it,
    # so concurrent workers are indistinguishable in the ledger. An OPAQUE ID
    # only — never a transcript path, and never a second transcript field.
    parent_id: str = ""


@dataclass(frozen=True)
class HookEvent:
    schema_version: int
    provider: str
    event: str
    session_id: str
    turn_id: str
    cwd: str
    permission_mode: str
    tool: ToolEnvelope = field(default_factory=ToolEnvelope)
    last_assistant_message: str = ""
    prompt: str = ""
    source: str = ""
    trigger: str = ""
    transcript_path: str = ""
    agent: AgentEnvelope = field(default_factory=AgentEnvelope)

    @property
    def evidence_turn_id(self) -> str:
        """The key under which this event's verification evidence is stored and queried.

        `turn_id` is the host's per-turn key when it sends one, but Claude Code sends
        `prompt_id` instead, so in practice most Claude events normalize to the empty
        string (measured in-tree: `harness-sota-2026-07-18-corpus/P1C04.md:26` sampled
        `claude|empty=742` against `codex|set=164`). The ledger's evidence queries read
        an empty turn as "match every turn" (`ledger.py:1123,1133`), so an unidentified
        event both stores its receipts as project-wide wildcards and answers its own
        completion gate with some OTHER session's receipt. Measured: a Stop claiming
        "Fixed; all tests passed" was ALLOWED because a concurrent session in the same
        project had run pytest.

        Falling back to a session-derived token keeps the key non-empty and unique per
        session, so evidence is scoped to the session that produced it instead of to the
        whole project — without inventing a turn boundary the host never reported. When
        neither identity is usable the result is "" and today's behavior is unchanged,
        because there is then nothing to scope by.

        Scope of the guarantee: this attributes events written from here on. Rows already
        on disk with turn_id="" keep matching every turn, because the ledger is
        append-only and they cannot be re-attributed after the fact; they age out of the
        bounded receipt scan (`ledger._RECEIPT_SCAN_LIMIT`) and must still beat the
        freshness floor. Only kind=="tool_result" and kind=="mutation" are written with
        this key, since those are the only kinds the evidence queries read.
        """
        if _identifies(self.turn_id):
            return str(self.turn_id).strip()
        session = str(self.session_id).strip()
        if not _identifies(session):
            return ""
        digest = hashlib.sha256(session.encode("utf-8", "replace")).hexdigest()
        return f"session-{digest[:16]}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HookResult:
    """The provider-neutral result contract.

    Do not add provider wire fields or diagnostic payloads here. Adapters own
    native JSON, while operational details belong in the terminal log.
    """

    status: str
    action: Action
    reason_code: str
    additional_context: list[str]
    continuation: str | None = None

    @classmethod
    def success(
        cls,
        *,
        action: Action = "allow",
        reason_code: str = "ok",
        additional_context: list[str] | None = None,
        continuation: str | None = None,
    ) -> "HookResult":
        return cls(
            status="SUCCESS:hook",
            action=action,
            reason_code=reason_code,
            additional_context=list(additional_context or []),
            continuation=continuation,
        )

    @classmethod
    def failed_open(cls, event_name: str) -> "HookResult":
        return cls(
            status=f"FAILED:hook-{event_name.lower()}",
            action="allow",
            reason_code="internal_error",
            additional_context=[],
            continuation=None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": self.status,
            "action": self.action,
            "reason_code": self.reason_code,
            "additional_context": list(self.additional_context),
        }
        if self.continuation is not None:
            result["continuation"] = self.continuation
        return result
