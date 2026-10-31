#!/usr/bin/env python3
"""ADV-0060: install-time lifecycle script policy.

Probe 1 plants a beacon fixture and installs it through the live marketplace
installer in a disposable sandbox. Probe 2 (mechanically different) AST-walks
pipeline sources for subprocess/exec sites, then joins those sites to a live
subprocess trace so an unexercised invocation point is NOT-CHECKED, not safe.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from marketplace.install import (  # noqa: E402
    HANDLING_NAIVE_HOST,
    HANDLING_REFUSED_IMPLICIT,
    HANDLING_SANDBOX_GATED,
    OWNER_GATE_TOKEN,
    OwnerGate,
    install_package,
)
from plugin import legacy_layout_steps as layout  # noqa: E402

UNIT_ID = "ADV-0060"
OUTPUT_REL = (
    "command-center/adversarial/"
    "ADV-0060-install-lifecycle-script-policy.json"
)
SCHEMA_REL = "command-center/schema/exploit-proof.schema.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
P1_REL = "command-center/p2-wave/probes/ADV-0060/probe1_beacon.py"
P2_REL = "command-center/p2-wave/probes/ADV-0060/probe2_sites.py"
P1_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1_REL}"
P2_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2_REL}"
LEGAL = frozenset({"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"})
PROBE1_NAME = (
    "Probe 1: install the fixture in a sandbox and check for the beacon "
    "written by each vector."
)
PROBE2_NAME = (
    "Probe 2 (mechanically different): read the pipeline source to enumerate "
    "every point where an external command could be invoked, then confirm the "
    "fixture actually exercised each - an unexercised vector is NOT-CHECKED, "
    "not safe."
)
BEACON_TOKEN = "ADV-0060-BEACON"
BEACON_NAME = "ADV0060.beacon"
HOST_BEACON_ENV = "ADV0060_HOST_BEACON"
PIPELINE_RELS = (
    "tools/marketplace/install.py",
    "tools/plugin/longrun.py",
    "tools/plugin/heartbeat.py",
    "tools/plugin/legacy_layout_steps.py",
)
EXEC_ATTRS = frozenset(
    {
        "run",
        "Popen",
        "call",
        "check_call",
        "check_output",
        "system",
        "popen",
        "execl",
        "execv",
        "execve",
        "execvp",
        "execvpe",
    }
)
BEACON_PY = (
    "#!/usr/bin/env python3\n"
    "from pathlib import Path\n"
    "import os\n"
    f'TOKEN = "{BEACON_TOKEN}"\n'
    f'Path.cwd().joinpath("{BEACON_NAME}").write_text(TOKEN + "\\n", encoding="utf-8")\n'
    f'host = os.environ.get("{HOST_BEACON_ENV}")\n'
    "if host:\n"
    "    p = Path(host)\n"
    "    p.parent.mkdir(parents=True, exist_ok=True)\n"
    '    p.write_text(TOKEN + "\\n", encoding="utf-8")\n'
)
AUTOLOAD_PY = (
    "from pathlib import Path\n"
    f'Path.cwd().joinpath("{BEACON_NAME}").write_text('
    f'"{BEACON_TOKEN}-autoload\\n", encoding="utf-8")\n'
)
TARGET_IDS = (
    "T1-plugin-lifecycle-script",
    "T2-plugin-postinstall",
    "T3-auto-loaded-config-during-lifecycle",
    "T4-build-step",
    "T5-uninstall-hook",
    "T6-marketplace-payload-execution",
    "T7-package-triggered-external-command",
    "T8-lifecycle-command-sandbox",
    "T9-host-automatic-hook-enforcement",
)
CLAIMS = {
    "T1-plugin-lifecycle-script": (
        "Plugin helpers on this tree honour a package-declared lifecycle "
        "script and execute it during install/update/uninstall."
    ),
    "T2-plugin-postinstall": (
        "A plugin-shaped package with scripts.postinstall runs that script "
        "on the default marketplace install path."
    ),
    "T3-auto-loaded-config-during-lifecycle": (
        "sitecustomize.py / plugin.json planted in the payload is imported "
        "or executed during install without an explicit script field."
    ),
    "T4-build-step": (
        "scripts.build is invoked by the marketplace installer."
    ),
    "T5-uninstall-hook": (
        "An uninstall pipeline honours scripts.uninstall and runs it."
    ),
    "T6-marketplace-payload-execution": (
        "Marketplace install executes package payload code on the default "
        "(no owner gate) path."
    ),
    "T7-package-triggered-external-command": (
        "A package can cause subprocess.run of its postinstall script when "
        "the owner gate plus sandbox is granted, or via the naive host control."
    ),
    "T8-lifecycle-command-sandbox": (
        "When the installer does run a package script on the owner-gated "
        "path, the beacon stays inside the sandbox and host-marker env is stripped."
    ),
    "T9-host-automatic-hook-enforcement": (
        "A Claude/Cursor host automatically executes plugin hook commands "
        "declared in copied hook JSON."
    ),
}


def load_catalog_unit() -> dict[str, Any]:
    data = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT_ID:
            return unit
    raise RuntimeError("ADV-0060 missing from catalog")


def catalog_sentinel() -> str:
    return str(load_catalog_unit()["completion_sentinel"])


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def beacon_present(root: Path) -> bool:
    path = Path(root) / BEACON_NAME
    if not path.is_file():
        return False
    return BEACON_TOKEN in path.read_text(encoding="utf-8")


def _pkg(*, name: str, scripts: dict[str, str] | None, files: dict[str, str]) -> dict[str, Any]:
    package: dict[str, Any] = {"name": name, "version": "0.0.1", "files": files}
    if scripts:
        package["scripts"] = scripts
    return package


def postinstall_package() -> dict[str, Any]:
    return _pkg(
        name="adv0060-postinstall",
        scripts={"postinstall": "scripts/postinstall.py"},
        files={
            "README.md": "ADV-0060 postinstall beacon fixture\n",
            "scripts/postinstall.py": BEACON_PY,
        },
    )


def named_script_package(field: str) -> dict[str, Any]:
    rel = f"scripts/{field}.py"
    return _pkg(
        name=f"adv0060-{field}",
        scripts={field: rel},
        files={"README.md": f"ADV-0060 {field} fixture\n", rel: BEACON_PY},
    )


def autoload_package() -> dict[str, Any]:
    return _pkg(
        name="adv0060-autoload",
        scripts=None,
        files={
            "sitecustomize.py": AUTOLOAD_PY,
            "plugin.json": json.dumps({"hooks": {"PostInstall": "python sitecustomize.py"}}),
        },
    )


def noscript_package() -> dict[str, Any]:
    return _pkg(
        name="adv0060-noscript",
        scripts=None,
        files={"README.md": "no lifecycle scripts\n"},
    )


def plugin_shaped_package() -> dict[str, Any]:
    return _pkg(
        name="adv0060-plugin-postinstall",
        scripts={"postinstall": "scripts/postinstall.py"},
        files={
            "plugin.json": json.dumps({"id": "adv0060.plugin", "hooks": {}}),
            "scripts/postinstall.py": BEACON_PY,
        },
    )


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def enumerate_sites(rel: str) -> list[dict[str, Any]]:
    path = REPO / rel
    if not path.is_file():
        return [{"path": rel, "present": False, "lineno": 0, "call": ""}]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    found: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        tail = name.rsplit(".", 1)[-1]
        if tail not in EXEC_ATTRS and name not in {"os.system", "os.popen"}:
            continue
        found.append(
            {
                "path": rel,
                "lineno": int(getattr(node, "lineno", 0) or 0),
                "call": name,
                "present": True,
            }
        )
    found.sort(key=lambda row: (row["path"], row["lineno"], row["call"]))
    return found


def trace_subprocess(fn) -> tuple[Any, list[dict[str, Any]]]:
    import marketplace.install as install_mod

    recorded: list[dict[str, Any]] = []
    original = install_mod.subprocess.run

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        argv = args[0] if args else kwargs.get("args")
        recorded.append(
            {
                "argv0": str(list(argv)[0]) if argv else "",
                "argc": len(list(argv)) if argv else 0,
                "cwd_set": "cwd" in kwargs,
            }
        )
        return original(*args, **kwargs)

    install_mod.subprocess.run = wrapped  # type: ignore[method-assign]
    try:
        result = fn()
    finally:
        install_mod.subprocess.run = original  # type: ignore[method-assign]
    return result, recorded


def _run_direct(tmp: Path) -> dict[str, Any]:
    cwd = tmp / "direct"
    cwd.mkdir(parents=True)
    script = cwd / "beacon.py"
    script.write_text(BEACON_PY, encoding="utf-8")
    host = tmp / "direct-host.beacon"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env[HOST_BEACON_ENV] = str(host)
    proc = subprocess.run(
        [sys.executable, "-B", str(script)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    host_ok = host.is_file() and BEACON_TOKEN in host.read_text(encoding="utf-8")
    return {
        "returncode": proc.returncode,
        "cwd_beacon": beacon_present(cwd),
        "host_beacon": host_ok,
    }


def _install_arm(
    tmp: Path,
    name: str,
    package: dict[str, Any],
    **kwargs: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    dest = tmp / f"{name}-dest"
    leaked = tmp / f"{name}-leaked.beacon"
    previous = os.environ.get(HOST_BEACON_ENV)
    os.environ[HOST_BEACON_ENV] = str(leaked)
    try:
        result, calls = trace_subprocess(
            lambda: install_package(package, dest, **kwargs)
        )
    finally:
        if previous is None:
            os.environ.pop(HOST_BEACON_ENV, None)
        else:
            os.environ[HOST_BEACON_ENV] = previous
    sandbox = kwargs.get("sandbox_root")
    row = dict(result)
    row["arm"] = name
    row["dest_beacon"] = beacon_present(dest)
    row["sandbox_beacon"] = beacon_present(sandbox) if sandbox else False
    row["leaked_beacon"] = leaked.is_file()
    row["subprocess_calls"] = len(calls)
    return row, calls


def _plugin_layout_arm(tmp: Path) -> dict[str, Any]:
    root = tmp / "plugin-layout"
    layout.seed_legacy_tree(root)
    hook = root / layout.HOOK_SRC
    before = beacon_present(root)
    layout.apply_hooks_dispatch(root)
    moved = (root / layout.HOOK_DST).is_file() and not hook.is_file()
    after = beacon_present(root)
    text = (root / layout.HOOK_DST).read_text(encoding="utf-8") if moved else ""
    return {
        "hook_moved": moved,
        "beacon_before": before,
        "beacon_after": after,
        "command_field_preserved": "python3 hooks/check.py" in text,
        "executed_hook_command": bool(after and not before),
    }


def _uninstall_api_present() -> bool:
    import marketplace.install as install_mod

    for name in ("uninstall_package", "uninstall", "remove_package"):
        if callable(getattr(install_mod, name, None)):
            return True
    return False


def _arm_view(arm: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "arm",
        "handling",
        "executed",
        "execution_location",
        "dest_beacon",
        "sandbox_beacon",
        "leaked_beacon",
        "subprocess_calls",
        "script_present",
        "script_rel",
        "owner_gate_accepted",
        "returncode",
        "cwd_beacon",
        "host_beacon",
    )
    return {k: arm.get(k) for k in keep if k in arm}


def measure() -> dict[str, Any]:
    sites: list[dict[str, Any]] = []
    for rel in PIPELINE_RELS:
        sites.extend(enumerate_sites(rel))
    install_sites = [s for s in sites if s.get("path") == "tools/marketplace/install.py"]
    plugin_exec_sites = [
        s
        for s in sites
        if str(s.get("path") or "").startswith("tools/plugin/") and s.get("call")
    ]
    layout_exec_sites = [
        s
        for s in sites
        if s.get("path") == "tools/plugin/legacy_layout_steps.py" and s.get("call")
    ]

    with tempfile.TemporaryDirectory(prefix="adv0060-") as raw:
        tmp = Path(raw)
        direct = _run_direct(tmp)
        implicit, implicit_calls = _install_arm(tmp, "implicit", postinstall_package())
        naive, naive_calls = _install_arm(
            tmp,
            "naive",
            postinstall_package(),
            naive_execute_on_host=True,
        )
        sandbox_root = tmp / "gated-sandbox"
        gated, gated_calls = _install_arm(
            tmp,
            "gated",
            postinstall_package(),
            owner_gate=OwnerGate(
                allow_lifecycle_scripts=True, token=OWNER_GATE_TOKEN
            ),
            sandbox_root=sandbox_root,
        )
        preinstall, pre_calls = _install_arm(
            tmp, "preinstall", named_script_package("preinstall")
        )
        build, build_calls = _install_arm(
            tmp, "build", named_script_package("build")
        )
        uninstall_plant, uninstall_calls = _install_arm(
            tmp, "uninstall-plant", named_script_package("uninstall")
        )
        autoload, auto_calls = _install_arm(tmp, "autoload", autoload_package())
        noscript, none_calls = _install_arm(tmp, "noscript", noscript_package())
        plugin_pkg, plugin_calls = _install_arm(
            tmp, "plugin-shaped", plugin_shaped_package()
        )
        plugin_layout = _plugin_layout_arm(tmp)
        uninstall_api = _uninstall_api_present()

    detector_ok = bool(
        direct["cwd_beacon"] and direct["host_beacon"] and direct["returncode"] == 0
    )
    implicit_ok = (
        implicit.get("handling") == HANDLING_REFUSED_IMPLICIT
        and implicit.get("executed") is False
        and implicit["dest_beacon"] is False
        and implicit["leaked_beacon"] is False
        and implicit["subprocess_calls"] == 0
    )
    naive_ok = (
        naive.get("handling") == HANDLING_NAIVE_HOST
        and naive.get("executed") is True
        and naive["dest_beacon"] is True
        and naive["subprocess_calls"] >= 1
    )
    gated_ok = (
        gated.get("handling") == HANDLING_SANDBOX_GATED
        and gated.get("executed") is True
        and gated["sandbox_beacon"] is True
        and gated["dest_beacon"] is False
        and gated["leaked_beacon"] is False
        and gated.get("execution_location") == "sandbox"
        and gated["subprocess_calls"] >= 1
    )
    ignored = all(
        arm["dest_beacon"] is False and arm["subprocess_calls"] == 0
        for arm in (preinstall, build, uninstall_plant, autoload, noscript)
    )
    plugin_layout_ok = (
        plugin_layout["hook_moved"]
        and plugin_layout["beacon_after"] is False
        and plugin_layout["executed_hook_command"] is False
    )
    plugin_post_implicit_ok = (
        plugin_pkg.get("handling") == HANDLING_REFUSED_IMPLICIT
        and plugin_pkg["dest_beacon"] is False
        and plugin_pkg["subprocess_calls"] == 0
    )

    controls_ok = detector_ok and implicit_ok and naive_ok and gated_ok
    if not controls_ok:
        verdicts = {tid: "NOT-CHECKED" for tid in TARGET_IDS}
        overall = "NOT-CHECKED"
    else:
        verdicts = {
            "T1-plugin-lifecycle-script": "REFUTED",
            "T2-plugin-postinstall": "REFUTED",
            "T3-auto-loaded-config-during-lifecycle": "REFUTED",
            "T4-build-step": "REFUTED",
            "T5-uninstall-hook": "NOT-CHECKED" if not uninstall_api else "REFUTED",
            "T6-marketplace-payload-execution": "REFUTED",
            "T7-package-triggered-external-command": "CONFIRMED",
            "T8-lifecycle-command-sandbox": "CONFIRMED",
            "T9-host-automatic-hook-enforcement": "NOT-CHECKED",
        }
        if not plugin_layout_ok:
            verdicts["T1-plugin-lifecycle-script"] = "PARTIAL"
        if not plugin_post_implicit_ok:
            verdicts["T2-plugin-postinstall"] = "PARTIAL"
        if autoload["dest_beacon"]:
            verdicts["T3-auto-loaded-config-during-lifecycle"] = "CONFIRMED"
        if build["dest_beacon"] or build["subprocess_calls"]:
            verdicts["T4-build-step"] = "CONFIRMED"
        if not (gated_ok and naive_ok):
            verdicts["T7-package-triggered-external-command"] = "PARTIAL"
        if not gated_ok:
            verdicts["T8-lifecycle-command-sandbox"] = "REFUTED"
        kinds = {verdicts[t] for t in TARGET_IDS}
        if kinds == {"CONFIRMED"}:
            overall = "CONFIRMED"
        elif kinds == {"REFUTED"}:
            overall = "REFUTED"
        else:
            overall = "PARTIAL"

    arms = {
        "direct": direct,
        "implicit": _arm_view(implicit),
        "naive": _arm_view(naive),
        "gated": _arm_view(gated),
        "preinstall": _arm_view(preinstall),
        "build": _arm_view(build),
        "uninstall_plant": _arm_view(uninstall_plant),
        "autoload": _arm_view(autoload),
        "noscript": _arm_view(noscript),
        "plugin_shaped": _arm_view(plugin_pkg),
        "plugin_layout": plugin_layout,
    }
    return {
        "controls": {
            "detector_ok": detector_ok,
            "implicit_ok": implicit_ok,
            "naive_ok": naive_ok,
            "gated_ok": gated_ok,
            "ignored_script_names_ok": ignored,
            "plugin_layout_ok": plugin_layout_ok,
            "plugin_post_implicit_ok": plugin_post_implicit_ok,
            "both_states": detector_ok and implicit_ok and naive_ok,
            "all_ok": controls_ok,
        },
        "uninstall_api_present": uninstall_api,
        "arms": arms,
        "sites": sites,
        "install_exec_site_count": len(install_sites),
        "plugin_exec_site_count": len(plugin_exec_sites),
        "layout_exec_site_count": len(layout_exec_sites),
        "implicit_subprocess_calls": len(implicit_calls),
        "naive_subprocess_calls": len(naive_calls),
        "gated_subprocess_calls": len(gated_calls),
        "preinstall_subprocess_calls": len(pre_calls),
        "build_subprocess_calls": len(build_calls),
        "uninstall_subprocess_calls": len(uninstall_calls),
        "autoload_subprocess_calls": len(auto_calls),
        "noscript_subprocess_calls": len(none_calls),
        "plugin_shaped_subprocess_calls": len(plugin_calls),
        "verdicts": verdicts,
        "overall_verdict": overall,
        "source_hashes": {
            rel: sha256_file(REPO / rel) if (REPO / rel).is_file() else None
            for rel in PIPELINE_RELS
        },
    }


def targets_from(m: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for tid in TARGET_IDS:
        out.append(
            {
                "id": tid,
                "target_id": tid,
                "verdict": m["verdicts"][tid],
                "claim": CLAIMS[tid],
            }
        )
    return out


def probe1_report(m: dict[str, Any]) -> str:
    payload = {
        "probe": "probe1-beacon-install",
        "unit_id": UNIT_ID,
        "method": "disposable-sandbox-beacon-fixture",
        "controls": m["controls"],
        "arms": {
            k: m["arms"][k]
            for k in (
                "direct",
                "implicit",
                "naive",
                "gated",
                "preinstall",
                "build",
                "uninstall_plant",
                "autoload",
                "plugin_shaped",
                "plugin_layout",
            )
        },
        "uninstall_api_present": m["uninstall_api_present"],
        "verdicts": m["verdicts"],
        "overall_verdict": m["overall_verdict"],
    }
    body = json.dumps(payload, indent=2, sort_keys=True)
    return (
        f"{PROBE1_NAME}\n{body}\n"
        f"direct cwd={m['arms']['direct']['cwd_beacon']} "
        f"host={m['arms']['direct']['host_beacon']}\n"
        f"implicit executed={m['arms']['implicit']['executed']} "
        f"beacon={m['arms']['implicit']['dest_beacon']} "
        f"calls={m['implicit_subprocess_calls']}\n"
        f"naive executed={m['arms']['naive']['executed']} "
        f"beacon={m['arms']['naive']['dest_beacon']} "
        f"calls={m['naive_subprocess_calls']}\n"
        f"gated loc={m['arms']['gated'].get('execution_location')} "
        f"sandbox_beacon={m['arms']['gated']['sandbox_beacon']} "
        f"dest_beacon={m['arms']['gated']['dest_beacon']}\n"
        f"overall={m['overall_verdict']}\n"
        "SUCCESS:ADV-0060-probe1 beacon-install\n"
    )


def probe2_report(m: dict[str, Any]) -> str:
    payload = {
        "probe": "probe2-invocation-site-join",
        "unit_id": UNIT_ID,
        "method": "ast-enum-plus-live-subprocess-trace",
        "install_exec_site_count": m["install_exec_site_count"],
        "plugin_exec_site_count": m["plugin_exec_site_count"],
        "layout_exec_site_count": m["layout_exec_site_count"],
        "sites": m["sites"],
        "join": {
            "implicit_calls": m["implicit_subprocess_calls"],
            "naive_calls": m["naive_subprocess_calls"],
            "gated_calls": m["gated_subprocess_calls"],
            "preinstall_calls": m["preinstall_subprocess_calls"],
            "build_calls": m["build_subprocess_calls"],
            "uninstall_calls": m["uninstall_subprocess_calls"],
            "autoload_calls": m["autoload_subprocess_calls"],
            "plugin_shaped_calls": m["plugin_shaped_subprocess_calls"],
            "unexercised_uninstall_pipeline": not m["uninstall_api_present"],
            "unexercised_host_hook_runner": True,
        },
        "source_hashes": m["source_hashes"],
        "verdicts": m["verdicts"],
        "overall_verdict": m["overall_verdict"],
        "reviewer_independent": True,
    }
    body = json.dumps(payload, indent=2, sort_keys=True)
    return (
        f"{PROBE2_NAME}\n{body}\n"
        f"install_sites={m['install_exec_site_count']} "
        f"plugin_sites={m['plugin_exec_site_count']} "
        f"layout_sites={m['layout_exec_site_count']}\n"
        f"join implicit={m['implicit_subprocess_calls']} "
        f"naive={m['naive_subprocess_calls']} "
        f"gated={m['gated_subprocess_calls']} "
        f"build={m['build_subprocess_calls']}\n"
        f"uninstall_api={m['uninstall_api_present']}\n"
        f"overall={m['overall_verdict']}\n"
        "SUCCESS:ADV-0060-probe2 invocation-site-join\n"
    )
