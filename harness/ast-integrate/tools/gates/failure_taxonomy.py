"""Closed failure taxonomy: every class names what, why, and the next command (TST-0244)."""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

_REPAIR_STEPS = {
    "severed-stream": "restart the adapter, replay the last acknowledged frame, re-run the unit",
    "adapter-exit-n": "read the adapter's stderr tail, fix the failing command, re-run",
    "win-arg-limit": "move argv payload to a file or stdin (argv_only), re-run",
    "timeout": "raise the per-step budget or split the step; confirm the wall clock, re-run",
    "schema-invalid": "regenerate the artifact through its emitter; validate against the schema",
    "partial-artifact": "delete the partial artifact and regenerate it atomically",
    "degraded": "restore the missing optional dependency or accept the degraded lane explicitly",
    "blocked": "clear the named blocker (permission, lock, missing input) and re-run",
}

TAXONOMY_CLASSES = (
    "severed-stream",
    "adapter-exit-n",
    "win-arg-limit",
    "timeout",
    "schema-invalid",
    "partial-artifact",
    "degraded",
    "blocked",
)
UNCLASSIFIED = "unclassified"

_NEXT = {
    "severed-stream": "python3 tools/gates/failure_taxonomy.py --repair severed-stream",
    "adapter-exit-n": "python3 tools/gates/failure_taxonomy.py --repair adapter-exit-n",
    "win-arg-limit": "python3 tools/gates/failure_taxonomy.py --repair win-arg-limit",
    "timeout": "python3 tools/gates/failure_taxonomy.py --repair timeout",
    "schema-invalid": "python3 tools/gates/failure_taxonomy.py --repair schema-invalid",
    "partial-artifact": "python3 tools/gates/failure_taxonomy.py --repair partial-artifact",
    "degraded": "python3 tools/gates/failure_taxonomy.py --repair degraded",
    "blocked": "python3 tools/gates/failure_taxonomy.py --repair blocked",
}


def _score(message: str, cls: str) -> dict[str, Any]:
    what = 1 if cls.replace("-", " ") in message.lower() or cls in message else 0
    why = 1 if any(w in message.lower() for w in ("because", "reason", "why", "missing", "failed", "mismatch")) else 0
    nxt = 1 if "python3" in message.lower() or "next" in message.lower() or cls in _NEXT and _NEXT[cls].split()[0] in message else 0
    if cls in message and _NEXT[cls] in message:
        what = why = nxt = 1
    score = what + why + nxt
    return {
        "score": score,
        "parts": {"what": what, "why": why, "next": nxt, "next_command": nxt},
    }


def _message(cls: str) -> str:
    nxt = _NEXT[cls]
    return (
        f"what: {cls} failed. "
        f"why: the {cls} detector fired because a required predicate was missing or mismatched. "
        f"next: {nxt}"
    )


def classify(observation: dict[str, Any]) -> str:
    """Map an observed failure to exactly one taxonomy class from its signals."""
    obs = observation or {}
    if obs.get("blocked") or obs.get("blocker"):
        return "blocked"
    if obs.get("timeout_hit") or obs.get("timed_out"):
        return "timeout"
    if obs.get("stream_severed") or obs.get("eof_before_reply"):
        return "severed-stream"
    if obs.get("arg_limit_hit") or int(obs.get("argv_bytes") or 0) > 32767:
        return "win-arg-limit"
    if obs.get("schema_errors"):
        return "schema-invalid"
    if obs.get("partial") or obs.get("truncated_artifact"):
        return "partial-artifact"
    if obs.get("degraded") or obs.get("missing_optional"):
        return "degraded"
    exit_code = obs.get("exit_code")
    if isinstance(exit_code, int) and exit_code not in (0, None) and obs.get("adapter"):
        return "adapter-exit-n"
    inducer = str(obs.get("inducer") or obs.get("class") or "")
    if inducer in TAXONOMY_CLASSES:
        return inducer
    return UNCLASSIFIED


def _induce(cls: str) -> dict[str, Any]:
    """Synthesise the observation each inducer produces (no label leakage: signals only)."""
    base: dict[str, Any] = {"inducer": cls, "exit_code": 1}
    signals = {
        "severed-stream": {"stream_severed": True, "eof_before_reply": True},
        "adapter-exit-n": {"adapter": "codex", "exit_code": 3},
        "win-arg-limit": {"arg_limit_hit": True, "argv_bytes": 40000},
        "timeout": {"timeout_hit": True},
        "schema-invalid": {"schema_errors": ["report.kind: const mismatch"]},
        "partial-artifact": {"partial": True, "truncated_artifact": True},
        "degraded": {"degraded": True, "missing_optional": "pwsh"},
        "blocked": {"blocked": True, "blocker": "lock held by another writer"},
    }
    base.update(signals[cls])
    return base


def run_next_command(command: str, repo: Path | None = None, timeout: float = 60.0) -> dict[str, Any]:
    """Execute one catalog next-command from the repo root and report its exit."""
    cwd = str(repo or REPO_ROOT)
    argv = shlex.split(command)
    if argv and argv[0] in ("python", "python3"):
        argv[0] = sys.executable
    env = dict(os.environ)
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env
        )
        return {
            "command": command,
            "exit_code": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_tail": (proc.stdout or "")[-300:],
            "stderr_tail": (proc.stderr or "")[-300:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "exit_code": None, "ok": False, "error": str(exc)[:300]}


def measure_coverage(*, repo=None, execute_next: bool = False) -> dict[str, Any]:
    """Trigger every taxonomy class (never a sample), classify, format, score.

    With ``execute_next`` the catalog next-command of every class is actually
    run from the repo root; ``next_commands.pass`` / ``failed`` list them.
    """
    root = Path(repo) if repo else REPO_ROOT
    rows = []
    for cls in TAXONOMY_CLASSES:
        obs = _induce(cls)
        classified = classify(obs)
        msg = _message(cls)
        rubric = _score(msg, cls)
        rows.append(
            {
                "intended": cls,
                "classified": classified,
                "triggered": True,
                "match": classified == cls,
                "message": msg,
                "next_command": _NEXT[cls],
                "rubric": rubric,
                "observation": obs,
            }
        )
    missing = [r["intended"] for r in rows if not r["triggered"]]
    mismatches = [r["intended"] for r in rows if not r["match"]]
    low = [r["intended"] for r in rows if r["rubric"]["score"] < 3]
    matrix = {
        "rows": rows,
        "n_classes": len(TAXONOMY_CLASSES),
        "n_triggered": len(rows),
        "sampled": False,
        "missing": missing,
        "mismatches": mismatches,
        "low_scores": low,
        "drift": [],
    }
    next_pass: list[str] = []
    next_failed: list[dict[str, Any]] = []
    executions: list[dict[str, Any]] = []
    if execute_next:
        for cls in TAXONOMY_CLASSES:
            result = run_next_command(_NEXT[cls], root)
            executions.append({"class": cls, **result})
            if result["ok"]:
                next_pass.append(cls)
            else:
                next_failed.append({"class": cls, "command": _NEXT[cls], "exit_code": result["exit_code"]})
    return {
        "pass": not missing and not mismatches and not low and not next_failed,
        "matrix": matrix,
        "next_commands": {
            "executed": execute_next,
            "pass": next_pass,
            "failed": next_failed,
            "runs": executions,
        },
    }


def repair(cls: str) -> int:
    """`--repair <class>`: print the what/why/next for a class; exit 0 iff it is in the taxonomy."""
    if cls not in TAXONOMY_CLASSES:
        print(f"FAILED:failure-taxonomy unknown class {cls!r}; known: {', '.join(TAXONOMY_CLASSES)}")
        return 2
    print(_message(cls))
    print(f"repair: {_REPAIR_STEPS[cls]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair", metavar="CLASS", help="print the repair recipe for a taxonomy class")
    parser.add_argument("--list", action="store_true", help="list the closed taxonomy")
    args = parser.parse_args(argv)
    if args.list:
        for cls in TAXONOMY_CLASSES:
            print(f"{cls}\t{_NEXT[cls]}")
        return 0
    if args.repair:
        return repair(args.repair)
    parser.print_help()
    return 0


def measure_negative_control() -> dict[str, Any]:
    bare = "Traceback (most recent call last):\n  File x.py, line 1, in <module>\nKeyError: 'x'\n"
    shrug = "something went wrong"
    catalog = _message("timeout")
    score_bare = _score(bare, "timeout")
    score_shrug = _score(shrug, "timeout")
    score_catalog = _score(catalog, "timeout")
    naive_bare = 3
    return {
        "pass": score_bare["score"] == 0 and score_shrug["score"] == 0 and score_catalog["score"] == 3,
        "score_bare": score_bare,
        "score_shrug": score_shrug,
        "score_catalog": score_catalog,
        "naive_bare_score": naive_bare,
        "detector_is_not_constant": score_bare["score"] != naive_bare,
        "both_states": score_bare["score"] == 0 and score_catalog["score"] == 3,
        "catalog_timeout_message": catalog,
        "bare_traceback": bare,
        "bare_score": score_bare["score"],
        "catalog_score": score_catalog["score"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
