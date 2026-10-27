#!/usr/bin/env python3
"""Provision 18 leftover OVH boxes (1x r3-256 + 1x r3-128 per region)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ovh_rest import call

STAGE = Path(__file__).resolve().parent
WAVE = STAGE.parent
OUT = WAVE / "ovh-monitor" / "g1-ovh-instances.json"
PROJECT = "2ddd379532644116a91cbec582a73a68"
SSH_KEY = "6344497459335679633239794c57787659324673"

# region, name-a r3-256, name-c r3-128
REGIONS = [
    "GRA11",
    "WAW1",
    "DE1",
    "GRA9",
    "RBX-A",
    "EU-WEST-PAR",
    "UK1",
    "SBG5",
    "GRA7",
]


def pick_flavor(flavors: list[dict], name: str) -> str:
    for f in flavors:
        if f.get("name") == name and f.get("available") is not False:
            return str(f["id"])
    for f in flavors:
        if f.get("name") == name:
            return str(f["id"])
    raise RuntimeError(f"no flavor {name}")


def pick_image(images: list[dict]) -> str:
    names = {str(im.get("name") or ""): str(im["id"]) for im in images}
    for want in ("Ubuntu 22.04", "Ubuntu 24.04"):
        if want in names:
            return names[want]
    for im in images:
        n = str(im.get("name") or "")
        if n.startswith("Ubuntu 22.04") and "Baremetal" not in n and "NVIDIA" not in n:
            return str(im["id"])
    raise RuntimeError("no image")


def list_instances():
    rows = call("GET", f"/cloud/project/{PROJECT}/instance", endpoint="ovh-ca")
    return list(rows or []), "ovh-ca"


def main() -> int:
    try:
        existing, ep = list_instances()
    except Exception as exc:
        # try discover project
        print(f"list-instance-fail {exc}", flush=True)
        for ep_try in ("ovh-eu", "ovh-ca"):
            try:
                projs = call("GET", "/cloud/project", endpoint=ep_try)
                print("projects", ep_try, projs, flush=True)
            except Exception as e2:
                print("projects-fail", ep_try, e2, flush=True)
        return 1
    print(json.dumps({"existing_n": len(existing), "endpoint": ep}), flush=True)
    created = []
    for region in REGIONS:
        flavors = [
            f
            for f in call("GET", f"/cloud/project/{PROJECT}/flavor", endpoint=ep)
            if f.get("region") == region
        ]
        images = [
            im
            for im in call("GET", f"/cloud/project/{PROJECT}/image", endpoint=ep)
            if im.get("region") == region
        ]
        f256 = pick_flavor(flavors, "r3-256")
        f128 = pick_flavor(flavors, "r3-128")
        img = pick_image(images)
        slug = region.lower().replace("eu-west-", "")
        for sku, flavor, tag in (("a", f256, "r3-256"), ("c", f128, "r3-128")):
            name = f"p2-g1-{slug}-{sku}"
            body = {
                "flavorId": flavor,
                "imageId": img,
                "monthlyBilling": False,
                "name": name,
                "region": region,
                "sshKeyId": SSH_KEY,
            }
            print(f"CREATE {name} {region} {tag}", flush=True)
            try:
                rec = call("POST", f"/cloud/project/{PROJECT}/instance", body, endpoint=ep)
            except Exception as exc:
                print(f"FAILED {name} {exc}", flush=True)
                continue
            created.append({"name": name, "region": region, "sku": tag, "id": rec.get("id") if isinstance(rec, dict) else rec})
            print(json.dumps(created[-1]), flush=True)
    OUT.write_text(json.dumps({"ts": "now", "created": created, "existing": existing}, indent=2) + "\n", encoding="utf-8")
    print(f"SUCCESS:provision n={len(created)}", flush=True)
    return 0 if created else 1


if __name__ == "__main__":
    raise SystemExit(main())
