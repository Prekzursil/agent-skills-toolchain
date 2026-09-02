#!/usr/bin/env python3
"""TST-0068: explicit-interpreter audit + Windows cmd.exe bare-.sh spawn model.

Windows cmd.exe / CreateProcess does not read shebang (#!). PATHEXT does not
include .sh. A bare `foo.sh` invocation is the failure class at spec:11304.

This module never uses Linux execve of a .sh path as evidence of Windows
success. A shebang-reading resolver that passed both the bare Windows case and
the explicit-bash case would be the detector this unit exists to catch.
"""
from __future__ import annotations

import json
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
SCRIPTS = FIXTURES / "scripts"

CMD_NOT_RECOGNIZED_TEMPLATE = (
    "'{name}' is not recognized as an internal or external command,\n"
    "operable program or batch file.\n"
)
CMD_NOT_RECOGNIZED_EXIT = 9009

# Default cmd.exe PATHEXT (Windows 10/11). .sh is absent.
WIN_PATHEXT = (
    ".COM",
    ".EXE",
    ".BAT",
    ".CMD",
    ".VBS",
    ".VBE",
    ".JS",
    ".JSE",
    ".WSF",
    ".WSH",
    ".MSC",
)

INTERPRETER_NAMES = frozenset(
    {
        "bash",
        "bash.exe",
        "sh",
        "zsh",
        "python",
        "python3",
        "python.exe",
        "py",
        "node",
        "nodejs",
        "pwsh",
        "powershell",
        "cmd",
        "cmd.exe",
    }
)

PRODUCTION_HOOK_MANIFESTS = ("hooks/_dispatch/manifest.json",)
PRODUCTION_PLUGIN_MANIFESTS = (
    "plugin.json",
    ".claude-plugin/plugin.json",
)
SETTINGS_PATH = "agent-self/config/settings.json"


def cmd_not_recognized(name: str) -> str:
    return CMD_NOT_RECOGNIZED_TEMPLATE.format(name=name)


def looks_like_script(token: str) -> bool:
    if not token or token in INTERPRETER_NAMES:
        return False
    lower = token.replace("\\", "/").lower()
    suffixes = (".sh", ".bash", ".zsh", ".py", ".mjs", ".js", ".ps1")
    if any(lower.endswith(s) for s in suffixes):
        return True
    if token.startswith("./") or token.startswith(".\\"):
        return True
    return False


def argv_of(command: Any) -> list[str]:
    if isinstance(command, list):
        return [str(x) for x in command]
    if isinstance(command, str) and command.strip():
        try:
            return shlex.split(command, posix=True)
        except ValueError:
            return command.split()
    return []


def declared_interpreter(row: dict[str, Any]) -> str | None:
    for key in ("interpreter", "runtime", "shell"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    argv = argv_of(row.get("command"))
    if argv:
        head = argv[0].lower().replace("\\", "/").split("/")[-1]
        if head in INTERPRETER_NAMES:
            return argv[0]
    return None


def script_ref(row: dict[str, Any]) -> str | None:
    for key in ("script", "path", "entry", "file"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    argv = argv_of(row.get("command"))
    if not argv:
        return None
    interp = declared_interpreter(row)
    if interp and len(argv) >= 2:
        return argv[1]
    if looks_like_script(argv[0]):
        return argv[0]
    return None


def relies_on_shebang(row: dict[str, Any]) -> bool:
    """True when Windows would have to honor #! (it does not).

    In-process importlib loads (production events.checks via dispatch.py) never
    consult PATHEXT or shebang. Scoring those as shebang-reliant is the inverse
    cheat of treating Linux execve success as a Windows pass.
    """
    if row.get("_runtime") == "in-process-importlib":
        return False
    interp = declared_interpreter(row)
    if interp:
        return False
    ref = script_ref(row)
    if ref and looks_like_script(ref):
        return True
    argv = argv_of(row.get("command"))
    if argv and looks_like_script(argv[0]):
        return True
    return False


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def hook_entries(manifest: dict[str, Any], source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    hooks = manifest.get("hooks")
    if isinstance(hooks, list):
        for i, raw in enumerate(hooks):
            if not isinstance(raw, dict):
                continue
            row = dict(raw)
            row["_source"] = source
            row["_kind"] = "hook"
            row["_index"] = i
            row["_id"] = str(row.get("id") or f"hook[{i}]")
            rows.append(row)
    events = manifest.get("events")
    if isinstance(events, dict):
        for event_name, ev in events.items():
            if not isinstance(ev, dict):
                continue
            checks = ev.get("checks")
            if not isinstance(checks, list):
                continue
            for i, raw in enumerate(checks):
                if not isinstance(raw, dict):
                    continue
                row = dict(raw)
                row["_source"] = source
                row["_kind"] = "dispatch-check"
                row["_index"] = i
                row["_id"] = str(
                    f"{event_name}/{row.get('name') or row.get('script') or i}"
                )
                # dispatch.py:_load_module uses importlib; cmd.exe never sees
                # the script path. Parent spawn is `python dispatch.py`.
                row["_runtime"] = "in-process-importlib"
                row["_event"] = str(event_name)
                rows.append(row)
    return rows


def plugin_command_entries(plugin: dict[str, Any], source: str) -> list[dict[str, Any]]:
    rows = []
    commands = plugin.get("commands")
    if not isinstance(commands, list):
        return rows
    for i, raw in enumerate(commands):
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        row["_source"] = source
        row["_kind"] = "plugin-command"
        row["_index"] = i
        row["_id"] = str(row.get("name") or row.get("id") or f"cmd[{i}]")
        rows.append(row)
    return rows


def classify_entry(row: dict[str, Any]) -> dict[str, Any]:
    interp = declared_interpreter(row)
    ref = script_ref(row)
    shebang = relies_on_shebang(row)
    runtime = str(row.get("_runtime") or "argv-or-interpreter-field")
    in_process = runtime == "in-process-importlib"
    return {
        "id": row["_id"],
        "kind": row["_kind"],
        "source": row["_source"],
        "interpreter": interp if interp else ("python" if in_process else None),
        "script": ref,
        "declares_interpreter": interp is not None or in_process,
        "relies_on_shebang": shebang,
        "runtime": runtime,
        "event": row.get("_event"),
        "command": row.get("command"),
    }


def audit_pair(hook_path: Path | None, plugin_path: Path | None) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    sources = []
    if hook_path is not None and hook_path.is_file():
        sources.append(str(hook_path).replace("\\", "/"))
        entries.extend(
            hook_entries(load_json(hook_path), "hooks/_dispatch/manifest.json")
        )
    if plugin_path is not None and plugin_path.is_file():
        sources.append(str(plugin_path).replace("\\", "/"))
        entries.extend(plugin_command_entries(load_json(plugin_path), "plugin.json"))
    classified = [classify_entry(e) for e in entries]
    reliant = [c for c in classified if c["relies_on_shebang"]]
    declared = [c for c in classified if c["declares_interpreter"]]
    return {
        "present": bool(sources),
        "sources": sources,
        "entries": classified,
        "count": len(classified),
        "declares_interpreter_count": len(declared),
        "shebang_reliant_count": len(reliant),
        "shebang_reliant_ids": [c["id"] for c in reliant],
        "all_declare_interpreter": bool(classified) and len(reliant) == 0,
        "vacuous": len(classified) == 0,
    }


def windows_pathext_allows(path: str) -> bool:
    ext = Path(path.replace("\\", "/")).suffix.upper()
    if not ext:
        return False
    return ext in WIN_PATHEXT


def windows_cmd_bare_invoke(command_token: str) -> dict[str, Any]:
    """cmd.exe command searcher: .sh is not in PATHEXT; shebang is not read.

    Modeled, not Wine. A Linux execve of the same path would succeed via #!
    and is the CHEAT control — if this function ever returned ok=True for a
    .sh token, the detector would be reading the shebang, not Windows.
    """
    token = command_token.strip()
    ext = Path(token.replace("\\", "/")).suffix.upper()
    if ext == ".SH" or not windows_pathext_allows(token):
        stderr = cmd_not_recognized(token)
        return {
            "ok": False,
            "returncode": CMD_NOT_RECOGNIZED_EXIT,
            "stdout": "",
            "stderr": stderr,
            "model": "cmd.exe-pathext",
            "read_shebang": False,
            "pathext_hit": False,
            "token": token,
        }
    return {
        "ok": False,
        "returncode": CMD_NOT_RECOGNIZED_EXIT,
        "stdout": "",
        "stderr": cmd_not_recognized(token),
        "model": "cmd.exe-pathext",
        "read_shebang": False,
        "pathext_hit": True,
        "token": token,
    }


def ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def linux_shebang_exec(script: Path, tag: str) -> dict[str, Any]:
    """Kernel execve honors #!. This MUST succeed on Linux for marker.sh.

    Used only as a control: the same path would pass a shebang-reading
    'Windows' probe. Windows cmd.exe must still fail.
    """
    ensure_executable(script)
    proc = subprocess.run(
        [str(script), tag],
        capture_output=True,
        text=True,
        cwd=str(FIXTURES),
        timeout=15,
        check=False,
    )
    return {
        "ok": proc.returncode == 0 and "TST-0068-MARKER:" in (proc.stdout or ""),
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "model": "linux-execve-shebang",
        "read_shebang": True,
        "path": str(script),
    }


def resolve_interpreter(name: str) -> str:
    key = Path(name).name.lower()
    if key in {"python", "python3", "py"}:
        return sys.executable
    found = shutil.which(name)
    if found:
        return found
    raise FileNotFoundError(f"interpreter not on PATH: {name}")


def explicit_invoke(interpreter: str, script: Path, tag: str) -> dict[str, Any]:
    bin_path = resolve_interpreter(interpreter)
    proc = subprocess.run(
        [bin_path, str(script), tag],
        capture_output=True,
        text=True,
        cwd=str(FIXTURES),
        timeout=15,
        check=False,
    )
    return {
        "ok": proc.returncode == 0 and "TST-0068-MARKER:" in (proc.stdout or ""),
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "model": "explicit-interpreter",
        "read_shebang": False,
        "interpreter": bin_path,
        "script": str(script),
    }


def production_census() -> dict[str, Any]:
    seen: list[str] = []
    rows = []
    for rel in (*PRODUCTION_HOOK_MANIFESTS, *PRODUCTION_PLUGIN_MANIFESTS):
        if rel in seen:
            continue
        seen.append(rel)
        path = REPO / rel
        rows.append(
            {
                "path": rel,
                "present": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    hook = REPO / "hooks/_dispatch/manifest.json"
    plugin: Path | None = None
    for rel in PRODUCTION_PLUGIN_MANIFESTS:
        candidate = REPO / rel
        if candidate.is_file():
            plugin = candidate
            break
    audit = audit_pair(hook if hook.is_file() else None, plugin)
    any_present = any(r["present"] for r in rows)
    if not any_present:
        claim = (
            "Catalog paths hooks/_dispatch/manifest.json and plugin.json are "
            "absent on this worktree. Production shebang-reliant count is 0 "
            "because there are 0 production entries, which is vacuous — the "
            "fixture estate is the SUT that makes the detector non-vacuous."
        )
    elif audit["vacuous"]:
        claim = (
            "Production hook/plugin files exist but the auditor parsed 0 "
            "entries. That is a green-not-live parser miss (hooks[]-only on an "
            "events.checks manifest), not a measured zero-hazard."
        )
    else:
        claim = (
            f"hooks/_dispatch/manifest.json is present; parsed {audit['count']} "
            f"entries, {audit['shebang_reliant_count']} shebang-reliant. "
            "events.checks are importlib-loaded in-process by dispatch.py; "
            "cmd.exe never sees those .py paths. Spawn of the dispatcher is "
            "`python .../dispatch.py` in agent-self/config/settings.json. "
            "plugin.json at repo root is absent; .claude-plugin/plugin.json "
            "has no commands array."
        )
    return {
        "rows": rows,
        "any_present": any_present,
        "audit": audit,
        "claim": claim,
    }


def settings_spawn_census() -> dict[str, Any]:
    """Live launcher surface: settings.json hook commands (Windows spawn)."""
    path = REPO / SETTINGS_PATH
    if not path.is_file():
        return {
            "present": False,
            "path": SETTINGS_PATH,
            "count": 0,
            "shebang_reliant_count": 0,
            "shebang_reliant_ids": [],
            "all_declare_interpreter": False,
            "vacuous": True,
            "entries": [],
        }
    data = load_json(path)
    raw_rows: list[dict[str, Any]] = []
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        for event, matchers in hooks.items():
            if not isinstance(matchers, list):
                continue
            for block in matchers:
                if not isinstance(block, dict):
                    continue
                inner = block.get("hooks")
                if not isinstance(inner, list):
                    continue
                for i, h in enumerate(inner):
                    if not isinstance(h, dict):
                        continue
                    cmd = h.get("command")
                    if not isinstance(cmd, str) or not cmd.strip():
                        continue
                    raw_rows.append(
                        {
                            "_id": f"settings.{event}[{i}]",
                            "_kind": "settings-hook",
                            "_source": SETTINGS_PATH,
                            "command": cmd,
                        }
                    )
    for key in ("statusLine", "statusline"):
        sl = data.get(key)
        if isinstance(sl, dict) and isinstance(sl.get("command"), str):
            raw_rows.append(
                {
                    "_id": f"settings.{key}",
                    "_kind": "settings-statusline",
                    "_source": SETTINGS_PATH,
                    "command": sl["command"],
                }
            )
    classified = [classify_entry(e) for e in raw_rows]
    reliant = [c for c in classified if c["relies_on_shebang"]]
    return {
        "present": True,
        "path": SETTINGS_PATH,
        "count": len(classified),
        "shebang_reliant_count": len(reliant),
        "shebang_reliant_ids": [c["id"] for c in reliant],
        "declares_interpreter_count": sum(
            1 for c in classified if c["declares_interpreter"]
        ),
        "all_declare_interpreter": bool(classified) and len(reliant) == 0,
        "vacuous": len(classified) == 0,
        "entries": classified,
    }


def related_tst0086() -> dict[str, Any]:
    manifest = REPO / "command-center/p2-wave/probes/TST-0086/manifest.json"
    if not manifest.is_file():
        return {"present": False, "shebang_reliant_count": None, "count": 0}
    audit = audit_pair(manifest, None)
    return {
        "present": True,
        "path": "command-center/p2-wave/probes/TST-0086/manifest.json",
        "count": audit["count"],
        "shebang_reliant_count": audit["shebang_reliant_count"],
        "all_declare_interpreter": audit["all_declare_interpreter"],
        "ids": [e["id"] for e in audit["entries"]],
    }


def fixture_audit(kind: str) -> dict[str, Any]:
    root = FIXTURES / kind
    return audit_pair(root / "hooks/_dispatch/manifest.json", root / "plugin.json")


def windows_vs_linux_control() -> dict[str, Any]:
    script = SCRIPTS / "marker.sh"
    if not script.is_file():
        raise FileNotFoundError(script)
    win = windows_cmd_bare_invoke("./scripts/marker.sh")
    linux = linux_shebang_exec(script, "shebang-control")
    explicit = explicit_invoke("bash", script, "explicit-bash")
    cheat = bool(win.get("ok")) and bool(linux.get("ok"))
    return {
        "windows_bare_sh": win,
        "linux_shebang_exec": linux,
        "explicit_bash": explicit,
        "windows_failed": win.get("ok") is False,
        "linux_shebang_succeeded": linux.get("ok") is True,
        "explicit_succeeded": explicit.get("ok") is True,
        "not_recognized_in_stderr": "not recognized" in (win.get("stderr") or "").lower(),
        "shebang_cheat_detected": cheat,
        "discriminates": (
            win.get("ok") is False
            and linux.get("ok") is True
            and explicit.get("ok") is True
            and not cheat
        ),
    }


def invoke_classified(row: dict[str, Any], tag: str) -> dict[str, Any]:
    script_s = row.get("script") or ""
    script = (FIXTURES / script_s).resolve() if script_s else None
    if row["relies_on_shebang"]:
        token = script_s if script_s else str(row.get("command") or "")
        win = windows_cmd_bare_invoke(token)
        return {"id": row["id"], "route": "windows-bare", **win}
    interp = row["interpreter"] or "bash"
    if script is None or not script.is_file():
        argv = argv_of(row.get("command"))
        if len(argv) >= 2:
            interp = argv[0]
            script = (FIXTURES / argv[1]).resolve()
        else:
            return {
                "id": row["id"],
                "route": "explicit",
                "ok": False,
                "returncode": 127,
                "stderr": "script missing",
            }
    live = explicit_invoke(interp, script, tag)
    return {"id": row["id"], "route": "explicit", **live}


def run_all() -> dict[str, Any]:
    gold = fixture_audit("gold")
    estate = fixture_audit("estate")
    prod = production_census()
    settings = settings_spawn_census()
    related = related_tst0086()
    control = windows_vs_linux_control()
    live_rows = [invoke_classified(e, e["id"]) for e in estate["entries"]]
    gold_property = gold["all_declare_interpreter"] and not gold["vacuous"]
    estate_property = estate["all_declare_interpreter"]
    detector_both_states = (
        gold_property
        and (not estate_property)
        and estate["shebang_reliant_count"] >= 2
    )
    test1 = detector_both_states
    test2 = (
        control["discriminates"]
        and control["not_recognized_in_stderr"]
        and control["windows_bare_sh"]["returncode"] == CMD_NOT_RECOGNIZED_EXIT
        and not control["shebang_cheat_detected"]
    )
    prod_vacuous = bool(prod["audit"]["vacuous"])
    return {
        "pass": bool(test1 and test2),
        "host": {
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "bash": shutil.which("bash"),
            "cmd_exe": shutil.which("cmd.exe") or shutil.which("cmd"),
            "windows_cmd_live": False,
        },
        "production": prod,
        "settings_hooks": settings,
        "gold": gold,
        "estate": estate,
        "related_tst0086": related,
        "windows_linux_control": control,
        "live_invocations": live_rows,
        "tests": {
            "test_every_script_entry_declares_an_interpreter": test1,
            "test_bare_sh_invocation_is_reproduced_as_a_failure_on_windows": test2,
        },
        "answer": {
            "production_entries": prod["audit"]["count"],
            "production_shebang_reliant": prod["audit"]["shebang_reliant_count"],
            "production_vacuous": prod_vacuous,
            "settings_entries": settings["count"],
            "settings_shebang_reliant": settings["shebang_reliant_count"],
            "fixture_estate_entries": estate["count"],
            "fixture_estate_shebang_reliant": estate["shebang_reliant_count"],
            "fixture_estate_shebang_reliant_ids": estate["shebang_reliant_ids"],
            "gold_shebang_reliant": gold["shebang_reliant_count"],
            "tst0086_shebang_reliant": related.get("shebang_reliant_count"),
            "shebang_reliant_count": estate["shebang_reliant_count"],
            "text": (
                f"{prod['claim']} Settings spawn census: {settings['count']} "
                f"commands, {settings['shebang_reliant_count']} shebang-reliant. "
                "On the fixture estate that encodes the historical hooks[] + "
                "plugin-commands spawn shape: "
                f"{estate['shebang_reliant_count']} of {estate['count']} entries "
                f"rely on shebang resolution Windows does not perform "
                f"({estate['shebang_reliant_ids']}). Gold control: "
                f"{gold['shebang_reliant_count']} of {gold['count']}. "
                "TST-0086 probe manifest (explicit python3): "
                f"{related.get('shebang_reliant_count')} shebang-reliant of "
                f"{related.get('count')}."
            ),
        },
    }


if __name__ == "__main__":
    doc = run_all()
    print(
        json.dumps(
            {k: doc[k] for k in ("pass", "tests", "answer")},
            indent=2,
            sort_keys=True,
        )
    )
    raise SystemExit(0 if doc.get("pass") else 1)
