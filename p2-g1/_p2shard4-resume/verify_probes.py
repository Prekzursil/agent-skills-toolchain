"""Re-run each unit's named_probes exactly as _measure_one_delivered would."""
import json
import sys
from pathlib import Path

REPO = Path.home() / "p2-g1"
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "_shard4_w1"))
import lib_shard4 as L

mine = ['BLD-0052','BLD-0057','CC-0011','CC-0017','CC-0022','CC-0024',
        'CNF-0063','CNF-0120','CNF-0135','CNF-0141','CNF-0144','CNF-0157']
for uid in mine:
    ret = json.loads((L.PROBES / uid / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
    cmds = [p["command"] for p in ret.get("named_probes") or [] if isinstance(p, dict)]
    rcs = []
    for cmd in cmds:
        rc, raw = L.run_cmd(cmd)
        rcs.append(rc)
        if rc != 0:
            print(f"{uid}: rc={rc} cmd={cmd}")
            print("   ", raw[-300:].replace("\n", "\n    "))
    print(f"{uid}: probes rc={rcs} -> {'GREEN' if rcs and all(r == 0 for r in rcs) else 'RED'}")
