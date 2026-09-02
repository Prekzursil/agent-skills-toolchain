#!/usr/bin/env python3
"""Probe 1: execute every documented flag against the installed binary."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import measure  # noqa: E402
from flags import INVENTED_FLAG  # noqa: E402


def main() -> int:
    data = measure()
    table = data["flag_table"]
    invented = data["invented"]
    help_longs = [o["long"] for o in data["binary"]["help_options"]]
    covered = {r["flag"] for r in table}

    if invented["verdict"] != "rejected":
        print("FAILED:RES-0015-probe1 invented flag was not rejected")
        print(json.dumps(invented, indent=2)[:1500])
        return 1
    if "unknown-option" not in invented["reason"]:
        print("FAILED:RES-0015-probe1 invented reason=" + invented["reason"])
        return 1

    missing_help = [f for f in help_longs if f not in covered]
    if missing_help:
        print("FAILED:RES-0015-probe1 help flags not executed: " + ",".join(missing_help))
        return 1

    n_acc = data["counts"]["accepted"]
    n_rej = data["counts"]["rejected"]
    if n_acc < 8:
        print(f"FAILED:RES-0015-probe1 too few accepted flags: {n_acc}")
        return 1
    if n_rej < 1:
        print("FAILED:RES-0015-probe1 detector did not reject anything")
        return 1

    # Print a compact accepted/rejected table (the catalog completion shape).
    print(
        "binary={path} version={version} help_sha256={help_sha256}".format(
            **{
                "path": data["binary"]["path"],
                "version": data["binary"]["version"],
                "help_sha256": data["binary"]["help_sha256"],
            }
        )
    )
    print("flag verdict reason sources kind")
    for row in table:
        src = ",".join(row["sources"]) or "-"
        print(f"{row['flag']} {row['verdict']} {row['reason']} {src} {row['kind']}")
    print(
        "counts executed={executed} accepted={accepted} rejected={rejected} "
        "doc_vs_binary={doc_vs_binary}".format(**data["counts"])
    )
    print(
        f"invented {INVENTED_FLAG} verdict={invented['verdict']} "
        f"stderr={invented['stderr_tail']!r}"
    )
    cache = HERE / "last-measure.json"
    cache.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print("SUCCESS:RES-0015-probe1 flag-by-flag accepted/rejected table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
