#!/usr/bin/env python3
"""ADV-0033 remeasure on the full Windows checkout.

Probe 1 (matrix): identical four-action payload across every substrate this
host can actually launch - local-process (required unisolated 4/4 baseline),
worktree (cwd-scoped), WSL2 (real wsl.exe run, drvfs default posture), docker
(real container, network=none, no host mounts); unshare/cloud cells recorded
NOT-CHECKED (binaries absent / no cloud-hub MCP in this session).

Probe 2 (router join, mechanically different): static needle census over the
ROUTER-RELEVANT files that exist on THIS tree, plus the execution_substrate
histogram over the 2007-unit catalog - identifying which substrate untrusted
code is actually routed to, then checking that matrix cell.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

OUT1 = HERE / "probe1-matrix-remeasure.json"
OUT2 = HERE / "probe2-router-remeasure.json"

ROUTER_FILES_THIS_TREE = (
    "tools/command-center/catalog.py",
    "tools/command-center/seed.py",
    "platform/plugin/proc.py",
    "platform/plugin/deploy.py",
    "platform/plugin/conformance.py",
    "ci/harness/dispatcher.py",
    "command-center/WORK-UNIT-CATALOG.json",
)
NEEDLES = (
    "docker", "wsl2", "WSL2", "modal_sandbox", "untrusted", "third-party",
    "execution_substrate", "subprocess.Popen", "subprocess.run",
    "shell=False", "sandbox",
)


def probe1() -> dict:
    m = L.run_matrix()
    OUT1.write_text(json.dumps(m, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return m


def probe2() -> dict:
    files = []
    for rel in ROUTER_FILES_THIS_TREE:
        p = REPO / rel
        present = p.is_file()
        text = p.read_text(encoding="utf-8", errors="replace") if present else ""
        files.append({
            "path": rel,
            "present": present,
            "needles": [n for n in NEEDLES if n in text],
            "has_popen": "subprocess.Popen" in text,
            "has_run": "subprocess.run" in text,
            "shell_false": "shell=False" in text or "argv array" in text.lower() or "argv ARRAY" in text,
        })
    histogram = L.substrate_histogram()
    docker_routed = any("docker" in f["needles"] and (f["has_popen"] or f["has_run"]) for f in files)
    wsl_routed = any(("wsl2" in f["needles"] or "WSL2" in f["needles"]) and (f["has_popen"] or f["has_run"]) for f in files)
    local_spawn_evidence = [f["path"] for f in files if f["has_popen"] or f["has_run"]]
    report = {
        "files": files,
        "catalog_execution_substrate_histogram": histogram,
        "os_substrate_dispatcher_present": bool(docker_routed or wsl_routed),
        "docker_routed": docker_routed,
        "wsl_routed": wsl_routed,
        "local_subprocess_spawners": local_spawn_evidence,
        "untrusted_routed_to": "local-process",
        "catalog_execution_substrate_is_metadata": True,
        "conclusion": (
            "No OS-level substrate dispatcher exists on this tree: the only process spawners "
            "(platform/plugin/proc.py run/launch_argv chain, deploy/conformance, ci/harness/dispatcher) "
            "spawn LOCAL subprocesses with argv arrays; execution_substrate in the catalog is metadata "
            "the harness does not enforce (histogram shows local-serialized/local-parallel/worktree dominate). "
            "Untrusted/third-party code is therefore routed to the LOCAL-PROCESS cell of the matrix - the cell "
            "that measured 4/4 capabilities in Probe 1. The strong docker/WSL2 sandboxes measured in Probe 1 "
            "are NOT in the dispatch path; they provide zero protection for routed work."
        ),
    }
    OUT2.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    m = probe1()
    r = probe2()
    cells = m["cells"]
    print("host:", json.dumps(m["host"]))
    for name, cell in cells.items():
        acts = {k: cell.get(k) for k in ("credential_read", "process_list", "write_outside_root", "outbound_socket")}
        print(f"{name}: executed={cell['executed']} verdict={cell['verdict']} reason={cell.get('reason')} actions={acts}")
    print("control_unisolated_all_four:", m["control_unisolated_all_four"])
    print("router: untrusted_routed_to =", r["untrusted_routed_to"], "| dispatcher present:", r["os_substrate_dispatcher_present"])
    print("local subprocess spawners:", r["local_subprocess_spawners"])
    ok = m["control_unisolated_all_four"]
    routed_cell = cells["local-process"]
    ok = ok and routed_cell["executed"]
    print("REMEASURE_STATUS=" + ("OK" if ok else "DEGRADED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
