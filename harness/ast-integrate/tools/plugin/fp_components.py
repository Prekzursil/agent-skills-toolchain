"""Plugin components with their declared failure posture (IMP-0053).

Every component below is the *enforcement* half of one row of
``failure_policy.json``.  The row declares the posture; the class here is what
actually happens when the component's own logic raises:

* a **fail-open** component (hook, advisory, warning channel, heartbeat) catches
  its failure, records it as a degraded outcome and lets the operation
  ``proceed`` -- it never blocks the user (AGENTS.md#6: hook errors exit 0);
* a **fail-closed** component (validator, secret gate, signature check, payload
  allowlist, forbidden-content gate, tool permissions, rollback) catches its
  failure and ``deny``s -- an unverifiable state never ships.

``apply(ctx, fault=None)`` runs the component's real check over ``ctx`` (a
:class:`Context`).  ``fault`` is the injection seam used by
``failure_policy.inject_all``: the exception is raised *inside* the component's
own logic, so the outcome shows what the component does when it breaks, not
what a wrapper does around it.

The static auditor (``failure_policy.audit_fail_closed_components``) parses this
file and refuses any fail-closed ``apply`` whose ``except`` swallows the failure
into a pass (``pass``, ``return None``, ``return True``, a proceeding
``Outcome``).  Keep the deny path explicit: ``return self.deny(exc)``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable

FAIL_OPEN = "fail-open"
FAIL_CLOSED = "fail-closed"


@dataclass
class Outcome:
    """What a component did when asked to run."""

    proceed: bool
    denied: bool
    degraded: bool
    failure: bool
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Context:
    """Inputs the components check.  Defaults describe a healthy, clean plan."""

    root: Path | None = None
    hooks_config: Path | None = None
    hooks: list[Callable[[], Any]] = field(default_factory=list)
    advisories: list[str] = field(default_factory=lambda: ["advisory: none"])
    manifest: dict[str, Any] = field(
        default_factory=lambda: {"name": "demo", "version": "1.0.0", "entry": "main.py"}
    )
    text: str = "plain content"
    payload_paths: list[str] = field(default_factory=lambda: ["skills/x/SKILL.md"])
    allowlist: list[str] = field(default_factory=lambda: ["skills/", "hooks/"])
    signature_key: bytes = b"imp-0053-demo-key"
    signed_blob: bytes = b"payload"
    signature: str = ""
    declared_permissions: set[str] = field(default_factory=lambda: {"read", "write"})
    used_permissions: set[str] = field(default_factory=lambda: {"read"})
    applied_steps: list[dict[str, Any]] = field(
        default_factory=lambda: [{"op": "write", "path": "a"}, {"op": "write", "path": "b"}]
    )
    warnings: list[str] = field(default_factory=list)
    heartbeat_token: int = 0

    def __post_init__(self) -> None:
        if not self.signature:
            self.signature = hmac.new(
                self.signature_key, self.signed_blob, hashlib.sha256
            ).hexdigest()


class Component:
    """Base: one row's enforcement.  Subclasses implement ``check``."""

    id: str = ""
    kind: str = ""
    posture: str = FAIL_CLOSED

    def check(self, ctx: Context, fault: BaseException | None) -> None:
        raise NotImplementedError(f"{type(self).__name__}.check")

    @staticmethod
    def _inject(fault: BaseException | None) -> None:
        if fault is not None:
            raise fault

    def ok(self) -> Outcome:
        return Outcome(proceed=True, denied=False, degraded=False, failure=False)

    def deny(self, exc: BaseException) -> Outcome:
        return Outcome(proceed=False, denied=True, degraded=False, failure=True, error=repr(exc))

    def degrade(self, ctx: Context, exc: BaseException) -> Outcome:
        ctx.warnings.append(f"{self.id}: degraded: {exc!r}")
        return Outcome(proceed=True, denied=False, degraded=True, failure=True, error=repr(exc))

    def apply(self, ctx: Context, fault: BaseException | None = None) -> Outcome:
        raise NotImplementedError(f"{type(self).__name__}.apply")


class FailOpenComponent(Component):
    posture = FAIL_OPEN

    def apply(self, ctx: Context, fault: BaseException | None = None) -> Outcome:
        try:
            self.check(ctx, fault)
        except Exception as exc:  # any failure: proceed, degraded, never block
            return self.degrade(ctx, exc)
        return self.ok()


class FailClosedComponent(Component):
    posture = FAIL_CLOSED

    def apply(self, ctx: Context, fault: BaseException | None = None) -> Outcome:
        try:
            self.check(ctx, fault)
        except Exception as exc:  # any failure: deny, never skip the check
            return self.deny(exc)
        return self.ok()


# --- fail-open ---------------------------------------------------------------


class Hooks(FailOpenComponent):
    id = "hooks"
    kind = "hook"

    def check(self, ctx: Context, fault: BaseException | None) -> None:
        if ctx.hooks_config is not None:
            config = json.loads(Path(ctx.hooks_config).read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                raise ValueError("hooks config must be a JSON object")
        for hook in ctx.hooks:
            hook()
        self._inject(fault)


class Advisories(FailOpenComponent):
    id = "advisories"
    kind = "advisory"

    def check(self, ctx: Context, fault: BaseException | None) -> None:
        for note in ctx.advisories:
            if not isinstance(note, str):
                raise TypeError("advisory must be text")
        self._inject(fault)


class DegradeLoudly(FailOpenComponent):
    id = "degrade_loudly"
    kind = "warning-channel"

    def check(self, ctx: Context, fault: BaseException | None) -> None:
        self._inject(fault)
        if ctx.root is not None:
            sink = Path(ctx.root) / "degrade-loudly.log"
            with sink.open("a", encoding="utf-8") as handle:
                for line in ctx.warnings:
                    handle.write(line + "\n")


class Heartbeat(FailOpenComponent):
    id = "heartbeat"
    kind = "heartbeat"

    def check(self, ctx: Context, fault: BaseException | None) -> None:
        self._inject(fault)
        ctx.heartbeat_token += 1


# --- fail-closed -------------------------------------------------------------


class Validators(FailClosedComponent):
    id = "validators"
    kind = "validator"
    REQUIRED = ("name", "version", "entry")

    def check(self, ctx: Context, fault: BaseException | None) -> None:
        self._inject(fault)
        missing = [k for k in self.REQUIRED if not ctx.manifest.get(k)]
        if missing:
            raise ValueError(f"manifest missing {missing}")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(ctx.manifest["version"])):
            raise ValueError("manifest version is not semver")


class SecretGate(FailClosedComponent):
    id = "secret_gate"
    kind = "secret-gate"
    CANARIES = (
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    )

    def check(self, ctx: Context, fault: BaseException | None) -> None:
        self._inject(fault)
        for pattern in self.CANARIES:
            if pattern.search(ctx.text):
                raise ValueError(f"secret canary matched {pattern.pattern!r}")


class SignatureCheck(FailClosedComponent):
    id = "signature_check"
    kind = "signature"

    def check(self, ctx: Context, fault: BaseException | None) -> None:
        self._inject(fault)
        expected = hmac.new(ctx.signature_key, ctx.signed_blob, hashlib.sha256).hexdigest()
        if not ctx.signature or not hmac.compare_digest(expected, ctx.signature):
            raise ValueError("signature missing or invalid")


class PayloadAllowlist(FailClosedComponent):
    id = "payload_allowlist"
    kind = "allowlist"

    def check(self, ctx: Context, fault: BaseException | None) -> None:
        self._inject(fault)
        outside = [p for p in ctx.payload_paths if not any(p.startswith(a) for a in ctx.allowlist)]
        if outside:
            raise ValueError(f"payload outside allowlist: {outside}")


class ForbiddenContent(FailClosedComponent):
    id = "forbidden_content"
    kind = "content-gate"
    FORBIDDEN = (re.compile(r"(?i)\bBEGIN PGP MESSAGE\b"), re.compile(r"\x00"))

    def check(self, ctx: Context, fault: BaseException | None) -> None:
        self._inject(fault)
        for pattern in self.FORBIDDEN:
            if pattern.search(ctx.text):
                raise ValueError(f"forbidden content matched {pattern.pattern!r}")


class ToolPermissions(FailClosedComponent):
    id = "tool_permissions"
    kind = "permission"

    def check(self, ctx: Context, fault: BaseException | None) -> None:
        self._inject(fault)
        undeclared = sorted(set(ctx.used_permissions) - set(ctx.declared_permissions))
        if undeclared:
            raise PermissionError(f"undeclared permissions used: {undeclared}")


class Rollback(FailClosedComponent):
    id = "rollback"
    kind = "rollback"

    def check(self, ctx: Context, fault: BaseException | None) -> None:
        self._inject(fault)
        for step in reversed(ctx.applied_steps):
            if step.get("op") not in {"write", "mkdir", "replace"}:
                raise ValueError(f"cannot invert step {step!r}")


REGISTRY: dict[str, type[Component]] = {
    cls.id: cls
    for cls in (
        Hooks,
        Advisories,
        DegradeLoudly,
        Heartbeat,
        Validators,
        SecretGate,
        SignatureCheck,
        PayloadAllowlist,
        ForbiddenContent,
        ToolPermissions,
        Rollback,
    )
}

__all__ = [
    "FAIL_CLOSED",
    "FAIL_OPEN",
    "Component",
    "Context",
    "FailClosedComponent",
    "FailOpenComponent",
    "Outcome",
    "REGISTRY",
]
