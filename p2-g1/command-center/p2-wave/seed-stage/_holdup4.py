#!/usr/bin/env python3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from subprocess import run

SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "ConnectTimeout=12",
    "-o",
    "StrictHostKeyChecking=accept-new",
    "-o",
    "IdentitiesOnly=yes",
    "-i",
    str(Path.home() / ".ssh" / "id_ed25519"),
]
BOXES = [
    ("par-c", "57.130.46.182"),
    ("rbx-c", "152.228.192.99"),
    ("uk1-a", "54.37.3.247"),
    ("uk1-c", "54.37.7.164"),
]
CMD = r"""
set +e
echo "=== heartbeat ==="
python3 -c 'import json;from pathlib import Path;p=Path("/opt/p2/supervisor-heartbeat.json");
d=json.loads(p.read_text()) if p.exists() else {};
print("in_flight",d.get("in_flight_n"),"queued",d.get("queued_n"),"ok",d.get("ok"),"ts",d.get("ts"))'
echo "=== fix json ==="
if test -f /opt/p2/g1-fix.json; then python3 -c 'import json;d=json.load(open("/opt/p2/g1-fix.json"));print("DONE",d.get("ok"),d.get("n"),d.get("fail"))'; else echo NO-FIX-JSON; fi
echo "=== fix log tail ==="
tail -n 8 /opt/p2/g1-fix.log 2>/dev/null || echo no-fix-log
echo "=== pgrep fix/agent ==="
pgrep -af 'fix_g1_fails|cursor-agent|cursor-grok|/root/.local/bin/agent' | head -n 20
echo "=== newest worker ==="
ls -lt /opt/p2/workers 2>/dev/null | head -n 8
echo "=== newest g1fix log tail ==="
newest=$(ls -td /opt/p2/workers/g1fix-* 2>/dev/null | head -n 1)
if test -n "$newest"; then echo DIR "$newest"; tail -n 12 "$newest/worker.log" 2>/dev/null; ls -l "$newest/worker.log" 2>/dev/null; else echo no-g1fix-dir; fi
"""


def one(name: str, ip: str) -> str:
    p = run(SSH + [f"root@{ip}", CMD], capture_output=True, text=True, timeout=25)
    return f"######## {name} {ip}\n{(p.stdout or '')}\n{(p.stderr or '')[-300:]}"


def main() -> None:
    with ThreadPoolExecutor(4) as ex:
        futs = [ex.submit(one, *b) for b in BOXES]
        for f in as_completed(futs):
            print(f.result(), flush=True)


if __name__ == "__main__":
    main()
