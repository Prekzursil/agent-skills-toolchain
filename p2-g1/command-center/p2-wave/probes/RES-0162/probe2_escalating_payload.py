#!/usr/bin/env python3
"""RES-0162 probe2_escalating_payload.

tests row: escalating-payload-live. LIVE leg: re-measures the invocation
surface on THIS box right now - a small payload must spawn and exit cleanly,
and the payload must be deliverable by FILE at sizes where argv fails, with
the argv failure LOUD (an exception, not a truncated silent spawn). Compares
against the artifact's recorded file-transport measurement. Defaults to FAIL.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def main() -> int:
    art = REPO / "command-center/research/prior-art/RES-0162-cross-vendor-invocation-surface-leaks.json"
    txt = art.read_text(encoding="utf-8")
    doc = json.loads(txt)
    checks = []

    def ck(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": str(detail)[:230]})
        return bool(ok)

    # recorded file-transport claim: a 1.25 MB payload delivered by file
    # spawned successfully while argv delivery fails loudly near 32K chars
    m = doc.get("measurements") or {}
    ft = m.get("file_transport") or {}
    ck("recorded-file-transport-1MB-spawned",
       ft.get("size") == 1310720 and ft.get("spawned") is True and ft.get("rc") == 0
       and ft.get("error") is None and ft.get("timeout") is False,
       json.dumps({k: ft.get(k) for k in ("size", "spawned", "rc", "error")}, default=str))

    # LIVE: small payload via argv spawns and exits 0
    small = subprocess.run(
        [sys.executable, "-c", "print('OK')", "x" * 512],
        capture_output=True, text=True, timeout=60)
    ck("live-small-payload-spawns-clean", small.returncode == 0 and "OK" in small.stdout,
       f"rc={small.returncode}")

    # LIVE: 60K-char argv fails LOUDLY (OSError raised, not a silent spawn)
    loud = None
    try:
        subprocess.run([sys.executable, "-c", "print('hi')", "x" * 60000],
                       capture_output=True, text=True, timeout=60)
        loud = "spawned-silently"
    except OSError as exc:
        loud = f"loud:{type(exc).__name__}"
    ck("live-large-payload-fails-loud", isinstance(loud, str) and loud.startswith("loud:"),
       f"observed={loud} (expected OSError class near the CreateProcess cap)")

    # LIVE: same payload delivered by FILE spawns and exits 0 where argv failed
    payload = "x" * 60000
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, dir=str(REPO / "_p2shard19-w2")) as fh:
        fh.write(payload)
        p = Path(fh.name)
    try:
        via_file = subprocess.run(
            [sys.executable, "-c",
             "import sys; d=open(sys.argv[1]).read(); print(len(d))", str(p)],
            capture_output=True, text=True, timeout=60)
        ck("live-file-transport-succeeds-where-argv-fails",
           via_file.returncode == 0 and via_file.stdout.strip().endswith("60000"),
           f"rc={via_file.returncode} out={via_file.stdout.strip()[-20:]}")
    finally:
        p.unlink(missing_ok=True)

    ck("state-success-sentinel",
       doc.get("state") == "SUCCESS" and doc.get("completion_sentinel") == "SUCCESS:RES-0162",
       f"state={doc.get('state')}")

    red = [c for c in checks if not c["pass"]]
    verdict = {"probe": "probe2-escalating-payload", "unit_id": "RES-0162", "pass": not red,
               "checks": checks, "red": red}
    print(json.dumps(verdict))
    print("SUCCESS:RES-0162-probe2 escalating-payload surface re-measured live" if not red
          else f"FAILED:RES-0162-probe2 red={len(red)}")
    return 0 if not red else 1


if __name__ == "__main__":
    sys.exit(main())
