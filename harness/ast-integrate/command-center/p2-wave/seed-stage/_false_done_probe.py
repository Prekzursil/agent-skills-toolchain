#!/usr/bin/env python3
from subprocess import run
from pathlib import Path

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
    ("gra9-c", "141.94.186.60"),
    ("uk1-c", "54.37.7.164"),
]
REMOTE = (
    "python3 - <<'PY'\n"
    "from pathlib import Path\n"
    "lines=Path('/opt/p2/supervisor.log').read_text(errors='replace').splitlines()\n"
    "hits=[l for l in lines if 'DONE-OK' in l and 'FAILED:delivered' in l]\n"
    "print('COUNT', len(hits))\n"
    "for l in hits:\n"
    "    print(l)\n"
    "PY"
)


def main() -> None:
    for name, ip in BOXES:
        print("====", name, flush=True)
        p = run(SSH + [f"root@{ip}", REMOTE], capture_output=True, text=True, timeout=30)
        print((p.stdout or "")[-2500:], flush=True)
        if p.returncode:
            print("rc", p.returncode, (p.stderr or "")[-400:], flush=True)


if __name__ == "__main__":
    main()
