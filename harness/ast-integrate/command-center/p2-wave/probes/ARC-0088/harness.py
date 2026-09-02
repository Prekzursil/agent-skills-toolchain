"""Scratch-hook helpers for ARC-0088 named probes."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

MARKER_HOOK = r"""
import json, os, sys
from pathlib import Path
payload = json.load(sys.stdin)
side = Path(os.environ["ARC0088_SIDE_EFFECT"])
side.parent.mkdir(parents=True, exist_ok=True)
side.write_text(payload.get("hook_event_name", "") + "\n", encoding="utf-8")
print(json.dumps({"additionalContext": "marker-ok"}))
sys.exit(0)
"""

RAISE_HOOK = r"""
import json, os, sys
from pathlib import Path
payload = json.load(sys.stdin)
side = Path(os.environ["ARC0088_SIDE_EFFECT"])
side.parent.mkdir(parents=True, exist_ok=True)
side.write_text("raised\n", encoding="utf-8")
raise RuntimeError("planted-internal-error")
"""

NONZERO_HOOK = r"""
import json, os, sys
from pathlib import Path
payload = json.load(sys.stdin)
side = Path(os.environ["ARC0088_SIDE_EFFECT"])
side.parent.mkdir(parents=True, exist_ok=True)
side.write_text("nonzero\n", encoding="utf-8")
print(json.dumps({"additionalContext": "crash-inject"}))
sys.exit(1)
"""

STYLE_BLOCK_HOOK = r"""
import json, os, sys
from pathlib import Path
payload = json.load(sys.stdin)
side = Path(os.environ["ARC0088_SIDE_EFFECT"])
side.parent.mkdir(parents=True, exist_ok=True)
side.write_text("style-block-attempt\n", encoding="utf-8")
print(json.dumps({
    "decision": "block",
    "reason": {"class": "style_warning", "irreversible": False, "target": "lint"},
    "additionalContext": "style only",
}))
sys.exit(2)
"""

DANGER_BLOCK_HOOK = r"""
import json, os, sys
from pathlib import Path
payload = json.load(sys.stdin)
side = Path(os.environ["ARC0088_SIDE_EFFECT"])
side.parent.mkdir(parents=True, exist_ok=True)
side.write_text("danger-block\n", encoding="utf-8")
print(json.dumps({
    "danger": {
        "class": "irreversible_fs_destroy",
        "irreversible": True,
        "target": "/production/dataset",
    }
}))
sys.exit(2)
"""

SLOW_HOOK = r"""
import json, os, sys, time
from pathlib import Path
payload = json.load(sys.stdin)
time.sleep(2.0)
side = Path(os.environ["ARC0088_SIDE_EFFECT"])
side.parent.mkdir(parents=True, exist_ok=True)
side.write_text("slow\n", encoding="utf-8")
print(json.dumps({"additionalContext": "too-late"}))
sys.exit(0)
"""


def write_script(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.lstrip("\n"), encoding="utf-8")
    return path


def spec_for(
    hook_id: str, event: str, script: Path, *, timeout_ms: int = 5000
) -> dict[str, Any]:
    return {
        "id": hook_id,
        "event": event,
        "enabled": True,
        "interpreter": sys.executable,
        "timeout_ms": timeout_ms,
        "command": [sys.executable, "-B", str(script)],
    }


def write_manifest(path: Path, hooks: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"hooks": hooks}, indent=2) + "\n", encoding="utf-8")
    return path
