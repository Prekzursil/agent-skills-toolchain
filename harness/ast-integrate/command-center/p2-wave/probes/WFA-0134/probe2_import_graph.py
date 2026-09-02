#!/usr/bin/env python3
"""Probe 2: independent confirmer — import graph + byte-identical condition statuses.

Starts from the three call-site source files (not the author's conclusion).
A planted rival predicate at the certification gate must make the detector fire.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from tools.foundry.certification_gate import certify_workflow as gate  # noqa: E402
from tools.foundry.local_runner import certify_workflow as local  # noqa: E402
from tools.foundry.tournament_runner import certify_workflow as tour  # noqa: E402
import import_graph as G  # noqa: E402
import subjects as S  # noqa: E402

ART = (
    REPO
    / "command-center/foundry/"
    / "WFA-0134-bind-the-shared-12-condition-completion-predicate-to.json"
)


def _fail(msg: str) -> int:
    print(f"FAILED:WFA-0134-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return _fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:WFA-0134" not in ART.read_text(encoding="utf-8"):
        return _fail("sentinel absent")

    live_graph = G.graph()
    if not live_graph.get("ok"):
        return _fail(f"import-graph {live_graph}")
    if live_graph.get("imported_modules") != [G.REDUCER_MOD]:
        return _fail(f"modules={live_graph.get('imported_modules')}")
    planted = G.mutant_drops_reducer()
    if not planted.get("ok"):
        return _fail(f"planted-rival {planted}")

    with tempfile.TemporaryDirectory(prefix="wfa0134-p2-") as tmp_s:
        root = Path(tmp_s)
        golden = S.materialize_golden(root)
        mutant = S.materialize_mutant(root, 11)
        vg = {
            "local-runner": local(golden, repo=REPO),
            "tournament-runner": tour(golden, repo=REPO, pair_id="p-golden"),
            "certification-gate": gate(golden, repo=REPO),
        }
        vm = {
            "local-runner": local(mutant, repo=REPO),
            "tournament-runner": tour(mutant, repo=REPO, pair_id="p-c11"),
            "certification-gate": gate(mutant, repo=REPO),
        }

    golden_status = [v.statuses() for v in vg.values()]
    if len(set(golden_status)) != 1:
        return _fail(f"golden statuses disagree {golden_status}")
    if any(v.record != "CERTIFIED" for v in vg.values()):
        return _fail("golden not CERTIFIED at every site")
    mutant_status = [v.statuses() for v in vm.values()]
    if len(set(mutant_status)) != 1:
        return _fail(f"mutant statuses disagree {mutant_status}")
    if any(v.record != "REJECTED" for v in vm.values()):
        return _fail("c11 mutant not REJECTED at every site")
    loci = {v.locus for v in vg.values()}
    if loci != {"local-runner", "tournament-runner", "certification-gate"}:
        return _fail(f"loci={loci}")

    art_graph = doc.get("import_graph") or {}
    if art_graph.get("reducer_module") != G.REDUCER_MOD:
        return _fail("artifact reducer_module mismatch vs live AST")
    if not art_graph.get("ok"):
        return _fail("artifact import_graph not ok")
    art_sites = {s.get("locus"): s.get("path") for s in art_graph.get("sites") or []}
    live_sites = {s["locus"]: s["path"] for s in live_graph["sites"]}
    if art_sites != live_sites:
        return _fail(f"artifact sites {art_sites} != live {live_sites}")

    summary = {
        "ok": True,
        "probe": "probe2-import-graph",
        "unit_id": "WFA-0134",
        "reducer_module": G.REDUCER_MOD,
        "sites": [
            {
                "locus": s["locus"],
                "path": s["path"],
                "function_lineno": s["function_lineno"],
                "import_lineno": (s["imports"][0]["lineno"] if s["imports"] else None),
            }
            for s in live_graph["sites"]
        ],
        "planted_rival_fires": True,
        "golden_statuses_identical": True,
        "mutant_c11_statuses_identical": True,
        "loci": sorted(loci),
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "SUCCESS:WFA-0134-probe2 one reducer at three sites; "
        "planted rival fires; identical statuses"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
