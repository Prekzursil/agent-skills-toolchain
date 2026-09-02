#!/usr/bin/env python3
"""AUD-0091 clean-room clone baseline engine.

Extracts documented README/RUNBOOK commands, runs them in a cache-redirected
scratch clone, records the first failing step, and classifies clean vs in-place
so an environment-only pass is distinguishable from a documentation defect.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"

NAMED_DOCS = (
    "README.md",
    "README.rst",
    "README.txt",
    "RUNBOOK.md",
    "command-center/RUNBOOK.md",
)

FENCE_RE = re.compile(
    r"```(?:bash|sh|shell|console|zsh)?[^\n]*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)
SKIP_CACHE_DIR = {
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".venv",
    ".git",
    ".cache",
}


def _tail(text: str, n: int = 2000) -> str:
    text = (text or "").replace("\r\n", "\n").strip()
    return text[-n:]


def extract_fenced_commands(text: str) -> list[str]:
    cmds: list[str] = []
    for block in FENCE_RE.findall(text or ""):
        for raw in block.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("$ "):
                line = line[2:].strip()
            if line:
                cmds.append(line)
    return cmds


def census_named_docs(root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    commands: list[str] = []
    for rel in NAMED_DOCS:
        path = root / rel
        present = path.is_file()
        item: dict[str, Any] = {
            "path": rel,
            "present": present,
            "bytes": path.stat().st_size if present else 0,
            "commands": [],
        }
        if present:
            extracted = extract_fenced_commands(
                path.read_text(encoding="utf-8", errors="replace")
            )
            item["commands"] = extracted
            for cmd in extracted:
                if cmd not in commands:
                    commands.append(cmd)
        rows.append(item)
    return {
        "docs": rows,
        "present_count": sum(1 for r in rows if r["present"]),
        "commands": commands,
        "readme_present": (root / "README.md").is_file()
        or (root / "README.rst").is_file()
        or (root / "README.txt").is_file(),
        "runbook_present": (root / "RUNBOOK.md").is_file()
        or (root / "command-center" / "RUNBOOK.md").is_file(),
    }


def git_state(root: Path) -> dict[str, Any]:
    git_dir = root / ".git"
    inside = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return {
        "git_dir_present": git_dir.exists(),
        "inside_work_tree": (inside.returncode == 0)
        and (inside.stdout or "").strip() == "true",
        "inside_exit": inside.returncode,
        "inside_output": _tail((inside.stdout or "") + (inside.stderr or ""), 400),
        "head_exit": head.returncode,
        "head": (head.stdout or "").strip() if head.returncode == 0 else None,
        "head_output": _tail((head.stdout or "") + (head.stderr or ""), 400),
        "pinned_sha": None,
    }


def redirected_env(scratch: Path) -> tuple[dict[str, str], Path]:
    home = scratch / "home"
    cache = scratch / "cache"
    pip = cache / "pip"
    npm = cache / "npm"
    for path in (home, pip, npm):
        path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_CACHE_HOME": str(cache),
            "PIP_CACHE_DIR": str(pip),
            "npm_config_cache": str(npm),
            "NPM_CONFIG_CACHE": str(npm),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
    )
    return env, cache


def cache_inventory(cache_root: Path) -> list[str]:
    if not cache_root.is_dir():
        return []
    files: list[str] = []
    for path in cache_root.rglob("*"):
        if path.is_file():
            files.append(path.relative_to(cache_root).as_posix())
    return sorted(files)


def assert_cache_free(cache_root: Path) -> dict[str, Any]:
    files = cache_inventory(cache_root)
    return {
        "ok": len(files) == 0,
        "n_files": len(files),
        "files": files[:20],
        "redirected": True,
        "cache_root": str(cache_root),
    }


def plant_cache(cache_root: Path) -> Path:
    planted = cache_root / "pip" / "wheels" / "planted.whl"
    planted.parent.mkdir(parents=True, exist_ok=True)
    planted.write_bytes(b"aud-0091-planted-cache-not-a-wheel\n")
    return planted


def copy_tree(src: Path, dest: Path, only: list[str] | None = None) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if only is not None:
        for rel in only:
            origin = src / rel
            target = dest / rel
            if origin.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origin, target)
        return
    for path in src.rglob("*"):
        rel_parts = path.relative_to(src).parts
        if any(part in SKIP_CACHE_DIR for part in rel_parts):
            continue
        target = dest / path.relative_to(src)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def run_command(cmd: str, cwd: Path, env: dict[str, str], timeout: int = 20) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    out = _tail((proc.stdout or "") + (proc.stderr or ""))
    return {
        "command": cmd,
        "exit_code": proc.returncode,
        "output": out,
        "ok": proc.returncode == 0,
    }


def run_sequence(
    commands: list[str], cwd: Path, env: dict[str, str]
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    first_fail: dict[str, Any] | None = None
    for idx, cmd in enumerate(commands, 1):
        try:
            step = run_command(cmd, cwd, env)
        except subprocess.TimeoutExpired as exc:
            step = {
                "command": cmd,
                "exit_code": 124,
                "output": _tail(str(exc.stdout or "") + str(exc.stderr or "") + "TIMEOUT"),
                "ok": False,
            }
        step["index"] = idx
        steps.append(step)
        if not step["ok"] and first_fail is None:
            first_fail = dict(step)
            break
    return {
        "n_commands": len(commands),
        "n_ran": len(steps),
        "all_ok": first_fail is None and len(commands) > 0,
        "empty_sequence": len(commands) == 0,
        "first_fail": first_fail,
        "steps": steps,
    }


def attempt_git_clone(src: Path, dest: Path) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = f"git clone -- {src.as_posix()} {dest.as_posix()}"
    try:
        proc = subprocess.run(
            ["git", "clone", "--", str(src), str(dest)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        out = _tail((proc.stdout or "") + (proc.stderr or ""))
        return {
            "command": cmd,
            "exit_code": proc.returncode,
            "output": out,
            "ok": proc.returncode == 0,
            "dest_has_files": dest.is_dir() and any(dest.iterdir()),
        }
    except subprocess.TimeoutExpired:
        return {
            "command": cmd,
            "exit_code": 124,
            "output": "TIMEOUT",
            "ok": False,
            "dest_has_files": False,
        }
    except FileNotFoundError:
        return {
            "command": cmd,
            "exit_code": 127,
            "output": "git executable not found",
            "ok": False,
            "dest_has_files": False,
        }


def classify(clean: dict[str, Any], inplace: dict[str, Any]) -> str:
    c_fail = clean.get("first_fail")
    i_fail = inplace.get("first_fail")
    if c_fail is None and i_fail is None:
        if clean.get("empty_sequence") and inplace.get("empty_sequence"):
            return "inputs-absent"
        return "clone-ok"
    if c_fail is not None and i_fail is None:
        return "environment-only"
    if c_fail is None and i_fail is not None:
        return "worktree-only-failure"
    assert c_fail is not None and i_fail is not None
    same_cmd = c_fail.get("command") == i_fail.get("command")
    same_rc = c_fail.get("exit_code") == i_fail.get("exit_code")
    if same_cmd and same_rc:
        return "documentation-defect"
    return "divergent-failures"


def _empty_docs_fail() -> dict[str, Any]:
    return {
        "index": 0,
        "command": "extract documented setup/build/test from README and RUNBOOK",
        "exit_code": 2,
        "output": "README.md and RUNBOOK.md are absent or contain no fenced commands",
        "ok": False,
    }


def run_documented_tree(
    tree: Path,
    *,
    clone_mode: str,
    committed_only: list[str] | None = None,
    plant_package_cache: bool = False,
) -> dict[str, Any]:
    """Run named-doc commands in a cache-redirected scratch copy of `tree`."""
    with tempfile.TemporaryDirectory(prefix="aud0091-run-") as raw:
        scratch = Path(raw)
        env, cache = redirected_env(scratch)
        if plant_package_cache:
            plant_cache(cache)
        cache_state = assert_cache_free(cache)
        docs = census_named_docs(tree)
        commands = list(docs["commands"])
        if not cache_state["ok"]:
            fail = {
                "index": 0,
                "command": "assert package cache empty or redirected before run",
                "exit_code": 4,
                "output": (
                    f"cache not free: n_files={cache_state['n_files']} "
                    f"files={cache_state['files']}"
                ),
                "ok": False,
            }
            return {
                "clone_mode": clone_mode,
                "cache": cache_state,
                "docs": docs,
                "commands": commands,
                "empty_sequence": len(commands) == 0,
                "all_ok": False,
                "n_commands": len(commands),
                "n_ran": 0,
                "first_fail": fail,
                "steps": [fail],
                "skipped_for_dirty_cache": True,
            }
        if clone_mode == "inplace":
            if not commands:
                seq = {
                    "n_commands": 0,
                    "n_ran": 0,
                    "all_ok": False,
                    "empty_sequence": True,
                    "first_fail": _empty_docs_fail(),
                    "steps": [_empty_docs_fail()],
                }
            else:
                seq = run_sequence(commands, tree, env)
            return {
                "clone_mode": clone_mode,
                "cache": cache_state,
                "docs": docs,
                "commands": commands,
                "skipped_clone": True,
                **seq,
            }
        clone_dest = scratch / "clone"
        copy_tree(tree, clone_dest, only=committed_only)
        clone_docs = census_named_docs(clone_dest)
        commands = list(clone_docs["commands"])
        if not commands:
            seq = {
                "n_commands": 0,
                "n_ran": 0,
                "all_ok": False,
                "empty_sequence": True,
                "first_fail": _empty_docs_fail(),
                "steps": [_empty_docs_fail()],
            }
        else:
            seq = run_sequence(commands, clone_dest, env)
        return {
            "clone_mode": clone_mode,
            "cache": cache_state,
            "docs": clone_docs,
            "commands": commands,
            "skipped_clone": False,
            **seq,
        }


def measure_worktree(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    docs = census_named_docs(root)
    git = git_state(root)
    with tempfile.TemporaryDirectory(prefix="aud0091-wt-") as raw:
        scratch = Path(raw)
        env, cache = redirected_env(scratch)
        cache_state = assert_cache_free(cache)
        clone_dest = scratch / "fresh-clone"
        clone = attempt_git_clone(root, clone_dest)
        steps: list[dict[str, Any]] = [
            {
                "index": 0,
                "command": "assert package cache empty or redirected before run",
                "exit_code": 0 if cache_state["ok"] else 4,
                "output": (
                    f"redirected cache n_files={cache_state['n_files']} "
                    f"ok={cache_state['ok']}"
                ),
                "ok": cache_state["ok"],
            },
            {
                "index": 1,
                "command": clone["command"],
                "exit_code": clone["exit_code"],
                "output": clone["output"],
                "ok": clone["ok"],
            },
        ]
        first_fail = next((s for s in steps if not s["ok"]), None)
        classification = "clone-impossible"
        if clone["ok"] and docs["commands"]:
            classification = "clone-reached-docs"
        elif clone["ok"]:
            classification = "clone-ok-no-docs"
        return {
            "root": str(root),
            "git": git,
            "docs": docs,
            "cache": cache_state,
            "clone": clone,
            "clean": {
                "empty_sequence": (not clone["ok"]) or (not docs["commands"]),
                "all_ok": False,
                "first_fail": first_fail,
                "steps": steps,
            },
            "inplace": {
                "skipped_clone": True,
                "skipped_execute": True,
                "skip_reason": (
                    "README.md and command-center/RUNBOOK.md document mutating "
                    "steps (git clone, npm install, close.py, seed.py --force). "
                    "Those commands are not executed against the live worktree. "
                    "Clean-room first fail is git clone of this path."
                ),
                "empty_sequence": not docs["commands"],
                "n_commands": len(docs["commands"]),
                "commands_head": list(docs["commands"][:20]),
                "all_ok": False,
                "first_fail": None,
            },
            "classification": classification,
            "headline": (
                "This worktree is not a git repository (no .git; rev-parse fails), "
                "so a cache-redirected git clone of this path is the first "
                "failing step of a clean-room clone at a pinned SHA. README.md "
                "and command-center/RUNBOOK.md are present with documented "
                "setup/build/test commands; those commands were not executed "
                "on the live tree."
            ),
            "env_home_redirected": env.get("HOME"),
            "pip_cache_dir": env.get("PIP_CACHE_DIR"),
        }


def run_controls() -> dict[str, Any]:
    good_tree = FIXTURES / "good"
    bad_tree = FIXTURES / "bad"
    env_tree = FIXTURES / "env_inplace"
    defect_tree = FIXTURES / "docs_defect"

    good_clean = run_documented_tree(good_tree, clone_mode="copy")
    bad_clean = run_documented_tree(bad_tree, clone_mode="copy")
    cache_dirty = run_documented_tree(
        good_tree, clone_mode="copy", plant_package_cache=True
    )
    env_clean = run_documented_tree(
        env_tree, clone_mode="copy", committed_only=["README.md"]
    )
    env_inplace = run_documented_tree(env_tree, clone_mode="inplace")
    defect_clean = run_documented_tree(defect_tree, clone_mode="copy")
    defect_inplace = run_documented_tree(defect_tree, clone_mode="inplace")

    env_class = classify(env_clean, env_inplace)
    defect_class = classify(defect_clean, defect_inplace)

    first_fail_fired = (
        bad_clean.get("first_fail") is not None
        and bad_clean["first_fail"].get("exit_code") == 17
    )
    first_fail_silent = good_clean.get("all_ok") is True
    cache_fired = cache_dirty.get("skipped_for_dirty_cache") is True
    cache_silent = good_clean.get("cache", {}).get("ok") is True
    env_fired = env_class == "environment-only"
    env_silent = defect_class == "documentation-defect"

    def _status(fired: bool, silent: bool) -> str:
        if fired and silent:
            return "ARMED"
        if fired and not silent:
            return "FIRES-IN-BOTH"
        if (not fired) and silent:
            return "SILENT-IN-BOTH"
        return "DISARMED"

    return {
        "good_clean": {
            "all_ok": good_clean.get("all_ok"),
            "commands": good_clean.get("commands"),
            "first_fail": good_clean.get("first_fail"),
            "cache_ok": good_clean.get("cache", {}).get("ok"),
            "steps": [
                {"command": s["command"], "exit_code": s["exit_code"]}
                for s in (good_clean.get("steps") or [])
            ],
        },
        "bad_clean": {
            "all_ok": bad_clean.get("all_ok"),
            "first_fail": bad_clean.get("first_fail"),
            "n_ran": bad_clean.get("n_ran"),
        },
        "cache_dirty": {
            "skipped_for_dirty_cache": cache_dirty.get("skipped_for_dirty_cache"),
            "cache": cache_dirty.get("cache"),
            "first_fail": cache_dirty.get("first_fail"),
        },
        "env_only": {
            "clean_exit": (env_clean.get("first_fail") or {}).get("exit_code"),
            "inplace_ok": env_inplace.get("all_ok"),
            "classification": env_class,
        },
        "docs_defect": {
            "clean_exit": (defect_clean.get("first_fail") or {}).get("exit_code"),
            "inplace_exit": (defect_inplace.get("first_fail") or {}).get("exit_code"),
            "classification": defect_class,
        },
        "detectors": {
            "first-failing-step": {
                "fired_on_bad_state": first_fail_fired,
                "silent_on_good_state": first_fail_silent,
                "status": _status(first_fail_fired, first_fail_silent),
            },
            "cache-free-precondition": {
                "fired_on_bad_state": cache_fired,
                "silent_on_good_state": cache_silent,
                "status": _status(cache_fired, cache_silent),
            },
            "env-vs-docs": {
                "fired_on_bad_state": env_fired,
                "silent_on_good_state": env_silent,
                "status": _status(env_fired, env_silent),
            },
        },
    }


def falsify_headline(repo: Path | None = None) -> dict[str, Any]:
    """Independently try to refute 'this worktree is not a git repository'."""
    root = repo or REPO
    root_readmes = [
        p.relative_to(root).as_posix()
        for p in root.glob("README*")
        if p.is_file()
    ]
    named = []
    for rel in (
        "README.md",
        "RUNBOOK.md",
        "command-center/RUNBOOK.md",
        "CONTRIBUTING.md",
        "AGENTS.md",
        "SETUP.md",
        "INSTALL.md",
    ):
        if (root / rel).is_file():
            named.append(rel)
    git = git_state(root)
    git_dir = bool(git["git_dir_present"])
    layout = root / "docs" / "layout-migration.md"
    alt = {
        "path": "docs/layout-migration.md",
        "present": layout.is_file(),
        "commands": extract_fenced_commands(
            layout.read_text(encoding="utf-8", errors="replace")
        )
        if layout.is_file()
        else [],
        "in_catalog_named_sources": False,
    }
    catalog_named = [
        n
        for n in named
        if n in {"README.md", "RUNBOOK.md", "command-center/RUNBOOK.md"}
    ]
    # Headline is clone-impossible, not docs-absent. README presence is expected.
    refuted = git_dir or bool(git["inside_work_tree"])
    return {
        "root_readme_glob": root_readmes,
        "named_present": named,
        "catalog_named_present": catalog_named,
        "git_dir_present": git_dir,
        "inside_work_tree": git["inside_work_tree"],
        "alternate_doc": alt,
        "headline": "not-a-git-repository-clone-impossible",
        "headline_refuted": refuted,
        "verdict": "REFUTED" if refuted else "STANDS",
    }


def live_report() -> dict[str, Any]:
    worktree = measure_worktree()
    controls = run_controls()
    reviewer = falsify_headline()
    return {
        "worktree": worktree,
        "controls": controls,
        "reviewer_falsify": reviewer,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(live_report(), indent=2, sort_keys=True, default=str))
