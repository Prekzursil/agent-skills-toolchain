"""Shared live spawn + canary helpers for TST-0210."""
from __future__ import annotations

import importlib.util
import json
import os
import shlex
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DUMPER = HERE / "dumper.py"
ADAPTER_PATH = REPO / "command-center" / "adapters" / "claude_adapter.py"
ENV_MOD_PATH = REPO / "tools" / "lib" / "env_allowlist.py"
SECURITY_MJS = REPO / "tools" / "lib" / "security.mjs"
CANARY_KEY = "TST0210_CANARY_TOKEN"
CANARY_VAL = "planted-fixture-not-a-credential"


def load_env_mod():
    spec = importlib.util.spec_from_file_location("tst0210_env_allowlist", ENV_MOD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {ENV_MOD_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_adapter():
    spec = importlib.util.spec_from_file_location("claude_adapter", ADAPTER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {ADAPTER_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@contextmanager
def planted_canary():
    prev = os.environ.get(CANARY_KEY)
    os.environ[CANARY_KEY] = CANARY_VAL
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop(CANARY_KEY, None)
        else:
            os.environ[CANARY_KEY] = prev


def dump_keys_via_adapter() -> tuple[list[str], dict]:
    """Spawn a child through ClaudeAdapter.Bash with the product env filter."""
    ca = load_adapter()
    adapter = ca.ClaudeAdapter()
    with tempfile.TemporaryDirectory(prefix="tst0210-") as td:
        root = Path(td)
        out_path = root / "env-keys.json"
        cmd = (
            f"{shlex.quote(sys.executable)} {shlex.quote(str(DUMPER))} "
            f"{shlex.quote(str(out_path))}"
        )
        dispatched = adapter.dispatch(
            {
                "id": "TST-0210-DUMP",
                "tool_permissions": ["Bash"],
                "timeout_seconds": 20,
            },
            lambda tools: tools.Bash(cmd),
            sandbox_root=root,
            sentinel="TST-0210-CHILD-DUMP",
        )
        if dispatched.get("state") != "SUCCESS":
            raise RuntimeError(f"adapter dump dispatch failed: {dispatched}")
        payload = (dispatched.get("result") or {}).get("payload") or {}
        if int(payload.get("returncode") or 0) != 0:
            raise RuntimeError(
                f"adapter child dumper rc={payload.get('returncode')} "
                f"stderr={(payload.get('stderr') or '')[:400]}"
            )
        stdout = payload.get("stdout") or ""
        lines = [ln for ln in stdout.strip().splitlines() if ln.strip()]
        if lines:
            keys = json.loads(lines[0])
        elif out_path.is_file():
            keys = json.loads(out_path.read_text(encoding="utf-8"))
        else:
            raise RuntimeError("adapter child produced no key list")
    if not isinstance(keys, list):
        raise RuntimeError("adapter child stdout is not a JSON key list")
    return [str(k) for k in keys], dispatched


def dump_keys_with_env(env: dict[str, str]) -> list[str]:
    env_mod = load_env_mod()
    return env_mod.dump_child_keys(env=env, dumper=DUMPER)
