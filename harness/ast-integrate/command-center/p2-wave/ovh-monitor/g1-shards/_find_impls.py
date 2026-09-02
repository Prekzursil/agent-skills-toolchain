#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"C:\Users\Prekzursil\source\ast-integrate")
needles = [
    "command-center/lib/overfit_detector.py",
    "command-center/lib/overfit_detector/__init__.py",
    "command-center/lib/overfit_detector/detector.py",
    "command-center/lib/overfit_detector/corpus.py",
    "command-center/lib/overfit_detector/partition.py",
    "command-center/lib/overfit_detector/workflows.py",
    "command-center/lib/overfit_detector/threshold.py",
    "command-center/blueprint_library/__init__.py",
    "command-center/blueprint_library/taxonomy.py",
    "command-center/blueprint_library/catalog.py",
    "command-center/blueprint_library/fingerprint.py",
    "command-center/blueprint_library/library.py",
    "command-center/blueprint_library/gate.py",
    "tools/blueprint_library.py",
    "tools/blueprint_library/__init__.py",
    "tools/wfa_injection_gate.py",
    "tools/wfa_injection_gate/__init__.py",
    "tools/wfa_injection_gate/gate.py",
    "tools/wfa_injection_gate/corpus.py",
    "tools/wfa_injection_gate/consumer.py",
    "tools/detectors/two_state.py",
    "tools/detectors/census.py",
    "tools/workflow_foundry/tool_requirements.py",
    "tools/agentspec/agentspec/cachekey.py",
    "tools/publishing.py",
    "tools/filename_gate.py",
]
hosts = [
    ROOT,
]
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

print("hosts", len(hosts))
for needle in needles:
    found = []
    for host in hosts:
        p = host / needle
        if p.is_file():
            found.append(str(p.relative_to(ROOT)).replace("\\", "/") + f" bytes={p.stat().st_size}")
    marker = "YES" if found else "NO "
    print(f"{marker} {needle}")
    for f in found[:8]:
        print("   ", f)

# also probe-local helpers
print("\n=== probe-local ===")
probes = ROOT / "command-center/p2-wave/probes"
for uid in ["IMP-0141", "IMP-0167", "IMP-0206", "IMP-0232", "WFA-0121", "TST-0018", "TST-0199"]:
    d = probes / uid
    print(uid, sorted(p.name for p in d.iterdir() if p.suffix in {".py", ".json"} or p.is_dir()))
