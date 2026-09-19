#!/usr/bin/env python3
"""AUD-0074 Probe 1: citation-derived edges between the 29 Prompt-One artifacts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "fixtures" / "corpus"
META = HERE / "fixtures" / "corpus-meta.json"
AUD0067 = (
    Path(__file__).resolve().parents[3]
    / "audit"
    / "AUD-0067-prompt-one-artifact-census.json"
)

# Match backtick or bare basename citations of contract artifacts.
CITE_RE_TMPL = r"(?:`|\b)({names})(?:`|\b)"


def load_contract() -> list[str]:
    doc = json.loads(AUD0067.read_text(encoding="utf-8"))
    if doc.get("state") != "SUCCESS":
        raise SystemExit(
            f"FAILED:AUD-0074 dependency AUD-0067 state={doc.get('state')} "
            "(must be SUCCESS on disk before relying on it)"
        )
    names: list[str] = []
    for row in doc["extensions"]["inventory"]:
        a = row["artifact"]
        names.append("19-DIAGRAMS" if a.startswith("(") else a)
    return names


def iter_text_files(root: Path):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".md", ".json", ".txt", ".yml", ".yaml"}:
            continue
        yield p


def artifact_id_for(path: Path, corpus: Path, names: set[str]) -> str | None:
    rel = path.relative_to(corpus)
    # Top-level contract file
    if rel.parts[0] in names:
        return rel.parts[0]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-output", type=Path, required=True)
    ap.add_argument("--result-json", type=Path, required=True)
    args = ap.parse_args()

    names = load_contract()
    name_set = set(names)
    # Prefer longer names first so 07-OPTION-UNIVERSE.json wins over .md prefix clashes
    sorted_names = sorted(names, key=len, reverse=True)
    pattern = re.compile(
        CITE_RE_TMPL.format(names="|".join(re.escape(n) for n in sorted_names))
    )

    if not CORPUS.is_dir() or not any(CORPUS.iterdir()):
        raise SystemExit(
            "FAILED:AUD-0074-probe1 corpus missing; run fixtures/build_corpus.py first"
        )

    nodes = []
    for n in names:
        p = CORPUS / n
        nodes.append(
            {
                "id": n,
                "present": p.exists(),
                "is_dir": p.is_dir(),
                "bytes": (p.stat().st_size if p.is_file() else None),
            }
        )

    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()
    cite_hits = 0
    for path in iter_text_files(CORPUS):
        src = artifact_id_for(path, CORPUS, name_set)
        if src is None:
            # nested under 19-DIAGRAMS
            if path.parts[-2] == "19-DIAGRAMS":
                src = "19-DIAGRAMS"
            else:
                continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in pattern.finditer(text):
            dst = m.group(1)
            cite_hits += 1
            if dst == src:
                continue
            key = (src, dst)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                {
                    "from": src,
                    "to": dst,
                    "kind": "citation",
                    "evidence_file": str(path.relative_to(HERE)).replace("\\", "/"),
                    "match": m.group(0),
                }
            )

    meta = json.loads(META.read_text(encoding="utf-8")) if META.is_file() else {}
    result = {
        "unit": "AUD-0074",
        "probe": "probe1-citation-edges",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "aud0067_dependency_state": "SUCCESS",
        "corpus_root": "command-center/p2-wave/probes/AUD-0074/fixtures/corpus",
        "corpus_kind": meta.get("kind", "fixture-reconstruction"),
        "contract_items": len(names),
        "nodes_present": sum(1 for n in nodes if n["present"]),
        "citation_match_hits": cite_hits,
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "scope_note": meta.get("scope_note"),
        "ok": len(edges) > 0 and sum(1 for n in nodes if n["present"]) == 29,
    }

    raw_lines = [
        "AUD-0074 NAMED PROBE 1: citation-derived edges between artifacts",
        f"CAPTURED_AT={result['captured_at']}",
        "AUD0067_STATE=SUCCESS",
        f"CORPUS_KIND={result['corpus_kind']}",
        f"CONTRACT_ITEMS={result['contract_items']}",
        f"NODES_PRESENT={result['nodes_present']}",
        f"CITATION_MATCH_HITS={result['citation_match_hits']}",
        f"EDGE_COUNT={result['edge_count']}",
    ]
    for e in edges:
        raw_lines.append(f"EDGE|{json.dumps(e, sort_keys=True)}")
    raw_lines.append(f"PROBE1_OK={result['ok']}")
    raw_lines.append(
        "SUCCESS:AUD-0074-probe1" if result["ok"] else "FAILED:AUD-0074-probe1"
    )
    raw = "\n".join(raw_lines) + "\n"

    args.raw_output.write_text(raw, encoding="utf-8", newline="\n")
    args.result_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(raw, end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
