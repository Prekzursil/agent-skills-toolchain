"""Closed inventory of user-facing install-gate error paths (TST-0113).

Scope (honest, closed): every `reason=` refuse branch in
`tools/plugin/client_negotiate.negotiate`, triggered live through the library
AND through `tools/plugin/install_gate.py` so the scored text is the
user-facing capture, not a string copied from source.

Not in scope (named residual): argparse usage lines, rollback/sbom/eol CLIs,
Windows PowerShell re-run of these probes.
"""
from __future__ import annotations

import ast
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
GATE = REPO / "tools" / "plugin" / "install_gate.py"
NEGOTIATE_SRC = REPO / "tools" / "plugin" / "client_negotiate.py"
UNPARSABLE_MIN = HERE / "fixtures" / "unparsable-min-manifest.json"
BARE = HERE / "fixtures" / "bare-messages.json"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.client_negotiate import load_manifest, negotiate  # noqa: E402

UNIT = "TST-0113"


def refuse_reasons_from_source() -> set[str]:
    tree = ast.parse(NEGOTIATE_SRC.read_text(encoding="utf-8"))
    reasons: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "negotiate":
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Call):
                    continue
                for kw in sub.keywords:
                    if kw.arg != "reason":
                        continue
                    val = kw.value
                    if isinstance(val, ast.Constant) and isinstance(val.value, str):
                        if val.value != "ok":
                            reasons.add(val.value)
    return reasons


def _specs(live: dict[str, Any]) -> list[dict[str, Any]]:
    floor = live.get("min_client_version") or live.get("min_client_version")
    clients = live.get("supported_clients") or live.get("supported_clients") or []
    if not floor or not clients:
        raise RuntimeError(f"live manifest missing compatibility fields: {sorted(live)}")
    ok_client = clients[0]
    return [
        {
            "id": "manifest-min-unparsable",
            "reason": "manifest-min-unparsable",
            "client": ok_client,
            "version": "1.0.0",
            "manifest": json.loads(UNPARSABLE_MIN.read_text(encoding="utf-8")),
            "manifest_path": UNPARSABLE_MIN,
        },
        {
            "id": "client-id-missing",
            "reason": "client-id-missing",
            "client": "   ",
            "version": floor,
            "manifest": live,
            "manifest_path": None,
        },
        {
            "id": "unsupported-client",
            "reason": "unsupported-client",
            "client": "windsurf",
            "version": "9.9.9",
            "manifest": live,
            "manifest_path": None,
        },
        {
            "id": "unparsable-version",
            "reason": "unparsable-version",
            "client": ok_client,
            "version": "not-a-version",
            "manifest": live,
            "manifest_path": None,
        },
        {
            "id": "below-floor",
            "reason": "below-floor",
            "client": ok_client,
            "version": "0.0.1",
            "manifest": live,
            "manifest_path": None,
        },
    ]


def _run_gate(manifest_path: Path, client: str, version: str, dest: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(TOOLS) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    p = subprocess.run(
        [
            sys.executable,
            "-B",
            str(GATE),
            "--manifest",
            str(manifest_path),
            "--client",
            client,
            "--version",
            version,
            "--dest",
            str(dest),
            "--write-on-allow",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    stdout = p.stdout or ""
    stderr = (p.stderr or "").strip()
    doc: dict[str, Any] = {}
    try:
        doc = json.loads(stdout)
    except json.JSONDecodeError:
        doc = {"parse_error": True, "stdout": stdout[-2000:]}
    neg = doc.get("negotiation") or doc.get("negotiation") or {}
    return {
        "exit_code": p.returncode,
        "stderr": stderr,
        "stdout_message": str(neg.get("message") or ""),
        "stdout_reason": str(neg.get("reason") or ""),
        "installed": bool(doc.get("installed")),
        "dest_has_payload": bool(doc.get("dest_has_payload") or doc.get("dest_has_payload")),
        "dest_exists": dest.exists(),
    }


def trigger_path(spec: dict[str, Any], live_manifest_path: Path) -> dict[str, Any]:
    lib = negotiate(spec["manifest"], spec["client"], spec["version"])
    with tempfile.TemporaryDirectory(prefix="tst0113-") as tmp:
        dest = Path(tmp) / "dest"
        man_path = spec["manifest_path"] or live_manifest_path
        cli = _run_gate(man_path, spec["client"], spec["version"], dest)
        dest_existed = dest.exists()
    captured = (cli["stderr"] or lib.message or "").strip()
    library_text = (lib.message or "").strip()
    return {
        "id": spec["id"],
        "expected_reason": spec["reason"],
        "library_reason": lib.reason,
        "library_allowed": lib.allowed,
        "library_text": library_text,
        "cli_exit_code": cli["exit_code"],
        "cli_stderr": cli["stderr"],
        "cli_stdout_message": cli["stdout_message"],
        "cli_reason": cli["stdout_reason"],
        "cli_installed": cli["installed"],
        "cli_dest_has_payload": cli["dest_has_payload"],
        "cli_dest_existed": dest_existed,
        "captured_text": captured,
        "library_matches_stderr": library_text == cli["stderr"],
        "library_matches_stderr": library_text == cli["stderr"],
        "stderr_matches_stdout_message": cli["stderr"] == cli["stdout_message"],
        "stderr_matches_stdout_message": cli["stderr"] == cli["stdout_message"],
        "triggered": (not lib.allowed) and lib.reason == spec["reason"] and bool(captured),
    }


def capture_all() -> dict[str, Any]:
    from plugin.client_negotiate import DEFAULT_MANIFEST

    live = load_manifest()
    specs = _specs(live)
    rows = [trigger_path(s, DEFAULT_MANIFEST) for s in specs]
    source_reasons = sorted(refuse_reasons_from_source())
    triggered_reasons = sorted({r["library_reason"] for r in rows if r["triggered"]})
    return {
        "unit_id": UNIT,
        "source_refuse_reasons": source_reasons,
        "triggered_reasons": triggered_reasons,
        "inventory_complete": source_reasons == triggered_reasons
        and source_reasons == sorted(s["reason"] for s in specs),
        "inventory_complete": source_reasons == triggered_reasons
        and source_reasons == sorted(s["reason"] for s in specs),
        "source_refuse_reasons": source_reasons,
        "rows": rows,
        "bare_messages": json.loads(BARE.read_text(encoding="utf-8"))["messages"],
        "bare_messages": json.loads(BARE.read_text(encoding="utf-8"))["messages"],
        "gate": str(GATE.relative_to(REPO).as_posix()),
        "negotiate_src": str(NEGOTIATE_SRC.relative_to(REPO).as_posix()),
    }


capture_all = capture_all
capture_all = capture_all
