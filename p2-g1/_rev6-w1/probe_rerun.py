"""Fix C5: re-run every named probe per unit with the measure's env handling."""
import json, os, re, subprocess, sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
UNITS = ["CNF-0180", "CNF-0188", "CNL-0076", "IMP-0003", "IMP-0013",
         "IMP-0014", "IMP-0018", "IMP-0020", "IMP-0022"]


def run(cmd, timeout=2700):
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    hook = str(REPO / "command-center/p2-wave/seed-stage")
    env["PYTHONPATH"] = os.pathsep.join([hook, str(REPO), str(REPO / "tools"),
        str(REPO / "tools/measure-guard"), str(REPO / "platform/lib"),
        str(REPO / "tools/agentspec"), env.get("PYTHONPATH", "")])
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    exe = sys.executable.replace("\\", "/")
    wrap = REPO / "command-center/p2-wave/seed-stage/g1_python.py"
    if "python3" in cmd:
        cmd = cmd.replace("python3", exe + " " + wrap.as_posix(), 1)
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True,
                       text=True, timeout=timeout, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


out = {}
for uid in UNITS:
    ret = json.loads((REPO / "command-center/p2-wave/probes" / uid /
                      "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
    cmds = []
    for item in (ret.get("named_probes") or []):
        if isinstance(item, dict) and isinstance(item.get("command"), str):
            cmds.append(item["command"].strip())
    for item in (ret.get("probes") or []):
        if isinstance(item, dict) and isinstance(item.get("command"), str):
            c = item["command"].strip()
            if c and c not in cmds:
                cmds.append(c)
    oks = []
    tail = None
    for c in cmds:
        rc, t = run(c)
        oks.append(rc)
        if rc != 0:
            tail = t[-800:]
            break
    out[uid] = {"n_probes": len(cmds), "rcs": oks, "all_zero": bool(oks) and all(r == 0 for r in oks),
                "fail_tail": tail}
    print(uid, "probes:", len(cmds), "rcs:", oks, "OK" if out[uid]["all_zero"] else "FAIL")
    if tail:
        print("   tail:", tail[:400])

(REPO / "_rev6-w1" / "probe_rerun_results.json").write_text(
    json.dumps(out, indent=1), encoding="utf-8", newline="\n")
