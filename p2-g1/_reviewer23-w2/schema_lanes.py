#!/usr/bin/env python3
"""Schema lanes for shard 23 units: (a) canonical whole-file (receipt_core),
(b) pointered strict def (unit's declared artifact class). Fail-closed census."""
import json
from pathlib import Path

import jsonschema

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
with open(REPO / "_p2shard23-w2-entries.json", encoding="utf-8") as f:
    cat = json.load(f)

for uid, e in cat.items():
    ref = str(e["output_schema"])
    filepart, _, pointer = ref.partition("#")
    spath = REPO / filepart
    with open(spath, encoding="utf-8") as f:
        whole = json.load(f)
    with open(REPO / e["output_path"], encoding="utf-8") as f:
        payload = json.load(f)
    line = [uid, "%s%s" % (spath.name, pointer)]
    # (a) canonical whole-file lane (fragment ignored, receipt_core)
    try:
        jsonschema.validate(payload, whole)
        line.append("core=PASS")
    except jsonschema.ValidationError as exc:
        line.append("core=FAIL:%s" % exc.message[:120])
    # (b) pointered def lane
    if pointer:
        node = whole
        for tok in pointer.lstrip("#/").split("/"):
            node = node[tok.replace("~1", "/").replace("~0", "~")]
        if isinstance(node, dict) and "$ref" in node:
            wrapped = dict(whole)
            wrapped["$ref"] = node["$ref"]
            schema = wrapped
        else:
            schema = {**whole, **node}
        try:
            jsonschema.validate(payload, schema)
            line.append("ptr=PASS")
        except jsonschema.ValidationError as exc:
            line.append("ptr=FAIL:%s" % exc.message[:120])
    else:
        line.append("ptr=n/a")
    print(" | ".join(line))
