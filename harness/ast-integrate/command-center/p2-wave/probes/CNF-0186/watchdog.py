#!/usr/bin/env python3
"""Replication-package rot watchdog (CNF-0186).

Re-runs replication packages, emits one terminal-state line per package
(SUCCESS:<pkg> or FAILED:<pkg> reason), and persists the environment
fingerprint with each result so a later failure attributes to a stored
delta rather than a reconstructed one.

Stdout is only terminal-state lines (no noise). Diagnostics go to stderr.
A missing or silent run is not a pass — see interpret.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TERMINAL_RE = re.compile(r"^(SUCCESS|FAILED):(\S+)(?:\s+(.*))?$")
FINGERPRINT_SCHEMA = "cnf-0186-env-fingerprint/v1"


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def default_classifications_path() -> Path:
    live = REPO / "command-center/receipts/CNF-0184.json"
    if live.is_file() and live.stat().st_size > 0:
        return live
    return HERE / "fixtures/classifications.json"


def load_classifications(path: Path | None) -> dict[str, Any]:
    p = path or default_classifications_path()
    if not p.is_file():
        return {
            "source": "absent",
            "classes": [],
            "path": str(p),
        }
    doc = load_json(p)
    classes = doc.get("classes") or doc.get("normalizers") or []
    if not isinstance(classes, list):
        classes = []
    source = "CNF-0184-receipt" if p.name == "CNF-0184.json" else "fixture"
    return {"source": source, "classes": classes, "path": p.as_posix()}


def normalize(text: str, classes: list[dict[str, Any]]) -> str:
    out = text.replace("\r\n", "\n").rstrip("\n")
    for cls in classes:
        if not isinstance(cls, dict):
            continue
        pattern = cls.get("pattern")
        repl = cls.get("replace")
        if isinstance(pattern, str) and isinstance(repl, str):
            out = re.sub(pattern, repl, out)
    return out


def discover_packages(packages_dir: Path) -> list[Path]:
    found: list[Path] = []
    if not packages_dir.is_dir():
        return found
    for child in sorted(packages_dir.iterdir()):
        if child.is_dir() and (child / "package.json").is_file():
            found.append(child)
    return found


def load_package(pkg_dir: Path) -> dict[str, Any]:
    meta = load_json(pkg_dir / "package.json")
    if not isinstance(meta, dict) or not meta.get("id"):
        raise ValueError(f"invalid package.json in {pkg_dir}")
    meta["_dir"] = pkg_dir
    return meta


def capture_fingerprint(pkg_dir: Path) -> dict[str, Any]:
    pins_path = pkg_dir / "pins.json"
    pins_raw = pins_path.read_bytes() if pins_path.is_file() else b""
    pins_text = pins_raw.decode("utf-8") if pins_raw else ""
    return {
        "schema": FINGERPRINT_SCHEMA,
        "python_version": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "executable_name": Path(sys.executable).name,
        "pins_sha256": hashlib.sha256(pins_raw).hexdigest(),
        "pins_bytes": pins_text,
        "package_id": pkg_dir.name,
    }


def persist_fingerprint(fp: dict[str, Any]) -> dict[str, str]:
    """Store canonical bytes. Callers must not reconstruct this later."""
    canonical = canonical_json(fp)
    return {
        "environment_fingerprint_canonical": canonical,
        "environment_fingerprint_sha256": sha256_text(canonical),
    }


def env_delta(stored_canonical: str, current: dict[str, Any]) -> dict[str, Any]:
    """Delta from persisted canonical bytes vs a newly captured fingerprint.

    The stored side is parsed from `stored_canonical` as written. It is never
    rebuilt from the current environment.
    """
    if not stored_canonical:
        return {
            "had_last_green": False,
            "changed": {},
            "source": "no-stored-fingerprint",
        }
    try:
        stored = json.loads(stored_canonical)
    except json.JSONDecodeError as exc:
        return {
            "had_last_green": True,
            "changed": {},
            "source": "stored-unparseable",
            "error": type(exc).__name__,
        }
    if not isinstance(stored, dict):
        return {
            "had_last_green": True,
            "changed": {},
            "source": "stored-not-object",
        }
    keys = sorted(set(stored) | set(current))
    changed: dict[str, Any] = {}
    for key in keys:
        before = stored.get(key, "<ABSENT>")
        after = current.get(key, "<ABSENT>")
        if before != after:
            changed[key] = {"before": before, "after": after}
    return {
        "had_last_green": True,
        "changed": changed,
        "source": "stored-canonical-bytes",
        "stored_sha256": sha256_text(stored_canonical),
        "current_sha256": sha256_text(canonical_json(current)),
    }


def _command(meta: dict[str, Any]) -> list[str]:
    cmd = meta.get("command")
    if not isinstance(cmd, list) or not cmd or not all(isinstance(c, str) for c in cmd):
        raise ValueError(f"package {meta.get('id')} missing command[]")
    out = list(cmd)
    if out[0] in {"python", "python3"}:
        out[0] = sys.executable
    return out


def run_package(
    meta: dict[str, Any],
    classes: list[dict[str, Any]],
    timeout_sec: float,
) -> dict[str, Any]:
    pkg_dir: Path = meta["_dir"]
    cmd = _command(meta)
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(pkg_dir),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "reason": "timeout",
            "exit_code": 124,
            "stdout": "",
            "stdout_normalized": "",
        }
    stdout = proc.stdout or ""
    normalized = normalize(stdout, classes)
    expected = meta.get("expected_stdout_normalized")
    ok = proc.returncode == 0
    reason = ""
    if expected is not None and normalized != str(expected):
        ok = False
        reason = "stdout-mismatch"
    if proc.returncode != 0:
        first = (stdout.strip().splitlines() or ["(empty)"])[0][:80]
        reason = f"exit={proc.returncode} {first}".strip()
        ok = False
    return {
        "ok": ok,
        "reason": reason,
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stdout_normalized": normalized,
    }


def package_state_path(state_dir: Path, pkg_id: str) -> Path:
    return state_dir / "packages" / f"{pkg_id}.json"


def load_package_state(state_dir: Path, pkg_id: str) -> dict[str, Any]:
    path = package_state_path(state_dir, pkg_id)
    if path.is_file():
        doc = load_json(path)
        if isinstance(doc, dict):
            return doc
    return {
        "package_id": pkg_id,
        "last_green": None,
        "first_fail_day": None,
        "first_fail_reason": None,
        "first_fail_env_delta": None,
        "history": [],
    }


def apply_result(
    state: dict[str, Any],
    *,
    date: str,
    ok: bool,
    reason: str,
    terminal: str,
    fp: dict[str, Any],
    stored: dict[str, str],
    delta: dict[str, Any],
) -> dict[str, Any]:
    rec = {
        "date": date,
        "verdict": "SUCCESS" if ok else "FAILED",
        "terminal": terminal,
        "reason": reason,
        "environment_fingerprint_canonical": stored["environment_fingerprint_canonical"],
        "environment_fingerprint_sha256": stored["environment_fingerprint_sha256"],
        "env_delta_vs_last_green": delta,
    }
    history = list(state.get("history") or [])
    history.append(rec)
    state["history"] = history[-50:]
    if ok:
        state["last_green"] = {
            "date": date,
            "environment_fingerprint_canonical": stored["environment_fingerprint_canonical"],
            "environment_fingerprint_sha256": stored["environment_fingerprint_sha256"],
            "fingerprint": fp,
        }
        # Recovery does not rewrite the historical first-fail day.
    else:
        if state.get("first_fail_day") is None:
            state["first_fail_day"] = date
            state["first_fail_reason"] = reason
            state["first_fail_env_delta"] = delta
    state["last_run"] = rec
    return state


def terminal_line(pkg_id: str, ok: bool, reason: str) -> str:
    if ok:
        return f"SUCCESS:{pkg_id}"
    why = reason.strip() or "failed"
    return f"FAILED:{pkg_id} {why}"


def run_watchdog(
    packages_dir: Path,
    state_dir: Path,
    date: str,
    *,
    classifications_path: Path | None = None,
    timeout_sec: float = 15.0,
) -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    classes_doc = load_classifications(classifications_path)
    classes = [c for c in classes_doc["classes"] if isinstance(c, dict)]
    pkgs = discover_packages(packages_dir)
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    partial = state_dir / "runs" / f"{date}.partial.jsonl"
    final = state_dir / "runs" / f"{date}.json"
    partial.parent.mkdir(parents=True, exist_ok=True)
    if partial.exists():
        partial.unlink()
    marker = {
        "date": date,
        "started_at": run_id,
        "complete": False,
        "packages_dir": packages_dir.as_posix(),
    }
    dump_json(state_dir / "runs" / f"{date}.in-progress.json", marker)

    results: list[dict[str, Any]] = []
    lines: list[str] = []
    if not pkgs:
        line = "FAILED:_watchdog no-packages"
        print(line, flush=True)
        lines.append(line)
        summary = {
            "date": date,
            "complete": True,
            "classifications": classes_doc,
            "terminal_lines": lines,
            "packages": [],
            "overall": "FAILED",
        }
        dump_json(final, summary)
        (state_dir / "runs" / f"{date}.in-progress.json").unlink(missing_ok=True)
        return summary

    with partial.open("a", encoding="utf-8") as log:
        for pkg_dir in pkgs:
            meta = load_package(pkg_dir)
            pkg_id = str(meta["id"])
            fp = capture_fingerprint(pkg_dir)
            stored = persist_fingerprint(fp)
            st = load_package_state(state_dir, pkg_id)
            last_green = st.get("last_green") or {}
            stored_canonical = ""
            if isinstance(last_green, dict):
                stored_canonical = str(
                    last_green.get("environment_fingerprint_canonical") or ""
                )
            delta = env_delta(stored_canonical, fp)
            ran = run_package(meta, classes, timeout_sec)
            line = terminal_line(pkg_id, ran["ok"], ran["reason"])
            print(line, flush=True)
            lines.append(line)
            st = apply_result(
                st,
                date=date,
                ok=ran["ok"],
                reason=ran["reason"],
                terminal=line,
                fp=fp,
                stored=stored,
                delta=delta,
            )
            dump_json(package_state_path(state_dir, pkg_id), st)
            row = {
                "package_id": pkg_id,
                "terminal": line,
                "ok": ran["ok"],
                "reason": ran["reason"],
                "exit_code": ran["exit_code"],
                "first_fail_day": st.get("first_fail_day"),
                "environment_fingerprint_sha256": stored["environment_fingerprint_sha256"],
                "environment_fingerprint_canonical": stored[
                    "environment_fingerprint_canonical"
                ],
                "env_delta_vs_last_green": delta,
            }
            results.append(row)
            log.write(canonical_json(row) + "\n")
            log.flush()

    overall = "SUCCESS" if all(r["ok"] for r in results) else "FAILED"
    summary = {
        "date": date,
        "complete": True,
        "classifications": classes_doc,
        "terminal_lines": lines,
        "packages": results,
        "overall": overall,
        "started_at": run_id,
        "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    dump_json(final, summary)
    if partial.exists():
        partial.unlink()
    inprog = state_dir / "runs" / f"{date}.in-progress.json"
    if inprog.exists():
        inprog.unlink()
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CNF-0186 replication-package rot watchdog")
    parser.add_argument("--packages-dir", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--date", required=True, help="calendar day YYYY-MM-DD")
    parser.add_argument("--classifications", default="")
    parser.add_argument("--timeout-sec", type=float, default=15.0)
    args = parser.parse_args(argv)
    cls_path = Path(args.classifications) if args.classifications else None
    summary = run_watchdog(
        Path(args.packages_dir),
        Path(args.state_dir),
        args.date,
        classifications_path=cls_path,
        timeout_sec=args.timeout_sec,
    )
    if not summary.get("terminal_lines"):
        # interpret.py treats empty stdout as FAILED; also fail the process.
        print("FAILED:_watchdog silence", flush=True)
        return 2
    return 0 if summary.get("overall") == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
