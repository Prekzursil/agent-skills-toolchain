#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"C:\Users\Prekzursil\source\ast-integrate")
needles = [
    "tools/shell/pathconv.py",
    "tools/wfa/nondeterminism.py",
    "tools/wfa/__init__.py",
    "command-center/blueprints/policy_as_code.py",
    "command-center/blueprints/legal_compliance.py",
    "command-center/blueprints/registry.py",
    "command-center/blueprints/ci_evaluate.py",
    "command-center/blueprints/privacy.py",
    "command-center/blueprints/governance_proposal.py",
    "command-center/blueprints/contract.py",
    "tools/plugin/pack.py",
    "plugin/pack.py",
    "tools/plugin/fixture_repo.py",
    "plugin/fixture_repo.py",
    "unique_line_differ.py",
    "message_renderer.py",
    "tools/integrity_sweep.py",
    "tools/agentspec/agentspec/human_checkpoint.py",
    "tools/agentspec/agentspec/checkpoint.py",
    "tools/council/participants/diversity.py",
    "tools/council/protocol/steelman.py",
    "council/protocol/steelman.py",
    "tools/council/owner.py",
    "tools/council/owner_ask.py",
    "tools/marketplace/deprecation.py",
    "marketplace/deprecation.py",
    "tools/workflow_forge/best_of_breed.py",
    "tools/agentspec/agentspec/evals/registry.py",
    "tools/router/inject.py",
    "router/inject.py",
    "tools/orphan_resume.py",
    "tools/test_orphan_resume.py",
    "tools/bench/tournament.py",
    "tools/bench/condition8.py",
    "tools/council/antifail/expertise.py",
    "council/antifail/expertise.py",
    "platform/lib/foundry/capability_diff.py",
    "foundry/capability_diff.py",
    "command-center/schema/source-lineage.schema.json",
    "tools/sycophancy.py",
    "tools/worktree_origin_guard.py",
]
hosts = [ROOT]
pull = ROOT / "command-center/p2-wave/ovh-monitor/delivery-pull"
if pull.is_dir():
    for host in pull.iterdir():
        if host.is_dir():
            hosts.append(host / "tree")
            hosts.append(host / "delta")
err = ROOT / "command-center/p2-wave/ovh-monitor/error-pull"
if err.is_dir():
    for p in ("extracted", "extracted-delta"):
        d = err / p
        if d.is_dir():
            for host in d.iterdir():
                if host.is_dir():
                    hosts.append(host)
                    hosts.append(host / "probes")

want_names = {Path(n).name for n in needles}
print("hosts", len(hosts))
found_map = {n: [] for n in needles}
name_hits = {n: [] for n in want_names}

for needle in needles:
    for host in hosts:
        p = host / needle
        if p.is_file():
            found_map[needle].append((str(p), p.stat().st_size))

walk_roots = [
    ROOT / "tools",
    ROOT / "plugin",
    ROOT / "command-center" / "blueprints",
    ROOT / "platform" / "lib",
]
# only named probe dirs (no harvest tree walk)
for uid in (
    "IMP-0002",
    "IMP-0024",
    "IMP-0052",
    "IMP-0123",
    "IMP-0143",
    "IMP-0185",
    "IMP-0218",
    "IMP-0244",
    "IMP-0272",
    "IMP-0293",
    "IMP-0319",
    "IMP-0342",
    "IMP-0366",
    "IMP-0466",
    "WFA-0089",
    "WFA-0140",
    "TST-0171",
    "TST-0211",
    "TST-0240",
    "TST-0270",
    "TST-0299",
    "TST-0324",
):
    walk_roots.append(ROOT / "command-center/p2-wave/probes" / uid)
for wr in walk_roots:
    if not wr.is_dir():
        continue
    for p in wr.rglob("*"):
        if p.is_file() and p.name in want_names and p.stat().st_size > 200:
            try:
                head = p.read_text(encoding="utf-8", errors="replace")[:240]
            except Exception:
                continue
            stub = (
                "# g1-mod: real-surface" in head
                or "# g1-surface: generated" in head
                or "class _NS:" in head
            )
            if not stub:
                name_hits[p.name].append((str(p), p.stat().st_size))

out = ROOT / "command-center/p2-wave/ovh-monitor/g1-shards/_shard15_harvest.txt"
lines = []
for n, hits in found_map.items():
    lines.append(f"REL {n} n={len(hits)}")
    for h, sz in hits[:6]:
        lines.append(f"  {sz}\t{h}")
lines.append("\n=== non-stub filename hits ===")
for n, hits in name_hits.items():
    if not hits:
        continue
    lines.append(f"NAME {n} n={len(hits)}")
    for h, sz in hits[:8]:
        lines.append(f"  {sz}\t{h}")
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", out)
print("\n".join(lines[:80]))
