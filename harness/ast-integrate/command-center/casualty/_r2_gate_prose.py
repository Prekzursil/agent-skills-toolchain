"""Print every field in the two receipts whose text mentions a gate condition id,
so the c1/c5/c3 scoping can be fixed at its source rather than only in the report."""

import json
import re
from pathlib import Path

CAS = Path("C:/Users/Prekzursil/source/ast-integrate/command-center/casualty")
PAT = re.compile(
    r"\bc(1|3|5|9|10|11)\b|family convention|fixed point|cannot be satisfied"
)


def walk(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(node, str):
        if PAT.search(node):
            yield path, node


for name in (
    "ADV-0021-install-path-stride-threat-model.json",
    "ADV-0022-declared-permission-escape.json",
):
    doc = json.loads((CAS / name).read_text(encoding="utf-8"))
    print(f"\n########## {name}")
    for path, text in walk(doc):
        if ".raw_output" in path:  # verbatim captures: never edit, only report
            print(f"  [VERBATIM-CAPTURE, do not edit] {path}  len={len(text)}")
            continue
        print(f"  {path}\n      {text[:700]}")
