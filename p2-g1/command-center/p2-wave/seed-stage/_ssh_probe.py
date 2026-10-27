import subprocess

ips = [
    "ubuntu@176.31.201.117",
    "ubuntu@164.132.87.22",
    "ubuntu@51.75.63.116",
    "ubuntu@37.59.27.161",
]
cmd = (
    "echo UP; hostname; "
    "sudo test -x /root/.local/bin/agent && echo AGENT-ROOT || echo NO-AGENT-ROOT; "
    "ls /root/.local/bin 2>/dev/null | head; "
    "sudo ls /root/.local/bin 2>/dev/null | head; "
    "nproc; free -g | head -2"
)
for ip in ips:
    r = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            "-o",
            "StrictHostKeyChecking=accept-new",
            ip,
            cmd,
        ],
        capture_output=True,
        text=True,
    )
    print("===", ip, "rc", r.returncode)
    print(r.stdout[-1500:])
    if r.stderr:
        print("ERR", r.stderr[-400:])
