#!/usr/bin/env python3
"""Final ADV-0033 emit patches: drop disallowed 'result' from negative_control row 2;
reviewer vendor -> enum value; disclose the instrument-closure caveat."""
from pathlib import Path

P = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/ADV-0033/build_artifact.py")
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)

# 1. negative_controls row 2: drop the 'result' key (2 lines: key + its long value)
start = next(i for i, ln in enumerate(lines)
             if '"id": "namespace-isolator-goes-red"' in ln)
res = next(i for i in range(start, start + 12)
           if '"result":' in lines[i])
depth = lines[res].count("(") - lines[res].count(")")
end = res
while depth > 0:
    end += 1
    depth += lines[end].count("(") - lines[end].count(")")
end += next((i for i in range(end + 1, end + 12)
             if lines[i].strip().startswith('"note"') or lines[i].strip().startswith('"description"')), end + 1)
# find the next sibling key after result-value block: scan until line strip-startswith '"description"'
desc = next(i for i in range(res, start + 30)
            if lines[i].strip().startswith('"description"'))
del lines[res:desc]
# 2. reviewer vendor + honesty note
t = "".join(lines)
t = t.replace(
    '"vendor": "openai-style-cross-probe",',
    '"vendor": "local",'
)
t = t.replace(
    '"notes": (\n                "Probe 2 re-derives the untrusted-code destination from "',
    '"notes": (\n                "Instrument closure: probe 2 re-derives the untrusted-code destination from "',
)
t = t.replace(
    '"matrix. It does not take probe 1\'s prose as input."',
    '"matrix. It does not take probe 1\'s prose as input. Instrument-level '
    'closure only: the program-level independent reviewer closure lives on '
    'the unit RECEIPT (state=BLOCKED, reviewer-absent)."',
)
P.write_text(t, encoding="utf-8", newline="")
print("patched c")
