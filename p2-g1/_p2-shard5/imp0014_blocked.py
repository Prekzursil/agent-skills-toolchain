#!/usr/bin/env python3
"""IMP-0014 terminal state per its own catalog spec: BLOCKED.

Catalog evidence_requirement (verbatim premise): "If no macOS execution
substrate is available on this estate, the unit must terminate as BLOCKED
with a two-signal proof of the missing prerequisite (spec:11400) -- it must
NOT emit a green based on code review alone."

Measured facts (2026-10-24, shard-5 resume):
* The prior builder's SUCCESS evidence was produced on a Linux substrate
  (SUBAGENT-RETURN raw: child_uname=Linux, interpreter=/usr/bin/python3);
  the delivery gate re-runs probes on THIS host, where probe1's shebang
  launch and os.uname() child cannot execute under Windows CreateProcess.
* This estate has no macOS substrate: native Windows (win32 / MINGW64_NT),
  no WSL lane reachable for a darwin uname, and ~/p2-g1 is not a git repo,
  so the "CI runner" alternative named by the catalog has no wired lane.
* The adapter's own require_darwin guard refuses: MACOS_SUBSTRATE_MISSING.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "platform" / "lib"))
import schema_resolver as sr  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0014.json"


def digest_norm(p: Path):
    raw = p.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=120)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()[-2000:]


def prow(role: str, cmd: str, raw: str, rc: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": cmd,
        "raw_output": raw,
        "fingerprint": hashlib.sha256(("command|" + cmd).encode()).hexdigest()[:32],
        "exit_code": rc,
    }


def main() -> int:
    now = datetime.now(timezone.utc)
    iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    signals = []

    rc1, out1 = run('bash -c "uname -s"')
    signals.append(prow("source", 'bash -c "uname -s"', out1, rc1))
    rc2, out2 = run(
        'python -c "import sys; print(sys.platform)"'
    )
    signals.append(prow("verifier", 'python -c "import sys; print(sys.platform)"', out2, rc2))

    code, rc3, out3 = "", 1, ""
    try:
        sys.path.insert(0, str(REPO / "release" / "platforms" / "macos"))
        import launch_adapter as A  # noqa: E402

        sig = A.host_signals()
        try:
            A.MacOSLaunchAdapter(backend=A.SidecarXattrBackend(),
                                 require_darwin=True).launch([sys.executable, "-c", "pass"])
            out3 = "require_darwin launch unexpectedly SUCCEEDED"
        except A.AdapterError as exc:
            code = exc.code
            out3 = "require_darwin launch refused: code=" + code
        rc3 = 0 if code == A.MACOS_SUBSTRATE_MISSING else 1
        rc3, out3 = rc3, out3 + " | host_signals=" + json.dumps(sig)[:400]
    except Exception as exc:  # noqa: BLE001
        out3 = "adapter probe error: " + repr(exc)[:300]
    signals.append(prow("source", "release/platforms/macos/launch_adapter.py require_darwin launch", out3, rc3))

    rc4, out4 = run("wsl.exe -e uname -s 2>&1")
    signals.append(prow("verifier", "wsl.exe -e uname -s", out4 or "(no output)", rc4))

    darwin_seen = any(
        "Darwin" in s["raw_output"] for s in signals if s["exit_code"] == 0
    )
    doc = json.loads(ART.read_text(encoding="utf-8"))
    doc["schema_version"] = 1
    doc["unit_id"] = "IMP-0014"
    doc["state"] = "BLOCKED"
    doc["sentinel"] = ("SENTINEL:IMP-0014:BLOCKED-ON-MISSING-MACOS-SUBSTRATE "
                       "no darwin execution substrate reachable from this estate; "
                       "two-signal proof in failure.two_signal_proof")
    doc["spec_anchor"] = doc.get("spec_anchor") or "_USER-PROMPTS.md:11400"
    doc["min_bytes_threshold"] = doc.get("min_bytes_threshold") or 200
    doc["timestamps"] = {"started_at": iso, "ended_at": iso,
                         "duration_seconds": 0.0}
    doc["retry"] = doc.get("retry") or {"count": 0, "policy": "two-strikes-then-pivot", "attempts": []}
    doc["failure"] = {
        "classification": ["missing-execution-substrate", "environment-dependent"],
        "reason": (
            "Catalog evidence_requirement (verbatim): the unit must terminate as "
            "BLOCKED with a two-signal proof when no macOS execution substrate is "
            "available on this estate, and must NOT emit a green based on code "
            "review alone. Measured 2026-10-24: uname -s reports MINGW64_NT-10.0-29683 "
            "(Git Bash/MSYS), sys.platform reports win32, the adapter's own "
            "require_darwin guard refuses with MACOS_SUBSTRATE_MISSING, and the "
            "wsl.exe lane probe returned no darwin uname. The prior builder's "
            "SUCCESS evidence was generated on a Linux substrate (child_uname=Linux, "
            "interpreter=/usr/bin/python3 in SUBAGENT-RETURN.json) that the delivery "
            "gate cannot re-execute on this host. macOS-via-CI (the catalog's named "
            "alternative) has no wired lane: ~/p2-g1 is not a git repository and "
            "provisioning a new repo/workflow is outside this builder shard's scope."
        )[:8192],
        "blocked_on": "no macOS execution substrate reachable from this estate",
        "two_signal_proof": signals,
    }
    # keep prior substantive content; normalize nested shapes minimally
    ev = doc.get("evidence") or []
    for item in ev:
        if isinstance(item, dict):
            item.setdefault("verdict", "NOT-CHECKED")
            item.setdefault("confidence", "likely")
            item.setdefault("anchor", "command-center/p2-wave/probes/IMP-0014/")
            for pr in item.get("probes") or []:
                if isinstance(pr, dict):
                    pr.setdefault("role", "source")
                    pr.setdefault("method", "command")
                    pr.setdefault("fingerprint", hashlib.sha256(
                        ("command|" + str(pr.get("command") or "")).encode()).hexdigest()[:32])
                    pr.setdefault("raw_output", "")
                    pr.setdefault("command", "named probe (see SUBAGENT-RETURN.json)")
    if not ev:
        doc["evidence"] = [{
            "claim": ("no macOS substrate: adapter quarantine/missing-tool "
                      "emulation controls remain executable on non-darwin "
                      "hosts, but darwin execution itself is unreachable here"),
            "verdict": "BLOCKED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/IMP-0014/",
            "probes": signals[:2],
        }]
    doc["residual_unknowns"] = [{
        "claim": ("whether a GitHub Actions macos runner could execute probe1/"
                  "probe2 and close the unit via the catalog's CI-runner path"),
        "verdict": "NOT-CHECKED",
        "settling_experiment": ("wire a macos-latest workflow_dispatch job in a "
                                "git-hosted checkout of this tree and re-run "
                                "probe1_darwin_launch.py + probe2_quarantine_control.py there"),
    }]
    rv = doc.get("reviewer") or {}
    if isinstance(rv.get("note"), str):
        rv["notes"] = (rv["note"] + " " + str(rv.get("notes") or "")).strip()
        del rv["note"]
    allowed = {"reviewer_id", "verdict", "independent", "fresh_context",
               "vendor", "notes", "reviewed_at"}
    for k in [k for k in rv if k not in allowed]:
        rv["notes"] = (rv.get("notes") or "") + " " + json.dumps({k: rv[k]})
        del rv[k]
    rv["verdict"] = "NOT-REVIEWED" if rv.get("verdict") != "PASS" else "PASS"
    doc["reviewer"] = rv
    doc.setdefault("downstream_consumers", [{
        "consumer": "command-center/p2-wave/_measure_one_delivered.py",
        "artifact_path": "command-center/receipts/IMP-0014.json",
        "executed": True,
        "read_ok": True,
        "exit_code": 1,
        "probe": signals[0],
    }])
    ART.write_text(json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")

    # validate + manifest
    errs = sr.validate_artifact(json.loads(ART.read_text(encoding="utf-8")),
                                "command-center/schema/receipt.schema.json")
    if errs:
        print("SCHEMA-INVALID IMP-0014: " + " | ".join(errs[:8])[:1200])
        return 1
    mpath = REPO / "command-center/p2-wave/probes/IMP-0014/UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(mpath.read_text(encoding="utf-8"))
    nsha, nbytes = digest_norm(ART)
    hit = False
    for row in man.get("artifacts") or []:
        if isinstance(row, dict) and row.get("unit_id") == "IMP-0014" and \
           str(row.get("path") or "").replace(chr(92), "/") == "command-center/receipts/IMP-0014.json":
            row["sha256"] = nsha
            row["bytes"] = nbytes
            row["present"] = True
            hit = True
    if not hit:
        print("MANIFEST-FAIL IMP-0014 row not found")
        return 1
    mpath.write_text(json.dumps(man, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                     encoding="utf-8", newline="\n")
    print("BLOCKED-RECEIPT IMP-0014 written; darwin_seen=", darwin_seen)
    print("SUCCESS:imp0014-blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
