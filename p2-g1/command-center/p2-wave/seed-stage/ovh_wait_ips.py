#!/usr/bin/env python3
"""Wait until all p2-g1-* OVH instances have a public IPv4."""
from __future__ import annotations

import json
import time
from pathlib import Path

from ovh_rest import call

PROJECT = "2ddd379532644116a91cbec582a73a68"
OUT = Path(__file__).resolve().parents[1] / "ovh-monitor" / "g1-ovh-ips.json"


def ipv4(inst: dict) -> str | None:
    for ip in inst.get("ipAddresses") or []:
        if ip.get("version") == 4 and ip.get("type") in {None, "public", "public_ovh"}:
            v = ip.get("ip")
            if v and not str(v).startswith("10."):
                return str(v)
    for ip in inst.get("ipAddresses") or []:
        if ip.get("version") == 4:
            return str(ip.get("ip"))
    return None


def main() -> int:
    for _ in range(60):
        rows = call("GET", f"/cloud/project/{PROJECT}/instance", endpoint="ovh-ca") or []
        mine = [r for r in rows if str(r.get("name") or "").startswith("p2-g1-")]
        recs = []
        for r in mine:
            recs.append(
                {
                    "name": r.get("name"),
                    "id": r.get("id"),
                    "status": r.get("status"),
                    "region": r.get("region"),
                    "ip": ipv4(r),
                    "flavor": (r.get("flavor") or {}).get("name") if isinstance(r.get("flavor"), dict) else r.get("flavorId"),
                }
            )
        up = [x for x in recs if x["status"] == "ACTIVE" and x["ip"]]
        print(json.dumps({"n": len(recs), "active_ip": len(up)}), flush=True)
        OUT.write_text(json.dumps({"boxes": recs}, indent=2) + "\n", encoding="utf-8")
        if len(up) >= 18:
            print("SUCCESS:ips 18", flush=True)
            return 0
        time.sleep(15)
    print("FAILED:ips-timeout", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
