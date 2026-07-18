from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Action = Literal["allow", "block", "inject", "continue"]


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
    agent: AgentEnvelope = field(default_factory=AgentEnvelope)

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
