#!/usr/bin/env python3
"""Ten enumerated credential-diagnosis surfaces for ADV-0037."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import probe_common as C  # noqa: E402

IMP0458 = REPO / "command-center/p2-wave/probes/IMP-0458"
WFA_CODEX = "command-center/p2-wave/probes/WFA-0052/fixtures/estate/codex-runner.yml"
DISPATCH = "command-center/p2-wave/seed-stage/dispatch_cursor.py"
FLEET = "command-center/p2-wave/seed-stage/bringup_cursor_fleet.py"
GH_ENGINE = "command-center/p2-wave/probes/WFA-0016/engine.py"

TARGET_IDS = (
    "ci_redaction",
    "ci_dispatcher",
    "ci_ledger",
    "plugin_logs",
    "build_mirror",
    "cursor_dispatch_presence",
    "cursor_fleet_prefix",
    "gh_bearer_header",
    "secret_scrub_report",
    "stdout_presence",
)

SOURCE_GROUND = {
    "ci_redaction": WFA_CODEX,
    "ci_dispatcher": WFA_CODEX,
    "ci_ledger": WFA_CODEX,
    "plugin_logs": "tools/plugin/healthcheck.py",
    "build_mirror": "tools/marketplace/blob_store.py",
    "cursor_dispatch_presence": DISPATCH,
    "cursor_fleet_prefix": FLEET,
    "gh_bearer_header": GH_ENGINE,
    "secret_scrub_report": "command-center/p2-wave/probes/IMP-0458/secret_scrub_gate.py",
    "stdout_presence": DISPATCH,
}


def _clone_url(token: str) -> str:
    return f"https://x-access-token:{token}@github.com/example/target.git"


def run_ci_redaction(root: Path, token: str, mode: str) -> dict[str, str]:
    stdout: list[str] = []
    stderr: list[str] = []
    auth = root / "codex-home" / "auth.json"
    log = root / "logs" / "ci-redaction.log"
    if mode == "unset":
        C.write_text(log, "redact: CODEX_AUTH_JSON missing; skipping persist\n")
        stdout.append("auth_json=absent")
        return {"stdout": "\n".join(stdout), "stderr": "\n".join(stderr)}
    payload = token if mode != "malformed" else token[:12] + "!!malformed"
    C.write_text(auth, json.dumps({"token": payload}) + "\n")
    C.write_text(auth.parent / "config.toml", 'cli_auth_credentials_store = "file"\n')
    raw_log = f"reconstructed auth.json bytes={len(payload)}\n"
    redacted = raw_log.replace("${CODEX_AUTH_JSON}", "***")
    C.write_text(log, redacted)
    stdout.append("auth_json=written redactor=shell-form-only")
    if mode == "error":
        stderr.append("auth reconstruct failed after persist")
    return {"stdout": "\n".join(stdout), "stderr": "\n".join(stderr)}


def run_ci_dispatcher(root: Path, token: str, mode: str) -> dict[str, str]:
    stdout: list[str] = []
    stderr: list[str] = []
    log = root / "logs" / "ci-dispatcher.log"
    if mode == "unset":
        C.write_text(log, "+ git clone https://x-access-token:@github.com/example/target.git\n")
        stdout.append("clone_url=empty-token skipped")
        return {"stdout": "\n".join(stdout), "stderr": "\n".join(stderr)}
    value = token if mode != "malformed" else token + ".expired"
    line = f'+ git clone "{_clone_url(value)}" work\n'
    C.write_text(log, line)
    stdout.append("clone_logged=true network=false")
    if mode == "error":
        stderr.append(f"clone failed: {_clone_url(value)}")
    return {"stdout": "\n".join(stdout), "stderr": "\n".join(stderr)}


def run_ci_ledger(root: Path, token: str, mode: str) -> dict[str, str]:
    ledger = root / "ledger" / "ci-events.jsonl"
    if mode == "unset":
        C.write_text(ledger, json.dumps({"event": "dispatch", "auth": "absent"}) + "\n")
        return {"stdout": "ledger=absent", "stderr": ""}
    value = token if mode != "malformed" else token + ".expired"
    event = {
        "event": "dispatch",
        "auth": "present",
        "command": f'git clone "{_clone_url(value)}" work',
    }
    C.write_text(ledger, json.dumps(event) + "\n")
    stderr = ""
    if mode == "error":
        stderr = json.dumps({"error": "dispatch", "command": event["command"]})
    return {"stdout": "ledger=appended", "stderr": stderr}


def run_plugin_logs(root: Path, token: str, mode: str) -> dict[str, str]:
    log = root / "plugin" / "plugin.log"
    if mode == "unset":
        C.write_text(log, "plugin config token=absent\n")
        return {"stdout": "plugin_log=absence", "stderr": ""}
    value = token if mode != "malformed" else token + ".expired"
    C.write_text(log, f"plugin config token={value}\n")
    rotated = log.with_name("plugin.log.1")
    shutil.copy2(log, rotated)
    log.write_text("plugin config token=<rotated>\n", encoding="utf-8")
    stderr = ""
    if mode == "error":
        C.write_text(root / "plugin" / "crash.dump", f"ConfigError: token={value}\n")
        stderr = "plugin exception formatter wrote crash.dump"
    return {"stdout": "plugin_log=rotated", "stderr": stderr}


def run_build_mirror(root: Path, token: str, mode: str) -> dict[str, str]:
    src = root / "stage"
    dest = root / "mirror-apply"
    src.mkdir(parents=True, exist_ok=True)
    env_file = src / ".env"
    if mode == "unset":
        C.write_text(env_file, "GITHUB_TOKEN=\n")
        shutil.copytree(src, dest, dirs_exist_ok=True)
        return {"stdout": "mirror=empty-token", "stderr": ""}
    value = token if mode != "malformed" else token + ".expired"
    C.write_text(env_file, f"GITHUB_TOKEN={value}\n")
    C.write_text(src / "payload.txt", "mirror payload without secrets\n")
    shutil.copytree(src, dest, dirs_exist_ok=True)
    stderr = ""
    if mode == "error":
        C.write_text(root / "cache" / "mirror-error.txt", f"apply failed env={value}\n")
        stderr = "mirror apply error recorded"
    return {"stdout": "mirror=applied", "stderr": stderr}


def run_cursor_dispatch_presence(root: Path, token: str, mode: str) -> dict[str, str]:
    auth_fail = root / "logs" / "AUTH_FAIL.txt"
    if mode == "unset" or not token:
        msg = "FAILED:no CURSOR_API_KEY in env"
        C.write_text(auth_fail, msg + "\n")
        return {"stdout": msg, "stderr": ""}
    C.write_text(auth_fail, "CURSOR_API_KEY present (value not written)\n")
    return {"stdout": "CURSOR_API_KEY present", "stderr": ""}


def run_cursor_fleet_prefix(root: Path, token: str, mode: str) -> dict[str, str]:
    log = root / "logs" / "fleet.txt"
    if mode == "unset" or not token:
        C.write_text(log, "FAILED:no CURSOR_API_TOKEN\n")
        return {"stdout": "FAILED:no CURSOR_API_TOKEN", "stderr": ""}
    value = token if mode != "malformed" else token[:8]
    line = f"token_len={len(value)} prefix={value[:4]} (not printing rest)"
    C.write_text(log, line + "\n")
    return {"stdout": line, "stderr": ""}


def run_gh_bearer_header(root: Path, token: str, mode: str) -> dict[str, str]:
    log = root / "logs" / "gh-headers.txt"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "wfa-0016-sweep",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if mode != "unset" and token:
        headers["Authorization"] = f"Bearer {token}"
    C.write_text(
        log,
        f"authorization_present={'Authorization' in headers} keys={sorted(headers)}\n",
    )
    stderr = ""
    if mode == "error":
        stderr = "http-401 (Authorization not dumped)"
    return {"stdout": "headers_constructed network=false", "stderr": stderr}


def run_secret_scrub_report(root: Path, token: str, mode: str) -> dict[str, str]:
    # shard1 wave-2 repair 2026-10-25: the IMP-0458 probe module is absent on
    # this worktree. IMP-form dependency tokens are NEVER guessed (program
    # contract), so instead of fabricating secret_scrub_gate the surface is
    # recorded instrument-absent: the sweep runs over the remaining nine
    # surfaces and this one is reported as not exercised, with the absence
    # persisted to logs/scrub.json so both probes and the artifact can see it.
    if not (IMP0458 / "secret_scrub_gate.py").is_file():
        marker = root / "logs" / "scrub.json"
        C.write_text(
            marker,
            json.dumps(
                {
                    "surface": "secret_scrub_report",
                    "instrument": "command-center/p2-wave/probes/IMP-0458/secret_scrub_gate.py",
                    "instrument_present": False,
                    "note": "IMP-form unknown-token not guessed; surface not exercised live this run",
                }
            )
            + chr(10),
        )
        return {
            "stdout": "instrument=absent IMP-0458-module-missing surface-not-exercised",
            "stderr": "",
            "instrument_absent": "true",
        }
    sys.path.insert(0, str(IMP0458))
    import secret_scrub_gate as G  # type: ignore  # noqa: E402

    canary = G.synthetic_canary_value(b"ADV-0037")
    receipt = root / "receipts" / "canary.json"
    if mode == "unset":
        C.write_text(receipt, json.dumps({"id": "empty"}) + "\n")
        findings = G.scan_bytes(receipt.read_bytes(), "receipt")
        report = {"finding_count": len(findings), "prefixes": [f.prefix for f in findings]}
        C.write_text(root / "logs" / "scrub.json", json.dumps(report) + "\n")
        leaked = canary in json.dumps(report)
        return {
            "stdout": f"scrub_findings={len(findings)} canary_in_report={leaked}",
            "stderr": "",
        }
    C.write_text(receipt, json.dumps({"id": "canary-receipt", "GITHUB_TOKEN": canary}) + "\n")
    findings = G.scan_bytes(receipt.read_bytes(), "receipt")
    slim = {
        "prefixes": [f.prefix for f in findings],
        "evidence": [f.evidence for f in findings],
    }
    report = {
        "finding_count": len(findings),
        "prefixes": slim["prefixes"],
        "evidence": slim["evidence"],
        "planted_diagnosis_token_in_report": C.PLANTED in json.dumps(slim),
        "canary_body_in_report": canary in json.dumps(slim),
    }
    C.write_text(root / "logs" / "scrub.json", json.dumps(report) + "\n")
    return {
        "stdout": (
            f"scrub_findings={report['finding_count']} "
            f"canary_body_in_report={report['canary_body_in_report']} "
            f"prefixes={report['prefixes']}"
        ),
        "stderr": "",
    }


def run_stdout_presence(root: Path, token: str, mode: str) -> dict[str, str]:
    log = root / "logs" / "presence.txt"
    line = "GITHUB_TOKEN=unset" if (mode == "unset" or not token) else "GITHUB_TOKEN=set"
    C.write_text(log, line + "\n")
    return {"stdout": line, "stderr": ""}


RUNNERS: dict[str, Callable[[Path, str, str], dict[str, str]]] = {
    "ci_redaction": run_ci_redaction,
    "ci_dispatcher": run_ci_dispatcher,
    "ci_ledger": run_ci_ledger,
    "plugin_logs": run_plugin_logs,
    "build_mirror": run_build_mirror,
    "cursor_dispatch_presence": run_cursor_dispatch_presence,
    "cursor_fleet_prefix": run_cursor_fleet_prefix,
    "gh_bearer_header": run_gh_bearer_header,
    "secret_scrub_report": run_secret_scrub_report,
    "stdout_presence": run_stdout_presence,
}


def run_one(tid: str, root: Path, token: str, mode: str) -> dict[str, Any]:
    streams = RUNNERS[tid](root / tid, token, mode)
    channels = C.capture_channels(root / tid, streams["stdout"], streams["stderr"])
    return {
        "id": tid,
        "mode": mode,
        "source": SOURCE_GROUND[tid],
        "source_exists": (REPO / SOURCE_GROUND[tid]).is_file(),
        "stdout_hit": channels["stdout"],
        "stderr_hit": channels["stderr"],
        "file_hits": channels["files"],
        "hit": channels["hit"],
        "stdout_sanitized": C.sanitize(streams["stdout"]),
        "stderr_sanitized": C.sanitize(streams["stderr"]),
        "instrument_absent": streams.get("instrument_absent", ""),
    }


def run_campaign(kind: str) -> dict[str, Any]:
    def inner(root: Path) -> dict[str, Any]:
        detector = C.run_detector_control(root / "detector")
        rows: list[dict[str, Any]] = []
        if kind == "happy":
            for tid in TARGET_IDS:
                rows.append(run_one(tid, root / "happy", C.PLANTED, "happy"))
        else:
            for tid in TARGET_IDS:
                sub = [
                    run_one(tid, root / "error" / mode, C.PLANTED, mode)
                    for mode in ("unset", "malformed", "error")
                ]
                rows.append(
                    {
                        "id": tid,
                        "mode": "error-bundle",
                        "source": SOURCE_GROUND[tid],
                        "source_exists": (REPO / SOURCE_GROUND[tid]).is_file(),
                        "hit": any(s["hit"] for s in sub),
                        "subcases": sub,
                    }
                )
        return {
            "kind": kind,
            "unit_id": C.UNIT,
            "planted": C.planted_meta(),
            "detector": detector,
            "targets": rows,
            "parent_credential_key_names_present": C.parent_secret_keys_unread(),
            "parent_credential_values_read": False,
            "hard_constraint": {
                "synthetic_only": True,
                "real_credential_read": False,
                "real_credential_printed": False,
                "real_credential_rotated": False,
                "real_credential_revoked": False,
                "real_credential_unset": False,
                "real_credential_modified": False,
            },
        }

    return C.with_isolation(inner)
