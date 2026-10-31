#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SHARD = REPO / "command-center" / "p2-wave" / "ovh-monitor" / "g1-shards"
SEED = REPO / "command-center" / "p2-wave" / "seed-stage"
OUT = SEED / "_g1_handoff_verify.txt"


def load_ids(path: Path) -> list[str]:
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def loadj(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    ids = load_ids(SHARD / "class-mod.txt")
    rem_path = SHARD / "class-mod.remaining.txt"
    rem = load_ids(rem_path)
    raw = rem_path.read_bytes()
    a = loadj(SEED / "_g1_class_mod_measure.jsonl")
    b = loadj(SEED / "_g1_class_mod_remaining.jsonl")
    by = {r["id"]: r for r in a}
    for r in b:
        by[r["id"]] = r
    ok = [i for i in ids if by.get(i, {}).get("ok")]
    fail = [i for i in ids if i in by and not by[i].get("ok")]
    unmeasured = [i for i in ids if i not in by]
    new_ok = [
        r["id"]
        for r in b
        if r.get("ok") and not any(x["id"] == r["id"] and x.get("ok") for x in a)
    ]
    lines = [
        f"assigned={len(ids)} unique={len(set(ids))} first={ids[0]} last={ids[-1]}",
        f"remaining={len(rem)} unique={len(set(rem))} bytes={len(raw)} cr={raw.count(b'\\r')} first={rem[0]} last={rem[-1]}",
        "sha=" + hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        f"pass1 n={len(a)} uniq={len({r['id'] for r in a})} ok={sum(1 for r in a if r.get('ok'))} fail={sum(1 for r in a if not r.get('ok'))}",
        f"pass2 n={len(b)} uniq={len({r['id'] for r in b})} ok={sum(1 for r in b if r.get('ok'))} fail={sum(1 for r in b if not r.get('ok'))}",
        "AUD-0011=" + json.dumps(next(r for r in a if r["id"] == "AUD-0011")),
        "ARC-0064=" + json.dumps(next(r for r in a if r["id"] == "ARC-0064")),
        "CNF-0159=" + json.dumps(next(r for r in a if r["id"] == "CNF-0159")),
        f"idset_pass1_eq_assigned={ {r['id'] for r in a} == set(ids) }",
        f"unmeasured={unmeasured}",
        f"merge_ok={len(ok)} fail={len(fail)}",
        f"fail_eq_rem={fail == rem}",
        f"ok_eq_setdiff={set(ok) == set(ids) - set(rem)}",
        "ok_ids=" + " ".join(ok),
        "new_ok=" + " ".join(new_ok),
        "SUCCESS_lines="
        + str(sum(1 for i in ids if str(by[i].get("line") or "").startswith("SUCCESS:delivered "))),
        "FAILED_lines="
        + str(sum(1 for i in ids if str(by[i].get("line") or "").startswith("FAILED:delivered "))),
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(OUT)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
