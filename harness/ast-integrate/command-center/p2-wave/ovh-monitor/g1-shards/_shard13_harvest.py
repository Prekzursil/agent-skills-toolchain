#!/usr/bin/env python3
"""Find non-stub harvest copies of shard-13 stub/missing modules."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MON = REPO / "command-center" / "p2-wave" / "ovh-monitor"
STUB = ("# g1-surface: generated", "# g1-mod: real-surface", "class _NS:")

NEED = [
    "plugin/backup.py",
    "plugin/projection.py",
    "plugin/secret_gate.py",
    "plugin/__init__.py",
    "plugin/projection_map.py",
    "marketplace/index_schema.py",
    "marketplace/benchmark_evidence.py",
    "marketplace/fixtures.py",
    "marketplace/index_lint.py",
    "marketplace/path_conflict.py",
    "marketplace/install.py",
    "marketplace/package_cache.py",
    "workflow_foundry/anti_rebuild_guard.py",
    "workflow_foundry/generator_gate.py",
    "council/participants/select_explicit.py",
    "council/outcomes/unresolved.py",
    "council/protocol/crossexam.py",
    "tools/council/topology/meta.py",
    "tools/council/synthesis.py",
    "tools/test_common_core.py",
    "tools/cmdline_guard.py",
    "bench/compare.py",
    "bench/synthetic.py",
    "bench/case_set.py",
    "testinfra/test_seed_replay.py",
    "variance_band/benchmarks.py",
    "variance_band/harness.py",
    "variance_band/stats.py",
    "eng_blueprints_17_21/library.py",
    "eng_blueprints_17_21/salvage.py",
    "eng_blueprints_17_21/soak.py",
    "tools/command-center/artifact_register.py",
    "command-center/p2-wave/probes/IMP-0003/census.py",
    "command-center/p2-wave/probes/IMP-0003/forbidden_scan.py",
    "command-center/p2-wave/probes/IMP-0049/hash_census.py",
    "command-center/p2-wave/probes/IMP-0049/legacy_layout_steps.py",
    "command-center/p2-wave/probes/IMP-0049/migration_ledger.py",
    "command-center/p2-wave/probes/IMP-0140/test_no_rival_core.py",
    "command-center/p2-wave/probes/IMP-0431/postcondition.py",
    "tools/agentspec/agentspec/workflow_retry.py",
]


def is_stub(text: str) -> bool:
    head = text[:2000]
    return any(m in head for m in STUB)


def candidate_roots() -> list[Path]:
    roots: list[Path] = []
    for kind in ("delivery-pull", "missing-pull", "error-pull"):
        base = MON / kind
        if not base.is_dir():
            continue
        for box in base.iterdir():
            if not box.is_dir():
                continue
            for sub in ("delta", "tree", "extracted", "extracted-delta"):
                p = box / sub
                if p.is_dir():
                    roots.append(p)
            roots.append(box)
    scw = REPO / "command-center" / "p2-wave" / "scw-pull"
    if scw.is_dir():
        roots.append(scw)
    return roots


def live_info(rel: str) -> dict:
    p = REPO / rel
    if not p.is_file():
        return {"exists": False, "bytes": 0, "stub": True}
    text = p.read_text(encoding="utf-8", errors="replace")
    return {"exists": True, "bytes": p.stat().st_size, "stub": is_stub(text)}


def main() -> None:
    roots = candidate_roots()
    print(f"roots={len(roots)}")
    out = {}
    for rel in NEED:
        found = []
        for root in roots:
            cand = root / rel
            if cand.is_file() and cand.stat().st_size > 80:
                text = cand.read_text(encoding="utf-8", errors="replace")
                if is_stub(text):
                    continue
                found.append(
                    {
                        "path": str(cand),
                        "bytes": cand.stat().st_size,
                        "head": text.splitlines()[:6],
                    }
                )
            if rel.startswith("tools/"):
                cand2 = root / rel[len("tools/") :]
                if cand2.is_file() and cand2.stat().st_size > 80:
                    text = cand2.read_text(encoding="utf-8", errors="replace")
                    if not is_stub(text):
                        found.append(
                            {
                                "path": str(cand2),
                                "bytes": cand2.stat().st_size,
                                "head": text.splitlines()[:6],
                            }
                        )
        found.sort(key=lambda x: x["bytes"], reverse=True)
        # dedupe by bytes+head0
        seen = set()
        uniq = []
        for f in found:
            k = (f["bytes"], f["head"][0] if f["head"] else "")
            if k in seen:
                continue
            seen.add(k)
            uniq.append(f)
        live = live_info(rel)
        # tools counterpart
        tools_rel = None
        if not rel.startswith("tools/") and not rel.startswith("command-center/"):
            tp = REPO / "tools" / rel
            if tp.is_file():
                ttext = tp.read_text(encoding="utf-8", errors="replace")
                tools_rel = {
                    "path": str(tp.relative_to(REPO)).replace("\\", "/"),
                    "bytes": tp.stat().st_size,
                    "stub": is_stub(ttext),
                }
        out[rel] = {"live": live, "tools": tools_rel, "harvest": uniq[:4]}
        h0 = uniq[0]["bytes"] if uniq else 0
        tflag = ""
        if tools_rel:
            tflag = f" tools={tools_rel['bytes']} stub={tools_rel['stub']}"
        print(
            f"{rel} live={live['bytes']} stub={live['stub']} harvest={len(uniq)} max={h0}{tflag}"
        )
    dest = HERE / "_shard13_harvest.json"
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", dest)


if __name__ == "__main__":
    main()
