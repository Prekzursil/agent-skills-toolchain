"""Drive workflow-parameter values into argv-array vs string-command adapters."""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0031"
SINK = HERE / "fixtures" / "canary_sink.py"
SLEEPER = HERE / "fixtures" / "sleeper.py"
TOUCH = "/usr/bin/touch"

sys.path.insert(0, str(REPO / "tools"))
from foundry.runtime import execute as foundry_execute  # noqa: E402
from launcher.explicit_interpreter import argv_for as launcher_argv_for  # noqa: E402
from launcher.explicit_interpreter import launch as launcher_launch  # noqa: E402

sys.path.insert(0, str(HERE))
from corpus import BENIGN_ID, CORPUS, materialize  # noqa: E402

ADAPTERS = (
    {
        "id": "foundry-typed-workflow-inputs",
        "family": "passthrough",
        "kind": "shipped",
        "note": (
            "foundry.runtime.execute stores Workflow inputs on a Python ctx; "
            "it does not spawn a shell or process adapter."
        ),
    },
    {
        "id": "launcher-argv-extra-args",
        "family": "argv-array",
        "kind": "shipped",
        "note": "tools.launcher.explicit_interpreter.launch builds argv and subprocess.run(list).",
    },
    {
        "id": "planted-string-unquoted",
        "family": "string-command",
        "kind": "planted-detector",
        "note": "Naive f-string into shell=True. Negative control so the canary oracle can go red.",
    },
    {
        "id": "planted-string-single-quoted",
        "family": "string-command",
        "kind": "planted-detector",
        "note": "Adapter wraps the value in single quotes; apostrophe breaks that quoting.",
    },
)


def dump_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _store_param(ctx: dict[str, Any]) -> None:
    inputs = ctx.get("inputs") if isinstance(ctx.get("inputs"), dict) else {}
    ctx["result"] = {"param": inputs.get("param")}


def _call_name(node: ast.AST) -> tuple[str, str]:
    """Return (qualifier, name) for a Call.func, e.g. ('os','system')."""
    func = getattr(node, "func", None)
    if isinstance(func, ast.Attribute):
        qual = ""
        if isinstance(func.value, ast.Name):
            qual = func.value.id
        return qual, func.attr
    if isinstance(func, ast.Name):
        return "", func.id
    return "", ""


def static_spawn_inventory() -> dict[str, Any]:
    """Shipped tools/*.py spawn sites via AST (docstring mentions are not USE)."""
    root = REPO / "tools"
    shell_true: list[str] = []
    os_system: list[str] = []
    argv_run: list[str] = []
    skip = ("/tests/", "/__pycache__/", "/fixtures/")
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        if any(tok in f"/{rel}/" for tok in skip):
            continue
        try:
            text = path.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (OSError, SyntaxError):
            continue
        hit_shell = False
        hit_system = False
        hit_sub = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            qual, name = _call_name(node)
            if name == "system" and qual in {"os", ""}:
                hit_system = True
            if name in {"run", "Popen", "call", "check_output", "check_call"}:
                hit_sub = True
                for kw in node.keywords:
                    if kw.arg != "shell":
                        continue
                    val = kw.value
                    if isinstance(val, ast.Constant) and val.value is True:
                        hit_shell = True
        if hit_shell:
            shell_true.append(rel)
        if hit_system:
            os_system.append(rel)
        if hit_sub:
            argv_run.append(rel)
    return {
        "shell_true": shell_true,
        "os_system": os_system,
        "subprocess_sites": argv_run,
        "shipped_string_command_adapter_present": bool(shell_true or os_system),
    }


def _work() -> Path:
    return Path(tempfile.mkdtemp(prefix="adv0031-"))


def _canary_path(work: Path, token: str) -> Path:
    return work / f"canary-{token}"


def _record_path(work: Path, token: str) -> Path:
    return work / f"record-{token}.json"


def run_foundry(payload: str) -> dict[str, Any]:
    wf = {
        "schema": "foundry.typed-workflow.v1",
        "kind": "typed-workflow",
        "id": "adv0031-param-passthrough",
        "title": "ADV-0031 param passthrough",
        "stages": [
            {
                "id": "store",
                "kind": "python",
                "handler": "adv0031.store",
                "depends_on": [],
            }
        ],
    }
    receipt = foundry_execute(
        wf,
        inputs={"param": payload},
        handler_table={"adv0031.store": _store_param},
    )
    got = None
    outputs = receipt.get("outputs")
    if isinstance(outputs, dict):
        got = outputs.get("param")
    return {
        "ok": receipt.get("ok") is True,
        "round_trip": got == payload,
        "spawned": False,
        "intended_argv": [],
        "observed_argv": [],
        "family": "passthrough",
        "adapter": "foundry-typed-workflow-inputs",
    }


def child_param(record: Path) -> str | None:
    if not record.is_file():
        return None
    try:
        doc = json.loads(record.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(doc.get("param"), str):
        return doc["param"]
    argv = doc.get("argv") or []
    if isinstance(argv, list) and len(argv) >= 3:
        return str(argv[-1])
    return None


def run_launcher_argv(payload: str, record: Path) -> dict[str, Any]:
    intended = launcher_argv_for(
        SINK,
        interpreter=sys.executable,
        extra_args=(str(record), payload),
    )
    proc = launcher_launch(
        SINK,
        interpreter=sys.executable,
        extra_args=(str(record), payload),
        timeout=20,
    )
    observed = child_param(record)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "intended_argv": intended,
        "observed_param": observed,
        "argv_match": observed == payload,
        "family": "argv-array",
        "adapter": "launcher-argv-extra-args",
        "stdout": (proc.stdout or "")[-400:],
        "stderr": (proc.stderr or "")[-400:],
    }


def run_string_unquoted(payload: str, record: Path) -> dict[str, Any]:
    intended = [sys.executable, str(SINK), str(record), payload]
    cmd = f"{sys.executable} {SINK} {record} {payload}"
    proc = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    observed: list[str] = []
    if record.is_file():
        try:
            observed = json.loads(record.read_text(encoding="utf-8")).get("argv") or []
        except json.JSONDecodeError:
            observed = []
    return {
        "ok": True,
        "returncode": proc.returncode,
        "intended_argv": intended,
        "observed_argv": observed,
        "argv_match": observed == intended,
        "family": "string-command",
        "adapter": "planted-string-unquoted",
        "command_string": cmd,
    }


def run_string_quoted(payload: str, record: Path) -> dict[str, Any]:
    intended = [sys.executable, str(SINK), str(record), payload]
    cmd = f"{sys.executable} {SINK} {record} '{payload}'"
    proc = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    observed: list[str] = []
    if record.is_file():
        try:
            observed = json.loads(record.read_text(encoding="utf-8")).get("argv") or []
        except json.JSONDecodeError:
            observed = []
    return {
        "ok": True,
        "returncode": proc.returncode,
        "intended_argv": intended,
        "observed_argv": observed,
        "argv_match": observed == intended,
        "family": "string-command",
        "adapter": "planted-string-single-quoted",
        "command_string": cmd,
    }


def _ppid(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except (OSError, ValueError):
        return None
    return None


def cmdline_of(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def descendants(root: int) -> list[int]:
    found = [root]
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return found
    kids: dict[int, list[int]] = {}
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        parent = _ppid(pid)
        if parent is None:
            continue
        kids.setdefault(parent, []).append(pid)
    stack = [root]
    seen = {root}
    while stack:
        cur = stack.pop()
        for child in kids.get(cur, []):
            if child in seen:
                continue
            seen.add(child)
            found.append(child)
            stack.append(child)
    return found


def snapshot_tree(root: int) -> list[dict[str, Any]]:
    rows = []
    for pid in descendants(root):
        argv = cmdline_of(pid)
        rows.append({"pid": pid, "ppid": _ppid(pid), "argv": argv})
    return rows


def payload_unsplit_in_tree(tree: list[dict[str, Any]], payload: str) -> bool:
    for row in tree:
        argv = row.get("argv") or []
        if payload in argv:
            return True
    return False


def extra_touch_in_tree(tree: list[dict[str, Any]], canary: str) -> bool:
    del canary  # oracle is the touch process image, not a substring of sleeper argv
    for row in tree:
        argv = row.get("argv") or []
        if not argv:
            continue
        name = Path(str(argv[0])).name
        if name in {"touch", "touch.exe"}:
            return True
    return False


def start_sleeper_argv(payload: str, record: Path) -> tuple[subprocess.Popen, list[str]]:
    intended = launcher_argv_for(
        SLEEPER,
        interpreter=sys.executable,
        extra_args=(str(record), payload),
    )
    env = os.environ.copy()
    env["ADV0031_SLEEP"] = "2.2"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.Popen(
        intended,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc, intended


def start_sleeper_string_unquoted(
    payload: str, record: Path
) -> tuple[subprocess.Popen, list[str]]:
    intended = [sys.executable, str(SLEEPER), str(record), payload]
    env = os.environ.copy()
    env["ADV0031_SLEEP"] = "2.2"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = f"{sys.executable} {SLEEPER} {record} {payload}"
    proc = subprocess.Popen(
        cmd,
        shell=True,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc, intended


def start_sleeper_string_quoted(
    payload: str, record: Path
) -> tuple[subprocess.Popen, list[str]]:
    intended = [sys.executable, str(SLEEPER), str(record), payload]
    env = os.environ.copy()
    env["ADV0031_SLEEP"] = "2.2"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = f"{sys.executable} {SLEEPER} {record} '{payload}'"
    proc = subprocess.Popen(
        cmd,
        shell=True,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc, intended


def observe_process(start_fn, payload: str, work: Path, token: str, canary: Path) -> dict[str, Any]:
    record = _record_path(work, token)
    proc, intended = start_fn(payload, record)
    try:
        time.sleep(0.35)
        tree = snapshot_tree(proc.pid)
        root_argv = cmdline_of(proc.pid)
        unsplit = payload_unsplit_in_tree(tree, payload)
        extra = extra_touch_in_tree(tree, str(canary))
        root_is_shell = bool(root_argv) and Path(root_argv[0]).name in {
            "sh",
            "bash",
            "dash",
            "busybox",
        }
        sleeper_has_payload = False
        for row in tree:
            argv = row.get("argv") or []
            if any("sleeper.py" in str(a) for a in argv) and payload in argv:
                sleeper_has_payload = True
                break
        alters = (not sleeper_has_payload) or extra
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        return {
            "root_pid": proc.pid,
            "root_argv": root_argv,
            "intended_argv": intended,
            "tree": tree,
            "payload_unsplit": sleeper_has_payload,
            "extra_touch": extra,
            "root_is_shell": root_is_shell,
            "argv_altered": bool(alters),
            "wait_rc": proc.returncode,
        }
    finally:
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass


def run_canary_campaign() -> dict[str, Any]:
    work = _work()
    inventory = static_spawn_inventory()
    rows: list[dict[str, Any]] = []
    for spec in CORPUS:
        token = spec["id"]
        canary = _canary_path(work, token)
        item = materialize(spec, str(canary))
        payload = item["value"]
        before = canary.exists()
        foundry = run_foundry(payload)
        canary_after_foundry = canary.exists()
        launcher = run_launcher_argv(payload, _record_path(work, f"{token}-launch"))
        canary_after_launcher = canary.exists()
        unquoted = run_string_unquoted(payload, _record_path(work, f"{token}-unq"))
        canary_after_unquoted = canary.exists()
        if canary.exists():
            try:
                canary.unlink()
            except OSError:
                pass
        quoted = run_string_quoted(payload, _record_path(work, f"{token}-q"))
        canary_after_quoted = canary.exists()
        rows.append(
            {
                "id": spec["id"],
                "family": spec["family"],
                "role": spec["role"],
                "payload": payload,
                "canary": str(canary),
                "canary_existed_before": before,
                "foundry": {
                    **{k: v for k, v in foundry.items() if k != "stdout"},
                    "canary": canary_after_foundry,
                },
                "launcher": {
                    "argv_match": launcher.get("argv_match"),
                    "observed_param": launcher.get("observed_param"),
                    "canary": canary_after_launcher,
                    "returncode": launcher.get("returncode"),
                },
                "string_unquoted": {
                    "argv_match": unquoted.get("argv_match"),
                    "canary": canary_after_unquoted,
                    "returncode": unquoted.get("returncode"),
                },
                "string_quoted": {
                    "argv_match": quoted.get("argv_match"),
                    "canary": canary_after_quoted,
                    "returncode": quoted.get("returncode"),
                },
                "expect": {
                    "string_unquoted": spec["expect_canary_on_string_unquoted"],
                    "string_quoted": spec["expect_canary_on_string_quoted"],
                    "argv": spec["expect_canary_on_argv"],
                },
            }
        )
        if canary.exists():
            try:
                canary.unlink()
            except OSError:
                pass
    benign = next(r for r in rows if r["id"] == BENIGN_ID)
    semi = next(r for r in rows if r["id"] == "semicolon")
    apos = next(r for r in rows if r["id"] == "apostrophe-breakout")
    controls = {
        "benign_no_canary_any_adapter": (
            not benign["foundry"]["canary"]
            and not benign["launcher"]["canary"]
            and not benign["string_unquoted"]["canary"]
            and not benign["string_quoted"]["canary"]
        ),
        "benign_launcher_argv_match": benign["launcher"]["argv_match"] is True,
        "semicolon_string_unquoted_canary": semi["string_unquoted"]["canary"] is True,
        "semicolon_launcher_no_canary": semi["launcher"]["canary"] is False,
        "semicolon_foundry_no_canary": semi["foundry"]["canary"] is False,
        "apostrophe_quoted_canary": apos["string_quoted"]["canary"] is True,
        "apostrophe_launcher_no_canary": apos["launcher"]["canary"] is False,
    }
    return {
        "probe": "probe1-canary-side-effect",
        "unit_id": UNIT,
        "work": str(work),
        "inventory": inventory,
        "adapters": list(ADAPTERS),
        "controls": controls,
        "rows": rows,
        "ok": all(controls.values()),
    }


def run_process_table_campaign() -> dict[str, Any]:
    work = _work()
    focus_ids = (
        BENIGN_ID,
        "semicolon",
        "dollar-paren",
        "apostrophe-breakout",
        "newline",
        "caret-powershell",
        "here-string-terminator",
        "msys-convertible-path",
    )
    rows: list[dict[str, Any]] = []
    for spec in CORPUS:
        if spec["id"] not in focus_ids:
            continue
        token = spec["id"]
        canary = _canary_path(work, f"p2-{token}")
        item = materialize(spec, str(canary))
        payload = item["value"]
        argv_obs = observe_process(
            start_sleeper_argv, payload, work, f"{token}-argv", canary
        )
        unq_obs = observe_process(
            start_sleeper_string_unquoted, payload, work, f"{token}-unq", canary
        )
        q_obs = observe_process(
            start_sleeper_string_quoted, payload, work, f"{token}-q", canary
        )
        rows.append(
            {
                "id": spec["id"],
                "family": spec["family"],
                "payload": payload,
                "argv_array": {
                    "adapter": "launcher-style-argv",
                    "family": "argv-array",
                    "payload_unsplit": argv_obs["payload_unsplit"],
                    "extra_touch": argv_obs["extra_touch"],
                    "root_is_shell": argv_obs["root_is_shell"],
                    "argv_altered": argv_obs["argv_altered"],
                    "root_argv": argv_obs["root_argv"],
                    "intended_argv_tail": (argv_obs["intended_argv"] or [None])[-1],
                },
                "string_unquoted": {
                    "adapter": "planted-string-unquoted",
                    "family": "string-command",
                    "payload_unsplit": unq_obs["payload_unsplit"],
                    "extra_touch": unq_obs["extra_touch"],
                    "root_is_shell": unq_obs["root_is_shell"],
                    "argv_altered": unq_obs["argv_altered"],
                    "root_argv_head": (unq_obs["root_argv"] or [])[:3],
                },
                "string_quoted": {
                    "adapter": "planted-string-single-quoted",
                    "family": "string-command",
                    "payload_unsplit": q_obs["payload_unsplit"],
                    "extra_touch": q_obs["extra_touch"],
                    "root_is_shell": q_obs["root_is_shell"],
                    "argv_altered": q_obs["argv_altered"],
                    "root_argv_head": (q_obs["root_argv"] or [])[:3],
                },
            }
        )
        if canary.exists():
            try:
                canary.unlink()
            except OSError:
                pass
    benign = next(r for r in rows if r["id"] == BENIGN_ID)
    semi = next(r for r in rows if r["id"] == "semicolon")
    apos = next(r for r in rows if r["id"] == "apostrophe-breakout")
    controls = {
        "procfs_readable": Path("/proc/self/cmdline").is_file(),
        "benign_argv_unsplit": benign["argv_array"]["payload_unsplit"] is True,
        "benign_argv_not_altered": benign["argv_array"]["argv_altered"] is False,
        "semicolon_argv_unsplit": semi["argv_array"]["payload_unsplit"] is True,
        "semicolon_argv_not_altered": semi["argv_array"]["argv_altered"] is False,
        "semicolon_string_altered": semi["string_unquoted"]["argv_altered"] is True,
        "apostrophe_quoted_altered": apos["string_quoted"]["argv_altered"] is True,
        "apostrophe_argv_unsplit": apos["argv_array"]["payload_unsplit"] is True,
    }
    return {
        "probe": "probe2-process-table-argv",
        "unit_id": UNIT,
        "work": str(work),
        "host_pwsh": bool(__import__("shutil").which("pwsh")),
        "controls": controls,
        "rows": rows,
        "ok": all(controls.values()),
    }
