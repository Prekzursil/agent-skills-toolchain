#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
JL = HERE / "_shard11_measure.jsonl"
MOD = re.compile(r"No module named ['\"]([^'\"]+)['\"]")
FILE = re.compile(r"No such file or directory: ['\"]([^'\"]+)['\"]")
ASSERT = re.compile(r"AssertionError: (.+)$")
FAILED = re.compile(r"FAILED:[A-Z0-9-]+(?:-probe\d)?\s+(.+)$")
IMPORT = re.compile(r"cannot import name ['\"]([^'\"]+)['\"]")
ATTR = re.compile(r"has no attribute ['\"]([^'\"]+)['\"]")


def classify(tail: str) -> tuple[str, str]:
    t = tail or ""
    last_fail = ""
    for ln in t.splitlines():
        s = ln.strip()
        if (
            "Error" in s
            or s.startswith("FAILED:")
            or "AssertionError" in s
            or "ModuleNotFound" in s
            or "Traceback" in s
        ):
            last_fail = s[:300]
    m = MOD.search(t)
    if m:
        return "mod:" + m.group(1), last_fail or t[-240:]
    m = IMPORT.search(t)
    if m:
        return "importname:" + m.group(1), last_fail or t[-240:]
    m = ATTR.search(t)
    if m:
        return "attr:" + m.group(1), last_fail or t[-240:]
    m = FILE.search(t)
    if m:
        return "file:" + m.group(1), last_fail or t[-240:]
    if "AssertionError" in t:
        m = ASSERT.search(t)
        return "assert", (m.group(1)[:240] if m else last_fail) or t[-240:]
    m = FAILED.search(t)
    if m:
        return "failedmsg", m.group(1)[:240]
    if "jsonschema" in t.lower() or "$ref" in t:
        return "schema", last_fail or t[-240:]
    if "PermissionError" in t:
        return "perm", last_fail or t[-240:]
    return "other", last_fail or t[-240:]


def main() -> None:
    rows = []
    for ln in JL.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        rec = json.loads(ln)
        if rec.get("ok"):
            rec["cls"] = "SUCCESS"
            rec["detail"] = ""
        else:
            cls, detail = classify(rec.get("tail") or "")
            rec["cls"] = cls
            rec["detail"] = detail
        rows.append(rec)
    ctr = Counter(r["cls"] for r in rows)
    payload = {
        "n": len(rows),
        "ok": sum(1 for r in rows if r.get("ok")),
        "fail": sum(1 for r in rows if not r.get("ok")),
        "classes": dict(ctr),
        "fails": [
            {
                "id": r["id"],
                "last": r.get("last"),
                "cls": r["cls"],
                "detail": r["detail"],
                "tail8": "\n".join((r.get("tail") or "").splitlines()[-10:]),
            }
            for r in rows
            if not r.get("ok")
        ],
    }
    dest = HERE / "_shard11_reasons.json"
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("ok", payload["ok"], "fail", payload["fail"])
    print("classes", json.dumps(ctr, indent=2))
    for f in payload["fails"]:
        print(f"{f['id']:10} {f['cls']:28} {f['detail'][:140]}")


if __name__ == "__main__":
    main()
