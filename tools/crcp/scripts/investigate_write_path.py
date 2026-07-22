"""Investigate ChatGPT write-path scopes and Desktop surface (owner auth only)."""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from crcp.auth import decode_jwt_claims


def main() -> dict:
    auth = json.loads(
        (Path.home() / ".codex" / "auth.json").read_text(encoding="utf-8")
    )
    access = auth["tokens"]["access_token"]
    claims = decode_jwt_claims(access) or {}
    oa = claims.get("https://api.openai.com/auth") or {}
    account_id = oa.get("chatgpt_account_id") or auth["tokens"].get("account_id") or ""
    scp = claims.get("scp") or []

    report = {
        "at": datetime.now(timezone.utc).isoformat(),
        "access_scp": scp,
        "oauth_scopes_requested_by_codex_login": (
            "openid profile email offline_access "
            "api.connectors.read api.connectors.invoke"
        ),
        "source": "codex-rs/login/src/server.rs scope param",
        "probes": [],
        "conclusions": [],
    }

    headers = {
        "Authorization": f"Bearer {access}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "ChatGPT-Account-Id": account_id,
        "User-Agent": "CRCP-write-probe/0.1",
    }

    # Probe write-ish endpoints (expect 4xx; record status only)
    bodies = {
        "POST /backend-api/conversation": b'{"action":"next","messages":[]}',
        "POST /backend-api/conversation/init": b"{}",
        "POST /backend-api/f/conversation": b'{"action":"next"}',
    }
    for label, body in bodies.items():
        method, path = label.split(" ", 1)
        url = "https://chatgpt.com" + path
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        entry = {"probe": label}
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                entry["status"] = resp.status
                entry["body_prefix"] = resp.read(200).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            entry["status"] = e.code
            entry["body_prefix"] = e.read(240).decode("utf-8", "replace")
        except Exception as e:
            entry["status"] = None
            entry["error"] = f"{type(e).__name__}: {e}"
        report["probes"].append(entry)

    # Connectors invoke (scope present)
    req = urllib.request.Request(
        "https://chatgpt.com/backend-api/aip/connectors",
        headers=headers,
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            report["probes"].append(
                {
                    "probe": "GET /backend-api/aip/connectors",
                    "status": resp.status,
                    "body_prefix": resp.read(200).decode("utf-8", "replace"),
                }
            )
    except urllib.error.HTTPError as e:
        report["probes"].append(
            {
                "probe": "GET /backend-api/aip/connectors",
                "status": e.code,
                "body_prefix": e.read(200).decode("utf-8", "replace"),
            }
        )
    except Exception as e:
        report["probes"].append(
            {"probe": "GET /backend-api/aip/connectors", "error": type(e).__name__}
        )

    # Desktop process surface
    try:
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.Name -match 'ChatGPT' } | "
                    "Select-Object -First 15 ProcessId,Name,"
                    "@{n='Cmd';e={if($_.CommandLine){$_.CommandLine.Substring(0,[Math]::Min(120,$_.CommandLine.Length))}}} | "
                    "ConvertTo-Json -Compress"
                ),
            ],
            text=True,
            timeout=30,
        )
        report["chatgpt_processes"] = json.loads(out) if out.strip() else []
    except Exception as e:
        report["chatgpt_processes_error"] = type(e).__name__

    report["conclusions"] = [
        "Codex OAuth explicitly requests only: openid profile email offline_access "
        "api.connectors.read api.connectors.invoke (server.rs).",
        "No conversation write scope appears in the Codex login scope string.",
        "Read path backend-api works with these tokens; write probes document HTTP status below.",
        "api.connectors.invoke is for connector plugins, not proven as ChatGPT chat send.",
        "ChatGPT Desktop is MSIX/Electron; no Listen ports found earlier — not a command API.",
        "Practical write path for CRCP: Claude/Codex/Grok on local rails; ChatGPT remains "
        "read/research ingest unless a future OAuth scope is granted by OpenAI.",
    ]
    return report


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    rep = main()
    out = (
        Path(__file__).resolve().parents[1]
        / "reports"
        / "write_path_investigation.json"
    )
    out.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                k: rep[k]
                for k in (
                    "access_scp",
                    "oauth_scopes_requested_by_codex_login",
                    "probes",
                    "conclusions",
                )
            },
            indent=2,
        )
    )
    print("WROTE", out)
