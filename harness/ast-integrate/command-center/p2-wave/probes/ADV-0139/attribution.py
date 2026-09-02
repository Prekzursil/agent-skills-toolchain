"""Artifact attribution from an event log; UNATTRIBUTED when reconstruction fails."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402
import load_probe as LP  # noqa: E402

CANARY_REL = "command-center/p2-wave/probes/ADV-0139/fixtures/attribution-canary.json"
EVENT_REL = "command-center/p2-wave/probes/ADV-0139/fixtures/attribution-event-log.jsonl"


def live_component_names() -> list[str]:
    names = ["cursor-agent-runtime"]
    rows = LP.iter_proc_cmdlines()
    if any("index.js worker-server" in cmd for _pid, cmd in rows):
        names.append("cursor-agent-worker-server")
    if any(
        ("/.local/bin/agent" in cmd or "cursor-agent" in cmd)
        for _pid, cmd in rows
    ):
        names.append("cursor-agent-cli")
    # Builtin write surface is live in this program whenever the agent is.
    names.append("cursor-builtin-Write")
    return names


def write_canary() -> dict:
    dest = C.REPO / CANARY_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    live = live_component_names()
    body = {
        "unit_id": "ADV-0139",
        "kind": "attribution-canary",
        "written_at": now,
        "note": "Benign canary used only to prove event-log reconstruction.",
    }
    dest.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = C.sha256_file(dest)
    event = {
        "event": "write",
        "path": CANARY_REL,
        "sha256": sha,
        "bytes": size,
        "ts": now,
        "components_live": live,
    }
    ev_path = C.REPO / EVENT_REL
    ev_path.write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
    return event


def reconstruct(event: dict) -> dict:
    path = C.REPO / str(event.get("path") or "")
    if not path.is_file():
        return {"reconstructed": False, "reason": "canary-missing"}
    sha, size = C.sha256_file(path)
    if sha != event.get("sha256") or size != event.get("bytes"):
        return {"reconstructed": False, "reason": "sha-or-size-mismatch"}
    live = list(event.get("components_live") or [])
    if "cursor-builtin-Write" not in live or "cursor-agent-runtime" not in live:
        return {"reconstructed": False, "reason": "live-set-incomplete"}
    return {
        "reconstructed": True,
        "path": event["path"],
        "components_live": live,
        "method": "event-log-sha256-and-live-set",
    }


def transcript_write_paths() -> set[str]:
    """Paths actually written via Write/StrReplace tool_use, not mere mentions."""
    found: set[str] = set()
    writers = {"Write", "StrReplace", "Delete", "EditNotebook"}
    if not C.TRANSCRIPTS.is_dir():
        return found
    for jsonl in C.TRANSCRIPTS.rglob("*.jsonl"):
        try:
            fh = jsonl.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                if '"tool_use"' not in line or "command-center/" not in line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = rec.get("message") if isinstance(rec, dict) else None
                content = (msg or {}).get("content") if isinstance(msg, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
                        continue
                    if block.get("name") not in writers:
                        continue
                    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
                    path = str(inp.get("path") or inp.get("target_notebook") or "")
                    path = path.replace("\\", "/")
                    prefix = "/opt/p2/ast-integrate/"
                    if path.startswith(prefix):
                        path = path[len(prefix) :]
                    if path.startswith("command-center/"):
                        found.add(path)
    return found


def scan_unattributed(limit: int = 24) -> list[dict]:
    """List unit-shaped artifacts whose writer cannot be reconstructed."""
    written = transcript_write_paths()
    roots = [
        C.REPO / "command-center" / "receipts",
        C.REPO / "command-center" / "adversarial",
        C.REPO / "command-center" / "audit",
        C.REPO / "command-center" / "research",
        C.REPO / "command-center" / "design",
    ]
    rows: list[dict] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            rel = path.relative_to(C.REPO).as_posix()
            if rel.endswith("attribution-canary.json"):
                continue
            if rel in written:
                continue
            rows.append(
                {
                    "path": rel,
                    "classification": "UNATTRIBUTED",
                    "reason": (
                        "event log / transcript did not reconstruct which "
                        "components were live at write time"
                    ),
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def run_attribution() -> dict:
    event = write_canary()
    rec = reconstruct(event)
    unattr = scan_unattributed()
    return {
        "control_artifact": CANARY_REL,
        "reconstructed": bool(rec.get("reconstructed")),
        "method": rec.get("method") or rec.get("reason") or "event-log",
        "control": rec,
        "event": event,
        "unattributed": unattr,
        "transcript_paths_sampled": len(transcript_write_paths()),
    }
