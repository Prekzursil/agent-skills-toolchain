#!/usr/bin/env python3
"""Execute the shipped client wrapper against a stub node that records argv/env."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from delta import run_cmd, scratch_dir

STUB_NODE = r"""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
log = Path(__file__).resolve().parent / "_node_log.jsonl"
rec = {
    "argv": sys.argv,
    "NODE_COMPILE_CACHE": os.environ.get("NODE_COMPILE_CACHE"),
    "XDG_CACHE_HOME": os.environ.get("XDG_CACHE_HOME"),
    "CURSOR_INVOKED_AS": os.environ.get("CURSOR_INVOKED_AS"),
    "AGENT_CLI_CREDENTIAL_STORE": os.environ.get("AGENT_CLI_CREDENTIAL_STORE"),
    "RES0021_INVENTED_FLAG": os.environ.get("RES0021_INVENTED_FLAG"),
}
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(rec) + "\n")
if "--version" in sys.argv:
    print("v0.0.0-stub")
    raise SystemExit(0)
print("stub-index")
raise SystemExit(0)
"""


def prepare_wrapper_sandbox(real_wrapper: Path) -> Path:
    root = scratch_dir("res0021-wrap-")
    text = real_wrapper.read_text(encoding="utf-8")
    (root / "cursor-agent").write_text(text, encoding="utf-8")
    (root / "cursor-agent").chmod(stat.S_IRWXU)
    node = root / "node"
    node.write_text(STUB_NODE, encoding="utf-8")
    node.chmod(stat.S_IRWXU)
    (root / "index.js").write_text("/* stub */\n", encoding="utf-8")
    return root


def run_wrapper(root: Path, extra_env: dict[str, str] | None, pop: tuple[str, ...] = ()) -> dict:
    log = root / "_node_log.jsonl"
    if log.is_file():
        log.unlink()
    env = os.environ.copy()
    for name in pop:
        env.pop(name, None)
    if extra_env:
        env.update(extra_env)
    run = run_cmd([str(root / "cursor-agent"), "--version"], env=env, timeout=15, cwd=str(root))
    records = []
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    argv_flat = []
    for rec in records:
        argv_flat.extend(rec.get("argv") or [])
    return {
        **run,
        "records": records,
        "argv_flat": argv_flat,
        "use_system_ca_count": sum(1 for a in argv_flat if a == "--use-system-ca"),
        "ncc": [rec.get("NODE_COMPILE_CACHE") for rec in records],
        "invoked_as": [rec.get("CURSOR_INVOKED_AS") for rec in records],
        "invented": [rec.get("RES0021_INVENTED_FLAG") for rec in records],
    }
