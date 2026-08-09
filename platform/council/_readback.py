"""Read the lane's twelve protocol files back off disk and report what is actually there.

Separate from _validate_protocols.py on purpose: this asserts nothing about quality, it
just counts and inventories bytes on disk, so a "12 files" claim rests on a directory
walk rather than on the generator's own success message.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))

from councilspec.registry import load_schema  # noqa: E402

PROTOCOLS = os.path.join(HERE, "protocols")
MINE = [f"p{n}-" for n in range(37, 49)]


def main() -> int:
    schema = load_schema()
    all_controls = set(
        schema["$defs"]["anti_failure"]["properties"]["controls"]["items"]["enum"]
    )
    all_topologies = set(schema["$defs"]["topology"]["properties"]["kind"]["enum"])
    all_orders = set(
        schema["$defs"]["protocol"]["properties"]["speaking_order"]["enum"]
    )
    all_methods = set(schema["$defs"]["voting"]["properties"]["method"]["enum"])

    rows, used_controls, used_topo, used_order, used_method = (
        [],
        set(),
        set(),
        set(),
        set(),
    )
    crlf_files, total_bytes = [], 0
    for name in sorted(os.listdir(PROTOCOLS)):
        if not name.endswith(".councilspec.json"):
            continue
        if not any(name.lower().startswith(p) for p in MINE):
            continue
        path = os.path.join(PROTOCOLS, name)
        raw = open(path, "rb").read()
        total_bytes += len(raw)
        if b"\r\n" in raw:
            crlf_files.append(name)
        spec = json.loads(raw.decode("utf-8"))
        used_controls.update(spec["anti_failure"]["controls"])
        used_topo.add(spec["topology"]["kind"])
        used_order.add(spec["protocol"]["speaking_order"])
        # Recurse: a subcouncil IS a CouncilSpec and its voting method is really exercised.
        # Counting only top-level methods under-reported coverage (it called `majority` unused
        # while p46-sub-cost-and-operability votes by majority).
        stack = [spec]
        while stack:
            node = stack.pop()
            used_method.add(node["voting"]["method"])
            stack.extend((node.get("topology") or {}).get("subcouncils") or [])
        rows.append(
            (
                spec["council_id"],
                spec["topology"]["kind"],
                spec["protocol"]["speaking_order"],
                spec["voting"]["method"],
                f"{spec['protocol']['rounds']['min']}-{spec['protocol']['rounds']['max']}",
                len(spec["anti_failure"]["controls"]),
                len(spec["anti_failure"]["fast_unanimity_response"]),
                len(spec["participants"]["roster"]),
                len(spec["protocol"]["sequence"]),
                len(raw),
            )
        )

    hdr = (
        "council_id",
        "topology",
        "speaking_order",
        "voting",
        "rnds",
        "ctl",
        "fu",
        "seats",
        "stg",
        "bytes",
    )
    widths = [max(len(str(r[i])) for r in rows + [hdr]) for i in range(len(hdr))]
    print("  ".join(str(h).ljust(widths[i]) for i, h in enumerate(hdr)))
    for r in rows:
        print("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(r)))

    print(f"\nfiles read off disk         : {len(rows)}")
    print(f"total bytes                 : {total_bytes}")
    print(f"files containing CRLF       : {len(crlf_files)} {crlf_files}")
    print(
        f"topology kinds covered      : {len(used_topo)}/{len(all_topologies)}"
        f"  missing={sorted(all_topologies - used_topo)}"
    )
    print(
        f"speaking orders covered     : {len(used_order)}/{len(all_orders)}"
        f"  missing={sorted(all_orders - used_order)}"
    )
    print(
        f"voting methods covered      : {len(used_method)}/{len(all_methods)}"
        f"  missing={sorted(all_methods - used_method)}"
    )
    print(
        f"anti-failure controls used  : {len(used_controls)}/{len(all_controls)}"
        f"  missing={sorted(all_controls - used_controls)}"
    )

    ok = len(rows) == 12 and not crlf_files
    print(
        "SUCCESS:council-readback 12 files, LF-only"
        if ok
        else f"FAILED:council-readback rows={len(rows)} crlf={crlf_files}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
