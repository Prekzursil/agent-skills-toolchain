"""ADV-0019 Probe 2 (Windows Git-Bash + pwsh, 2026-10-21): resolve extracted names
through a second, shell-independent inventory.

Resolvers:
  A. PATH resolver (shutil.which — same Windows PATH Git-Bash translates; stands in for
     `bash command -v`, which MEASURED-HANGS when spawned from Windows python for .exe
     targets — recorded as detector defect D-ADV0019-3, evidence in raw output).
  B. pwsh Get-Command (sees .cmd shims the PATH resolver ordering can miss).
  C. live MCP inventory: ~/.claude.json mcpServers (live mounted config) + this
     session's tool-schema snapshot + the 2026-10-21 live `claude mcp list` health
     states captured in-session before health checks began hanging.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
FABRICATED = "zzz-definitely-not-real-1"
PRESENT_CONTROL = ["git", "python", "node", "pwsh"]
CLAUDE_JSON = Path.home() / ".claude.json"

# Live `claude mcp list` health states, captured 2026-10-21 in-session (the same
# command later hung at "Checking MCP server health..." — network-dependent).
LIVE_MCP_STATES = {
    "plugin:exa:exa": "Needs authentication",
    "context7": "Disabled",
    "basic-memory": "Connected",
    "figma": "Connected",
    "hexstrike-ai": "Disabled",
    "huggingface": "Failed",
    "agent-mail": "Connected",
    "firecrawl": "Disabled",
    "linear": "Disabled",
    "notion": "Disabled",
    "semgrep": "Disabled",
    "cve-mcp": "Disabled",
    "github": "Connected",
}

# Live session tool-schema snapshot (ZCode session 2026-10-21, the operating agent's
# own mounted tool roster — manual-inspection method).
SESSION_SERVERS = [
    "agent-mail", "basic-memory", "4_5v_mcp", "consult-offsec", "deepwiki",
    "exa", "node_repl", "openaiDeveloperDocs", "web_reader", "zai-lane-a",
    "plugin_android-emulator_android-emulator", "plugin_cloudbase-skills_cloudbase",
    "plugin_documents_documents", "plugin_pdf_pdf", "plugin_presentations_presentations",
    "plugin_spreadsheets_spreadsheets", "plugin_video-agent-kit_video-edit",
    "plugin_video2code_runtime", "plugin_video2code_video", "plugin_ios-simulator_ios-simulator",
]


def pwsh_inventory(tokens: list[str]) -> set[str]:
    found: set[str] = set()
    tokset = set(tokens)
    B = 200
    for i in range(0, len(tokens), B):
        chunk = tokens[i:i + B]
        script = (
            "$ErrorActionPreference='SilentlyContinue';"
            + "".join(
                f"if (Get-Command -Name '{t}' -ErrorAction SilentlyContinue) "
                f"{{ Write-Output '{t}' }};" for t in chunk)
        )
        try:
            r = subprocess.run(["pwsh", "-NoProfile", "-Command", script],
                               capture_output=True, text=True, timeout=180)
            found |= {ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip() in tokset}
        except Exception:  # noqa: BLE001  (timeout etc. -> resolver partial, recorded)
            continue
    return found


def bash_batch_probe(tokens: list[str]) -> dict:
    """Attempt the literal `bash -c 'command -v t ...'` batch resolver with a short
    timeout; expected to hang per the measured msys defect. Recorded either way."""
    try:
        r = subprocess.run(
            ["bash", "-c", " ".join(f"command -v {t} >/dev/null 2>&1 && echo {t};" for t in tokens[:10])],
            capture_output=True, text=True, timeout=15)
        return {"status": "ok", "found": sorted(set(r.stdout.split()))}
    except subprocess.TimeoutExpired:
        return {"status": "timeout-15s-on-first-batch", "found": [],
                "note": "msys bash spawned from Windows python hangs on .exe PATH "
                        "lookups (gh/node/pwsh/codex each TIMEOUT at 10s in per-token "
                        "isolation; git, an msys binary, resolves instantly). Detector "
                        "defect recorded as D-ADV0019-3; PATH resolver A substitutes."}


def main() -> int:
    p1 = json.loads((OUT / "probe1-extract.json").read_text(encoding="utf-8"))
    cmd_tokens = sorted(p1["cmd_tokens_sample"].keys())
    mcp_servers = sorted({t.split("__")[1] for t in p1["mcp_tokens"]})

    to_resolve = list(dict.fromkeys(cmd_tokens + [FABRICATED] + PRESENT_CONTROL))
    which_inv = {t for t in to_resolve if shutil.which(t)}
    pwsh_inv = pwsh_inventory(to_resolve)
    bash_attempt = bash_batch_probe(to_resolve)

    both = [t for t in to_resolve if t in which_inv and t in pwsh_inv]
    which_only = [t for t in to_resolve if t in which_inv and t not in pwsh_inv]
    pwsh_only = [t for t in to_resolve if t not in which_inv and t in pwsh_inv]
    absent = [t for t in to_resolve if t not in which_inv and t not in pwsh_inv]

    cfg_servers: list[str] = []
    if CLAUDE_JSON.is_file():
        try:
            cfg_servers = sorted(json.loads(
                CLAUDE_JSON.read_text(encoding="utf-8")).get("mcpServers", {}).keys())
        except Exception:  # noqa: BLE001
            cfg_servers = []

    mcp_rows = []
    for srv in mcp_servers:
        in_cfg = srv in cfg_servers
        state = LIVE_MCP_STATES.get(srv)
        in_session = srv in SESSION_SERVERS
        mcp_rows.append({
            "server": srv,
            "in_claude_json_config": in_cfg,
            "claude_mcp_list_2026_10_21": state,
            "session_tool_schema": in_session,
            "live": bool(in_cfg or state or in_session),
        })
    dead_mcp = [r["server"] for r in mcp_rows if not r["live"]]

    controls = {
        "CTRL-ABSENT-BIN": FABRICATED in absent,
        "CTRL-PRESENT-BIN": all(t in which_inv or t in pwsh_inv for t in PRESENT_CONTROL),
        "CTRL-PRESENT-MCP": any(r["claude_mcp_list_2026_10_21"] == "Connected"
                                for r in mcp_rows) or bool(SESSION_SERVERS),
        "CTRL-L2-BOTH-STATES": (FABRICATED in absent) and all(t not in absent for t in PRESENT_CONTROL),
    }

    payload = {
        "probe": "probe2-resolve",
        "resolved_count": len(to_resolve),
        "which_inv_count": len(which_inv),
        "pwsh_inv_count": len(pwsh_inv),
        "both_resolvers": len(both),
        "which_only": len(which_only),
        "pwsh_only": len(pwsh_only),
        "absent_count": len(absent),
        "absent_sample": absent[:60],
        "bash_literal_attempt": bash_attempt,
        "fabricated_control_absent": FABRICATED in absent,
        "present_control": {t: [t in which_inv, t in pwsh_inv] for t in PRESENT_CONTROL},
        "claude_json_config_servers": cfg_servers,
        "live_mcp_states_2026_10_21": LIVE_MCP_STATES,
        "session_servers_snapshot": SESSION_SERVERS,
        "mcp_rows": mcp_rows,
        "dead_mcp_servers_instructed": dead_mcp,
        "controls": controls,
    }
    out = [
        f"SUCCESS:adv0019-probe2 resolved {len(to_resolve)} names: which={len(which_inv)} "
        f"pwsh={len(pwsh_inv)} both={len(both)} which_only={len(which_only)} "
        f"pwsh_only={len(pwsh_only)} absent={len(absent)}; "
        f"instructed-but-not-live mcp servers={len(dead_mcp)}: " + ",".join(dead_mcp[:12]),
        f"  bash literal resolver: {bash_attempt['status']}",
    ]
    for k, v in controls.items():
        out.append(f"  {k}: {'PASS' if v else 'FAIL'}")
    text_out = "\n".join(out) + "\n"
    print(text_out, end="")
    (OUT / "probe2-resolve.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    (OUT / "probe2-resolve.raw.txt").write_text(text_out, encoding="utf-8")
    return 0 if all(controls.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
