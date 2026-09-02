#!/usr/bin/env python3
"""shard-01 scratch: verify CNF-0031 schema rejects garbage, accepts artifact."""
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "CNF-0031"))
import schema_ctl as S  # noqa: E402

errs = S.iter_errors({"totally": "unrelated"})
print("garbage errors:", len(errs))
for e in errs[:5]:
    print(" ", e[:150])
doc = json.loads((REPO / "command-center/confirmation/CNF-0031-duplicate-dispatch.json").read_text(encoding="utf-8"))
art_errs = S.iter_errors(doc)
print("artifact errors:", len(art_errs))
for e in art_errs[:10]:
    print(" ", e[:200])
