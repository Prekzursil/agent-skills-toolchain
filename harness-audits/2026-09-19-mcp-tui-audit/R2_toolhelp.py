"""R2 cross-check: CreateToolhelp32Snapshot via ctypes (kernel32), no WMI, no psutil.
Mechanically independent API vs Get-CimInstance Win32_Process."""
import ctypes, ctypes.wintypes as wt, sys
from collections import Counter

TH32CS_SNAPPROCESS = 0x2
k32 = ctypes.WinDLL("kernel32", use_last_error=True)

class PE32W(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)), ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD), ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wt.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

h = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
if h == -1 or h == 0xFFFFFFFFFFFFFFFF or h == 0:
    print("FAILED:snapshot", ctypes.get_last_error()); sys.exit(1)
e = PE32W(); e.dwSize = ctypes.sizeof(PE32W)
procs = []
ok = k32.Process32FirstW(h, ctypes.byref(e))
while ok:
    procs.append((e.th32ProcessID, e.th32ParentProcessID, e.szExeFile))
    e = PE32W(); e.dwSize = ctypes.sizeof(PE32W)
    ok = k32.Process32NextW(h, ctypes.byref(e))
k32.CloseHandle(h)
names = Counter(p[2].lower() for p in procs)
print("TH_TS=run")
print("TH_TOTAL_PROCS=%d" % len(procs))
print("TH_NODE_TOTAL=%d" % names.get("node.exe", 0))
nodes = [(pid, ppid) for pid, ppid, n in procs if n.lower() == "node.exe"]
byppid = Counter(ppid for _, ppid in nodes)
namemap = {pid: n for pid, _, n in procs}
print("TH_NODE_PIDS=%s" % ",".join(str(p) for p, _ in sorted(nodes)))
for ppid, c in byppid.most_common(12):
    print("TH_NODE_PARENT ppid=%d name=%s children_node=%d" % (ppid, namemap.get(ppid, "DEAD/unknown"), c))
