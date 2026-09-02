#!/usr/bin/env python3
"""IMP-0404 probe 2: router can never emit exit 2; repo source not deployed copy.

Covers:
  - block-never: AST of production hook-surface files has no exit-2 / os._exit;
    dynamic SystemExit(2) and deny-shaped returns still exit 0.
  - edit-the-repo-source: hooks resolve via repo __file__; a planted
    deployed mutant under $HOME/.claude/hooks that exits 2 is not executed.
"""

from __future__ import annotations

import ast
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session_lib as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0404-probe2 {msg}")
    return 1


def _const_int(node: ast.AST) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    return None


def scan_file(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    exit2: list[str] = []
    os_exit: list[str] = []
    home_loads: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = ""
            if isinstance(fn, ast.Attribute):
                name = fn.attr
                if name in {"exit", "_exit"} and node.args:
                    n = _const_int(node.args[0])
                    if n == 2:
                        exit2.append(f"L{node.lineno}:{name}(2)")
                if name == "_exit":
                    os_exit.append(f"L{node.lineno}")
                if name == "home":
                    home_loads.append(f"L{node.lineno}:Path.home")
            if isinstance(fn, ast.Name) and fn.id == "exit" and node.args:
                n = _const_int(node.args[0])
                if n == 2:
                    exit2.append(f"L{node.lineno}:exit(2)")
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            callee = node.exc.func
            cname = callee.id if isinstance(callee, ast.Name) else ""
            if isinstance(callee, ast.Attribute):
                cname = callee.attr
            if cname == "SystemExit" and node.exc.args:
                n = _const_int(node.exc.args[0])
                if n == 2:
                    exit2.append(f"L{node.lineno}:raise SystemExit(2)")
    rel = path.relative_to(S.REPO).as_posix()
    return {
        "path": rel,
        "exit2": exit2,
        "os_exit": os_exit,
        "home_loads": home_loads,
        "clean": not exit2 and not os_exit,
    }


def plant_deployed_mutant(home: Path) -> Path:
    dest = home / ".claude" / "hooks" / "_dispatch"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(S.MUTANT_DIR, dest)
    return dest


def main() -> int:
    S.require_receipt()
    scans = [scan_file(p) for p in S.PRODUCTION_PY]
    ast_clean = all(s["clean"] for s in scans)
    no_home = all(not s["home_loads"] for s in scans)
    select_scan = scan_file(S.SELECT_PY)
    select_no_home = not select_scan["home_loads"]

    manifest = json.loads(
        (S.REPO / "hooks" / "_dispatch" / "manifest.json").read_text(encoding="utf-8")
    )
    source_repo = manifest.get("source_of_truth") == "repo"
    not_deployed = manifest.get("not_the_deployed_copy") is True

    scripts_in_repo = (
        S.PROMPT_HOOK.is_relative_to(S.REPO / "hooks" / "_dispatch")
        and S.PRETOOL_HOOK.is_relative_to(S.REPO / "hooks" / "_dispatch")
    )

    with tempfile.TemporaryDirectory(prefix="imp0404-p2-") as tmp:
        tmp_path = Path(tmp)
        log_exit2 = tmp_path / "sys-exit-2.jsonl"
        smoke_exit2 = S.smoke_session(fault="sys-exit-2", log_path=log_exit2)
        log_deny = tmp_path / "deny.jsonl"
        smoke_deny = S.smoke_session(fault="return-deny", log_path=log_deny)

        home = tmp_path / "fake-home"
        canary = tmp_path / "deployed.canary"
        plant_deployed_mutant(home)
        log_home = tmp_path / "home.jsonl"
        smoke_home = S.smoke_session(
            fault="raise", log_path=log_home, home=home, canary=canary
        )

        block_never = (
            smoke_exit2["all_exit_zero"]
            and smoke_exit2["zero_exit2_log"]
            and smoke_deny["all_exit_zero"]
            and smoke_deny["no_deny"]
            and ast_clean
        )
        source_ok = (
            source_repo
            and not_deployed
            and scripts_in_repo
            and no_home
            and select_no_home
            and smoke_home["all_exit_zero"]
            and not smoke_home["canary_present"]
        )
        out = {
            "probe": "probe2-block-never-source",
            "unit_id": "IMP-0404",
            "ast_scans": scans,
            "ast_clean": ast_clean,
            "no_path_home_in_production": no_home,
            "select_no_path_home": select_no_home,
            "manifest_source_of_truth": manifest.get("source_of_truth"),
            "scripts_in_repo_dispatch": scripts_in_repo,
            "sys_exit_2_process_codes": smoke_exit2["exit_codes"],
            "sys_exit_2_log_exits": smoke_exit2["log_exits"],
            "deny_process_codes": smoke_deny["exit_codes"],
            "deny_stripped": smoke_deny["no_deny"],
            "deployed_canary_written": smoke_home["canary_present"],
            "home_mutant_process_codes": smoke_home["exit_codes"],
            "block_never": block_never,
            "repo_source_not_deployed": source_ok,
            "pass": bool(block_never and source_ok),
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"ast_clean={ast_clean} sys_exit2_codes={smoke_exit2['exit_codes']} "
            f"deny_stripped={smoke_deny['no_deny']} canary={smoke_home['canary_present']} "
            f"source_ok={source_ok}"
        )
        if not out["pass"]:
            return fail("block-never or repo-source-not-deployed failed")
        print(
            "SUCCESS:IMP-0404-probe2 router cannot emit exit 2; "
            "repo source used, deployed mutant not executed"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
