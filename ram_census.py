"""RAM forensic census: python x54 + conhost + WindowsTerminal riders.
5.1-safe: subprocess wmic-style via CIM, no PS null operators. Writes census to stdout."""
import subprocess, json, csv, io

def q(wql):
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process -Filter \"%s\" | Select-Object ProcessId,ParentProcessId,Name,CreationDate,CommandLine | ConvertTo-Json -Compress" % wql],
        capture_output=True, text=True, timeout=90)
    try:
        d = json.loads(r.stdout)
        return d if isinstance(d, list) else [d]
    except Exception:
        return []

procs = {p["ProcessId"]: p for p in q("Name='python.exe'") if p}
allp = {p["ProcessId"]: p for p in q("Name!='python.exe'")}
allp.update(procs)

def parent(pid):
    p = allp.get(pid)
    return p["Name"] if p else "DEAD"

rows = []
for pid, p in procs.items():
    cmd = (p.get("CommandLine") or "?").replace("\n", " ")[:88]
    rows.append((p.get("CreationDate", "")[:16], pid, p["ParentProcessId"], parent(p["ParentProcessId"]), cmd))

rows.sort()
print("=== PYTHON CENSUS (%d) ===" % len(rows))
for t, pid, ppid, pn, cmd in rows:
    print("%s pid=%-7s <- %s(%s) | %s" % (t, pid, pn, ppid, cmd))

# duplicates by command signature
from collections import Counter
sig = Counter(cmd[30:70] for _, _, _, _, cmd in rows)
print("\n=== DUPLICATE SIGNATURES (2+) ===")
for s, n in sig.most_common(8):
    if n >= 2:
        print("x%d  %s" % (n, s))

conh = q("Name='conhost.exe'")
print("\nconhost total:", len(conh))
wt = q("Name='WindowsTerminal.exe'")
for w in wt:
    print("WT pid", w["ProcessId"], "started", str(w.get("CreationDate"))[:19], "cmdlen", len(w.get("CommandLine") or ""))
