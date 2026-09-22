#!/usr/bin/env python3
"""AUD-0074 Probe 2: timestamp ordering check per citation edge.

Flags citations pointing at a source version that predates a known correction.
The citation graph alone cannot see staleness — this probe adds mtime/as-of
ordering against the known 2026-08-07 doc-13 correction.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "fixtures" / "corpus"
META = HERE / "fixtures" / "corpus-meta.json"
VERSIONS = HERE / "fixtures" / "versions"

DOC13 = "13-ARCHITECTURE-CANDIDATES.md"
CORRECTION_AT = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def artifact_mtime(name: str) -> float | None:
    p = CORPUS / name
    if p.is_file():
        return p.stat().st_mtime
    if p.is_dir():
        return p.stat().st_mtime
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-output", type=Path, required=True)
    ap.add_argument("--result-json", type=Path, required=True)
    ap.add_argument(
        "--edges-json",
        type=Path,
        default=HERE / "probe1-citation-edges.json",
    )
    args = ap.parse_args()

    p1 = json.loads(args.edges_json.read_text(encoding="utf-8"))
    edges = p1.get("edges") or []
    meta = json.loads(META.read_text(encoding="utf-8")) if META.is_file() else {}
    correction_epoch = CORRECTION_AT.timestamp()

    # Known corrections registry (extensible). Doc-13 is the catalog-named case.
    corrections = {
        DOC13: {
            "correction_at": CORRECTION_AT.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "correction_epoch": correction_epoch,
            "pre_path": str(
                (VERSIONS / f"{DOC13}.pre-correction").relative_to(HERE)
            ).replace("\\", "/"),
            "post_path": str(
                (VERSIONS / f"{DOC13}.post-correction").relative_to(HERE)
            ).replace("\\", "/"),
            "note": "F-B-02 M-NN -> MECH-NN re-prefix applied 2026-08-07",
        }
    }

    flags: list[dict] = []
    edge_checks: list[dict] = []
    for e in edges:
        src = e["from"]
        dst = e["to"]
        src_mtime = artifact_mtime(src)
        dst_mtime = artifact_mtime(dst)
        corr = corrections.get(dst)
        stale = False
        reason = None
        if corr is not None and src_mtime is not None:
            # Citer last written before the source correction → points at a
            # pre-correction version of the source (citation graph alone misses this).
            if src_mtime < corr["correction_epoch"]:
                stale = True
                reason = (
                    f"citer_mtime={iso(src_mtime)} < "
                    f"source_correction_at={corr['correction_at']}"
                )
        check = {
            "from": src,
            "to": dst,
            "citer_mtime": iso(src_mtime) if src_mtime is not None else None,
            "source_mtime": iso(dst_mtime) if dst_mtime is not None else None,
            "source_has_known_correction": corr is not None,
            "stale_downstream": stale,
            "reason": reason,
        }
        edge_checks.append(check)
        if stale:
            flags.append(
                {
                    "flag": "stale-downstream",
                    "from": src,
                    "to": dst,
                    "reason": reason,
                    "correction_at": corr["correction_at"],
                }
            )

    doc13_flags = [f for f in flags if f["to"] == DOC13]
    result = {
        "unit": "AUD-0074",
        "probe": "probe2-timestamp-ordering",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "known_corrections": corrections,
        "edges_checked": len(edge_checks),
        "stale_downstream_flag_count": len(flags),
        "doc13_stale_downstream_flag_count": len(doc13_flags),
        "edge_checks": edge_checks,
        "stale_downstream_flags": flags,
        "corpus_kind": meta.get("kind", "fixture-reconstruction"),
        "ok": len(edge_checks) > 0,
    }

    raw_lines = [
        "AUD-0074 NAMED PROBE 2: timestamp ordering check per citation edge",
        f"CAPTURED_AT={result['captured_at']}",
        f"DOC13_CORRECTION_AT={corrections[DOC13]['correction_at']}",
        f"EDGES_CHECKED={result['edges_checked']}",
        f"STALE_DOWNSTREAM_FLAGS={result['stale_downstream_flag_count']}",
        f"DOC13_STALE_FLAGS={result['doc13_stale_downstream_flag_count']}",
    ]
    for f in flags:
        raw_lines.append(f"STALE|{json.dumps(f, sort_keys=True)}")
    raw_lines.append(f"PROBE2_OK={result['ok']}")
    raw_lines.append(
        "SUCCESS:AUD-0074-probe2" if result["ok"] else "FAILED:AUD-0074-probe2"
    )
    raw = "\n".join(raw_lines) + "\n"

    args.raw_output.write_text(raw, encoding="utf-8", newline="\n")
    args.result_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(raw, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
