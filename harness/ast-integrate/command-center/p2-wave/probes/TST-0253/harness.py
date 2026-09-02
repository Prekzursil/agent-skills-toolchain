"""Extract runbook/rollback steps and execute machine-checkable postconditions.

A step is MACHINE when it carries a parseable ```postcondition fence with a
recognized kind. A step whose only success criterion is prose is PROSE_ONLY.
Coverage of a live document fails if the file is missing, has zero steps, or
any step is PROSE_ONLY, or any repo-scoped postcondition does not hold.

Rollback rehearsal runs each step's actions then its postcondition against a
scratch tree. Paths may use $REHEARSAL; they cannot escape that root.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_RUNBOOK = "command-center/RUNBOOK.md"
LIVE_ROLLBACK = "command-center/ROLLBACK-MANIFEST.md"
STEP_RE = re.compile(r"(?m)^## Step +(\S+):\s*(.+)$")
FENCE_RE = re.compile(
    r"```(postcondition|action)\s*\n(.*?)\n```",
    re.DOTALL,
)
KINDS = frozenset({"file_exists", "json_parse", "bytes_match", "command"})
ACTION_KINDS = frozenset({"mkdir", "copy", "write_text", "unlink"})


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    return sha256_bytes(raw), len(raw.replace(b"\r\n", b"\n"))


def parse_steps(text: str, source: str) -> list[dict[str, Any]]:
    matches = list(STEP_RE.finditer(text))
    steps: list[dict[str, Any]] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        actions: list[dict[str, Any]] = []
        postcondition: dict[str, Any] | None = None
        pc_error: str | None = None
        for kind, payload in FENCE_RE.findall(body):
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError as exc:
                if kind == "postcondition":
                    pc_error = f"json:{exc}"
                continue
            if not isinstance(obj, dict):
                pc_error = "postcondition-not-object"
                continue
            if kind == "action":
                actions.append(obj)
            else:
                postcondition = obj
        machine = (
            isinstance(postcondition, dict)
            and str(postcondition.get("kind") or "") in KINDS
            and pc_error is None
        )
        steps.append(
            {
                "id": match.group(1),
                "title": match.group(2).strip(),
                "source": source,
                "line": text[: match.start()].count("\n") + 1,
                "classification": "MACHINE" if machine else "PROSE_ONLY",
                "actions": actions,
                "postcondition": postcondition,
                "postcondition_error": pc_error,
                "prose_excerpt": body[:240],
            }
        )
    return steps


def load_doc(rel: str) -> dict[str, Any]:
    path = REPO / rel
    if not path.is_file():
        return {
            "path": rel,
            "present": False,
            "bytes": 0,
            "sha256": "",
            "steps": [],
        }
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "present": True,
        "bytes": size,
        "sha256": digest,
        "steps": parse_steps(text, rel),
    }


def _expand(raw: str, rehearsal: Path | None) -> str:
    if "$REHEARSAL" not in raw:
        return raw
    if rehearsal is None:
        raise ValueError("rehearsal path used without rehearsal root")
    return raw.replace("$REHEARSAL", str(rehearsal))


def resolve_path(raw: str, rehearsal: Path | None) -> Path:
    expanded = _expand(raw, rehearsal)
    path = Path(expanded)
    if not path.is_absolute():
        path = (REPO / path).resolve()
    else:
        path = path.resolve()
    repo = REPO.resolve()
    try:
        path.relative_to(repo)
        in_repo = True
    except ValueError:
        in_repo = False
    if rehearsal is not None:
        root = rehearsal.resolve()
        try:
            path.relative_to(root)
            return path
        except ValueError:
            if in_repo:
                return path
            raise ValueError(f"path escapes rehearsal and repo: {raw}")
    if not in_repo:
        raise ValueError(f"path escapes repo: {raw}")
    return path


def run_postcondition(
    pc: dict[str, Any] | None, rehearsal: Path | None = None
) -> dict[str, Any]:
    if not isinstance(pc, dict):
        return {"ok": False, "reason": "missing-postcondition"}
    kind = str(pc.get("kind") or "")
    if kind not in KINDS:
        return {"ok": False, "reason": f"unknown-kind:{kind}"}
    try:
        if kind in {"file_exists", "json_parse"}:
            path = resolve_path(str(pc.get("path") or ""), rehearsal)
            if not path.is_file():
                return {"ok": False, "reason": "absent", "path": str(path)}
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            min_bytes = int(pc.get("min_bytes") or 0)
            if len(raw) < min_bytes:
                return {
                    "ok": False,
                    "reason": f"too-small:{len(raw)}<{min_bytes}",
                    "path": str(path),
                }
            needle = pc.get("contains")
            if needle and str(needle) not in text:
                return {"ok": False, "reason": "contains-miss", "path": str(path)}
            if kind == "json_parse":
                try:
                    doc = json.loads(text)
                except json.JSONDecodeError as exc:
                    return {"ok": False, "reason": f"json:{exc}", "path": str(path)}
                if not isinstance(doc, dict):
                    return {"ok": False, "reason": "json-not-object", "path": str(path)}
                for key in pc.get("required_keys") or []:
                    if key not in doc:
                        return {"ok": False, "reason": f"missing-key:{key}"}
            return {
                "ok": True,
                "reason": "pass",
                "path": str(path.relative_to(REPO.resolve()))
                if str(path).startswith(str(REPO.resolve()))
                else str(path),
                "bytes": len(raw),
            }
        if kind == "bytes_match":
            a = resolve_path(str(pc.get("path") or ""), rehearsal)
            b = resolve_path(str(pc.get("other") or ""), rehearsal)
            if not a.is_file() or not b.is_file():
                return {"ok": False, "reason": "absent-pair"}
            da, sa = sha256_file(a)
            db, sb = sha256_file(b)
            ok = da == db
            return {
                "ok": ok,
                "reason": "match" if ok else "mismatch",
                "sha256_a": da,
                "sha256_b": db,
                "bytes_a": sa,
                "bytes_b": sb,
            }
        argv = pc.get("argv")
        if not isinstance(argv, list) or not argv:
            return {"ok": False, "reason": "command-missing-argv"}
        argv_s = [str(x) for x in argv]
        timeout = int(pc.get("timeout_seconds") or 30)
        expect = int(pc.get("expect_exit") or 0)
        proc = subprocess.run(
            argv_s,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        needle = pc.get("stdout_contains")
        ok = proc.returncode == expect and (
            needle is None or str(needle) in out
        )
        return {
            "ok": ok,
            "reason": "pass" if ok else f"exit:{proc.returncode}",
            "exit_code": proc.returncode,
            "stdout_tail": out[-500:],
        }
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}


def run_action(action: dict[str, Any], rehearsal: Path) -> dict[str, Any]:
    kind = str(action.get("kind") or "")
    if kind not in ACTION_KINDS:
        return {"ok": False, "reason": f"unknown-action:{kind}"}
    try:
        if kind == "mkdir":
            path = resolve_path(str(action.get("path") or ""), rehearsal)
            path.mkdir(parents=True, exist_ok=True)
            return {"ok": True, "reason": "mkdir", "path": str(path)}
        if kind == "write_text":
            path = resolve_path(str(action.get("path") or ""), rehearsal)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(action.get("text") or ""), encoding="utf-8")
            return {"ok": True, "reason": "write_text", "path": str(path)}
        if kind == "unlink":
            path = resolve_path(str(action.get("path") or ""), rehearsal)
            if path.is_file():
                path.unlink()
            return {"ok": True, "reason": "unlink", "path": str(path)}
        src = resolve_path(str(action.get("src") or ""), rehearsal)
        dest = resolve_path(str(action.get("dest") or ""), rehearsal)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        return {"ok": True, "reason": "copy", "src": str(src), "dest": str(dest)}
    except (OSError, ValueError) as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}:{exc}"}


def evaluate_steps(
    steps: list[dict[str, Any]],
    *,
    execute_repo: bool,
    rehearsal: Path | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in steps:
        pc = step.get("postcondition")
        scope = str((pc or {}).get("scope") or "repo")
        executed = False
        result: dict[str, Any] | None = None
        if (
            step["classification"] == "MACHINE"
            and execute_repo
            and scope != "rehearsal"
        ):
            result = run_postcondition(pc, rehearsal=None)
            executed = True
        elif (
            step["classification"] == "MACHINE"
            and rehearsal is not None
            and scope == "rehearsal"
        ):
            result = run_postcondition(pc, rehearsal=rehearsal)
            executed = True
        rows.append(
            {
                "id": step["id"],
                "title": step["title"],
                "source": step["source"],
                "line": step["line"],
                "classification": step["classification"],
                "scope": scope if pc else None,
                "postcondition_kind": (pc or {}).get("kind"),
                "executed": executed,
                "ok": None if not executed else bool(result and result.get("ok")),
                "result": result,
            }
        )
    return rows


def coverage_of(rel: str, *, execute_repo: bool = True) -> dict[str, Any]:
    doc = load_doc(rel)
    rows = evaluate_steps(doc["steps"], execute_repo=execute_repo)
    prose = [r for r in rows if r["classification"] == "PROSE_ONLY"]
    failed = [r for r in rows if r["executed"] and r["ok"] is False]
    ok = (
        doc["present"]
        and bool(rows)
        and not prose
        and not failed
        and all(r["classification"] == "MACHINE" for r in rows)
    )
    return {
        "path": rel,
        "present": doc["present"],
        "bytes": doc["bytes"],
        "sha256": doc["sha256"],
        "n_steps": len(rows),
        "n_machine": sum(1 for r in rows if r["classification"] == "MACHINE"),
        "n_prose_only": len(prose),
        "n_failed_postconditions": len(failed),
        "ok": ok,
        "reason": (
            "pass"
            if ok
            else (
                "absent"
                if not doc["present"]
                else "zero-steps"
                if not rows
                else "prose-only"
                if prose
                else "postcondition-failed"
            )
        ),
        "prose_ids": [r["id"] for r in prose],
        "failed_ids": [r["id"] for r in failed],
        "table": rows,
    }


def both_states() -> dict[str, Any]:
    good = coverage_of(
        "command-center/p2-wave/probes/TST-0253/fixtures/good-runbook.md"
    )
    broken_doc = load_doc(
        "command-center/p2-wave/probes/TST-0253/fixtures/broken-step.md"
    )
    broken_rows = evaluate_steps(broken_doc["steps"], execute_repo=True)
    broken_failed = [
        r for r in broken_rows if r["executed"] and r["ok"] is False
    ]
    prose = coverage_of(
        "command-center/p2-wave/probes/TST-0253/fixtures/prose-only.md",
        execute_repo=False,
    )
    # Naive detector: any step body containing "Success" is MACHINE. The
    # prose-only fixture uses that word, so a string match would green it.
    prose_doc = load_doc(
        "command-center/p2-wave/probes/TST-0253/fixtures/prose-only.md"
    )
    naive_classifies_prose_as_machine = any(
        "success" in (s.get("prose_excerpt") or "").lower()
        for s in prose_doc["steps"]
    )
    ok = (
        good["ok"] is True
        and bool(broken_failed)
        and prose["n_prose_only"] == prose["n_steps"] == 1
        and naive_classifies_prose_as_machine
    )
    return {
        "ok": ok,
        "good_passes": good["ok"],
        "broken_fails": bool(broken_failed),
        "broken_ids": [r["id"] for r in broken_failed],
        "prose_only_count": prose["n_prose_only"],
        "naive_would_pass_prose": naive_classifies_prose_as_machine,
        "good": {"path": good["path"], "n_steps": good["n_steps"], "ok": good["ok"]},
        "broken_results": broken_rows,
        "prose": {
            "n_steps": prose["n_steps"],
            "n_prose_only": prose["n_prose_only"],
            "ids": prose["prose_ids"],
        },
    }


def rehearse(rel: str, rehearsal: Path) -> dict[str, Any]:
    if rehearsal.exists():
        shutil.rmtree(rehearsal)
    rehearsal.mkdir(parents=True)
    doc = load_doc(rel)
    if not doc["present"]:
        return {
            "ok": False,
            "reason": "absent",
            "path": rel,
            "steps": [],
            "rehearsal": str(rehearsal),
        }
    records: list[dict[str, Any]] = []
    ok = True
    for step in doc["steps"]:
        action_results = []
        for action in step.get("actions") or []:
            ar = run_action(action, rehearsal)
            action_results.append(ar)
            if not ar.get("ok"):
                ok = False
        pc = run_postcondition(step.get("postcondition"), rehearsal)
        if step["classification"] != "MACHINE" or not pc.get("ok"):
            ok = False
        records.append(
            {
                "id": step["id"],
                "title": step["title"],
                "classification": step["classification"],
                "actions": action_results,
                "postcondition": pc,
            }
        )
    return {
        "ok": ok and bool(records),
        "reason": "pass" if ok and records else "rehearsal-failed",
        "path": rel,
        "n_steps": len(records),
        "n_postconditions_ok": sum(
            1 for r in records if (r.get("postcondition") or {}).get("ok")
        ),
        "rehearsal": str(rehearsal.relative_to(REPO)),
        "steps": records,
    }


def measure() -> dict[str, Any]:
    runbook = coverage_of(LIVE_RUNBOOK, execute_repo=True)
    rollback_cov = coverage_of(LIVE_ROLLBACK, execute_repo=False)
    states = both_states()
    live_rehearsal = rehearse(LIVE_ROLLBACK, HERE / "runtime" / "live-rollback")
    fixture_rehearsal = rehearse(
        "command-center/p2-wave/probes/TST-0253/fixtures/good-rollback.md",
        HERE / "runtime" / "fixture-rollback",
    )
    table = list(runbook["table"]) + list(rollback_cov["table"])
    target_pass = (
        runbook["ok"]
        and rollback_cov["ok"]
        and live_rehearsal["ok"]
        and states["ok"]
        and fixture_rehearsal["ok"]
    )
    return {
        "unit_id": "TST-0253",
        "target_pass": target_pass,
        "runbook": runbook,
        "rollback_coverage": rollback_cov,
        "coverage_table": table,
        "both_states": states,
        "live_rollback_rehearsal": live_rehearsal,
        "fixture_rollback_rehearsal": fixture_rehearsal,
        "n_live_steps": runbook["n_steps"] + rollback_cov["n_steps"],
        "n_prose_only": runbook["n_prose_only"] + rollback_cov["n_prose_only"],
        "n_live_postconditions_ok": sum(
            1 for r in table if r.get("ok") is True
        ),
    }
