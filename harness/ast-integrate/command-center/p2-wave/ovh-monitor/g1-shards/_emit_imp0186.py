#!/usr/bin/env python3
import json
import sys
from pathlib import Path

REPO = Path("/home/prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "IMP-0186"))
from workflow_fusion.conditional_hybrid import emit_conditional_hybrid
import scenario as S

fusion = emit_conditional_hybrid(S.good_spec())
text = json.dumps(fusion, indent=2, sort_keys=True) + "\n"
dests = [
    REPO / "command-center" / "fusion" / "IMP-0186-conditional-hybrid.json",
    Path("/mnt/c/Users/Prekzursil/source/ast-integrate/command-center/fusion/IMP-0186-conditional-hybrid.json"),
]
for dest in dests:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    print("wrote", dest)
print("id", fusion.get("id"), "unreachable", fusion.get("reachability_proof", {}).get("unreachable"))
