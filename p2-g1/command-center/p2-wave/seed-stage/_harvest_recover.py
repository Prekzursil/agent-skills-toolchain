#!/usr/bin/env python3
"""Pull every still-useful file out of leftover tgz + box trees. No rglob of harvest."""
from __future__ import annotations

import json
import tarfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WAVE = REPO / "command-center" / "p2-wave"
PULL = WAVE / "ovh-monitor" / "delivery-pull"
MISS = WAVE / "ovh-monitor" / "missing-pull"
JSONL = WAVE / "ovh-monitor" / "g1-local-full.jsonl"
OUT = WAVE / "ovh-monitor" / "harvest-recover.json"

WANT_PREFIX = (
    "tools/",
    "platform/",
    "command-center/p2-wave/probes/",
    "command-center/receipts/",
    "command-center/adversarial/",
    "command-center/research/",
    "command-center/audit/",
    "command-center/schema/",
    "command-center/confirmation/",
    "command-center/wfa/",
    "command-center/synthesis/",
    "command-center/design/",
)


def fail_ids() -> set[str]:
    out: set[str] = set()
    if not JSONL.is_file():
        return out
    with JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("id") and not rec.get("ok"):
                out.add(rec["id"])
    return out


def tgzs() -> list[Path]:
    roots = [p for p in (PULL, MISS) if p.is_dir()]
    out: list[Path] = []
    for root in roots:
        for box in root.iterdir():
            if not box.is_dir():
                continue
            for name in ("p2-delivery.tgz", "p2-leftover-delta.tgz", "p2-delta.tgz"):
                p = box / name
                if p.is_file() and p.stat().st_size > 0:
                    out.append(p)
    return out


def copy_file(src: Path, dest: Path) -> bool:
    if not src.is_file() or src.stat().st_size <= 0:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size >= src.stat().st_size:
        return False
    dest.write_bytes(src.read_bytes())
    return True


def main() -> int:
    extracted = 0
    tools_hits: Counter[str] = Counter()
    probe_hits = 0
    scanned = 0
    errors: list[str] = []
    for tgz in tgzs():
        scanned += 1
        try:
            with tarfile.open(tgz, "r:gz") as tf:
                for m in tf.getmembers():
                    if not m.isfile() or m.size <= 0:
                        continue
                    name = m.name.replace("\\", "/").lstrip("./")
                    if name.startswith("opt/p2/ast-integrate/"):
                        name = name[len("opt/p2/ast-integrate/") :]
                    if not name.startswith(WANT_PREFIX):
                        continue
                    dest = REPO / name
                    if dest.is_file() and dest.stat().st_size >= m.size:
                        continue
                    try:
                        f = tf.extractfile(m)
                    except Exception:
                        continue
                    if f is None:
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(f.read())
                    extracted += 1
                    if name.startswith("tools/") and "/command-center/" not in name and "/fan_in/" not in name:
                        top = "/".join(name.split("/")[:3])
                        tools_hits[top] += 1
                    if "/probes/" in name and name.endswith(".py"):
                        probe_hits += 1
        except Exception as exc:
            errors.append(f"{tgz.parent.name}:{type(exc).__name__}:{exc}"[:160])
    # explicit box tree/delta copies for missing probe scripts
    fails = fail_ids()
    restored_named = 0
    for uid in sorted(fails):
        rel_dir = f"command-center/p2-wave/probes/{uid}"
        for root in (PULL, MISS):
            if not root.is_dir():
                continue
            for box in root.iterdir():
                if not box.is_dir():
                    continue
                for sub in ("tree", "delta"):
                    srcdir = box / sub / rel_dir
                    if not srcdir.is_dir():
                        continue
                    for src in srcdir.iterdir():
                        if not src.is_file():
                            continue
                        dest = REPO / rel_dir / src.name
                        if copy_file(src, dest):
                            restored_named += 1
    rec = {
        "tgz_scanned": scanned,
        "extracted": extracted,
        "probe_py_from_tgz": probe_hits,
        "restored_named_from_trees": restored_named,
        "extra_tools": dict(tools_hits.most_common(40)),
        "errors": errors[:20],
        "fail_ids": len(fails),
    }
    OUT.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rec), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
