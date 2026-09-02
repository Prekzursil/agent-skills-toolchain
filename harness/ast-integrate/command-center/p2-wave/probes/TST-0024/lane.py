#!/usr/bin/env python3
"""Clean-room lane: scratch clone + empty HOME/USERPROFILE, then suite delta.

Git operations run only inside the caller-supplied scratch directory. The
worktree at /opt/p2/ast-integrate is never git-added, committed, or checked out.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURE_ORIGIN = HERE / "fixtures" / "origin"
PASS_LIKE = frozenset({"passed", "xpassed"})
STRIP_ENV = (
    "CLAUDE_HOME",
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_CONFIG_HOME",
    "XDG_CONFIG_HOME",
)
PLANTED_SETTINGS = {
    "tst0024_marker": "ambient-profile",
    "note": "planted fixture profile; not a live credential",
}


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_AUTHOR_NAME"] = "TST-0024"
    env["GIT_AUTHOR_EMAIL"] = "tst0024@invalid.example"
    env["GIT_COMMITTER_NAME"] = "TST-0024"
    env["GIT_COMMITTER_EMAIL"] = "tst0024@invalid.example"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    p = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if p.returncode != 0:
        raise RuntimeError(
            f"git {args!r} rc={p.returncode} stderr={(p.stderr or '')[-1200:]}"
        )
    return p


def inspect_home(home: Path) -> dict[str, Any]:
    home = home.resolve()
    top: list[str] = []
    if home.is_dir():
        top = sorted(p.name for p in home.iterdir())
    claude_dir = home / ".claude"
    settings = claude_dir / "settings.json"
    ssh_decoy = home / ".ssh" / "decoy"
    return {
        "path": str(home),
        "exists": home.is_dir(),
        "top_level": top,
        "top_level_count": len(top),
        "claude_dir": claude_dir.is_dir(),
        "claude_settings": settings.is_file(),
        "ssh_decoy": ssh_decoy.is_file(),
        "empty_of_profile": home.is_dir() and len(top) == 0,
    }


def plant_ambient_home(home: Path) -> dict[str, Any]:
    home.mkdir(parents=True, exist_ok=True)
    claude = home / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    settings = claude / "settings.json"
    settings.write_text(
        json.dumps(PLANTED_SETTINGS, indent=2) + "\n", encoding="utf-8"
    )
    ssh = home / ".ssh"
    ssh.mkdir(parents=True, exist_ok=True)
    (ssh / "decoy").write_text("not-a-key\n", encoding="utf-8")
    return inspect_home(home)


def profile_env(home: Path, developer_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(developer_env if developer_env is not None else os.environ)
    home_s = str(home.resolve())
    env["HOME"] = home_s
    env["USERPROFILE"] = home_s
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    stripped = []
    for key in STRIP_ENV:
        if key in env:
            del env[key]
            stripped.append(key)
    env["_TST0024_STRIPPED"] = ",".join(stripped)
    return env


def subprocess_home_view(home: Path, env: dict[str, str]) -> dict[str, Any]:
    script = (
        "import json,os\n"
        "from pathlib import Path\n"
        "home=Path(os.environ.get('HOME') or '')\n"
        "top=sorted(p.name for p in home.iterdir()) if home.is_dir() else []\n"
        "print(json.dumps({"
        "'HOME':os.environ.get('HOME'),"
        "'USERPROFILE':os.environ.get('USERPROFILE'),"
        "'claude_exists':(home/'.claude').exists(),"
        "'ssh_decoy':(home/'.ssh'/'decoy').is_file(),"
        "'top_level':top"
        "}))\n"
    )
    p = subprocess.run(
        [sys.executable, "-B", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    if p.returncode != 0:
        return {
            "ok": False,
            "returncode": p.returncode,
            "stderr": (p.stderr or "")[-800:],
        }
    try:
        view = json.loads((p.stdout or "").strip() or "{}")
    except json.JSONDecodeError as exc:
        return {"ok": False, "parse_error": str(exc), "stdout": (p.stdout or "")[-400:]}
    view["ok"] = True
    view["home_matches_lane"] = view.get("HOME") == str(home.resolve())
    return view


def materialize_clone(scratch: Path) -> dict[str, Any]:
    if not FIXTURE_ORIGIN.is_dir():
        raise FileNotFoundError(f"missing fixture origin {FIXTURE_ORIGIN}")
    origin = scratch / "origin"
    clone = scratch / "clone"
    if origin.exists():
        shutil.rmtree(origin)
    if clone.exists():
        shutil.rmtree(clone)
    shutil.copytree(
        FIXTURE_ORIGIN,
        origin,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    _git(["init", "-b", "main"], cwd=origin)
    _git(["add", "-A"], cwd=origin)
    _git(
        ["commit", "--no-gpg-sign", "-m", "TST-0024 fixture origin"],
        cwd=origin,
    )
    _git(["clone", "--local", str(origin), str(clone)], cwd=scratch)
    head = _git(["rev-parse", "HEAD"], cwd=clone).stdout.strip()
    inside = _git(["rev-parse", "--is-inside-work-tree"], cwd=clone).stdout.strip()
    remote = _git(["remote", "get-url", "origin"], cwd=clone).stdout.strip()
    suite = clone / "tests" / "test_profile_suite.py"
    runner = clone / "run_suite.py"
    return {
        "origin": str(origin),
        "clone": str(clone),
        "head": head,
        "is_work_tree": inside == "true",
        "remote": remote,
        "clone_is_not_origin": origin.resolve() != clone.resolve(),
        "suite_present": suite.is_file(),
        "runner_present": runner.is_file(),
        "remote_is_origin": Path(remote).resolve() == origin.resolve(),
    }


def run_suite_in_clone(clone: Path, env: dict[str, str]) -> dict[str, Any]:
    runner = clone / "run_suite.py"
    p = subprocess.run(
        [sys.executable, "-B", str(runner)],
        cwd=str(clone),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    text = (p.stdout or "").strip()
    try:
        payload = json.loads(text) if text else {}
    except json.JSONDecodeError:
        payload = {}
    members = payload.get("members") if isinstance(payload, dict) else None
    if not isinstance(members, list):
        members = []
    return {
        "returncode": p.returncode,
        "members": members,
        "stderr_tail": (p.stderr or "")[-800:],
        "parse_ok": isinstance(payload, dict) and isinstance(payload.get("members"), list),
    }


def _index(members: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(m.get("id") or ""): str(m.get("outcome") or "")
        for m in members
        if m.get("id")
    }


def enumerate_ambient_dependent(
    ambient: list[dict[str, Any]], clean: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """A test that passes in only one profile is ambient-dependent."""
    a = _index(ambient)
    c = _index(clean)
    rows: list[dict[str, Any]] = []
    for tid in sorted(set(a) | set(c)):
        ao = a.get(tid)
        co = c.get(tid)
        a_pass = ao in PASS_LIKE
        c_pass = co in PASS_LIKE
        if a_pass == c_pass:
            continue
        rows.append(
            {
                "id": tid,
                "ambient_outcome": ao,
                "clean_room_outcome": co,
                "kind": "ambient-only-pass" if a_pass and not c_pass else "clean-only-pass",
            }
        )
    return rows


def counts_of(members: list[dict[str, Any]]) -> dict[str, int]:
    from collections import Counter

    raw = Counter(str(m.get("outcome") or "") for m in members)
    return {
        "passed": int(raw["passed"] + raw["xpassed"]),
        "failed": int(raw["failed"]),
        "skipped": int(raw["skipped"] + raw["xfailed"]),
        "error": int(raw["error"]),
        "collection_error": int(raw["collection_error"]),
        "total_ids": len(members),
    }


def developer_home() -> Path:
    raw = os.environ.get("HOME") or os.environ.get("USERPROFILE") or ""
    return Path(raw) if raw else Path.cwd()


def run_lane(scratch: Path) -> dict[str, Any]:
    scratch = scratch.resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    clone_meta = materialize_clone(scratch)
    clone = Path(clone_meta["clone"])

    live_home = developer_home()
    empty_home = scratch / "empty-home"
    planted_home = scratch / "planted-home"
    empty_home.mkdir(parents=True, exist_ok=True)
    planted_inspect = plant_ambient_home(planted_home)
    empty_inspect = inspect_home(empty_home)

    live_env = profile_env(live_home)
    planted_env = profile_env(planted_home)
    clean_env = profile_env(empty_home)

    live_view = subprocess_home_view(live_home, live_env)
    planted_view = subprocess_home_view(planted_home, planted_env)
    clean_view = subprocess_home_view(empty_home, clean_env)

    live_run = run_suite_in_clone(clone, live_env)
    planted_run = run_suite_in_clone(clone, planted_env)
    clean_run = run_suite_in_clone(clone, clean_env)

    planted_delta = enumerate_ambient_dependent(
        planted_run["members"], clean_run["members"]
    )
    live_delta = enumerate_ambient_dependent(live_run["members"], clean_run["members"])

    return {
        "clone": clone_meta,
        "developer_home": str(live_home),
        "live": {
            "label": "live-developer-HOME",
            "home": str(live_home),
            "inspect": inspect_home(live_home),
            "subprocess_view": live_view,
            "run": live_run,
            "counts": counts_of(live_run["members"]),
        },
        "planted_ambient": {
            "label": "planted-ambient-profile",
            "home": str(planted_home),
            "inspect": planted_inspect,
            "subprocess_view": planted_view,
            "run": planted_run,
            "counts": counts_of(planted_run["members"]),
        },
        "clean_room": {
            "label": "clean-room-empty-HOME",
            "home": str(empty_home),
            "inspect": empty_inspect,
            "subprocess_view": clean_view,
            "run": clean_run,
            "counts": counts_of(clean_run["members"]),
        },
        "ambient_dependent_planted_vs_clean": planted_delta,
        "ambient_dependent_live_vs_clean": live_delta,
        "home_redirected": str(empty_home.resolve()) != str(live_home.resolve()),
        "clean_home_is_empty": bool(empty_inspect.get("empty_of_profile")),
        "clean_subprocess_empty": bool(clean_view.get("ok"))
        and not clean_view.get("claude_exists")
        and not clean_view.get("ssh_decoy")
        and list(clean_view.get("top_level") or []) == [],
        "planted_not_empty": not bool(planted_inspect.get("empty_of_profile")),
    }


EXPECTED_AMBIENT_ONLY = "test_profile_suite.py::ProfileSuite::test_requires_claude_settings"
EXPECTED_CLEAN_ONLY = "test_profile_suite.py::ProfileSuite::test_fails_if_profile_polluted"
FORBIDDEN_IDS = (
    "test_profile_suite.py::ProfileSuite::test_independent_pass",
    "test_profile_suite.py::ProfileSuite::test_independent_fail",
)


def check_home_empty_control(lane: dict[str, Any]) -> dict[str, Any]:
    clean = lane["clean_room"]
    planted = lane["planted_ambient"]
    reasons: list[str] = []
    if not lane["clone"].get("is_work_tree"):
        reasons.append("clone is not a git work tree")
    if not lane["clone"].get("clone_is_not_origin"):
        reasons.append("clone path equals origin")
    if not lane["home_redirected"]:
        reasons.append("clean-room HOME equals developer HOME")
    if not lane["clean_home_is_empty"]:
        reasons.append("clean-room HOME listing is not empty of profile files")
    if not lane["clean_subprocess_empty"]:
        reasons.append("subprocess with clean HOME still saw profile files")
    view = clean["subprocess_view"]
    if view.get("HOME") != clean["home"]:
        reasons.append("subprocess HOME did not match lane empty home")
    if view.get("USERPROFILE") != clean["home"]:
        reasons.append("subprocess USERPROFILE did not match lane empty home")
    if planted["inspect"].get("empty_of_profile"):
        reasons.append("negative control: planted home reported empty")
    if not planted["inspect"].get("claude_settings"):
        reasons.append("planted ambient missing settings.json")
    if clean["inspect"].get("ssh_decoy"):
        reasons.append("clean-room HOME inherited planted ssh decoy")
    if clean["inspect"].get("claude_settings"):
        reasons.append("clean-room HOME inherited ~/.claude/settings.json")
    return {
        "id": "test_clean_room_home_is_actually_empty",
        "pass": not reasons,
        "reasons": reasons,
        "empty_inspect": clean["inspect"],
        "planted_inspect": planted["inspect"],
        "subprocess_view": view,
    }


def check_ambient_enumeration(lane: dict[str, Any]) -> dict[str, Any]:
    rows = lane["ambient_dependent_planted_vs_clean"]
    ids = {r["id"] for r in rows}
    kinds = {r["id"]: r["kind"] for r in rows}
    reasons: list[str] = []
    if EXPECTED_AMBIENT_ONLY not in ids:
        reasons.append(f"missing ambient-only-pass {EXPECTED_AMBIENT_ONLY}")
    elif kinds.get(EXPECTED_AMBIENT_ONLY) != "ambient-only-pass":
        reasons.append(f"{EXPECTED_AMBIENT_ONLY} kind={kinds.get(EXPECTED_AMBIENT_ONLY)}")
    if EXPECTED_CLEAN_ONLY not in ids:
        reasons.append(f"missing clean-only-pass {EXPECTED_CLEAN_ONLY}")
    elif kinds.get(EXPECTED_CLEAN_ONLY) != "clean-only-pass":
        reasons.append(f"{EXPECTED_CLEAN_ONLY} kind={kinds.get(EXPECTED_CLEAN_ONLY)}")
    leaked = [tid for tid in FORBIDDEN_IDS if tid in ids]
    if leaked:
        reasons.append(f"profile-independent tests marked ambient-dependent: {leaked}")
    if len(rows) != 2:
        reasons.append(f"expected exactly 2 ambient-dependent rows, got {len(rows)}")
    return {
        "id": "test_ambient_dependent_tests_are_enumerated",
        "pass": not reasons,
        "reasons": reasons,
        "rows": rows,
        "live_vs_clean": lane["ambient_dependent_live_vs_clean"],
    }
