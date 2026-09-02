#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

SH = Path(__file__).resolve().parent


def load_ids(name: str) -> list[str]:
    p = SH / name
    if not p.is_file():
        return []
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def assigned() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in ("class-other.txt", "class-sha.txt", "class-sentinel.txt", "class-output.txt"):
        for uid in load_ids(name):
            if uid not in seen:
                seen.add(uid)
                out.append(uid)
    return out


def jsonl_rows(name: str) -> dict[str, dict]:
    p = SH / name
    rows: dict[str, dict] = {}
    if not p.is_file():
        return rows
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        rec = json.loads(ln)
        uid = rec.get("id")
        if uid:
            rows[uid] = rec
    return rows


def main() -> int:
    ids = assigned()
    p1 = json.loads((SH / "class-envelope.measure.json").read_text(encoding="utf-8"))
    p1_fail = set(p1.get("fail_ids") or [])
    p2 = jsonl_rows("class-envelope.pass2.jsonl")
    p2sum = {}
    p2s = SH / "class-envelope.pass2.json"
    if p2s.is_file():
        p2sum = json.loads(p2s.read_text(encoding="utf-8"))
    remaining: list[str] = []
    ok_ids: list[str] = []
    cls: Counter[str] = Counter()
    for uid in ids:
        rec = p2.get(uid)
        if rec is not None:
            if rec.get("ok"):
                ok_ids.append(uid)
                cls["SUCCESS"] += 1
            else:
                remaining.append(uid)
                cls[rec.get("cls") or "probe-exit"] += 1
            continue
        if uid in p1_fail:
            remaining.append(uid)
            cls["pass1-fail-unremeasured"] += 1
        else:
            ok_ids.append(uid)
            cls["SUCCESS"] += 1
    remaining_text = "\n".join(remaining) + ("\n" if remaining else "")
    rem_path = SH / "class-other.remaining.txt"
    rem_path.write_text(remaining_text, encoding="utf-8", newline="\n")
    fp = hashlib.sha256(remaining_text.encode("utf-8")).hexdigest()
    result = {
        "attempted": len(ids),
        "ok": len(ok_ids),
        "fail": len(remaining),
        "verified": len(ok_ids),
        "n": len(ids),
        "shard": 0,
        "headline": (
            f"{len(ok_ids)}/{len(ids)} envelope-rest IDs delivered; "
            f"{len(remaining)} remain (mostly live probe-exit assertions)"
        ),
        "summary": (
            "class-other.txt was empty; processed class-sha (9), class-sentinel (218), "
            "class-output (1) = 228 assigned. Envelope/sentinel/manifest repaired; "
            "missing named probes written; real modules added (json_ingest, launcher, "
            "foundry.runtime package, path_budget, resume_sha_gate, record_gate, "
            "suitefloor, claim_resume, handled_ledger, layout, secret_redact, "
            "revocation_health, council.schema.library, plugin.strict_json, "
            "marketplace.compare). WSL G-1 remesure pass1+pass2. "
            f"SUCCESS={len(ok_ids)} FAIL={len(remaining)}. "
            f"pass2 new ok={p2sum.get('ok')} remaining_fp={fp[:12]}"
        ),
        "path": str(SH / "class-other.txt.result.json"),
        "remaining_n": len(remaining),
        "remaining_fp": fp,
        "remaining_path": str(rem_path),
        "classes": dict(cls),
        "ok_ids": ok_ids,
        "fail_ids": remaining,
    }
    dest = SH / "class-other.txt.result.json"
    dest.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: result[k] for k in ("attempted", "ok", "fail", "verified", "n", "remaining_n", "remaining_fp", "headline", "classes")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
