#!/usr/bin/env python3
"""ADV-0037 real-module credential-path drivers (upgrade of the G-1 simulations).

Each TARGET drives the LIVE module/script this repo ships -- no reconstructed
log lines. Fixture INPUTS the probe plants live under ``<sandbox>/input`` and
are excluded from the sweep; only channels the code path EMITTED (captured
stdout/stderr and files under ``<sandbox>/out``) count as leak channels.

Modes: ``happy`` (planted present), ``unset``, ``malformed``, ``expired``.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
import types
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import probe_common as C  # noqa: E402

TARGET_IDS = (
    "T1_ci_redaction",
    "T2_ci_secret_guard",
    "T3_ci_ledger",
    "T4_ci_dispatcher",
    "T5_plugin_payload",
    "T6_plugin_logs",
    "T7_mkt_publish",
    "T8_routing_fixture",
    "T9_build_mirror",
    "T10_crash_dump",
    "T11_mkt_cli_key",
    "T12_plugin_proc_env",
    "T13_cs_backup_copy",
    "T14_gh_client_static",
)

SOURCE_GROUND = {
    "T1_ci_redaction": "ci/harness/redaction.py::contains_secret,redact_text",
    "T2_ci_secret_guard": "ci/harness/modules.py::SecretGuardModule.run",
    "T3_ci_ledger": "ci/harness/ledger.py::EventLedger.append,set_goal",
    "T4_ci_dispatcher": "ci/harness/dispatcher.py::HarnessDispatcher.dispatch,_record_terminal",
    "T5_plugin_payload": "platform/plugin/payload.py::scan_secrets,collect",
    "T6_plugin_logs": "platform/plugin/logs.py::redact_text,redact,Logger.log",
    "T7_mkt_publish": "platform/marketplace/mkt/publish.py::scan_text,scan_payload",
    "T8_routing_fixture": "platform/routing/fixtures/build_fixture.py::Scrubber,emit_mcp",
    "T9_build_mirror": "scripts/build-codespace-mirror.py MCP/config ingestion and redaction",
    "T10_crash_dump": "CPython default traceback via repository probe subprocess",
    "T11_mkt_cli_key": "platform/marketplace/mkt/cli.py::_load_secret",
    "T12_plugin_proc_env": "platform/plugin/proc.py::run",
    "T13_cs_backup_copy": "scripts/claude-science/cs-backup.sh encryption.key and .oauth-tokens copy",
    "T14_gh_client_static": "scripts/gh-api-single-file-pr.sh and scripts/agentic-perfection/world-watch.ps1",
}

_LOADER_CACHE: dict[str, Any] = {}


def _load(fq: str, rel: str):
    """Import a live repo module under an alias package (repo ``platform/``
    shadows the stdlib ``platform`` module, so a plain import is impossible)."""
    if fq in _LOADER_CACHE:
        return _LOADER_CACHE[fq]

    def ns(name: str, relp: str) -> None:
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.__path__ = [str(REPO / relp)]
            sys.modules[name] = mod

    ns("astj", "platform")
    ns("astj.plugin", "platform/plugin")
    ns("astj.marketplace", "platform/marketplace")
    ns("astj.mkt", "platform/marketplace/mkt")
    ns("astj.routing", "platform/routing")
    ns("astj.routing.fixtures", "platform/routing/fixtures")
    ns("cih", "ci/harness")
    spec = importlib.util.spec_from_file_location(fq, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[fq] = mod
    spec.loader.exec_module(mod)
    _LOADER_CACHE[fq] = mod
    return mod


def _shape(value: str | None, mode: str) -> str | None:
    if mode == "unset":
        return None
    if value is None:
        return None
    if mode == "malformed":
        return value[:12] + "!!malformed"
    if mode == "expired":
        return value + "::expired-2030-01-01"
    return value


def _scrub_env() -> dict[str, str]:
    keep = {}
    for k in ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "PATHEXT", "TEMP", "TMP", "LANG", "PYTHONDONTWRITEBYTECODE"):
        if os.environ.get(k):
            keep[k] = os.environ[k]
    return keep


def _find_bash() -> str:
    for cand in ("C:/Program Files/Git/bin/bash.exe", "C:/Program Files/Git/usr/bin/bash.exe"):
        if Path(cand).is_file():
            return cand
    return "bash"


# --------------------------------------------------------------------------- #
# drivers: (indir, outdir, value, mode) -> {"stdout":..., "stderr":...}
# --------------------------------------------------------------------------- #


def t1_ci_redaction(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    r = _load("cih.redaction", "ci/harness/redaction.py")
    v = _shape(value, mode)
    if v is None:
        print("presence: contains_secret(None)=False (credential absent)")
        return {"stdout": "absent", "stderr": ""}
    hit = r.contains_secret(v)
    red = r.redact_text(f"token={v}")
    print(f"contains_secret={hit} redacted={red}")
    (outdir / "out.json").write_text(json.dumps({"contains": hit, "redacted": red}), encoding="utf-8")
    return {"stdout": f"contains_secret={hit}", "stderr": ""}


def t2_ci_secret_guard(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    models = _load("cih.models", "ci/harness/models.py")
    modules = _load("cih.modules", "ci/harness/modules.py")
    v = _shape(value, mode)
    text = "" if v is None else f"run deploy with key {v}"
    ev = models.HookEvent(
        schema_version=1,
        provider="claude",
        event="PreToolUse",
        session_id="s",
        turn_id="t",
        cwd=str(outdir),
        permission_mode="default",
        tool=models.ToolEnvelope(name="Bash", input=text),
    )
    guard = modules.SecretGuardModule()
    res = guard.run(ev)
    payload = {
        "blocked": bool(getattr(res, "blocked", False)),
        "reason": str(getattr(res, "reason", "")),
        "stdout": str(getattr(res, "stdout", "")),
    }
    (outdir / "guard.json").write_text(json.dumps(payload), encoding="utf-8")
    print(f"guard blocked={payload['blocked']} reason={payload['reason'][:120]}")
    return {"stdout": f"blocked={payload['blocked']}", "stderr": ""}


def t3_ci_ledger(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    ledger = _load("cih.ledger", "ci/harness/ledger.py")
    v = _shape(value, mode)
    led = ledger.EventLedger(outdir / "ledger-state")
    note = "credential absent" if v is None else f"dispatch note {v}"
    led.append(str(outdir), "probe", note=note)
    led.set_goal(str(outdir), text=f"goal: {note}")
    print("ledger append+set_goal done")
    return {"stdout": "ledger append+set_goal done", "stderr": ""}


def t4_ci_dispatcher(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    disp = _load("cih.dispatcher", "ci/harness/dispatcher.py")
    v = _shape(value, mode)
    d = disp.HarnessDispatcher(state_root=outdir / "disp-state")
    raw = {"prompt": "" if v is None else f"prompt containing {v}"}
    terr = None
    if v is None:
        terr = "connection reset"
    elif mode == "expired":
        terr = f"401 token expired context={v}"
    res = d.dispatch(raw, provider="claude", event_name="UserPromptSubmit", transport_error=terr)
    (outdir / "disp-result.json").write_text(
        json.dumps({"blocked": getattr(res, "blocked", None), "reason": str(getattr(res, "reason", ""))}),
        encoding="utf-8",
    )
    print(f"dispatch done blocked={getattr(res, 'blocked', None)}")
    return {"stdout": "dispatch done", "stderr": ""}


def t5_plugin_payload(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    payload = _load("astj.plugin.payload", "platform/plugin/payload.py")
    v = _shape(value, mode)
    f = indir / "config.env"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("URL=https://example.invalid\n" + ("" if v is None else f"API_KEY={v}\n"), encoding="utf-8")
    findings = payload.scan_secrets(f, "config.env")
    rows = [x.as_dict() for x in findings]
    (outdir / "findings.json").write_text(json.dumps(rows), encoding="utf-8")
    print(f"scan_secrets findings={len(rows)}")
    return {"stdout": f"findings={len(rows)}", "stderr": ""}


def t6_plugin_logs(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    logs = _load("astj.plugin.logs", "platform/plugin/logs.py")
    v = _shape(value, mode)
    log = logs.Logger(outdir / "plugin" / "plugin.log")
    log.log("info", "probe", "credential_diag", token="" if v is None else v)
    red = logs.redact({"token": v})
    print(f"redact -> {red!r}")
    try:
        log.log("bogus-level", "probe", "invalid_level", token="" if v is None else v)
    except ValueError as exc:
        (outdir / "plugin" / "exception.txt").write_text(f"ValueError: {exc}\n", encoding="utf-8")
        print(f"invalid-level exception: {exc}")
    return {"stdout": "log written; redact called; invalid-level raised", "stderr": ""}


def t7_mkt_publish(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    pub = _load("astj.mkt.publish", "platform/marketplace/mkt/publish.py")
    v = _shape(value, mode)
    text = "plain line\n" + ("" if v is None else f"GITHUB_TOKEN={v}\n")
    findings = pub.scan_text(text, "probe.env")
    rows = [
        {"rule": x.rule, "path": x.path, "line": x.line, "detail": x.detail} for x in findings
    ]
    pr = indir / "pkg"
    pr.mkdir(parents=True, exist_ok=True)
    (pr / "secrets.env").write_text(text, encoding="utf-8")
    findings2 = pub.scan_payload(pr, ["secrets.env"])
    rows2 = [
        {"rule": x.rule, "path": x.path, "line": x.line, "detail": x.detail} for x in findings2
    ]
    (outdir / "publish-findings.json").write_text(
        json.dumps({"scan_text": rows, "scan_payload": rows2}), encoding="utf-8"
    )
    print(f"scan_text={len(rows)} scan_payload={len(rows2)}")
    return {"stdout": f"scan_text={len(rows)} scan_payload={len(rows2)}", "stderr": ""}


def t8_routing_fixture(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    bf = _load("astj.routing.fixtures.build_fixture", "platform/routing/fixtures/build_fixture.py")
    v = _shape(value, mode)
    src = indir / "mcp-in.json"
    src.parent.mkdir(parents=True, exist_ok=True)
    env = {} if v is None else {"API_TOKEN": v}
    src.write_text(
        json.dumps({"mcpServers": {"probe": {"command": "probe-bin", "env": env}}}), encoding="utf-8"
    )
    scrub = bf.Scrubber(username="probe-user")
    n = bf.emit_mcp(src, outdir / "mcp-out.json", scrub)
    print(f"emit_mcp servers={n}")
    return {"stdout": f"emit_mcp={n}", "stderr": ""}


def t9_build_mirror(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    v = _shape(value, mode)
    home = indir / "fakehome"
    home.mkdir(parents=True, exist_ok=True)
    env = {} if v is None else {"MCP_SECRET_TOKEN": v}
    (home / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"probe": {"command": "x", "env": env}}}), encoding="utf-8"
    )
    (home / ".claude.json").write_text("{}", encoding="utf-8")
    mirror_repo = outdir / "mirror-repo"
    mirror_repo.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(REPO / "scripts/build-codespace-mirror.py"), "--repo", str(mirror_repo)]
    cp = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env={**_scrub_env(), "HOME": str(home), "USERPROFILE": str(home)},
        cwd=str(outdir),
        timeout=300,
    )
    (outdir / "mirror-stdout.txt").write_text(cp.stdout, encoding="utf-8")
    (outdir / "mirror-stderr.txt").write_text(cp.stderr, encoding="utf-8")
    print(f"mirror rc={cp.returncode} (stdout/stderr captured under out/)")
    return {"stdout": f"rc={cp.returncode}", "stderr": cp.stderr[:2000]}


def t10_crash_dump(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    v = _shape(value, mode)
    if v is None:
        return {"stdout": "absent (nothing to plant)", "stderr": ""}
    code = (
        "v = %r\n"
        "def boom():\n"
        "    cred = v\n"
        "    raise RuntimeError('probe failure')\n"
        "boom()\n" % v
    )
    cp = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=_scrub_env(), cwd=str(outdir)
    )
    (outdir / "crash-stderr.txt").write_text(cp.stderr, encoding="utf-8")
    print(f"crash probe rc={cp.returncode} stderr_len={len(cp.stderr)}")
    return {"stdout": f"rc={cp.returncode}", "stderr": cp.stderr}


def t11_mkt_cli_key(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    cli = _load("astj.mkt.cli", "platform/marketplace/mkt/cli.py")
    import argparse

    v = _shape(value, mode)
    if v is None:
        args = argparse.Namespace(fixture_key=None, key_file=None)
        try:
            cli._load_secret(args)
        except SystemExit as exc:
            print(f"no-key SystemExit: {exc}")
            (outdir / "exit.txt").write_text(f"{exc}\n", encoding="utf-8")
        return {"stdout": "unset branch", "stderr": ""}
    kf = indir / "signing.key"
    kf.parent.mkdir(parents=True, exist_ok=True)
    kf.write_text("# mkt signing key\n" + v + "\n", encoding="utf-8")
    args = argparse.Namespace(fixture_key=None, key_file=str(kf))
    secret = cli._load_secret(args)
    (outdir / "loaded.sha").write_text(
        "loaded-secret-sha256:" + hashlib.sha256(secret.encode()).hexdigest() + "\n", encoding="utf-8"
    )
    print("key loaded (value not printed)")
    return {"stdout": "key loaded", "stderr": ""}


def t12_plugin_proc_env(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    _load("astj.plugin.proc", "platform/plugin/proc.py")
    v = _shape(value, mode)
    dump = indir / "envdump.py"
    dump.parent.mkdir(parents=True, exist_ok=True)
    dump.write_text(
        "import os, pathlib\n"
        "rows = {k: v for k, v in os.environ.items() if k.startswith('SYN37')}\n"
        "pathlib.Path('envdump.json').write_text(__import__('json').dumps(rows))\n",
        encoding="utf-8",
    )
    env = {**_scrub_env()}
    if v is not None:
        env["SYN37_PLANTED"] = v
    cp = subprocess.run(
        [sys.executable, str(dump)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(outdir),
    )
    print(f"child rc={cp.returncode} (env inheritance measured via child-written file)")
    return {"stdout": f"rc={cp.returncode}", "stderr": cp.stderr}


def t13_cs_backup_copy(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    v = _shape(value, mode)
    home = indir / "fakehome"
    csdir = home / ".claude-science"
    csdir.mkdir(parents=True, exist_ok=True)
    keyfile = csdir / "encryption.key"
    keyfile.write_text("" if v is None else v + "\n", encoding="utf-8")
    (csdir / ".oauth-tokens").write_text("oauth-body-without-credential\n", encoding="utf-8")
    dest = outdir / "backups"
    keydest = outdir / "key-backups"
    dest.mkdir(parents=True, exist_ok=True)
    keydest.mkdir(parents=True, exist_ok=True)
    script = REPO / "scripts/claude-science/cs-backup.sh"
    env = {
        **_scrub_env(),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "CS_BACKUP_ROOT": str(dest),
        "CS_BACKUP_KEY_ROOT": str(keydest),
        "CS_DATA_DIR": str(csdir),
    }
    cp = subprocess.run(
        [_find_bash(), str(script)],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(outdir),
        timeout=120,
    )
    (outdir / "cs-backup.stdout.txt").write_text(cp.stdout, encoding="utf-8")
    (outdir / "cs-backup.stderr.txt").write_text(cp.stderr, encoding="utf-8")
    print(f"cs-backup rc={cp.returncode} (stdout/stderr captured under out/)")
    return {"stdout": f"rc={cp.returncode}", "stderr": cp.stderr[:2000]}


def t14_gh_client_static(indir: Path, outdir: Path, value: str | None, mode: str) -> dict[str, str]:
    v = _shape(value, mode)
    subjects = [
        REPO / "scripts/gh-api-single-file-pr.sh",
        REPO / "scripts/agentic-perfection/world-watch.ps1",
    ]
    markers = []
    echo_pat = re.compile(
        r"(echo|printf|Write-Host|Write-Output|print)[^\n]{0,160}(TOKEN|SECRET|KEY|AUTH)", re.IGNORECASE
    )
    for s in subjects:
        text = s.read_text(encoding="utf-8", errors="replace")
        hits = echo_pat.findall(text)
        markers.append({"file": str(s.relative_to(REPO)), "echo_of_credential_named": len(hits)})
    (outdir / "static-markers.json").write_text(
        json.dumps({"subjects": markers, "planted": v is not None}), encoding="utf-8"
    )
    print(f"static marker scan: {markers}")
    return {"stdout": json.dumps(markers), "stderr": ""}


RUNNERS: dict[str, Callable[[Path, Path, str | None, str], dict[str, str]]] = {
    "T1_ci_redaction": t1_ci_redaction,
    "T2_ci_secret_guard": t2_ci_secret_guard,
    "T3_ci_ledger": t3_ci_ledger,
    "T4_ci_dispatcher": t4_ci_dispatcher,
    "T5_plugin_payload": t5_plugin_payload,
    "T6_plugin_logs": t6_plugin_logs,
    "T7_mkt_publish": t7_mkt_publish,
    "T8_routing_fixture": t8_routing_fixture,
    "T9_build_mirror": t9_build_mirror,
    "T10_crash_dump": t10_crash_dump,
    "T11_mkt_cli_key": t11_mkt_cli_key,
    "T12_plugin_proc_env": t12_plugin_proc_env,
    "T13_cs_backup_copy": t13_cs_backup_copy,
    "T14_gh_client_static": t14_gh_client_static,
}


def drive_target(tid: str, sandbox: Path, value: str | None, mode: str) -> dict[str, Any]:
    """Run one target; sweep ONLY emitted channels (stdout/stderr + out/ tree)."""
    indir = sandbox / "input"
    outdir = sandbox / "out"
    indir.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)
    out_io, err_io = io.StringIO(), io.StringIO()
    error: str | None = None
    streams: dict[str, str] = {"stdout": "", "stderr": ""}
    try:
        with redirect_stdout(out_io), redirect_stderr(err_io):
            streams = RUNNERS[tid](indir, outdir, value, mode) or {"stdout": "", "stderr": ""}
    except Exception:  # noqa: BLE001 - the exception text is a measured channel
        error = traceback.format_exc()
        streams = {"stdout": "", "stderr": ""}
    stdout = streams.get("stdout", "") + "\n" + out_io.getvalue()
    stderr = streams.get("stderr", "") + "\n" + err_io.getvalue() + ("\n" + error if error else "")
    (sandbox / "stdout.txt").write_text(stdout, encoding="utf-8")
    (sandbox / "stderr.txt").write_text(stderr, encoding="utf-8")
    files = C.sweep_tree(outdir)
    hit = C.sweep_text(stdout) or C.sweep_text(stderr) or bool(files)
    return {
        "id": tid,
        "mode": mode,
        "source": SOURCE_GROUND[tid],
        "source_exists": (REPO / SOURCE_GROUND[tid].split("::")[0]).exists(),
        "executed": error is None,
        "error": C.sanitize(error) if error else None,
        "stdout_hit": C.sweep_text(stdout),
        "stderr_hit": C.sweep_text(stderr),
        "file_hits": files,
        "hit": hit,
        "stdout_sanitized": C.sanitize(stdout)[:800],
        "stderr_sanitized": C.sanitize(stderr)[:800],
    }


def campaign(kind: str) -> dict[str, Any]:
    """kind: 'happy' | 'error'."""

    def inner(root: Path) -> dict[str, Any]:
        detector = C.run_detector_control(root / "detector")
        rows: list[dict[str, Any]] = []
        if kind == "happy":
            for tid in TARGET_IDS:
                rows.append(drive_target(tid, root / "happy" / tid, C.PLANTED, "happy"))
        else:
            for tid in TARGET_IDS:
                sub = [
                    drive_target(tid, root / "error" / tid / m, C.PLANTED, m)
                    for m in ("unset", "malformed", "expired")
                ]
                rows.append(
                    {
                        "id": tid,
                        "mode": "error-bundle",
                        "source": SOURCE_GROUND[tid],
                        "source_exists": sub[0]["source_exists"],
                        "executed": any(s["executed"] for s in sub),
                        "hit": any(s["hit"] for s in sub),
                        "subcases": sub,
                    }
                )
        return {
            "kind": kind,
            "unit_id": C.UNIT,
            "host": {"os": os.name, "python": sys.version.split()[0], "repo": str(REPO)},
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
