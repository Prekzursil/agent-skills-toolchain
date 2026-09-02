#!/usr/bin/env python3
"""Shard-13 remaining units, isolated sys.path per fix."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def refresh_manifest(uid: str, paths: list[str]) -> None:
    mp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(mp.read_text(encoding="utf-8"))
    wanted = set(paths)
    seen = set()
    for row in man.get("artifacts") or []:
        rel = str(row.get("path") or "").replace("\\", "/")
        if rel not in wanted:
            continue
        p = REPO / rel
        sha, size = digest_file(p)
        row["sha256"] = sha
        row["bytes"] = size
        row["present"] = p.is_file()
        seen.add(rel)
        print(f"  manifest {uid} {rel} sha={sha[:12]} bytes={size}")
    missing = wanted - seen
    if missing:
        print(f"  NOT-IN-MANIFEST {uid}: {sorted(missing)}")
    mp.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")


def isolate(paths: list[Path]) -> None:
    for key in list(sys.modules):
        if key in {
            "scenario",
            "contract",
            "fingerprint",
            "load",
            "runtime",
            "desc_lint",
            "calibrate",
            "bands",
            "live_join",
            "fixtures",
            "join",
        }:
            sys.modules.pop(key, None)
    sys.path[:] = [str(p) for p in paths] + [
        p for p in sys.path if Path(p) not in paths
    ]


def fix_imp0234() -> None:
    print("=== IMP-0234 ===")
    here = REPO / "command-center/p2-wave/probes/IMP-0234"
    libdir = REPO / "command-center/blueprints/research"
    isolate([here, libdir])
    import scenario as S  # noqa: E402
    from fingerprint import fingerprint  # noqa: E402
    from load import load_library  # noqa: E402

    lib = load_library()
    fps = {bp_id: fingerprint(lib[bp_id]) for bp_id in lib}
    rel = S.RECEIPT_REL
    path = REPO / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    em = doc.setdefault("evidence_measurements", {})
    em["fingerprints"] = fps
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"  sys={fps['systematic-literature-review'][:12]} "
        f"rap={fps['rapid-literature-review'][:12]}"
    )
    refresh_manifest("IMP-0234", [rel])


def fix_imp0388() -> None:
    print("=== IMP-0388 ===")
    isolate([REPO / "tools" / "router"])
    import desc_lint as L  # noqa: E402

    index = REPO / "command-center/p2-wave/probes/IMP-0388/fixtures/capability-index.json"
    caps, _loaded = L.load_index(index)
    live = L.lint(caps, top_n=20)
    rel = "command-center/receipts/IMP-0388.json"
    path = REPO / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["zero_negative_scope"] = live["zero_negative_scope"]
    doc["confusability"] = live["confusability"]
    rpt = doc.get("report")
    if isinstance(rpt, dict):
        rpt["zero_negative_scope"] = live["zero_negative_scope"]
        rpt["confusability"] = live["confusability"]
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"  zeros={live['zero_negative_scope']['count']} "
        f"top20={len(live['confusability']['top_20'])}"
    )
    refresh_manifest("IMP-0388", [rel])


def fix_syn0035() -> None:
    print("=== SYN-0035 ===")
    isolate([REPO / "command-center/p2-wave/probes/SYN-0035"])
    from calibrate import run_calibration  # noqa: E402

    cal = run_calibration(REPO)
    rel = "command-center/synthesis/SYN-0035.calibration-report.json"
    path = REPO / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["live_bands"] = cal["live_bands"]
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    ac = next(r for r in cal["live_bands"] if r["band"] == "almost-certain")
    print(f"  live almost-certain n={ac['n']}")
    refresh_manifest("SYN-0035", [rel])


def fix_tst0124() -> None:
    print("=== TST-0124 ===")
    isolate([REPO / "command-center/p2-wave/probes/TST-0124"])
    from join import live_census  # noqa: E402

    live = live_census()
    rel = "command-center/receipts/TST-0124.json"
    path = REPO / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    join_table = [
        {"suite": r["suite"], "classification": r["classification"]}
        for r in live["join"]
    ]
    doc["join_table"] = join_table
    doc["ungated_count"] = live["ungated_count"]
    doc["ungated_suites"] = live["invariants"]["ungated_suites"]
    rpt = doc.get("report")
    if isinstance(rpt, dict):
        rpt["join_table"] = join_table
        rpt["ungated_count"] = live["ungated_count"]
        rpt["ungated_suites"] = live["invariants"]["ungated_suites"]
    path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"  suites={live['suite_count']} gated={live['gated_count']} "
        f"ungated={live['ungated_count']}"
    )
    refresh_manifest("TST-0124", [rel])


def main() -> int:
    fix_imp0234()
    fix_imp0388()
    fix_syn0035()
    fix_tst0124()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
