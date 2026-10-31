#!/usr/bin/env python3
"""Normalize _shard11_w2_finish.py names to the EXACT literals the measure
script requires, extracted mechanically from _measure_one_delivered.py."""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent
MEASURE = (REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py").read_text(encoding="utf-8")

# 1. Extract exact probe-dir file names from the measure source.
ret_m = re.search(r'ret_path\s*=\s*probe_dir\s*/\s*"([^"]+)"', MEASURE)
man_m = re.search(r'man_path\s*=\s*probe_dir\s*/\s*"([^"]+)"', MEASURE)
assert ret_m and man_m, "could not extract names from measure source"
RET_NAME = ret_m.group(1)
MAN_NAME = man_m.group(1)
print("exact names required by measure:", repr(RET_NAME), repr(MAN_NAME))

# 2. Extract the exact env var name the measure sets.
env_m = re.search(r'env\["([A-Z_]+)"\]\s*=\s*"1"', MEASURE)
assert env_m, "could not extract env var name"
ENV_NAME = env_m.group(1)
print("exact env var:", repr(ENV_NAME))

DRV = REPO / "_shard11_w2_finish.py"
c = DRV.read_text(encoding="utf-8")

# Normalize every variant of those names in the driver to the exact literals.
c = re.sub(r'SUB[A-Z]+(?:-[A-Z]+)*-RETURN\.json', RET_NAME, c)
c = re.sub(r'UNIT-ARTIFACT-MANIFEST\.json', MAN_NAME, c)
c = re.sub(r'UNIT-[A-Z]+-MANIFEST\.json', MAN_NAME, c)
c = re.sub(r'PYTHONDONTWRITEBYTECODE', ENV_NAME, c)
c = re.sub(r'PYTHONDONTWRITEBYTECODE', ENV_NAME, c)
c = re.sub(r'PYTHONDONTWRITEBYTECODE', ENV_NAME, c)

# Normalize the probes dir path fragment and repo-fragment used in commands/paths.
c = re.sub(r'command-center/p2-wave/probes/', 'command-center/p2-wave/probes/', c)
c = re.sub(r'command-center/p2-wave/probes/', 'command-center/p2-wave/probes/', c)
c = re.sub(r'command-center/p2-wave/probes/\{uid\}', 'command-center/p2-wave/probes/{uid}', c)
c = re.sub(r'"command-center", "p2-wave", "probes"', '"command-center", "p2-wave", "probes"', c)

DRV.write_text(c, encoding="utf-8", newline="\n")

# 3. Assert the normalized file carries the exact literals.
c2 = DRV.read_text(encoding="utf-8")
for needle in (RET_NAME, MAN_NAME, ENV_NAME, "command-center/p2-wave/probes/{uid}"):
    n = c2.count(needle)
    assert n >= 1, f"missing exact literal {needle!r}"
    print(f"present x{n}: {needle!r}")

compile(c2, str(DRV), "exec")
print("SUCCESS:shard11 driver normalized + compiles")
