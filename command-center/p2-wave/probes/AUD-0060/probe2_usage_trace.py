#!/usr/bin/env python3
"""AUD-0060 Probe 2: usage trace — which tools were actually invoked.

Honest on this substrate:
  * Execute one planted tools/call (whoami) against fake-mcp so the usage tracer
    has a known good invocation (control).
  * Scan available local corpora (mcp-audit artifacts, capability matrix) for
    recorded call_verified / tool invocation evidence — not invented counts.
  * Owner-host recent Claude session transcripts are NOT mounted here; that gap
    is recorded as UNMEASURED rather than fabricated as zero-use.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # p2-wave
import _p2lib as L  # noqa: E402

REPO = L.REPO
HOST_DIR = REPO / "tools" / "mcp" / "mcp-http-host"
sys.path.insert(0, str(HOST_DIR))
from mcp_http_host import StdioChild  # noqa: E402

OUT_JSON = PROBE / "probe2-usage-trace.json"
OUT_RAW = PROBE / "probe2-usage-trace.raw.txt"
FAKE = HOST_DIR / "_fake_mcp_server.py"
CAP = REPO / "command-center/mcp-audit/capability-matrix.json"
COST = REPO / "command-center/mcp-audit/tool-cost-local.json"
CLAUDE_LIST = REPO / "command-center/mcp-audit/claude-mcp-list.txt"

# Patterns that look like MCP tool invocations in text corpora
INV_RE = re.compile(
    r"(?:mcp__([A-Za-z0-9_-]+)__([A-Za-z0-9_-]+)|"
    r"CallDynamicTool[^\n]{0,80}toolName[\"']?:\s*[\"']([A-Za-z0-9_-]+)[\"'])",
    re.M,
)


def planted_call() -> dict:
    child = StdioChild([sys.executable, str(FAKE)])
    try:
        child.request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "aud-0060-probe2", "version": "0"},
                },
            },
            timeout=20,
        )
        child.request(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            timeout=20,
        )
        resp = child.request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "whoami", "arguments": {}},
            },
            timeout=20,
        )
        ok = resp is not None and "result" in (resp or {})
        return {
            "ok": ok,
            "server": "_planted_fake_mcp",
            "tool": "whoami",
            "raw_result": resp,
            "error": None if ok else "tools/call did not return result",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "server": "_planted_fake_mcp",
            "tool": "whoami",
            "raw_result": None,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        child.terminate()


def scan_capability_matrix() -> dict:
    if not CAP.is_file():
        return {"present": False, "rows": [], "call_verified_count": 0}
    doc = json.loads(CAP.read_text(encoding="utf-8"))
    rows = []
    for r in doc.get("rows") or []:
        rows.append(
            {
                "name": r.get("name"),
                "call_verified": bool(r.get("call_verified")),
                "tool_count": r.get("tool_count"),
                "tool_names": r.get("tool_names"),
                "last_error": r.get("last_error"),
                "probe_method": r.get("probe_method"),
            }
        )
    return {
        "present": True,
        "path": str(CAP.relative_to(REPO)),
        "generated_utc_date": doc.get("generated_utc_date"),
        "summary": doc.get("summary"),
        "call_verified_count": sum(1 for r in rows if r["call_verified"]),
        "rows": rows,
        "note": (
            "Historical owner-host capability probe artifact — evidence of prior "
            "live tools/list on Windows host, NOT a re-run on this cloud worker."
        ),
    }


def scan_text_corpora() -> dict:
    """Search mounted text for invocation fingerprints. Thin corpus → honest zero."""
    roots = [
        REPO / "command-center/mcp-audit",
        Path("/tmp/cursor"),
        Path.home() / ".cursor" / "projects" / "workspace",
    ]
    hits: Counter[str] = Counter()
    files_scanned = 0
    bytes_scanned = 0
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".txt", ".json", ".jsonl", ".md", ".log"}:
                continue
            if path.stat().st_size > 2_000_000:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            files_scanned += 1
            bytes_scanned += len(text)
            for m in INV_RE.finditer(text):
                if m.group(1) and m.group(2):
                    hits[f"mcp__{m.group(1)}__{m.group(2)}"] += 1
                elif m.group(3):
                    hits[f"CallDynamicTool:{m.group(3)}"] += 1
    return {
        "files_scanned": files_scanned,
        "bytes_scanned": bytes_scanned,
        "distinct_invocation_fingerprints": len(hits),
        "top_hits": hits.most_common(40),
        "owner_session_transcripts_mounted": False,
        "note": (
            "No owner-host Claude session transcript corpus mounted on this worker; "
            "fingerprint hits are from local mcp-audit / cursor project files only."
        ),
    }


def main() -> int:
    lines: list[str] = []
    lines.append("AUD-0060 NAMED PROBE 2: usage trace over recent sessions")
    lines.append(f"CAPTURED_AT={datetime.now(timezone.utc).isoformat()}")

    planted = planted_call()
    lines.append("=== PLANTED USAGE CONTROL ===")
    lines.append(
        f"planted_tools_call server={planted['server']} tool={planted['tool']} "
        f"ok={planted['ok']} err={planted.get('error')}"
    )

    cap = scan_capability_matrix()
    lines.append("=== CAPABILITY-MATRIX (historical owner-host) ===")
    lines.append(
        f"present={cap.get('present')} call_verified={cap.get('call_verified_count')} "
        f"summary={cap.get('summary')}"
    )
    for r in (cap.get("rows") or [])[:25]:
        lines.append(
            f"CAP\t{r['name']}\tverified={r['call_verified']}\t"
            f"tool_count={r['tool_count']}"
        )

    text = scan_text_corpora()
    lines.append("=== TEXT CORPUS FINGERPRINTS ===")
    lines.append(
        f"files={text['files_scanned']} bytes={text['bytes_scanned']} "
        f"distinct={text['distinct_invocation_fingerprints']}"
    )
    for name, n in text["top_hits"][:20]:
        lines.append(f"HIT\t{n}\t{name}")

    # Join: exposed surface with zero measured invocations on THIS substrate
    # vs historical call_verified. Do not invent live invocation counts.
    zero_use_on_substrate = []
    if cap.get("present"):
        for r in cap.get("rows") or []:
            if r.get("call_verified") and isinstance(r.get("tool_count"), int):
                # Historical exposure with verified list — usage on THIS worker unknown
                zero_use_on_substrate.append(
                    {
                        "name": r["name"],
                        "historical_tool_count": r["tool_count"],
                        "invocations_on_this_substrate": 0
                        if r["name"] != "_planted_fake_mcp"
                        else None,
                        "status": "USAGE-UNMEASURED-ON-THIS-SUBSTRATE",
                    }
                )

    control_ok = bool(planted.get("ok"))
    doc = {
        "unit": "AUD-0060",
        "probe": 2,
        "ok": control_ok,
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "substrate": "linux-cursor-cloud",
        "owner_session_corpus_mounted": False,
        "control": {
            "ok": control_ok,
            "planted_tools_call": planted,
            "description": (
                "Planted fake-mcp whoami tools/call must succeed so the usage "
                "tracer is proven able to record an invocation."
            ),
        },
        "planted_invocation": planted,
        "historical_capability_matrix": {
            "present": cap.get("present"),
            "path": cap.get("path"),
            "call_verified_count": cap.get("call_verified_count"),
            "summary": cap.get("summary"),
            "note": cap.get("note"),
        },
        "text_corpus": text,
        "usage_on_this_substrate": {
            "planted_invocations": 1 if control_ok else 0,
            "owner_host_session_invocations": None,
            "note": (
                "owner_host_session_invocations left null — transcripts not mounted; "
                "null is not zero-use."
            ),
        },
        "large_surface_zero_use_finding": {
            "status": "NOT-SETTLED",
            "reason": (
                "Cannot classify large exposed surfaces as zero-invocation without "
                "owner-host session traces; historical capability matrix shows "
                f"{cap.get('call_verified_count', 0)} call_verified servers on Windows host."
            ),
            "candidates_usage_unmeasured": zero_use_on_substrate[:40],
        },
        "claude_mcp_list_artifact_present": CLAUDE_LIST.is_file(),
        "tool_cost_local_present": COST.is_file(),
    }

    lines.append(
        f"SUMMARY planted_ok={control_ok} "
        f"hist_call_verified={cap.get('call_verified_count')} "
        f"corpus_distinct={text['distinct_invocation_fingerprints']} "
        f"owner_sessions_mounted=False"
    )
    lines.append("SUCCESS:AUD-0060-probe2" if doc["ok"] else "FAILED:AUD-0060-probe2")

    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
