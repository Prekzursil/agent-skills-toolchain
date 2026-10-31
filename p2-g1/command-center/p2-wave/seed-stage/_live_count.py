import subprocess

ips = [
    ("gra11-a", "176.31.201.117"),
    ("gra11-c", "176.31.201.215"),
    ("waw1-b", "51.75.63.116"),
    ("de1-a", "51.75.93.252"),
    ("gra9-b", "37.59.27.161"),
    ("rbx-a", "164.132.87.22"),
    ("par-a", "57.130.47.223"),
    ("uk1-a", "54.37.3.247"),
    ("sbg5-a", "57.128.35.67"),
    ("gra7-a", "51.91.140.54"),
]
ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "StrictHostKeyChecking=accept-new"]
total = 0
for name, ip in ips:
    r = subprocess.run(
        ssh + [f"root@{ip}", "python3 -c \"import json; d=json.load(open('/opt/p2/supervisor-heartbeat.json')); print(d.get('in_flight_n'), d.get('cap'), d.get('queued_n'), d.get('box'))\" 2>/dev/null || echo NA"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    line = (r.stdout or "").strip()
    print(f"{name:10s} {ip:16s} {line}")
    try:
        total += int(line.split()[0])
    except Exception:
        pass
print("LIVE_SUM", total)
