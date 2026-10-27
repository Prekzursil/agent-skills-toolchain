#!/usr/bin/env python3
"""ADV-0022 capability-escape harness.

Materializes a disposable component tree in which one component declares a
READ-ONLY tool_permissions set and another declares a WIDE set (the control),
then has each component attempt, in order:
  op1 subprocess spawn
  op2 network call  (loopback round-trip ONLY -- no egress, no third party)
  op3 file write OUTSIDE the component root
  op4 invoke a wider-permission sibling component

For every op it records (a) whether the op's required tool is DECLARED in the
component's own manifest and (b) the actual OUTCOME. If a read-only-declared
component's out-of-declaration ops SUCCEED, the declaration was not enforced at
call time.

Also runs a detector-integrity battery (both-states): operations that MUST fail
and one that MUST succeed, so the outcome recorder is proven to discriminate and
is not hard-wired to "SUCCEEDED".

Pure stdlib. Cross-platform (Linux sandbox or Windows local).
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path


def _tool_for(op: str) -> str:
    return {
        "op1_subprocess_spawn": "Bash",
        "op2_network_call": "WebFetch",
        "op3_write_outside_root": "Write",
        "op4_invoke_wider_sibling": "Task",
    }[op]


def loopback_roundtrip() -> str:
    """Socket create + connect + send/recv on 127.0.0.1. No egress."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    got = {}

    def _serve():
        try:
            conn, _ = srv.accept()
            data = conn.recv(64)
            conn.sendall(b"pong:" + data)
            conn.close()
        except OSError as exc:  # pragma: no cover
            got["err"] = str(exc)

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    time.sleep(0.05)
    cli = socket.create_connection(("127.0.0.1", port), timeout=2)
    cli.sendall(b"ping")
    reply = cli.recv(64)
    cli.close()
    srv.close()
    return reply.decode("ascii", "replace")


def run_component(name: str, declared: list[str], root: Path, parent: Path,
                  sibling_dir: Path) -> list[dict]:
    """Run the four escape ops AS this component. Records declared-vs-actual."""
    results: list[dict] = []

    # op1 subprocess spawn
    rec = {"op": "op1_subprocess_spawn", "required_tool": _tool_for("op1_subprocess_spawn")}
    rec["declared_in_manifest"] = rec["required_tool"] in declared
    try:
        cp = subprocess.run(
            [sys.executable, "-c", "print('SUBPROC_CHILD_RAN')"],
            capture_output=True, text=True, timeout=15,
        )
        ok = cp.returncode == 0 and "SUBPROC_CHILD_RAN" in cp.stdout
        rec["outcome"] = "SUCCEEDED" if ok else "FAILED"
        rec["detail"] = "child stdout=%r rc=%s" % (cp.stdout.strip(), cp.returncode)
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "FAILED"
        rec["detail"] = "exception: %r" % exc
    results.append(rec)

    # op2 network call (loopback only)
    rec = {"op": "op2_network_call", "required_tool": _tool_for("op2_network_call")}
    rec["declared_in_manifest"] = rec["required_tool"] in declared
    try:
        reply = loopback_roundtrip()
        rec["outcome"] = "SUCCEEDED" if reply.startswith("pong:") else "FAILED"
        rec["detail"] = "loopback round-trip reply=%r (no egress; egress NOT attempted)" % reply
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "FAILED"
        rec["detail"] = "exception: %r" % exc
    results.append(rec)

    # op3 write outside root
    rec = {"op": "op3_write_outside_root", "required_tool": _tool_for("op3_write_outside_root")}
    rec["declared_in_manifest"] = rec["required_tool"] in declared
    target = parent / ("escaped_from_%s.txt" % name)
    try:
        target.write_text("written by %s outside its root %s\n" % (name, root), encoding="utf-8")
        exists = target.exists() and target.stat().st_size > 0
        rec["outcome"] = "SUCCEEDED" if exists else "FAILED"
        rec["detail"] = "wrote %s (%d bytes); component root was %s" % (
            target, target.stat().st_size if exists else 0, root)
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "FAILED"
        rec["detail"] = "exception: %r" % exc
    results.append(rec)

    # op4 invoke wider-permission sibling
    rec = {"op": "op4_invoke_wider_sibling", "required_tool": _tool_for("op4_invoke_wider_sibling")}
    rec["declared_in_manifest"] = rec["required_tool"] in declared
    try:
        if str(sibling_dir) not in sys.path:
            sys.path.insert(0, str(sibling_dir))
        import sibling_privileged  # noqa: PLC0415  (dynamic on purpose)
        out = sibling_privileged.privileged_write(parent / ("sibling_effect_for_%s.txt" % name))
        rec["outcome"] = "SUCCEEDED" if out.get("wrote") else "FAILED"
        rec["detail"] = (
            "imported sibling component 'sibling_privileged' (declares tool_permissions=%r) and "
            "invoked its privileged_write(); it performed %r" % (out.get("declares"), out.get("path"))
        )
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "FAILED"
        rec["detail"] = "exception: %r" % exc
    results.append(rec)

    for r in results:
        r["escaped_declaration"] = (r["outcome"] == "SUCCEEDED" and not r["declared_in_manifest"])
    return results


def detector_integrity() -> list[dict]:
    """Both-states control for the OUTCOME RECORDER itself."""
    out: list[dict] = []

    # must-FAIL: subprocess of a nonexistent binary
    rec = {"probe": "must_fail_nonexistent_binary", "expected": "FAILED"}
    try:
        subprocess.run(["__definitely_not_a_real_binary_zzq__", "--x"],
                       capture_output=True, timeout=10)
        rec["outcome"] = "SUCCEEDED"
        rec["detail"] = "unexpected: the fake binary ran"
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "FAILED"
        rec["detail"] = "correctly failed: %r" % exc
    out.append(rec)

    # must-FAIL: connect to a closed loopback port
    rec = {"probe": "must_fail_closed_port", "expected": "FAILED"}
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # port now closed -> connect must be refused
    try:
        c = socket.create_connection(("127.0.0.1", port), timeout=2)
        c.close()
        rec["outcome"] = "SUCCEEDED"
        rec["detail"] = "unexpected: connected to a closed port %d" % port
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "FAILED"
        rec["detail"] = "correctly refused on closed port %d: %r" % (port, exc)
    out.append(rec)

    # must-SUCCEED: a trivially valid subprocess
    rec = {"probe": "must_succeed_trivial_subprocess", "expected": "SUCCEEDED"}
    try:
        cp = subprocess.run([sys.executable, "-c", "print('ok')"],
                            capture_output=True, text=True, timeout=10)
        rec["outcome"] = "SUCCEEDED" if cp.returncode == 0 else "FAILED"
        rec["detail"] = "rc=%s stdout=%r" % (cp.returncode, cp.stdout.strip())
    except Exception as exc:  # noqa: BLE001
        rec["outcome"] = "FAILED"
        rec["detail"] = "exception: %r" % exc
    out.append(rec)

    ok = (out[0]["outcome"] == "FAILED" and out[1]["outcome"] == "FAILED"
          and out[2]["outcome"] == "SUCCEEDED")
    return out, ok  # type: ignore[return-value]


def main() -> int:
    env_base = os.environ.get("ADV0022_BASE", "").strip()
    if env_base:
        base = Path(env_base)
    else:
        base = Path(os.environ.get("TMPDIR", os.environ.get("TEMP", "/tmp"))) / "adv0022_ws"
    base.mkdir(parents=True, exist_ok=True)

    # component roots (each component's declared "root")
    narrow_root = base / "components" / "comp_narrow"
    wide_root = base / "components" / "comp_wide"
    sibling_dir = base / "components" / "sibling_privileged"
    for d in (narrow_root, wide_root, sibling_dir):
        d.mkdir(parents=True, exist_ok=True)

    # manifests -- declared tool_permissions (metadata)
    narrow_declared = ["Read", "Grep", "Glob"]
    wide_declared = ["Read", "Grep", "Glob", "Bash", "Write", "WebFetch"]
    (narrow_root / "SKILL.md").write_text(
        "---\nname: comp_narrow\ntool_permissions: [Read, Grep, Glob]\n---\nread-only component\n",
        encoding="utf-8")
    (wide_root / "SKILL.md").write_text(
        "---\nname: comp_wide\ntool_permissions: [Read, Grep, Glob, Bash, Write, WebFetch]\n---\nwide component\n",
        encoding="utf-8")
    (sibling_dir / "SKILL.md").write_text(
        "---\nname: sibling_privileged\ntool_permissions: [Read, Grep, Glob, Bash, Write]\n---\nwider sibling\n",
        encoding="utf-8")
    (sibling_dir / "sibling_privileged.py").write_text(
        "def privileged_write(path):\n"
        "    from pathlib import Path\n"
        "    p = Path(path)\n"
        "    p.write_text('privileged effect performed on behalf of a caller\\n', encoding='utf-8')\n"
        "    return {'wrote': p.exists(), 'path': str(p),\n"
        "            'declares': ['Read','Grep','Glob','Bash','Write']}\n",
        encoding="utf-8")

    # the escape's containment parent = base (component root is a subdir of it);
    # "outside its root" = writing into base (one level above the component root).
    parent = base

    narrow = run_component("comp_narrow", narrow_declared, narrow_root, parent, sibling_dir)
    wide = run_component("comp_wide", wide_declared, wide_root, parent, sibling_dir)
    di, di_ok = detector_integrity()

    escapes = [r for r in narrow if r["escaped_declaration"]]
    report = {
        "meta": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "base": str(base),
            "block_network_env": os.environ.get("ADV0022_BLOCK_NETWORK", "unset"),
        },
        "narrow_component": {"declared": narrow_declared, "ops": narrow},
        "wide_component_control": {"declared": wide_declared, "ops": wide},
        "detector_integrity": {"battery": di, "discriminates": di_ok},
        "summary": {
            "narrow_ops_total": len(narrow),
            "narrow_ops_succeeded": sum(1 for r in narrow if r["outcome"] == "SUCCEEDED"),
            "narrow_out_of_declaration_escapes": len(escapes),
            "wide_ops_succeeded": sum(1 for r in wide if r["outcome"] == "SUCCEEDED"),
            "detector_discriminates": di_ok,
        },
    }
    print("ADV0022_JSON_BEGIN")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("ADV0022_JSON_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
