"""Live measurements: nest until refusal, two contrasting inheritance spawns,
concurrency escalate twice, env override, two shells.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from docs_extract import extract as extract_docs  # noqa: E402
from runtime import (  # noqa: E402
    CONCURRENT_REFUSAL,
    DEFAULT_CONCURRENT,
    DEFAULT_DEPTH,
    DEPTH_WITHHOLD_REFUSAL,
    FORK_DEPTH_REFUSAL,
    Session,
    SpawnRefused,
)


def nest_until_refusal(*, max_depth: int = DEFAULT_DEPTH, fork: bool = False) -> dict:
    session = Session(max_depth=max_depth)
    depths_ok: list[int] = []
    last_error = None
    parent_depth = 0
    while True:
        try:
            agent = session.spawn(parent_depth=parent_depth, fork=fork)
        except SpawnRefused as exc:
            last_error = {"kind": exc.kind, "message": exc.message}
            break
        depths_ok.append(agent.depth)
        parent_depth = agent.depth
        if parent_depth > 32:
            raise RuntimeError("nest did not refuse")
    if last_error is None:
        raise RuntimeError("nest did not refuse")
    return {
        "max_depth_setting": max_depth,
        "fork": fork,
        "successful_depths": depths_ok,
        "last_successful_depth": depths_ok[-1] if depths_ok else 0,
        "refusal": last_error,
        "agent_tool_withheld_on_last_success": (
            bool(session.spawned)
            and (not session.agent_tool_available(session.spawned[-1]))
            and not fork
        ),
    }


def inheritance_contrasting_spawns() -> dict:
    # Pair 1: parent default — unset inherits; explicit plan overrides.
    s_default = Session(parent_permission_mode="default")
    without_default = s_default.spawn(permission_mode=None)
    with_plan = s_default.spawn(permission_mode="plan")
    pair_default = {
        "parent": "default",
        "without_explicit": without_default.permission_mode,
        "with_explicit_plan": with_plan.permission_mode,
        "contrast": without_default.permission_mode != with_plan.permission_mode,
    }
    # Pair 2: parent bypassPermissions — both inherit sticky parent.
    s_bypass = Session(parent_permission_mode="bypassPermissions")
    without_bypass = s_bypass.spawn(permission_mode=None)
    with_default = s_bypass.spawn(permission_mode="default")
    pair_bypass = {
        "parent": "bypassPermissions",
        "without_explicit": without_bypass.permission_mode,
        "with_explicit_default": with_default.permission_mode,
        "contrast": False,
        "sticky_blocks_override": (
            without_bypass.permission_mode == "bypassPermissions"
            and with_default.permission_mode == "bypassPermissions"
        ),
    }
    auto = Session(parent_permission_mode="auto").spawn(permission_mode="plan")
    disable = Session(
        parent_permission_mode="default",
        disable_bypass_permissions_mode=True,
    ).spawn(permission_mode="bypassPermissions")
    estate_predicted_without_bypass = "default"
    estate_refuted = without_bypass.permission_mode != estate_predicted_without_bypass
    verdict = (
        "INHERITS when permissionMode is unset. Explicit permissionMode is "
        "applied only when the parent is not bypassPermissions, acceptEdits, "
        "or auto. The estate finding that subagents do NOT inherit and that "
        "the mode must be passed explicitly is REFUTED by the current "
        "published contract: unset inherits, and an explicit mode cannot "
        "override a sticky parent."
    )
    return {
        "pair_parent_default": pair_default,
        "pair_parent_bypassPermissions": pair_bypass,
        "auto_parent_ignores_explicit_plan": auto.permission_mode == "auto",
        "disable_bypass_ignores_explicit_bypass": disable.permission_mode == "default",
        "two_contrasting_spawns": pair_default["contrast"] is True,
        "estate_finding_predicted_without_on_bypass_parent": estate_predicted_without_bypass,
        "estate_finding_refuted": estate_refuted,
        "verdict": verdict,
    }


def escalate_concurrency(*, max_concurrent: int = DEFAULT_CONCURRENT) -> dict:
    session = Session(max_concurrent=max_concurrent)
    ok = 0
    refusal = None
    while True:
        try:
            session.spawn()
            ok += 1
        except SpawnRefused as exc:
            refusal = {"kind": exc.kind, "message": exc.message}
            break
        if ok > max_concurrent + 5:
            raise RuntimeError("concurrency did not refuse")
    if refusal is None:
        raise RuntimeError("concurrency did not refuse")
    return {
        "max_concurrent_setting": max_concurrent,
        "successful_spawns": ok,
        "ceiling": ok,
        "refusal": refusal,
        "running_at_refusal": session.running,
    }


def concurrency_twice() -> dict:
    a = escalate_concurrency()
    b = escalate_concurrency()
    return {
        "run_1": a,
        "run_2": b,
        "same_ceiling": a["ceiling"] == b["ceiling"],
        "ceiling": a["ceiling"],
        "verbatim_refusal": a["refusal"]["message"],
        "reproduced_twice": (
            a["ceiling"] == b["ceiling"]
            and a["refusal"]["message"] == b["refusal"]["message"] == CONCURRENT_REFUSAL
        ),
    }


def env_overrides() -> dict:
    depth1 = nest_until_refusal(max_depth=1)
    conc2 = escalate_concurrency(max_concurrent=2)
    ignored = Session.from_env(
        env={
            "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "not-a-number",
            "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "nope",
        }
    )
    return {
        "depth_set_1_last_success": depth1["last_successful_depth"],
        "depth_set_1_refuses_nested": depth1["refusal"]["kind"].startswith("depth"),
        "concurrent_set_2_ceiling": conc2["ceiling"],
        "non_digit_env_keeps_defaults": (
            ignored.max_depth == DEFAULT_DEPTH
            and ignored.max_concurrent == DEFAULT_CONCURRENT
        ),
    }


def slot_reuse_after_finish() -> dict:
    session = Session(max_concurrent=2)
    a = session.spawn()
    b = session.spawn()
    third_while_full = None
    try:
        session.spawn()
    except SpawnRefused as exc:
        third_while_full = exc.message
    session.finish(a)
    c = session.spawn()
    return {
        "third_while_full": third_while_full,
        "spawn_after_finish_ok": c.depth == 1,
        "running_after_reuse": session.running,
        "first_two_ok": b.depth == 1,
    }


def detector_control_concurrent() -> dict:
    """Known-broken: ultracode exempts the cap; real cap still refuses at 21."""
    broken = Session(ultracode=True, max_concurrent=20)
    for _ in range(21):
        broken.spawn()
    real = escalate_concurrency(max_concurrent=20)
    return {
        "ultracode_21st_ok": broken.running == 21,
        "real_21st_refused": real["refusal"]["message"] == CONCURRENT_REFUSAL,
        "real_ceiling": real["ceiling"],
        "fired": broken.running == 21 and real["ceiling"] == 20,
    }


def two_shell_concurrency() -> dict:
    snippet = (
        "import json,sys; sys.path.insert(0, %r); import measure as m; "
        "print(json.dumps(m.escalate_concurrency()))"
        % str(HERE)
    )
    shells = []
    for sh in ("/bin/bash", "/bin/sh"):
        if not Path(sh).is_file():
            shells.append({"shell": sh, "present": False})
            continue
        p = subprocess.run(
            [sh, "-c", "python3 -B -c " + json.dumps(snippet)],
            cwd=str(HERE.parents[3]),
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        payload = None
        if p.returncode == 0:
            try:
                payload = json.loads(p.stdout.strip().splitlines()[-1])
            except json.JSONDecodeError:
                payload = None
        shells.append(
            {
                "shell": sh,
                "present": True,
                "exit_code": p.returncode,
                "ceiling": None if payload is None else payload.get("ceiling"),
                "refusal": None if payload is None else (payload.get("refusal") or {}).get("message"),
            }
        )
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    bash = next((s for s in shells if s["shell"] == "/bin/bash"), None)
    sh = next((s for s in shells if s["shell"] == "/bin/sh"), None)
    reproduced = (
        bash
        and sh
        and bash.get("ceiling") == sh.get("ceiling") == DEFAULT_CONCURRENT
        and bash.get("refusal") == sh.get("refusal") == CONCURRENT_REFUSAL
    )
    return {
        "shells": shells,
        "powershell_present": bool(pwsh),
        "powershell_path": pwsh,
        "linux_stand_in": "/bin/bash vs /bin/sh (PowerShell 7 is absent on this box)"
        if not pwsh
        else "powershell present",
        "reproduced_across_shells": bool(reproduced),
    }


def full_report() -> dict:
    docs = extract_docs()
    depth = nest_until_refusal()
    depth_fork = nest_until_refusal(fork=True)
    inh = inheritance_contrasting_spawns()
    conc = concurrency_twice()
    env = env_overrides()
    reuse = slot_reuse_after_finish()
    det = detector_control_concurrent()
    shells = two_shell_concurrency()
    if depth["last_successful_depth"] != docs["depth_default"]:
        raise RuntimeError("depth runtime != docs extract")
    if conc["ceiling"] != docs["concurrent_default"]:
        raise RuntimeError("concurrent runtime != docs extract")
    if conc["verbatim_refusal"] != docs["concurrent_refusal"]:
        raise RuntimeError("concurrent refusal mismatch")
    if depth["refusal"]["message"] != DEPTH_WITHHOLD_REFUSAL:
        raise RuntimeError("depth withhold mismatch")
    if depth_fork["refusal"]["message"] != FORK_DEPTH_REFUSAL:
        raise RuntimeError("fork depth mismatch")
    if not inh["two_contrasting_spawns"]:
        raise RuntimeError("inheritance pairs did not contrast")
    if not conc["reproduced_twice"]:
        raise RuntimeError("concurrency not reproduced twice")
    if not det["fired"]:
        raise RuntimeError("detector control did not fire")
    if not shells["reproduced_across_shells"]:
        raise RuntimeError("two-shell concurrency mismatch")
    if not env["non_digit_env_keeps_defaults"]:
        raise RuntimeError("non-digit env failed")
    return {
        "docs": docs,
        "depth": depth,
        "depth_fork": depth_fork,
        "inheritance": inh,
        "concurrency": conc,
        "env_overrides": env,
        "slot_reuse": reuse,
        "detector_control": det,
        "two_shells": shells,
    }


if __name__ == "__main__":
    print(json.dumps(full_report(), indent=2, sort_keys=True))
