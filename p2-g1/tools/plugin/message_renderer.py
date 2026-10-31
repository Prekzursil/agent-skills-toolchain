"""Three-part operator messages: cause / impact / next command (IMP-0052)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LABEL_CAUSE = "CAUSE:"
LABEL_IMPACT = "IMPACT:"
LABEL_NEXT = "NEXT:"

_CATALOG: dict[str, dict[str, str]] = {
    "AST.PLUGIN.INTERNAL.001": {
        "cause": "the packer refused to emit a payload member outside the allowlist",
        "impact": "the plugin archive was not written; the previous version remains installed",
        "next": "python3 -B tools/plugin/pack.py --help",
    },
    "AST.PLUGIN.INTERNAL.002": {
        "cause": "manifest schema validation rejected the plugin.json document",
        "impact": "install did not start; no files were copied into the live tree",
        "next": "python3 -B tools/plugin/manifest_schema.py --check plugin.json",
    },
    "AST.PLUGIN.INTERNAL.003": {
        "cause": "payload digest did not match the signed handoff record",
        "impact": "the copy on disk was left untouched",
        "next": "python3 -B tools/plugin/install.py --verify",
    },
    "AST.PLUGIN.INTERNAL.004": {
        "cause": "duplicate case-folded paths collided in the staging tree",
        "impact": "pack aborted before writing an archive",
        "next": "python3 -B tools/plugin/case_collision.py --staging ./staging",
    },
    "AST.PLUGIN.INTERNAL.005": {
        "cause": "secret-gate matched a planted credential in the payload",
        "impact": "the publish step was refused",
        "next": "python3 -B tools/plugin/secret_gate.py --scan ./payload",
    },
    "AST.PLUGIN.INTERNAL.006": {
        "cause": "interpreter probe could not start the declared runtime",
        "impact": "health check remains FAIL until the runtime is present",
        "next": "python3 -B tools/plugin/interpreter_probe.py",
    },
    "AST.PLUGIN.INTERNAL.007": {
        "cause": "rollback journal was missing the previous tree snapshot",
        "impact": "uninstall would not restore the prior version",
        "next": "python3 -B tools/plugin/rollback.py --status",
    },
    "AST.PLUGIN.INTERNAL.008": {
        "cause": "compatibility linter found a shell disagreement",
        "impact": "the plugin is marked warning and is not auto-enabled",
        "next": "python3 -B tools/plugin/compat_linter.py",
    },
    "AST.PLUGIN.INTERNAL.009": {
        "cause": "size budget exceeded the declared maximum archive bytes",
        "impact": "pack output was discarded",
        "next": "python3 -B tools/plugin/size_budget.py --check",
    },
    "AST.PLUGIN.INTERNAL.010": {
        "cause": "an internal exception was caught at the operator boundary",
        "impact": "the command returned a coded error instead of a traceback",
        "next": "python3 -B tools/plugin/cli.py --doctor",
    },
    "AST.PLUGIN.INTERNAL.011": {
        "cause": "the payload allowlist file was missing or unreadable",
        "impact": "deny-by-default refused to pack anything",
        "next": "python3 -B tools/plugin/payload_allowlist.py --init",
    },
    "AST.PLUGIN.INTERNAL.012": {
        "cause": "CRLF leaked into a declared LF-only member",
        "impact": "the archive hash would have been platform-dependent",
        "next": "python3 -B tools/plugin/eol_assert.py --path payload",
    },
}


@dataclass
class InternalError:
    code: str
    detail: str = ""
    exception: BaseException | None = None
    traceback_text: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def all_codes() -> list[str]:
    return sorted(_CATALOG)


def _parts_for(code: str, detail: str = "") -> tuple[str, str, str]:
    row = _CATALOG.get(code)
    if row is None:
        cause = f"unknown plugin error code {code}"
        if detail:
            cause = f"{cause}: {detail}"
        impact = "the command stopped without mutating the live tree"
        nxt = "python3 -B tools/plugin/cli.py --doctor"
        return cause, impact, nxt
    cause = row["cause"]
    if detail:
        cause = f"{cause} ({detail})"
    return row["cause"] if not detail else cause, row["impact"], row["next"]


def render_text(err: InternalError, debug: bool = False, redact: bool = True) -> str:
    cause, impact, nxt = _parts_for(err.code, err.detail)
    body = f"{LABEL_CAUSE} {cause}\n{LABEL_IMPACT} {impact}\n{LABEL_NEXT} {nxt}\n"
    if debug and err.traceback_text:
        tb = err.traceback_text
        body += tb if tb.endswith("\n") else tb + "\n"
    if redact:
        from redaction import redact_text  # type: ignore

        body = redact_text(body)
    return body


def parse_three_part(text: str) -> dict[str, Any]:
    cause = impact = nxt = ""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.startswith(LABEL_CAUSE):
            cause = line[len(LABEL_CAUSE) :].strip()
        elif line.startswith(LABEL_IMPACT):
            impact = line[len(LABEL_IMPACT) :].strip()
        elif line.startswith(LABEL_NEXT):
            nxt = line[len(LABEL_NEXT) :].strip()
    ok = bool(cause) and bool(impact) and bool(nxt)
    return {
        "ok": ok,
        "cause": cause,
        "impact": impact,
        "next_command": nxt,
        "has_traceback": "Traceback (most recent call last)" in (text or ""),
    }
