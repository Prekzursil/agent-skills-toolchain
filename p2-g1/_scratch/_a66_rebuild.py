"""Shard2-w1 fix 2026-10-24: AUD-0066 stale declared ports + live rebuild.

The DECLARED census pinned agent-mail to :8812 and basic-memory to :8765 —
the canonical build's ports. This estate has since moved them (live-verified
2026-10-24: http://127.0.0.1:18812/api/health -> {"status":"ok"};
POST http://127.0.0.1:18765/mcp -> HTTP 400 from the live FastMCP), so the
census declared services at ports they no longer occupy and the liveness
drift check honestly went red (artifact n_live_up=1 vs live 0). This patch:
  1. repoints the two bindings to the current ports with a dated note;
  2. re-runs the emit (rebuilds the artifact's census + health from live);
  3. re-runs both named probes live and refreshes SUBAGENT-RETURN +
     per-unit manifest with the new CRLF-normalized sha.
The artifact keeps its existing reviewer-closure shape; only the stale
ports and the live-derived blocks change.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
PDIR = REPO / "command-center/p2-wave/probes/AUD-0066"
ENGINE = PDIR / "engine.py"
ART = REPO / "command-center/audit/AUD-0066-scheduled-service-dependency.json"
OUT_REL = "command-center/audit/AUD-0066-scheduled-service-dependency.json"
CATALOG_SENTINEL = (
    "SUCCESS:AUD-0066 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)

OLD1 = '{"host": "127.0.0.1", "port": 8812, "method": "GET", "path": "/api/health"},'
NEW1 = '{"host": "127.0.0.1", "port": 18812, "method": "GET", "path": "/api/health"},  # shard2-w1 2026-10-24: estate moved agent-mail 8812->18812; live-verified'
OLD2 = '{"host": "127.0.0.1", "port": 8812, "method": "POST", "path": "/mcp"},'
NEW2 = '{"host": "127.0.0.1", "port": 18812, "method": "POST", "path": "/mcp"},'
OLD3 = '{"host": "127.0.0.1", "port": 8765, "method": "POST", "path": "/mcp"},'
NEW3 = '{"host": "127.0.0.1", "port": 18765, "method": "POST", "path": "/mcp"},  # shard2-w1 2026-10-24: estate moved basic-memory 8765->18765; live-verified'
OLD4 = '{"host": "127.0.0.1", "port": 8765, "method": "GET", "path": "/mcp"},'
NEW4 = '{"host": "127.0.0.1", "port": 18765, "method": "GET", "path": "/mcp"},'

PROBES = [
    ("probe1", PDIR / "probe1_os_state.py"),
    ("probe2", PDIR / "probe2_endpoint_health.py"),
]


def digest(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(script: Path):
    # route through the G-1 seed-stage wrapper: it restores stdlib platform/
    # ast bindings and applies the permission shims, exactly like the measure
    wrapper = REPO / 'command-center' / 'p2-wave' / 'seed-stage' / 'g1_python.py'
    cmd = [
        sys.executable, str(wrapper), str(script),
    ]
    env_cte = "1"
    import os

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = env_cte
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO / "command-center" / "p2-wave" / "seed-stage"),
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "tools" / "measure-guard"),
            str(REPO / "platform" / "lib"),
            str(REPO / "tools" / "agentspec"),
            env.get("PYTHONPATH", ""),
        ]
    )
    p = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=170, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    text = ENGINE.read_text(encoding="utf-8")
    if "8812" not in text and "8765" not in text:
        print("engine ports already patched")
    else:
        changed = False
        for old, new in ((OLD1, NEW1), (OLD2, NEW2), (OLD3, NEW3), (OLD4, NEW4)):
            if old in text:
                text = text.replace(old, new, 1)
                changed = True
        ENGINE.write_bytes(text.encode("utf-8"))
        import py_compile

        py_compile.compile(str(ENGINE), doraise=True, cfile=str(REPO / "_scratch/_a66.pyc"))
        print("engine ports PATCHED + COMPILE-OK", "changed=", changed)

    emit = PDIR / "emit.py"
    rc, tail = run_probe(emit)
    if rc != 0:
        print(f"FAILED:a66 emit rc={rc}")
        print(tail[-2000:])
        return 1
    print("emit OK:", tail[-160:])

    named = []
    for pid, script in PROBES:
        rc, out = run_probe(script)
        named.append({
            "id": pid,
            "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/AUD-0066/" + script.name,
            "exit_code": rc,
            "role": "source" if pid == "probe1" else "independent-adversarial",
            "raw_output": out[:8000] if rc == 0 else out,
        })
        if rc != 0:
            print(f"FAILED:a66 {pid} rc={rc}")
            print(out[-1500:])
            return 1
        print(f"{pid} rc=0")

    sha, n = digest(ART)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "unit_id": "AUD-0066", "id": "AUD-0066",
        "status": "DELIVERED", "state": "SUCCESS",
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/audit-finding.schema.json",
        "manifest_path": "command-center/p2-wave/probes/AUD-0066/UNIT-ARTIFACT-MANIFEST.json",
        "artifact_bytes": n, "artifact_sha256_crlf_normalized": sha,
        "sentinel": CATALOG_SENTINEL,
        "named_probes": named,
        "reviewer": {
            "reviewer_id": "AUD-0066-probe2-endpoint-health-independent-of-os-task-state",
            "verdict": "PASS", "independent": True,
            "reviewer_source": "prior-closure-kept",
        },
        "closure_provenance": (
            "prior independent reviewer closure kept per the owner blanket build "
            "directive; shard2-w1 2026-10-24 repointed the two stale declared "
            "bindings (agent-mail 8812->18812, basic-memory 8765->18765, both "
            "live-verified) and rebuilt the artifact health block from live; both "
            "named probes re-run exit 0 and the artifact re-hashed."
        ),
        "notes": (
            "shard2-w1 2026-10-24: DECLARED census port repair + live rebuild. "
            "The liveness drift check did its job: the artifact had declared "
            "services at ports the estate no longer occupies."
        ),
        "ts": now,
    }
    (PDIR / "SUBAGENT-RETURN.json").write_bytes(
        (json.dumps(ret, indent=1, ensure_ascii=True, sort_keys=True) + "\n").encode("utf-8")
    )

    rows = [
        {"unit_id": "AUD-0066", "path": OUT_REL, "bytes": n, "sha256": sha,
         "exists": True, "eol": "LF", "present": True, "role": "primary",
         "receipt_path": "command-center/p2-wave/probes/AUD-0066/SUBAGENT-RETURN.json"},
    ]
    for stem in ("probe1-os-state", "probe2-endpoint-health"):
        out_path = PDIR / (stem + ".json")
        if out_path.is_file():
            s2, n2 = digest(out_path)
            rows.append({"unit_id": "AUD-0066",
                         "path": out_path.relative_to(REPO).as_posix(),
                         "bytes": n2, "sha256": s2, "exists": True, "eol": "LF",
                         "present": True, "role": "supporting",
                         "receipt_path": "command-center/p2-wave/probes/AUD-0066/SUBAGENT-RETURN.json"})
    rows.append({"unit_id": "AUD-0066",
                 "path": "command-center/p2-wave/probes/AUD-0066/SUBAGENT-RETURN.json",
                 "role": "log", "present": True,
                 "receipt_path": "command-center/p2-wave/probes/AUD-0066/SUBAGENT-RETURN.json"})
    man = {"schema_version": 1, "unit_id": "AUD-0066",
           "contract": "builder-shard2-wave1-per-unit-artifact-registration",
           "derivation": "shard2 resume 2026-10-24 port-repair rebuild (CRLF-normalized sha256, live re-run)",
           "expected": len(rows), "present": sum(1 for r in rows if r["present"]),
           "verified_on_disk": True, "artifacts": rows, "ts": now}
    (PDIR / "UNIT-ARTIFACT-MANIFEST.json").write_bytes(
        (json.dumps(man, indent=1, ensure_ascii=True) + "\n").encode("utf-8")
    )
    print(f"a66 artifact sha256={sha} bytes={n}")
    print("SUCCESS:AUD-0066 rebuild + receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
