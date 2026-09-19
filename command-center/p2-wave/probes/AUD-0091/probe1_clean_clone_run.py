#!/usr/bin/env python3
"""AUD-0091 named probe 1: execute the documented setup/build/test sequence
verbatim in a genuinely fresh clone, into a scratch directory outside this
checkout, with the package cache redirected to a brand-new empty directory
(never the operator's real `~/.npm`) and $HOME pointed at a scratch dir too
so no ambient config/cache from THIS session's checkout can leak in.

Scope of "the documented setup, build, and test sequence" (README.md +
AGENTS.md Cursor Cloud caveats), in doc order, each one a REAL subprocess
call with its exit code and output recorded -- never invented:

  1. `git clone <public url>`                     (README Quick Start)
  2. `git checkout <pinned main SHA>`              (catalog input: "pinned SHA")
  3. `npm install`                                 (README Quick Start)
  4. `npm test`                                    (README Quick Start)
  5. `npm run validate:skills`                     (README Validation)
  6. `python3 scripts/test-live-skill-helpers.py`   (README Validation)

Explicitly OUT of scope, and recorded as such rather than silently skipped:
the README's `claude plugin marketplace add/install`, `git-crypt unlock`,
and `claude mcp add` steps. Those mount this repo's skill/MCP surface into a
live Claude Code / Codex session -- they are not part of building or testing
THIS repository's own code, and this substrate has neither the `claude` nor
the `git-crypt` binary (measured below, not assumed).

This probe reports ok=false with the real subprocess output on any crash of
the PROBE ITSELF (e.g. clone failure); a failing DOCUMENTED step is not a
probe failure -- it is the measurement this unit exists to make, and is
carried in `first_failing_step` instead.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cache_check import is_cache_free  # noqa: E402

REPO = Path(__file__).resolve().parents[4]
OUT_JSON = Path(__file__).resolve().parent / "probe1-clean-clone-run.json"
OUT_RAW = Path(__file__).resolve().parent / "probe1-clean-clone-run.raw.txt"
CLONE_URL = "https://github.com/Prekzursil/agent-skills-toolchain.git"

OUT_OF_SCOPE = [
    {
        "doc_step": "claude plugin marketplace add Prekzursil/agent-skills-toolchain "
        "--sparse .claude-plugin .agents/skills skills skills-claude-only",
        "reason": "mounts this repo as a Claude Code plugin marketplace; requires the "
        "`claude` CLI, which is absent on this substrate (checked with shutil.which).",
    },
    {
        "doc_step": "claude plugin install agent-skills-toolchain@agent-skills-toolchain",
        "reason": "same `claude` CLI dependency as above.",
    },
    {
        "doc_step": "git-crypt unlock /path/to/agent-skills-toolchain.gitcrypt.key",
        "reason": "requires an exported key from an external password manager that this "
        "substrate has no access to, and the `git-crypt` binary is also absent.",
    },
    {
        "doc_step": "claude mcp add --scope user codex -- codex mcp-server",
        "reason": "mounts Codex as an MCP server inside a live Claude Code session; "
        "requires the `claude` CLI, absent on this substrate.",
    },
]


def run(cmd: list[str], cwd: Path, env: dict | None, timeout: int) -> dict:
    """`stdout_full`/`stderr_full` are for THIS PROCESS's own parsing only
    (e.g. summing per-workspace TAP summary lines) and are stripped before
    anything is written to disk -- see the explicit key filter in main()."""
    try:
        r = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "cmd": cmd,
            "exit_code": r.returncode,
            "stdout_tail": r.stdout[-12000:],
            "stderr_tail": r.stderr[-12000:],
            "stdout_full": r.stdout,
            "stderr_full": r.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        err = exc.stderr or ""
        return {
            "cmd": cmd,
            "exit_code": None,
            "stdout_tail": out[-12000:],
            "stderr_tail": err[-12000:],
            "stdout_full": out,
            "stderr_full": err,
            "timed_out": True,
        }
    except OSError as exc:
        return {
            "cmd": cmd,
            "exit_code": None,
            "stdout_tail": "",
            "stderr_tail": f"{type(exc).__name__}: {exc}",
            "stdout_full": "",
            "stderr_full": f"{type(exc).__name__}: {exc}",
            "timed_out": False,
            "os_error": True,
        }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_lines: list[str] = [
        "AUD-0091 NAMED PROBE 1: clean-room fresh-clone documented setup/build/test sequence",
        f"started_at={started}",
        f"clone_url={CLONE_URL}",
    ]

    claude_bin = shutil.which("claude")
    git_crypt_bin = shutil.which("git-crypt")
    pwsh_bin = shutil.which("pwsh")
    raw_lines.append(
        f"tool_presence claude={claude_bin!r} git-crypt={git_crypt_bin!r} pwsh={pwsh_bin!r}"
    )

    # --- pinned SHA: live HEAD of origin main, measured via ls-remote (no local cache) ---
    # Uses the ambient PATH (inherited env) purely to resolve the `git` binary and
    # DNS/TLS -- this is a read-only network query, not part of the isolated run.
    lsremote = run(
        ["git", "ls-remote", CLONE_URL, "main"], cwd=REPO, env=None, timeout=60
    )
    raw_lines.append("---- git ls-remote origin main ----")
    raw_lines.append(lsremote["stdout_tail"])
    pinned_sha = None
    if lsremote["exit_code"] == 0 and lsremote["stdout_tail"].strip():
        pinned_sha = lsremote["stdout_tail"].split()[0].strip()

    if not pinned_sha:
        doc = {
            "started_at": started,
            "ok": False,
            "error": "could not resolve a pinned main SHA via git ls-remote",
            "ls_remote": lsremote,
        }
        OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        raw_lines.append("FAILED:AUD-0091-probe1 no pinned SHA resolved")
        OUT_RAW.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
        print("\n".join(raw_lines[-5:]))
        return 1

    scratch_root = Path(tempfile.mkdtemp(prefix="aud-0091-clean-clone-"))
    clone_dir = scratch_root / "repo"
    npm_cache_dir = scratch_root / "npm-cache-empty"
    fake_home = scratch_root / "fake-home"
    npm_cache_dir.mkdir(parents=True, exist_ok=True)
    fake_home.mkdir(parents=True, exist_ok=True)

    # Cache-free precheck: the SAME detector the control script uses,
    # applied to the REAL directory this run is about to use.
    precheck = is_cache_free(npm_cache_dir)
    raw_lines.append(f"cache_dir_precheck={json.dumps(precheck)}")

    # Derive PATH from the ACTUAL resolved binary locations on this substrate
    # (never hardcode a version-specific nvm path) so the isolated run can find
    # git/node/npm/python3 while still using a scratch HOME and a redirected
    # npm cache -- isolating caches/config, not breaking binary resolution.
    node_bin = shutil.which("node")
    npm_bin = shutil.which("npm")
    git_bin = shutil.which("git")
    bin_dirs = sorted(
        {str(Path(p).parent) for p in (node_bin, npm_bin, git_bin, sys.executable) if p}
    )
    isolated_path = ":".join(
        bin_dirs
        + [
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
        ]
    )
    isolated_env = {
        "HOME": str(fake_home),
        "NPM_CONFIG_CACHE": str(npm_cache_dir),
        "PATH": isolated_path,
        "LANG": "C.UTF-8",
    }
    raw_lines.append(f"isolated_PATH={isolated_path}")

    steps: list[dict] = []

    # Step 1: git clone (README Quick Start, verbatim URL).
    # SCOPE NOTE (disclosed, not hidden): this clone runs with env=None, i.e. this
    # cloud substrate's AMBIENT git config, which rewrites https://github.com/ to
    # an authenticated URL via `url.<...>.insteadof` (measured below). A truly
    # credential-free network fetch is therefore NOT what this step tests -- the
    # tests_required cache-free guarantee is about the npm PACKAGE cache used by
    # the build/test steps that follow, which IS fully isolated (fake $HOME +
    # brand-new $NPM_CONFIG_CACHE), not about git credential provisioning.
    ambient_insteadof = run(
        ["git", "config", "--global", "--get-regexp", "url\\..*\\.insteadof"],
        cwd=REPO,
        env=None,
        timeout=10,
    )
    raw_lines.append(
        "ambient_git_insteadof_rewrite_present="
        f"{bool(ambient_insteadof['stdout_tail'].strip())} "
        "(credentials redacted by the harness in any tool-result echo; "
        "verbatim value never written to this receipt)"
    )
    r = run(
        ["git", "clone", CLONE_URL, str(clone_dir)],
        cwd=scratch_root,
        env=None,
        timeout=600,
    )
    steps.append({"id": "git-clone", "doc_step": f"git clone {CLONE_URL}", **r})
    raw_lines.append(f"---- step git-clone exit={r['exit_code']} ----")
    raw_lines.append(r["stdout_tail"][-2000:] + r["stderr_tail"][-2000:])

    clone_ok = r["exit_code"] == 0 and clone_dir.is_dir()
    if clone_ok:
        # Step 2: pin to the measured main SHA (catalog input: "a fresh clone
        # of main at the pinned SHA", not whatever ref HEAD happens to float to).
        r2 = run(["git", "checkout", pinned_sha], cwd=clone_dir, env=None, timeout=60)
        steps.append(
            {"id": "git-checkout-pin", "doc_step": f"git checkout {pinned_sha}", **r2}
        )
        raw_lines.append(f"---- step git-checkout-pin exit={r2['exit_code']} ----")
        raw_lines.append(r2["stdout_tail"][-2000:] + r2["stderr_tail"][-2000:])
        pin_ok = r2["exit_code"] == 0
    else:
        pin_ok = False

    documented_cmds: list[tuple[str, list[str], int]] = [
        ("npm-install", ["npm", "install"], 900),
        ("npm-test", ["npm", "test"], 300),
        ("npm-run-validate-skills", ["npm", "run", "validate:skills"], 120),
        (
            "python-test-live-skill-helpers",
            [sys.executable, "scripts/test-live-skill-helpers.py"],
            120,
        ),
    ]

    if clone_ok and pin_ok:
        for step_id, cmd, timeout in documented_cmds:
            r3 = run(cmd, cwd=clone_dir, env=isolated_env, timeout=timeout)
            steps.append({"id": step_id, "doc_step": " ".join(cmd), **r3})
            raw_lines.append(f"---- step {step_id} exit={r3['exit_code']} ----")
            raw_lines.append((r3["stdout_tail"] + "\n" + r3["stderr_tail"])[-6000:])
    else:
        raw_lines.append(
            "SKIPPED remaining documented steps: clone or pin-checkout failed first"
        )

    # First failing step = first step whose exit_code is not 0 (None/timeout counts as failing).
    first_failing = None
    for s in steps:
        if s.get("exit_code") != 0:
            first_failing = s
            break

    all_steps_passed = first_failing is None and len(steps) == 2 + len(documented_cmds)
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # test-count extraction from npm-test step, for the probe2 comparator.
    npm_test_step = next((s for s in steps if s["id"] == "npm-test"), None)
    npm_test_summary = {"pass": None, "fail": None, "exit_code": None}
    if npm_test_step is not None:
        # node --test's TAP summary ("# pass N" / "# fail N") is printed ONCE
        # PER WORKSPACE (npm --workspaces runs 3 separate test commands), so
        # these must be SUMMED across all occurrences, not overwritten by the
        # last one -- overwriting silently under-counts by 2/3 of the suite.
        combined = npm_test_step.get(
            "stdout_full", npm_test_step["stdout_tail"]
        ) + npm_test_step.get("stderr_full", npm_test_step["stderr_tail"])
        npm_test_summary["exit_code"] = npm_test_step["exit_code"]
        pass_total = 0
        fail_total = 0
        saw_any = False
        for line in combined.splitlines():
            line = line.strip()
            if line.startswith("# pass "):
                pass_total += int(line.split()[-1])
                saw_any = True
            elif line.startswith("# fail "):
                fail_total += int(line.split()[-1])
                saw_any = True
        if saw_any:
            npm_test_summary["pass"] = pass_total
            npm_test_summary["fail"] = fail_total

    doc = {
        "started_at": started,
        "ended_at": ended,
        "ok": clone_ok
        and pin_ok,  # the PROBE ran to completion; docs-step pass/fail is separate
        "clone_url": CLONE_URL,
        "pinned_sha": pinned_sha,
        "scratch_root": str(scratch_root),
        "npm_cache_dir": str(npm_cache_dir),
        "fake_home": str(fake_home),
        "cache_dir_precheck": precheck,
        "tool_presence": {
            "claude": claude_bin,
            "git_crypt": git_crypt_bin,
            "pwsh": pwsh_bin,
        },
        "out_of_scope_documented_steps": OUT_OF_SCOPE,
        "steps": [
            {
                k: v
                for k, v in s.items()
                if k not in ("stdout_tail", "stderr_tail", "stdout_full", "stderr_full")
            }
            | {
                "stdout_tail": s["stdout_tail"][-4000:],
                "stderr_tail": s["stderr_tail"][-4000:],
            }
            for s in steps
        ],
        "first_failing_step": (
            {
                k: v
                for k, v in first_failing.items()
                if k not in ("stdout_tail", "stderr_tail", "stdout_full", "stderr_full")
            }
            | {
                "stdout_tail": first_failing["stdout_tail"][-4000:],
                "stderr_tail": first_failing["stderr_tail"][-4000:],
            }
            if first_failing
            else None
        ),
        "all_documented_steps_passed": all_steps_passed,
        "npm_test_summary": npm_test_summary,
    }
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    raw_lines.append(f"pinned_sha={pinned_sha}")
    raw_lines.append(
        f"first_failing_step={first_failing['id'] if first_failing else None} "
        f"all_documented_steps_passed={all_steps_passed}"
    )
    raw_lines.append(
        f"{'SUCCESS' if doc['ok'] else 'FAILED'}:AUD-0091-probe1 clone_ok={clone_ok} pin_ok={pin_ok}"
    )
    OUT_RAW.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

    # cleanup scratch (the artifact is the JSON/raw, not the scratch tree itself)
    shutil.rmtree(scratch_root, ignore_errors=True)

    print(
        f"unit=AUD-0091 probe1 clone_ok={clone_ok} pin_ok={pin_ok} "
        f"first_failing_step={first_failing['id'] if first_failing else None} "
        f"ok={doc['ok']}"
    )
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
