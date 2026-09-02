#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
RES = REPO / "command-center/p2-wave/ovh-monitor/g1-shards/class-schema.txt.result.json"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    res = json.loads(RES.read_text(encoding="utf-8"))
    print("result", res["attempted"], res["ok"], res["fail"], res["remaining_n"])
    bad = 0
    for row in res["verified_last_lines"]:
        uid, rel, sha, n = row["id"], row["artifact"], row["sha256"], row["bytes"]
        path = REPO / rel
        live, size = digest(path) if path.is_file() else ("MISSING", 0)
        man = json.loads(
            (REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json").read_text(
                encoding="utf-8"
            )
        )
        mrows = [
            a
            for a in man.get("artifacts") or []
            if a.get("unit_id") == uid and str(a.get("path") or "").replace("\\", "/") == rel
        ]
        msha = mrows[0].get("sha256") if mrows else None
        ok = path.is_file() and live == sha == msha and size == n
        print(uid, "OK" if ok else "DRIFT", "bytes", size, "man", bool(mrows))
        if not ok:
            bad += 1
            print("  live", live)
            print("  want", sha)
            print("  man ", msha)
    old = "https://ast-integrate.invalid/"
    n_old = n_file = n_files = 0
    samples = []
    for d in (REPO / "platform/schema", REPO / "command-center/schema"):
        for p in d.rglob("*.json"):
            t = p.read_text(encoding="utf-8")
            c1 = t.count(old)
            c2 = t.count("file://")
            if c1 or c2:
                n_files += 1
                n_old += c1
                n_file += c2
                if c1 and len(samples) < 6:
                    samples.append((str(p.relative_to(REPO)), c1, c2, t[t.find("$id") : t.find("$id") + 120] if "$id" in t else ""))
    print("schema_files_with_ids", n_files, "https_invalid", n_old, "file_scheme", n_file)
    for s in samples:
        print(" sample", s[0], "https", s[1], "file", s[2])
        print("  ", s[3][:160])
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
