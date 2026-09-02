"""Replay a cited command in a controlled environment and classify divergence."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import normalize
import safety

REPO = None  # optional override via configure()
TIMEOUT_SEC = 20

READONLY_HEADS = frozenset(
    {
        "printf",
        "echo",
        "true",
        "false",
        "uname",
        "date",
        "pwd",
        "hostname",
        "grep",
        "egrep",
        "fgrep",
        "rg",
    }
)


def configure(repo) -> None:
    global REPO
    REPO = repo


def _repo():
    if REPO is not None:
        return REPO
    return HERE.parents[3]


def allowlisted(command: str) -> tuple[bool, str]:
    body = safety.strip_env_prefix(command)
    token = safety.first_token(command)
    base = token.rsplit("/", 1)[-1]
    if base in {"grep", "egrep", "fgrep", "rg"}:
        # Recursive greps over trees are unbounded; harvest them as NOT-CHECKED.
        if " -r" in f" {body} " or " -R" in f" {body} " or " -rn" in body or " -rN" in body:
            return False, "grep-recursive-not-allowlisted"
        return True, "allowlist-readonly"
    if base in READONLY_HEADS or token in READONLY_HEADS:
        return True, "allowlist-readonly"
    if base in {"python3", "python"} or token.endswith("/python3"):
        parts = body.split(None, 1)
        if len(parts) < 2:
            return False, "python-without-args"
        args = parts[1]
        if args.startswith("--version"):
            return True, "python-version"
        if args.startswith("-c ") or args.startswith("-c\t"):
            return True, "python-c"
        return False, "python-script-not-allowlisted"
    return False, "not-on-replay-allowlist"


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    env["TZ"] = "UTC"
    env["LANG"] = "C"
    env["LC_ALL"] = "C"
    return env


def execute(command: str) -> dict[str, Any]:
    """Run `command` only after the safety gate. Never runs a refused command."""
    gate = safety.classify(command)
    if not gate["ok"]:
        return {
            "executed": False,
            "refused": True,
            "refuse_reason": f"{gate['class']}:{gate['rule_id']}:{gate['rationale']}",
            "exit_code": None,
            "output": None,
            "gate": gate,
        }
    allowed, why = allowlisted(command)
    if not allowed:
        return {
            "executed": False,
            "refused": True,
            "refuse_reason": f"not-checked:{why}",
            "exit_code": None,
            "output": None,
            "gate": gate,
        }
    missing = safety.missing_tool(command)
    if missing:
        return {
            "executed": False,
            "refused": True,
            "refuse_reason": f"not-checked:{missing}",
            "exit_code": None,
            "output": None,
            "gate": gate,
        }
    try:
        proc = subprocess.run(
            command,
            cwd=str(_repo()),
            shell=True,
            executable="/bin/bash",
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
            env=_env(),
        )
        out = (proc.stdout or "") + (
            (proc.stderr or "") if proc.returncode != 0 else ""
        )
        return {
            "executed": True,
            "refused": False,
            "refuse_reason": None,
            "exit_code": proc.returncode,
            "output": out,
            "gate": gate,
        }
    except subprocess.TimeoutExpired:
        return {
            "executed": True,
            "refused": False,
            "refuse_reason": None,
            "exit_code": 124,
            "output": f"TIMEOUT after {TIMEOUT_SEC}s",
            "gate": gate,
        }
    except OSError as exc:
        return {
            "executed": False,
            "refused": True,
            "refuse_reason": f"not-checked:oserror:{type(exc).__name__}",
            "exit_code": 127,
            "output": None,
            "gate": gate,
        }


def _looks_env(recorded: str, replayed: str, command: str = "") -> bool:
    rec_n, _ = normalize.apply(recorded)
    live_n, _ = normalize.apply(replayed)
    if rec_n == live_n:
        return False
    cmd = command.lower()
    if any(tok in cmd for tok in ("sys.version", "--version", "hostname", "uname")):
        return True
    joined = (recorded + "\n" + replayed).lower()
    if any(m in joined for m in ("version", "hostname", "linux", "darwin")):
        return set(recorded.split()) != set(replayed.split())
    return False


def classify_divergence(
    recorded: str,
    run1: str,
    run2: str | None,
    *,
    executed_twice: bool,
    command: str = "",
) -> tuple[str, str]:
    """Return (divergence_class, note). Nondeterminism requires two differing raw runs."""
    n_rec, _ = normalize.apply(recorded)
    n1, used1 = normalize.apply(run1)
    if n_rec == n1:
        return "match", f"normalized-equal normalizers={used1}"
    if executed_twice and run2 is not None:
        n2, _ = normalize.apply(run2)
        if run1 != run2:
            # Proven unstable. If normalized runs agree with each other, the
            # named normalizers captured the variance; the cited bytes still
            # cannot be treated as a stable quote.
            if n1 == n2:
                return (
                    "nondeterminism",
                    "two raw runs differ; normalized runs agree with each other",
                )
            return (
                "nondeterminism",
                "two raw runs differ; normalized runs also differ",
            )
        # Two identical live runs that still disagree with the recording.
        if _looks_env(recorded, run1, command):
            return (
                "environment-drift",
                "two identical live runs; host/version markers differ from recording",
            )
        return (
            "false-original-claim",
            "two identical live runs disagree with the cited output (no proof the citation was ever produced)",
        )
    return "false-original-claim", "single-run mismatch; second run not taken"


def verdict_for(div_class: str) -> str:
    if div_class == "match":
        return "CONFIRMED"
    if div_class == "not-checked":
        return "NOT-CHECKED"
    if div_class in {"nondeterminism", "environment-drift"}:
        return "PARTIAL"
    return "REFUTED"


def replay_claim(claim: dict[str, Any]) -> dict[str, Any]:
    command = str(claim.get("command") or "")
    recorded = str(claim.get("recorded_output") or "")
    first = execute(command)
    out1 = first.get("output")
    out2 = None
    twice = False
    if first.get("refused") or not first.get("executed"):
        div = "not-checked"
        note = str(first.get("refuse_reason") or "refused")
        n_rec, n_used = normalize.apply(recorded)
        n_live = None
        used = n_used
    else:
        # Second run whenever the first disagrees, or the command is in the
        # known-unstable family (date / time.time_ns / hostname).
        n_rec, n_used = normalize.apply(recorded)
        n_live, n_used_live = normalize.apply(out1 or "")
        used = sorted(set(n_used) | set(n_used_live))
        unstable_hint = any(
            tok in command
            for tok in ("date ", "time.time", "time_ns", "hostname", "uuid", "random")
        )
        if n_rec != n_live or unstable_hint:
            second = execute(command)
            if second.get("executed") and not second.get("refused"):
                out2 = second.get("output")
                twice = True
        div, note = classify_divergence(
            recorded,
            out1 or "",
            out2,
            executed_twice=twice,
            command=command,
        )
        # Attribution rule: a nondeterminism label is illegal unless two raw
        # runs were taken and they differ.
        if div == "nondeterminism" and not (
            twice and out2 is not None and (out1 or "") != out2
        ):
            div = "false-original-claim"
            note = "nondeterminism unproven (second raw run missing or identical); reclassified"

    row = {
        "id": claim.get("id") or command[:40],
        "source": claim.get("source") or "unknown",
        "source_path": claim.get("source_path"),
        "command": command,
        "recorded_output": recorded,
        "replayed_output": out1,
        "replayed_output_run2": out2,
        "executed": bool(first.get("executed")),
        "refused": bool(first.get("refused")),
        "refuse_reason": first.get("refuse_reason"),
        "exit_code": first.get("exit_code"),
        "normalizers_applied": used if first.get("executed") else [],
        "divergence_class": div,
        "verdict": verdict_for(div),
        "note": note,
        "second_run_taken": twice,
    }
    return row
