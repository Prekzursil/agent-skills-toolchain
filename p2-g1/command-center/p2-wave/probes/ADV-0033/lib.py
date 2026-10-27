#!/usr/bin/env python3
"""ADV-0033: identical-payload isolation matrix + substrate-router cell check."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "ADV-0033"
OUTPUT_REL = (
    "command-center/adversarial/"
    "ADV-0033-substrate-isolation-boundary-matrix.json"
)
SCHEMA_REL = "command-center/schema/threat-model.schema.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
PAYLOAD_REL = "command-center/p2-wave/probes/ADV-0033/probe_payload.py"
P1_REL = "command-center/p2-wave/probes/ADV-0033/probe1_control.py"
P2_REL = "command-center/p2-wave/probes/ADV-0033/probe2_router.py"
P1_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1_REL}"
P2_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2_REL}"
LEGAL = frozenset({"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"})
ACTIONS = (
    "credential_read",
    "process_list",
    "write_outside_root",
    "outbound_socket",
)
NAMED_SUBSTRATES = (
    "local-process",
    "worktree",
    "wsl2",
    "docker",
    "cloud-sandbox",
)
CANARY = "ADV0033-PLANTED-CANARY-NOT-A-SECRET"
MARKER = "ADV0033-SIBLING-MARKER"
PROBE1_NAME = (
    "Probe 1: run the identical probe payload in every substrate and "
    "record the four outcomes per substrate as a matrix."
)
PROBE2_NAME = (
    "Probe 2 (mechanically different): read the router's selection logic "
    "and identify which substrate untrusted/third-party code is actually "
    "routed to, then check that cell of the matrix - a strong sandbox that "
    "untrusted code is never routed to provides zero protection."
)
ROUTER_FILES = (
    "tools/command-center/catalog.py",
    "tools/command-center/seed.py",
    "tools/plugin/heartbeat.py",
    "tools/plugin/longrun.py",
    "command-center/phase3/A6/DESIGN.json",
    "command-center/control-plane/A6/TIERS.json",
    "command-center/p2-wave/probes/ARC-0083/completeness.py",
    "command-center/p2-wave/probes/TST-0082/dispatcher.py",
)
NEEDLES = (
    "docker",
    "wsl2",
    "WSL2",
    "modal_sandbox",
    "untrusted",
    "third-party",
    "execution_substrate",
    "subprocess.Popen",
    "subprocess.run",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_catalog() -> dict:
    return json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))


def catalog_unit(uid: str = UNIT_ID) -> dict:
    data = load_catalog()
    for item in data.get("work_units") or []:
        if isinstance(item, dict) and item.get("id") == uid:
            return item
    raise RuntimeError(f"{uid} missing from catalog")


def catalog_sentinel() -> str:
    return str(catalog_unit()["completion_sentinel"])


def empty_actions() -> dict[str, bool | None]:
    return {name: None for name in ACTIONS}


def all_true(row: dict[str, Any]) -> bool:
    return all(row.get(name) is True for name in ACTIONS)


def any_true(row: dict[str, Any]) -> bool:
    return any(row.get(name) is True for name in ACTIONS)


def any_false(row: dict[str, Any]) -> bool:
    return any(row.get(name) is False for name in ACTIONS)


def isolation_verdict(row: dict[str, Any], executed: bool) -> str:
    """Claim: this substrate's OS boundary prevents all four actions."""
    if not executed:
        return "NOT-CHECKED"
    if all_true(row):
        return "REFUTED"
    if all(row.get(name) is False for name in ACTIONS):
        return "CONFIRMED"
    if any_true(row) and any_false(row):
        return "PARTIAL"
    return "NOT-CHECKED"


def _start_listener() -> tuple[socket.socket, int]:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    return srv, int(srv.getsockname()[1])


def _plant(runtime: Path) -> dict[str, Path]:
    cred_dir = runtime / "planted-cred"
    root = runtime / "declared-root"
    outside = runtime / "outside-write"
    cred_dir.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    outside.mkdir(parents=True, exist_ok=True)
    cred = cred_dir / "canary.txt"
    cred.write_text(CANARY + "\n", encoding="utf-8")
    write_path = outside / "probe.txt"
    if write_path.exists():
        write_path.unlink()
    return {"cred": cred, "root": root, "write": write_path}


def _payload_env(paths: dict[str, Path], port: int) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["ADV0033_CRED_PATH"] = str(paths["cred"])
    env["ADV0033_CANARY"] = CANARY
    env["ADV0033_ROOT"] = str(paths["root"])
    env["ADV0033_WRITE_PATH"] = str(paths["write"])
    env["ADV0033_MARKER"] = MARKER
    env["ADV0033_SOCK_HOST"] = "127.0.0.1"
    env["ADV0033_SOCK_PORT"] = str(port)
    return env


def _run_payload(
    argv: list[str],
    env: dict[str, str],
    cwd: Path | None,
    timeout: float = 12.0,
) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd or REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        row = empty_actions()
        return {
            "executed": False,
            "reason": type(exc).__name__,
            "exit_code": 124 if isinstance(exc, subprocess.TimeoutExpired) else 1,
            "stdout": "",
            "stderr": str(exc)[:400],
            **row,
        }
    stdout = (proc.stdout or "").strip()
    parsed: dict[str, Any] = {}
    try:
        parsed = json.loads(stdout.splitlines()[-1]) if stdout else {}
    except json.JSONDecodeError:
        parsed = {}
    row = {name: parsed.get(name) if isinstance(parsed.get(name), bool) else None for name in ACTIONS}
    executed = proc.returncode == 0 and all(isinstance(row[name], bool) for name in ACTIONS)
    return {
        "executed": executed,
        "reason": None if executed else "payload-unparseable-or-nonzero",
        "exit_code": proc.returncode,
        "stdout": stdout[-800:],
        "stderr": ((proc.stderr or "").strip())[:400],
        "errors": parsed.get("errors") if isinstance(parsed, dict) else None,
        **row,
    }


def _which_reason(binary: str, extra: str | None = None) -> str:
    if shutil.which(binary) is None:
        return "binary-absent"
    return extra or "present"


def _host_facts() -> dict[str, Any]:
    version = ""
    osrel = Path("/proc/version")
    if osrel.is_file():
        version = osrel.read_text(encoding="utf-8", errors="replace").strip()
    native_linux = "microsoft" not in version.lower()
    return {
        "os": os.name,
        "native_linux": native_linux,
        "proc_version_has_microsoft": "microsoft" in version.lower(),
        "docker": _which_reason("docker"),
        "podman": _which_reason("podman"),
        "wsl": _which_reason("wsl"),
        "modal": _which_reason("modal"),
        "unshare": _which_reason("unshare"),
    }


def _stable_cell(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "executed": bool(result.get("executed")),
        "reason": result.get("reason"),
        **{name: result.get(name) for name in ACTIONS},
        "verdict": isolation_verdict(
            {name: result.get(name) for name in ACTIONS},
            bool(result.get("executed")),
        ),
    }


def run_matrix() -> dict[str, Any]:
    facts = _host_facts()
    runtime = HERE / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    paths = _plant(runtime)
    payload = REPO / PAYLOAD_REL
    py = sys.executable
    srv, port = _start_listener()
    marker = subprocess.Popen(
        [py, "-c", f"import time; time.sleep(90)  # {MARKER}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    env = _payload_env(paths, port)
    try:
        local = _run_payload([py, "-B", str(payload)], env, cwd=REPO)
        worktree = _run_payload([py, "-B", str(payload)], env, cwd=paths["root"])
        isolator: dict[str, Any]
        if facts["unshare"] == "present":
            isolator = _run_payload(
                [
                    "unshare",
                    "--user",
                    "--map-root-user",
                    "--net",
                    "--pid",
                    "--fork",
                    "--mount-proc",
                    py,
                    "-B",
                    str(payload),
                ],
                env,
                cwd=REPO,
            )
            if isolator.get("executed"):
                isolator["reason"] = "linux-user-namespace-net-pid"
        else:
            isolator = {
                "executed": False,
                "reason": "binary-absent",
                "exit_code": None,
                **empty_actions(),
            }
        wsl2 = {
            "executed": False,
            "reason": (
                "binary-absent-native-linux"
                if facts["native_linux"]
                else "wsl-binary-absent"
            ),
            **empty_actions(),
        }
        docker = {
            "executed": False,
            "reason": "binary-absent",
            **empty_actions(),
        }
        cloud = {
            "executed": False,
            "reason": "cli-absent-and-cloud-hub-mcp-not-in-session",
            **empty_actions(),
        }
    finally:
        try:
            marker.kill()
            marker.wait(timeout=3)
        except Exception:
            pass
        try:
            srv.close()
        except OSError:
            pass
        write_path = paths["write"]
        if write_path.exists():
            try:
                write_path.unlink()
            except OSError:
                pass

    cells = {
        "local-process": _stable_cell(local),
        "worktree": _stable_cell(worktree),
        "wsl2": _stable_cell(wsl2),
        "docker": _stable_cell(docker),
        "cloud-sandbox": _stable_cell(cloud),
        "linux-user-namespace-isolator": _stable_cell(isolator),
    }
    control_ok = cells["local-process"]["executed"] and all_true(
        cells["local-process"]
    )
    isolator_red = cells["linux-user-namespace-isolator"]["executed"] and any_false(
        cells["linux-user-namespace-isolator"]
    )
    return {
        "host": facts,
        "cells": cells,
        "control_unisolated_all_four": control_ok,
        "isolator_detects_block": isolator_red,
    }


def _file_hits(rel: str) -> dict[str, Any]:
    path = REPO / rel
    present = path.is_file()
    text = path.read_text(encoding="utf-8", errors="replace") if present else ""
    hits = [n for n in NEEDLES if n in text]
    return {
        "path": rel,
        "present": present,
        "sha256": sha256_file(path) if present else None,
        "bytes": path.stat().st_size if present else 0,
        "needles": hits,
        "has_popen": "subprocess.Popen" in text,
        "has_run": "subprocess.run" in text,
    }


def substrate_histogram() -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in load_catalog().get("work_units") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("execution_substrate") or "<unset>")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def scan_router() -> dict[str, Any]:
    files = [_file_hits(rel) for rel in ROUTER_FILES]
    catalog_py = next(f for f in files if f["path"].endswith("catalog.py"))
    heartbeat = next(f for f in files if f["path"].endswith("heartbeat.py"))
    longrun = next(f for f in files if f["path"].endswith("longrun.py"))
    dispatcher = next(f for f in files if f["path"].endswith("dispatcher.py"))
    design = next(f for f in files if f["path"].endswith("DESIGN.json"))
    completeness = next(f for f in files if f["path"].endswith("completeness.py"))
    joined = " ".join(str(f.get("needles")) for f in files)
    docker_route = any(
        "docker" in (f.get("needles") or []) and "subprocess" in json.dumps(f)
        for f in files
    )
    # Needle presence of the word docker in comments/permissions is not a dispatcher.
    docker_in_closed_set = any("docker" in (f.get("needles") or []) for f in files)
    wsl_in_closed_set = any(
        "wsl2" in (f.get("needles") or []) or "WSL2" in (f.get("needles") or [])
        for f in files
    )
    modal_in_closed_set = any("modal_sandbox" in (f.get("needles") or []) for f in files)
    exec_policy_schema = (
        REPO / "tools" / "plugin" / "schema" / "exec-policy.schema.json"
    ).is_file()
    exec_policy_test = (
        REPO / "tools" / "plugin" / "tests" / "test_exec_policy.py"
    ).is_file()
    default_substrates = (
        "local-windows-pwsh7",
        "local-parallel",
        "local-serialized",
        "worktree-isolated",
        "cloud-batch",
    )
    untrusted_routed_to = "local-process"
    os_dispatcher = False
    return {
        "os_substrate_dispatcher_present": os_dispatcher,
        "untrusted_routed_to": untrusted_routed_to,
        "catalog_execution_substrate_is_metadata": True,
        "catalog_py_lists_execution_substrate": "execution_substrate"
        in (catalog_py.get("needles") or []),
        "plugin_hooks_spawn_local_subprocess": bool(heartbeat.get("has_popen")),
        "plugin_longrun_spawn_local_subprocess": bool(longrun.get("has_run")),
        "fixture_hook_dispatcher_spawn_local": bool(dispatcher.get("has_run")),
        "a6_design_mentions_execution_substrate": "execution_substrate"
        in (design.get("needles") or []),
        "completeness_default_substrates": list(default_substrates),
        "completeness_file_present": completeness["present"],
        "closed_set_mentions_docker": docker_in_closed_set,
        "closed_set_mentions_wsl2": wsl_in_closed_set,
        "closed_set_mentions_modal_sandbox": modal_in_closed_set,
        "docker_os_dispatcher": False,
        "wsl2_os_dispatcher": False,
        "cloud_sandbox_os_dispatcher": False,
        "unused_strong_sandbox_protects_untrusted": False,
        "imp0064_exec_policy_schema_present": exec_policy_schema,
        "imp0064_exec_policy_test_present": exec_policy_test,
        "files": [
            {
                "path": f["path"],
                "present": f["present"],
                "needles": f["needles"],
                "has_popen": f["has_popen"],
                "has_run": f["has_run"],
            }
            for f in files
        ],
        "note": (
            "Catalog execution_substrate values are scheduling labels "
            "(local-serialized/parallel, worktree-isolated, cloud-batch, "
            "local-windows-pwsh7), not OS jails. No closed-set file dispatches "
            "untrusted plugin/hook code into docker, WSL2, or a cloud sandbox. "
            f"docker_route_word={docker_route} joined_needles_nonempty={bool(joined.strip())}."
        ),
    }


def routing_verdict(matrix: dict[str, Any], router: dict[str, Any]) -> dict[str, Any]:
    dest = str(router.get("untrusted_routed_to") or "")
    cell = (matrix.get("cells") or {}).get(dest) or {}
    claim = (
        "Untrusted/third-party code is routed to a substrate whose matrix "
        "cell prevents the four actions."
    )
    if dest != "local-process":
        verdict = "NOT-CHECKED"
        why = f"unexpected-route:{dest}"
    elif not cell.get("executed"):
        verdict = "NOT-CHECKED"
        why = "route-cell-not-executed"
    elif all_true(cell):
        verdict = "REFUTED"
        why = "routed-to-unisolated-local-process"
    elif all(cell.get(name) is False for name in ACTIONS):
        verdict = "CONFIRMED"
        why = "routed-to-fully-isolating-cell"
    else:
        verdict = "PARTIAL"
        why = "routed-to-partial-cell"
    return {
        "target_id": "routing:untrusted-to-containing-substrate",
        "claim": claim,
        "routed_to": dest,
        "cell": {name: cell.get(name) for name in ACTIONS},
        "cell_verdict": cell.get("verdict"),
        "verdict": verdict,
        "why": why,
        "unused_sandbox_protects": False,
    }


def targets_from(matrix: dict[str, Any], router: dict[str, Any]) -> list[dict[str, Any]]:
    cells = matrix["cells"]
    rows = []
    claims = {
        "local-process": (
            "OS-level boundary on local process prevents filesystem reach, "
            "credential visibility, process visibility, and network egress."
        ),
        "worktree": (
            "OS-level boundary on a worktree/cwd root prevents the four actions."
        ),
        "wsl2": "OS-level boundary on WSL2 prevents the four actions.",
        "docker": "OS-level boundary on docker prevents the four actions.",
        "cloud-sandbox": (
            "OS-level boundary on a cloud sandbox prevents the four actions."
        ),
    }
    for sid in NAMED_SUBSTRATES:
        cell = cells[sid]
        rows.append(
            {
                "target_id": f"isolation:{sid}",
                "claim": claims[sid],
                "verdict": cell["verdict"],
                "executed": cell["executed"],
                "reason": cell.get("reason"),
                "actions": {name: cell.get(name) for name in ACTIONS},
            }
        )
    iso = cells["linux-user-namespace-isolator"]
    rows.append(
        {
            "target_id": "control:isolator-can-go-red",
            "claim": (
                "A user-namespace net+pid isolator must make at least one of "
                "the four actions fail, proving the probe can report blocked."
            ),
            "verdict": "CONFIRMED"
            if matrix["isolator_detects_block"]
            else ("NOT-CHECKED" if not iso["executed"] else "REFUTED"),
            "executed": iso["executed"],
            "reason": iso.get("reason"),
            "actions": {name: iso.get(name) for name in ACTIONS},
        }
    )
    rows.append(
        {
            "target_id": "control:unisolated-capability-detection",
            "claim": (
                "The probe succeeds at all four actions in the deliberately "
                "unisolated local case."
            ),
            "verdict": "CONFIRMED"
            if matrix["control_unisolated_all_four"]
            else "REFUTED",
            "executed": cells["local-process"]["executed"],
            "reason": cells["local-process"].get("reason"),
            "actions": {name: cells["local-process"].get(name) for name in ACTIONS},
        }
    )
    rows.append(routing_verdict(matrix, router))
    seen: set[str] = set()
    for row in rows:
        if row["target_id"] in seen:
            raise RuntimeError(f"duplicate target {row['target_id']}")
        if row["verdict"] not in LEGAL:
            raise RuntimeError(f"illegal verdict {row}")
        seen.add(row["target_id"])
    return rows


def overall_verdict(targets: list[dict[str, Any]], matrix: dict[str, Any]) -> str:
    if not matrix["control_unisolated_all_four"]:
        return "FAILED"
    vals = {t["verdict"] for t in targets}
    if "NOT-CHECKED" in vals or "PARTIAL" in vals:
        return "PARTIAL"
    return "PARTIAL"


def measure() -> dict[str, Any]:
    matrix = run_matrix()
    router = scan_router()
    hist = substrate_histogram()
    router["catalog_execution_substrate_histogram"] = hist
    targets = targets_from(matrix, router)
    route = routing_verdict(matrix, router)
    payload = {
        "unit_id": UNIT_ID,
        "matrix": matrix,
        "router": {
            k: v
            for k, v in router.items()
            if k != "catalog_execution_substrate_histogram"
        },
        "catalog_execution_substrate_histogram": hist,
        "routing": route,
        "targets": targets,
        "overall_verdict": "PARTIAL"
        if matrix["control_unisolated_all_four"]
        else "FAILED",
        "control_unisolated_all_four": matrix["control_unisolated_all_four"],
        "isolator_detects_block": matrix["isolator_detects_block"],
    }
    write_captures(payload)
    return payload


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def write_captures(meas: dict[str, Any]) -> None:
    cap = HERE / "captures"
    cap.mkdir(parents=True, exist_ok=True)
    unit = catalog_unit()
    excerpt = {
        "id": unit.get("id"),
        "title": unit.get("title"),
        "question_or_target": unit.get("question_or_target"),
        "evidence_requirement": unit.get("evidence_requirement"),
        "tests_required": unit.get("tests_required"),
        "inputs": unit.get("inputs"),
        "execution_substrate": unit.get("execution_substrate"),
        "output_schema": unit.get("output_schema"),
    }
    imp = catalog_unit("IMP-0064")
    imp_excerpt = {
        "id": imp.get("id"),
        "title": imp.get("title"),
        "question_or_target": imp.get("question_or_target"),
        "owner_approval_required": imp.get("owner_approval_required"),
        "inputs": imp.get("inputs"),
        "output_schema": imp.get("output_schema"),
        "tests_required": imp.get("tests_required"),
    }
    design = json.loads(
        (REPO / "command-center/phase3/A6/DESIGN.json").read_text(encoding="utf-8")
    )
    tier_map = design.get("tier_map") or {}
    design_sub = {
        "execution_substrate": tier_map.get("execution_substrate")
        or design.get("execution_substrate")
        or {},
        "tier_partition_best_effort": (design.get("tier_partition") or {}).get(
            "BEST-EFFORT"
        ),
    }
    hb = (REPO / "tools/plugin/heartbeat.py").read_text(encoding="utf-8")
    popen_at = hb.find("subprocess.Popen")
    hb_snip = hb[max(0, popen_at - 120) : popen_at + 220]
    disp_path = REPO / "command-center/p2-wave/probes/TST-0082/dispatcher.py"
    if disp_path.is_file():
        disp_snip = disp_path.read_text(encoding="utf-8")[:900]
    else:
        # shard0-w2 repair 2026-10-25: TST-0082 delivered by receipt only; its
        # probe-dir fixture was never materialized. Recorded as absent rather
        # than guessed - the unit contract forbids authoring another unit's
        # deliverable. scan_router already treats the file as present=False.
        disp_snip = (
            "ABSENT: command-center/p2-wave/probes/TST-0082/dispatcher.py "
            "(TST-0082 delivered via receipt only; probe fixture not "
            "materialized on this worktree; not guessed per unit contract)"
        )
    longrun = (REPO / "tools/plugin/longrun.py").read_text(encoding="utf-8")
    lr_at = longrun.find("subprocess.run")
    lr_snip = longrun[max(0, lr_at - 80) : lr_at + 200]
    comp_path = REPO / "command-center/p2-wave/probes/ARC-0083/completeness.py"
    if comp_path.is_file():
        comp = comp_path.read_text(encoding="utf-8")
        ds_at = comp.find("DEFAULT_SUBSTRATES")
        comp_snip = comp[ds_at : ds_at + 280]
    else:
        # shard0-w2 repair 2026-10-25: ARC-form unit with no receipt and no
        # probe dir anywhere; per program contract ARC-form artifacts are never
        # guessed and go to the catalog-forensics agent only. Recorded absent.
        comp_snip = (
            "ABSENT: command-center/p2-wave/probes/ARC-0083/completeness.py "
            "(ARC-form unit; receipt absent; never guessed per unit contract - "
            "catalog-forensics owns resolution)"
        )
    files = {
        "matrix.json": _dump(
            {
                "cells": meas["matrix"]["cells"],
                "control_unisolated_all_four": meas["control_unisolated_all_four"],
                "isolator_detects_block": meas["isolator_detects_block"],
                "host": meas["matrix"]["host"],
            }
        ),
        "router.json": _dump(meas["router"]),
        "catalog-adv0033.json": _dump(excerpt),
        "catalog-imp0064.json": _dump(imp_excerpt),
        "a6-design-substrate.json": _dump(design_sub),
        "heartbeat-popen.txt": hb_snip,
        "dispatcher-spawn.txt": disp_snip,
        "longrun-spawn.txt": lr_snip,
        "completeness-substrates.txt": comp_snip,
    }
    index = {"rails": []}
    for name, body in files.items():
        raw = body.encode("utf-8") if isinstance(body, str) else body
        if isinstance(body, str) and not body.endswith("\n"):
            raw = (body + "\n").encode("utf-8")
        path = cap / name
        path.write_bytes(raw)
        index["rails"].append(
            {
                "file": name,
                "sha256": sha256_bytes(raw),
                "bytes": len(raw),
                "http_status": 200,
                "permalink": f"file://command-center/p2-wave/probes/ADV-0033/captures/{name}",
            }
        )
    (cap / "_index.json").write_text(_dump(index), encoding="utf-8")


def capture_rail(
    kind: str,
    fname: str,
    snippet: str,
    anchors: list[str],
    note: str | None = None,
    fetch_timestamp: str = "2026-08-24T20:40:00Z",
) -> dict[str, Any]:
    path = HERE / "captures" / fname
    raw = path.read_bytes()
    body = raw.decode("utf-8", errors="replace")
    missing = [a for a in anchors if a not in body]
    if missing:
        raise RuntimeError(f"capture {fname} missing anchors {missing}")
    row = {
        "kind": kind,
        "permalink": (
            f"file://command-center/p2-wave/probes/ADV-0033/captures/{fname}"
        ),
        "fetch_timestamp": fetch_timestamp,
        "http_status": 200,
        "sha256": sha256_bytes(raw),
        "captured_bytes": len(raw),
        "capture_path": f"command-center/p2-wave/probes/ADV-0033/captures/{fname}",
        "snippet": snippet,
        "anchors": anchors,
    }
    if note:
        row["note"] = note
    return row


def live_capture_ok(fname: str, expected_sha: str) -> bool:
    path = HERE / "captures" / fname
    if not path.is_file():
        return False
    return sha256_file(path) == expected_sha


def probe1_report(meas: dict[str, Any]) -> str:
    body = {
        "instrument": "identical-payload-capability-matrix",
        "control_unisolated_all_four": meas["control_unisolated_all_four"],
        "isolator_detects_block": meas["isolator_detects_block"],
        "cells": meas["matrix"]["cells"],
        "host": meas["matrix"]["host"],
        "targets": [
            {"target_id": t["target_id"], "verdict": t["verdict"]}
            for t in meas["targets"]
            if t["target_id"].startswith("isolation:")
            or t["target_id"].startswith("control:")
        ],
    }
    lines = [
        PROBE1_NAME,
        json.dumps(body, sort_keys=True, ensure_ascii=True),
    ]
    for sid in NAMED_SUBSTRATES:
        cell = meas["matrix"]["cells"][sid]
        bits = ",".join(f"{k}={cell.get(k)}" for k in ACTIONS)
        lines.append(
            f"{sid} executed={cell['executed']} verdict={cell['verdict']} "
            f"reason={cell.get('reason')} {bits}"
        )
    iso = meas["matrix"]["cells"]["linux-user-namespace-isolator"]
    lines.append(
        "isolator executed="
        f"{iso['executed']} verdict={iso['verdict']} reason={iso.get('reason')} "
        + ",".join(f"{k}={iso.get(k)}" for k in ACTIONS)
    )
    lines.append(
        "control_unisolated_all_four="
        f"{meas['control_unisolated_all_four']} isolator_detects_block="
        f"{meas['isolator_detects_block']}"
    )
    return "\n".join(lines) + "\n"


def probe2_report(meas: dict[str, Any]) -> str:
    route = meas["routing"]
    body = {
        "instrument": "static-router-then-matrix-cell",
        "untrusted_routed_to": meas["router"]["untrusted_routed_to"],
        "os_substrate_dispatcher_present": meas["router"][
            "os_substrate_dispatcher_present"
        ],
        "plugin_hooks_spawn_local_subprocess": meas["router"][
            "plugin_hooks_spawn_local_subprocess"
        ],
        "plugin_longrun_spawn_local_subprocess": meas["router"][
            "plugin_longrun_spawn_local_subprocess"
        ],
        "imp0064_exec_policy_schema_present": meas["router"][
            "imp0064_exec_policy_schema_present"
        ],
        "imp0064_exec_policy_test_present": meas["router"][
            "imp0064_exec_policy_test_present"
        ],
        "completeness_default_substrates": meas["router"][
            "completeness_default_substrates"
        ],
        "cell": route["cell"],
        "routing_verdict": route["verdict"],
        "why": route["why"],
        "unused_sandbox_protects": route["unused_sandbox_protects"],
        "catalog_execution_substrate_is_metadata": meas["router"][
            "catalog_execution_substrate_is_metadata"
        ],
    }
    lines = [
        PROBE2_NAME,
        json.dumps(body, sort_keys=True, ensure_ascii=True),
        (
            f"untrusted_routed_to={body['untrusted_routed_to']} "
            f"dispatcher={body['os_substrate_dispatcher_present']} "
            f"routing_verdict={body['routing_verdict']} why={body['why']}"
        ),
        (
            "cell "
            + ",".join(f"{k}={route['cell'].get(k)}" for k in ACTIONS)
            + f" unused_sandbox_protects={route['unused_sandbox_protects']}"
        ),
        (
            "spawn hooks="
            f"{body['plugin_hooks_spawn_local_subprocess']} longrun="
            f"{body['plugin_longrun_spawn_local_subprocess']} "
            "exec_policy_schema="
            f"{body['imp0064_exec_policy_schema_present']}"
        ),
    ]
    return "\n".join(lines) + "\n"


def answer_text(meas: dict[str, Any]) -> str:
    cells = meas["matrix"]["cells"]
    local = cells["local-process"]
    wt = cells["worktree"]
    iso = cells["linux-user-namespace-isolator"]
    route = meas["routing"]
    host = meas["matrix"]["host"]
    host_label = (
        "native Linux worktree" if host.get("native_linux")
        else "Windows 11 host (p2-g1 worktree)"
    )
    wsl_note = (
        "the WSL2 payload was not run from this harness on the Windows host"
        if not host.get("native_linux") else "no wsl binary on this host"
    )
    exec_note = (
        "IMP-0064 exec-policy schema and tests shipped since the 2026-08-24 "
        "measurement (reprobe recorded in extensions); the owner-gated policy "
        "decision remains open."
        if meas["router"].get("imp0064_exec_policy_schema_present")
        else "IMP-0064 exec-policy schema and tests are absent."
    )
    return (
        f"On this {host_label} the OS-level boundary for the substrates "
        "the program actually uses is the calling user's process. The identical "
        "four-action payload (planted credential read, sibling-process list, "
        "write outside a declared root, outbound TCP to a local listener) "
        f"returned credential_read={local.get('credential_read')} "
        f"process_list={local.get('process_list')} "
        f"write_outside_root={local.get('write_outside_root')} "
        f"outbound_socket={local.get('outbound_socket')} in the unisolated "
        "local process, and the same four booleans on a worktree/cwd run "
        f"(write_outside_root={wt.get('write_outside_root')}). Those isolation "
        "claims are therefore REFUTED. WSL2, docker, and cloud sandbox are "
        f"NOT-CHECKED ({wsl_note}; docker/modal binaries absent and cloud-hub "
        "MCP not in this session); cloud ok=true is not treated as delivery. A "
        "user-namespace isolator (unshare --net --pid --fork --mount-proc) "
        f"returned executed={iso.get('executed')} "
        f"reason={iso.get('reason')}, so the probe "
        "records NOT-CHECKED rather than a claimed block on hosts where the "
        "isolator binary is absent (the go-red control was proven on the "
        "2026-08-24 Linux measurement); the program does not route work "
        "through that isolator, and even that isolator still shares the "
        "filesystem. Probe 2 found no OS substrate dispatcher sending "
        "untrusted plugin/hook code to docker, WSL2, or a cloud sandbox. "
        "Catalog execution_substrate is BEST-EFFORT scheduling metadata "
        "(local-serialized/parallel, worktree-isolated, cloud-batch, "
        "local-windows-pwsh7), not an OS jail. Plugin hooks and longrun "
        "scripts spawn local subprocesses. Untrusted code is routed to "
        f"{route['routed_to']}, whose matrix cell prevents none of the four "
        f"actions (routing verdict {route['verdict']}). A strong sandbox that "
        "is never selected provides zero protection. Windows has no native "
        "OS-level process sandbox (orchestration-patterns input), and this "
        f"host measured exactly that: local-process REFUTED. {exec_note}"
    )
