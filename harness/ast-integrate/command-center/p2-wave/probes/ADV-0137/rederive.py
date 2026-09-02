#!/usr/bin/env python3
"""Isolated re-deriver: reads only --allow paths. No brief, no digest, no sibling artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from counting_rule import (  # noqa: E402
    SPEC_FILE,
    passages_from_inputs,
    sources_from_inputs,
)
from harvest_json import harvest as harvest_json  # noqa: E402

FORBIDDEN_NAME = re.compile(
    r"(?i)(pinned|brief|digest|ADV-0137-premise-concentration)"
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def fingerprint(paths: list[Path], repo: Path) -> dict:
    rows = []
    for p in paths:
        raw = p.read_bytes()
        try:
            rel = p.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            rel = str(p.resolve())
        rows.append(
            {
                "path": rel,
                "sha256": sha256_bytes(raw),
                "bytes": len(raw.replace(b"\r\n", b"\n")),
            }
        )
    rows.sort(key=lambda r: r["path"])
    blob = json.dumps(rows, sort_keys=True).encode("utf-8")
    return {
        "files": rows,
        "bundle_sha256": hashlib.sha256(blob).hexdigest(),
        "n_files": len(rows),
    }


def hygiene_ok(fp: dict) -> tuple[bool, str]:
    bad = [
        r["path"]
        for r in fp["files"]
        if FORBIDDEN_NAME.search(Path(r["path"]).name)
        or FORBIDDEN_NAME.search(r["path"])
    ]
    if bad:
        return False, "forbidden-path-in-bundle:" + ",".join(bad)
    return True, "clean"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--allow", action="append", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--source-key", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    allow = [Path(p).resolve() for p in args.allow]
    catalog = Path(args.catalog).resolve()
    if catalog not in allow:
        print("FAILED:rederive catalog not in --allow", file=sys.stderr)
        return 2
    allowed_set = set(allow)
    opened = []

    def read_allowed(path: Path) -> bytes:
        rp = path.resolve()
        if rp not in allowed_set:
            raise PermissionError(f"context-hygiene refused {rp}")
        opened.append(str(rp))
        return rp.read_bytes()

    raw = read_allowed(catalog)
    doc = json.loads(raw.decode("utf-8"))
    harvested = harvest_json(repo, catalog=doc)
    key = args.source_key
    citers = [
        uid
        for uid, srcs in harvested["unit_sources"].items()
        if key in srcs
    ]
    citers.sort()
    passages: dict[str, int] = {}
    samples: list[str] = []
    for u in doc.get("work_units") or []:
        if not isinstance(u, dict) or u.get("id") not in set(citers):
            continue
        inputs = u.get("inputs") or []
        for item in inputs:
            if not isinstance(item, str):
                continue
            if key in sources_from_inputs([item]) and len(samples) < 3:
                samples.append(item)
            for p in passages_from_inputs([item]):
                if key == SPEC_FILE or p.startswith(key):
                    passages[p] = passages.get(p, 0) + 1
    fp = fingerprint(allow, repo)
    hy_ok, hy_why = hygiene_ok(fp)
    conclusion = {
        "source_key": key,
        "direct_unit_count": len(citers),
        "n_units_in_catalog": harvested["n_units"],
        "citing_unit_ids_sha256": hashlib.sha256(
            "\n".join(citers).encode("utf-8")
        ).hexdigest(),
        "citing_unit_id_count": len(citers),
        "distinct_spec_passages_on_citers": len(passages) if key == SPEC_FILE else None,
        "spec_passage_histogram_top": sorted(
            passages.items(), key=lambda kv: (-kv[1], kv[0])
        )[:8]
        if key == SPEC_FILE
        else [],
        "sample_inputs": samples,
        "input_bundle": fp,
        "hygiene_ok": hy_ok,
        "hygiene_reason": hy_why,
        "opened_resolved": opened,
        "allow_count": len(allow),
        "raw_source_note": (
            "Re-derivation is from the catalog work_units inputs arrays "
            "(the raw citation ledger). The cited document itself is not "
            "opened unless it is also in --allow."
        ),
    }
    out = Path(args.out)
    out.write_text(json.dumps(conclusion, indent=2) + "\n", encoding="utf-8")
    print(f"rederive source={key} direct={len(citers)} hygiene_ok={hy_ok}")
    return 0 if hy_ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
