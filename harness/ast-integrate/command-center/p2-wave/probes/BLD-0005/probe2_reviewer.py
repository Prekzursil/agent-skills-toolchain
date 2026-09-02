#!/usr/bin/env python3
"""Probe 2: independent reviewer samples five orphan verdicts and greps.

Includes non-Python callers (PowerShell Get-ItemProperty, YAML ${ENV}).
A product-code read site for a claimed orphan is detector-failure (FAIL).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import config_orphan as C  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0005.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:BLD-0005-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    reviewer = doc.get("reviewer") or {}
    samples = reviewer.get("samples") or []
    if len(samples) < 5:
        print(f"FAILED:BLD-0005-probe2 sample count {len(samples)} < 5")
        return 1
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        print("FAILED:BLD-0005-probe2 reviewer record not independent PASS")
        return 1

    fail = False
    for row in samples[:5]:
        key = str(row.get("key") or "")
        classification = str(row.get("classification") or "")
        if not key or classification != "ORPHAN":
            print(f"FAILED:BLD-0005-probe2 sample not an orphan verdict {row}")
            fail = True
            continue
        decl = (row.get("declaration_site") or {}).get("path") or ""
        skip = [decl] if decl else []
        hits = C.find_read_sites_for_key(REPO, key, skip_paths=skip)
        product_hits = [
            h
            for h in hits
            if not h.get("is_test")
            and not str(h.get("path") or "").replace("\\", "/").startswith(
                "command-center/p2-wave/probes/BLD-0005/"
            )
        ]
        # Own-unit probe tree may mention the planted key as a constant; that is
        # use-vs-mention. The reviewer looks for a real read site in product code.
        recorded = bool(row.get("read_site_found"))
        found = bool(product_hits)
        print(
            f"sample key={key} classification={classification} "
            f"product_read_hits={len(product_hits)} recorded_found={recorded}"
        )
        if found:
            print(json.dumps(product_hits[:3], indent=2)[:1500])
            print(f"FAILED:BLD-0005-probe2 orphan {key} has a product read site")
            fail = True
        if recorded:
            print(f"FAILED:BLD-0005-probe2 receipt claimed a read site for orphan {key}")
            fail = True

    # Re-grep PowerShell and YAML suffixes explicitly (catalog non-Python pivot).
    for row in samples[:5]:
        key = str(row.get("key") or "")
        for path in C.iter_files(
            REPO,
            skip_own_unit=False,
            skip_probe_tree=False,
            suffixes=frozenset({".ps1", ".psm1", ".yml", ".yaml"}),
        ):
            rel = C._rel(REPO, path)
            if rel.replace("\\", "/").startswith("command-center/p2-wave/probes/BLD-0005/"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if key not in text:
                continue
            if C.READ_SHAPED_RE.search(text) and key in text:
                # Confirm it is a read-shaped line, not a mention in a comment.
                for i, line in enumerate(text.splitlines(), 1):
                    if key in line and C.READ_SHAPED_RE.search(line) and not line.lstrip().startswith("#"):
                        print(
                            f"FAILED:BLD-0005-probe2 non-python read {key} at {rel}:{i}"
                        )
                        fail = True
                        break

    if fail:
        print("FAILED:BLD-0005-probe2 reviewer grep found a read site or bad sample")
        return 1
    print("SUCCESS:BLD-0005-probe2 five orphan verdicts grepped including PS/YAML")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
