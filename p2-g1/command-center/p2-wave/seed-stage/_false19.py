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
LIST = (
    "python3 - <<'PY'\n"
    "from pathlib import Path\n"
    "hits=[l for l in Path('/opt/p2/supervisor.log').read_text(errors='replace').splitlines() "
    "if 'DONE-OK' in l and 'FAILED:delivered' in l]\n"
    "print('COUNT', len(hits))\n"
    "for l in hits: print(l)\n"
    "PY"
)
JOBS = [
    ("gra9-c", "141.94.186.60", "list", None),
    ("uk1-a", "54.37.3.247", "list", None),
]


def ssh(ip: str, cmd: str, timeout: int = 40):
    return run(SSH + [f"root@{ip}", cmd], capture_output=True, text=True, timeout=timeout)


def main() -> None:
    for name, ip, _, _ in JOBS:
        print("==== LIST", name, flush=True)
        p = ssh(ip, LIST)
        print((p.stdout or "").strip() or (p.stderr or "")[-400:], flush=True)

    measures = [
        ("gra9-c", "141.94.186.60", "TST-0041"),
        ("uk1-a", "54.37.3.247", "LAST"),
    ]
    # LAST is resolved from uk1-a list stdout already printed; re-fetch last id
    p = ssh("54.37.3.247", LIST)
    last_uid = "UNKNOWN"
    for line in (p.stdout or "").splitlines():
        if "FAILED:delivered" in line:
            parts = line.split("FAILED:delivered", 1)[-1].strip().split()
            if parts:
                last_uid = parts[0]
    measures[1] = ("uk1-a", "54.37.3.247", last_uid)
    for name, ip, uid in measures:
        print("==== REMEASURE", name, uid, flush=True)
        p = ssh(
            ip,
            f"cd /opt/p2/ast-integrate && python3 command-center/p2-wave/_measure_one_delivered.py {uid}",
            timeout=90,
        )
        lines = ((p.stdout or "") + "\n" + (p.stderr or "")).strip().splitlines()
        for line in lines[-8:]:
            print(line, flush=True)
        print("rc", p.returncode, flush=True)


if __name__ == "__main__":
    main()
