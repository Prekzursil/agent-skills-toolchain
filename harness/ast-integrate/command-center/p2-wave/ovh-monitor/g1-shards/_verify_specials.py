#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
by = {u["id"]: u for u in cat["work_units"]}
IDS = [
    "CC-0009",
    "CNF-0004",
    "RES-0079",
    "ARC-0007",
    "ARC-0095",
    "CNF-0001",
    "ADV-0005",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    for uid in IDS:
        u = by[uid]
        rel = str(u["output_path"]).replace("\\", "/")
        out = REPO / rel
        sent = str(u.get("completion_sentinel") or "")
        manp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
        sha, n = digest(out)
        man = json.loads(manp.read_text(encoding="utf-8"))
        rows = [a for a in man.get("artifacts") or [] if a.get("unit_id") == uid]
        match = any(
            str(a.get("path") or "").replace("\\", "/") == rel
            and a.get("sha256") == sha
            and a.get("present") is True
            for a in rows
        )
        text = out.read_text(encoding="utf-8")
        doc = json.loads(text)
        print(
            f"{uid} bytes={n} sha_match={match} sent_in={sent in text} "
            f"state={doc.get('state')} nkeys={len(doc)}"
        )
        if uid == "RES-0079":
            print(
                "  method_table",
                type(doc.get("method_table")).__name__,
                "n",
                len(doc.get("method_table") or []),
                "zh",
                str(doc.get("zero_history_method"))[:80],
            )
        if uid == "CNF-0004":
            proof = doc.get("timestamp_proof") or {}
            sims = doc.get("simulations") or {}
            print(
                "  committed",
                doc.get("committed_at"),
                "predates",
                proof.get("threshold_predates_every_receipt"),
                "minus_fired",
                (sims.get("minus_epsilon") or {}).get("fired"),
                "plus_fired",
                (sims.get("plus_epsilon") or {}).get("fired"),
                "bound",
                (doc.get("expansion_bound") or {}).get("bounded"),
            )
        if uid == "CC-0009":
            am = json.loads((REPO / "command-center" / "ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
            hit = [
                a
                for a in am.get("artifacts") or []
                if str(a.get("path") or "").replace("\\", "/") == rel
            ]
            print(
                "  art-man-match",
                (hit[0].get("sha256") == sha) if hit else None,
                "first_key",
                (hit[0].get("first_parsed_key") if hit else None),
                "tests",
                [t.get("id") for t in (doc.get("tests") or []) if isinstance(t, dict)],
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
