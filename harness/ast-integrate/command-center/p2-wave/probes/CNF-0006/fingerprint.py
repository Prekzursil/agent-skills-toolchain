"""Probe fingerprint: (tool, shell, data_field, measurement_kind).

Independence is a property of a pair. An undeclared source_probe is zero
signals, not one: it is a VIOLATION, never 'differs-from-verifier'.
"""
from __future__ import annotations

from typing import Any, Optional

AXES = ("tool", "shell", "data_field", "measurement_kind")

REJECTED = "REJECTED"
ACCEPTED = "ACCEPTED"
VIOLATION = "VIOLATION"

SAME_PROBE_RERUN = "same-probe-rerun"
INDEPENDENT = "independent"
UNDECLARED_SOURCE = "undeclared-source-probe"
UNDECLARED_VERIFIER = "undeclared-verifier-probe"

SHELL_CANON = {
    "git bash": "git-bash",
    "git-bash": "git-bash",
    "gitbash": "git-bash",
    "bash.exe": "git-bash",
    "powershell": "powershell",
    "powershell.exe": "powershell",
    "pwsh": "powershell",
    "pwsh.exe": "powershell",
}

TOOL_ALIASES = ("tool", "engine", "binary", "executable")
FIELD_ALIASES = ("data_field", "field", "datum", "target")
KIND_ALIASES = ("measurement_kind", "measurement", "kind", "instrument")
SHELL_ALIASES = ("shell", "shell_name", "runtime_shell")


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return str(value).strip()
    return str(value).strip()


def normalize_shell(value: Any) -> str:
    raw = _as_text(value).lower().replace("_", "-")
    if not raw:
        return ""
    return SHELL_CANON.get(raw, raw)


def _first(mapping: dict, names: tuple[str, ...]) -> str:
    for name in names:
        if name in mapping and mapping[name] not in (None, ""):
            return _as_text(mapping[name])
    return ""


def _from_command(command: str, shell: str = "") -> dict[str, str]:
    parts = command.strip().split()
    tool = parts[0] if parts else ""
    rest = " ".join(parts[1:]) if len(parts) > 1 else ""
    return {
        "tool": tool,
        "shell": normalize_shell(shell),
        "data_field": rest,
        "measurement_kind": "command-output",
    }


def _from_mapping(mapping: dict) -> dict[str, str]:
    tool = _first(mapping, TOOL_ALIASES)
    shell = normalize_shell(_first(mapping, SHELL_ALIASES))
    field = _first(mapping, FIELD_ALIASES)
    kind = _first(mapping, KIND_ALIASES)
    command = _as_text(mapping.get("command") or mapping.get("cmd") or "")
    derived = _from_command(command, shell or _as_text(mapping.get("shell"))) if command else None
    if derived:
        tool = tool or derived["tool"]
        shell = shell or derived["shell"]
        field = field or derived["data_field"]
        kind = kind or derived["measurement_kind"]
    nested = mapping.get("fingerprint")
    if isinstance(nested, dict):
        inner = _from_mapping(nested)
        tool = tool or inner["tool"]
        shell = shell or inner["shell"]
        field = field or inner["data_field"]
        kind = kind or inner["measurement_kind"]
    elif isinstance(nested, (list, tuple)) and len(nested) == 4:
        tool = tool or _as_text(nested[0])
        shell = shell or normalize_shell(nested[1])
        field = field or _as_text(nested[2])
        kind = kind or _as_text(nested[3])
    return {
        "tool": tool,
        "shell": shell,
        "data_field": field,
        "measurement_kind": kind,
    }


def components(probe: Any) -> Optional[dict[str, str]]:
    """Normalized four axes, or None when the probe is undeclared/empty."""
    if probe is None:
        return None
    if isinstance(probe, str):
        text = probe.strip()
        if not text:
            return None
        if text.startswith("{") or text.startswith("["):
            import json

            try:
                return components(json.loads(text))
            except json.JSONDecodeError:
                pass
        if "|" in text:
            parts = [p.strip() for p in text.split("|")]
            if len(parts) == 4:
                return components(
                    {
                        "tool": parts[0],
                        "shell": parts[1],
                        "data_field": parts[2],
                        "measurement_kind": parts[3],
                    }
                )
        return components(_from_command(text))
    if isinstance(probe, (list, tuple)):
        if len(probe) == 0:
            return None
        if len(probe) == 4 and not isinstance(probe[0], dict):
            return components(
                {
                    "tool": probe[0],
                    "shell": probe[1],
                    "data_field": probe[2],
                    "measurement_kind": probe[3],
                }
            )
        return None
    if isinstance(probe, dict):
        if not probe:
            return None
        got = _from_mapping(probe)
        if not any(got[axis] for axis in AXES):
            return None
        return got
    return None


def is_undeclared(probe: Any) -> bool:
    return components(probe) is None


def report_body(doc: Any) -> dict:
    """CNF-0006 payload lives in report when the receipt is schema-shaped."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and (
        "controls" in report
        or "same_probe_rate" in report
        or report.get("kind") == "confirmation-audit"
    ):
        return report
    return doc


def fingerprint(probe: Any) -> Optional[tuple[str, str, str, str]]:
    """Fingerprint a probe as (tool, shell, data_field, measurement_kind).

    Returns None when the probe is undeclared. Callers MUST treat None as a
    violation and must not compare it to a verifier (that is the empty-source
    hole: empty strings trivially differ from any filled verifier).
    """
    got = components(probe)
    if got is None:
        return None
    return (got["tool"], got["shell"], got["data_field"], got["measurement_kind"])


def differing_axes(
    left: tuple[str, str, str, str], right: tuple[str, str, str, str]
) -> list[str]:
    return [axis for axis, a, b in zip(AXES, left, right) if a != b]


def independence_check(source_probe: Any, verifier_probe: Any) -> dict:
    """Accept only when both probes are declared and fingerprints differ.

    Empty source is VIOLATION, never ACCEPTED-as-different.
    Identical fingerprints are REJECTED (same-probe re-run).
    A shell-only difference is ACCEPTED (shell is a declared independence axis).
    """
    src = fingerprint(source_probe)
    ver = fingerprint(verifier_probe)
    if src is None:
        return {
            "verdict": VIOLATION,
            "classification": UNDECLARED_SOURCE,
            "accepted": False,
            "source_fingerprint": None,
            "verifier_fingerprint": None if ver is None else list(ver),
            "differing_axes": [],
        }
    if ver is None:
        return {
            "verdict": VIOLATION,
            "classification": UNDECLARED_VERIFIER,
            "accepted": False,
            "source_fingerprint": list(src),
            "verifier_fingerprint": None,
            "differing_axes": [],
        }
    if src == ver:
        return {
            "verdict": REJECTED,
            "classification": SAME_PROBE_RERUN,
            "accepted": False,
            "source_fingerprint": list(src),
            "verifier_fingerprint": list(ver),
            "differing_axes": [],
        }
    axes = differing_axes(src, ver)
    return {
        "verdict": ACCEPTED,
        "classification": INDEPENDENT,
        "accepted": True,
        "source_fingerprint": list(src),
        "verifier_fingerprint": list(ver),
        "differing_axes": axes,
    }


# Controls from the unit contract. Precedent: Git-Bash `which` re-run.
IDENTICAL_COMMAND = "which python"
IDENTICAL_SOURCE = {
    "tool": "which",
    "shell": "git-bash",
    "data_field": "python",
    "measurement_kind": "command-presence",
    "command": IDENTICAL_COMMAND,
}
IDENTICAL_VERIFIER = {
    "tool": "which",
    "shell": "Git Bash",
    "data_field": "python",
    "measurement_kind": "command-presence",
    "command": IDENTICAL_COMMAND,
}
SHELL_ONLY_VERIFIER = {
    "tool": "which",
    "shell": "PowerShell",
    "data_field": "python",
    "measurement_kind": "command-presence",
    "command": IDENTICAL_COMMAND,
}
EMPTY_SOURCE = {}


def run_fingerprint_controls() -> dict:
    """Run both fingerprint controls in THIS invocation.

    Designed opposite verdicts: identical command REJECTED, shell-only ACCEPTED.
    Empty source is a third required test (VIOLATION, not differs-from-verifier).
    """
    identical = independence_check(IDENTICAL_SOURCE, IDENTICAL_VERIFIER)
    shell_only = independence_check(IDENTICAL_SOURCE, SHELL_ONLY_VERIFIER)
    empty = independence_check(EMPTY_SOURCE, SHELL_ONLY_VERIFIER)
    empty_none = independence_check(None, SHELL_ONLY_VERIFIER)
    empty_str = independence_check("", SHELL_ONLY_VERIFIER)
    identical_ok = identical["verdict"] == REJECTED and identical["classification"] == SAME_PROBE_RERUN
    shell_ok = (
        shell_only["verdict"] == ACCEPTED
        and shell_only["classification"] == INDEPENDENT
        and shell_only["differing_axes"] == ["shell"]
    )
    empty_ok = (
        empty["verdict"] == VIOLATION
        and empty["classification"] == UNDECLARED_SOURCE
        and empty_none["verdict"] == VIOLATION
        and empty_str["verdict"] == VIOLATION
    )
    opposite = identical["verdict"] != shell_only["verdict"]
    return {
        "same_invocation": True,
        "opposite_verdicts_as_designed": bool(opposite and identical_ok and shell_ok),
        "identical_command": {
            "id": "control-identical-command-reject",
            "designed_verdict": REJECTED,
            "observed_verdict": identical["verdict"],
            "classification": identical["classification"],
            "pass": identical_ok,
            "detail": identical,
        },
        "shell_only": {
            "id": "control-shell-axis-accept",
            "designed_verdict": ACCEPTED,
            "observed_verdict": shell_only["verdict"],
            "classification": shell_only["classification"],
            "differing_axes": shell_only["differing_axes"],
            "pass": shell_ok,
            "detail": shell_only,
        },
        "empty_source": {
            "id": "control-empty-source-violation",
            "designed_verdict": VIOLATION,
            "observed_verdict": empty["verdict"],
            "classification": empty["classification"],
            "pass": empty_ok,
            "detail": empty,
        },
        "pass": bool(identical_ok and shell_ok and empty_ok and opposite),
    }
