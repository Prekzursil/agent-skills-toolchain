#!/usr/bin/env python3
"""REL-0011 fixture release + the four catalog mutation controls.

Clean subject is fixtures/release packed then unpacked (archive, not the
source tree). Mutations run on copies.
"""
from __future__ import annotations

import json
import shutil
import tarfile
import tempfile
from pathlib import Path

import diff as D
import generator as G
import resolver as R

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "release"
PLANTED_NAME = "planted-undeclared"
PLANTED_VER = "0.0.1"
PLANTED_PURL = f"pkg:generic/{PLANTED_NAME}@{PLANTED_VER}"
PHANTOM_PURL = "pkg:npm/phantom-not-shipped@9.9.9"
DELETE_PURL = "pkg:npm/tiny-pkg@1.0.0"


def copy_fixture(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(FIXTURE, dest)
    return dest


def pack_and_unpack(src: Path, work: Path) -> Path:
    archive = work / "ast-release.tar.gz"
    unpacked = work / "unpacked"
    if unpacked.exists():
        shutil.rmtree(unpacked)
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(src, arcname="release")
    with tarfile.open(archive, "r:gz") as tf:
        kwargs = {}
        if hasattr(tarfile, "data_filter"):
            kwargs["filter"] = "data"
        tf.extractall(unpacked, **kwargs)
    root = unpacked / "release"
    if not root.is_dir():
        raise RuntimeError("archive did not contain release/")
    return root


def gate(release_root: Path) -> dict:
    bom = G.generate(release_root)
    closure = R.resolve(release_root)
    report = D.bidirectional(bom.get("components") or [], closure.get("components") or [])
    report["bom"] = bom
    report["closure_report"] = closure
    report["walked_depth"] = int(closure.get("walked_depth") or 0)
    report["not_checked"] = list(closure.get("not_checked") or [])
    report["generator_tool"] = G.TOOL_NAME
    report["resolver_tool"] = R.TOOL_NAME
    report["tools_distinct"] = G.TOOL_NAME != R.TOOL_NAME
    return report


def plant_undeclared(root: Path) -> Path:
    planted = root / "vendor" / "planted-crate"
    planted.mkdir(parents=True, exist_ok=True)
    (planted / "component.json").write_text(
        json.dumps({"name": PLANTED_NAME, "version": PLANTED_VER}, indent=2) + "\n",
        encoding="utf-8",
    )
    return planted


def hand_delete_bill(bom: dict, purl: str) -> dict:
    kept = [c for c in (bom.get("components") or []) if c.get("purl") != purl]
    if len(kept) == len(bom.get("components") or []):
        raise RuntimeError(f"hand-delete missed {purl}")
    out = dict(bom)
    out["components"] = kept
    return out


def add_phantom(bom: dict, purl: str) -> dict:
    name, version = purl.split("/")[-1].split("@", 1)
    comps = list(bom.get("components") or [])
    comps.append(
        {
            "type": "library",
            "name": name,
            "version": version,
            "purl": purl,
            "bom-ref": purl,
        }
    )
    out = dict(bom)
    out["components"] = comps
    return out


def control_undeclared() -> dict:
    with tempfile.TemporaryDirectory(prefix="rel0011-u-") as tmp:
        work = Path(tmp)
        src = copy_fixture(work / "src")
        plant_undeclared(src)
        root = pack_and_unpack(src, work)
        g = gate(root)
        fired = PLANTED_PURL in g["closure_minus_bill"]
        return {
            "id": "undeclared-vendored",
            "direction": "closure_minus_bill",
            "fired": fired,
            "hit": PLANTED_PURL,
            "closure_minus_bill": g["closure_minus_bill"],
            "bill_minus_shipped": g["bill_minus_shipped"],
            "pass": fired and g["counts"]["closure_minus_bill"] >= 1,
        }


def control_hand_delete() -> dict:
    with tempfile.TemporaryDirectory(prefix="rel0011-d-") as tmp:
        work = Path(tmp)
        src = copy_fixture(work / "src")
        root = pack_and_unpack(src, work)
        bom = G.generate(root)
        closure = R.resolve(root)
        mutated = hand_delete_bill(bom, DELETE_PURL)
        g = D.bidirectional(mutated.get("components") or [], closure.get("components") or [])
        fired = DELETE_PURL in g["closure_minus_bill"]
        return {
            "id": "hand-delete-from-bill",
            "direction": "closure_minus_bill",
            "fired": fired,
            "hit": DELETE_PURL,
            "closure_minus_bill": g["closure_minus_bill"],
            "bill_minus_shipped": g["bill_minus_shipped"],
            "pass": fired and g["counts"]["closure_minus_bill"] >= 1,
        }


def control_phantom() -> dict:
    with tempfile.TemporaryDirectory(prefix="rel0011-p-") as tmp:
        work = Path(tmp)
        src = copy_fixture(work / "src")
        root = pack_and_unpack(src, work)
        bom = G.generate(root)
        closure = R.resolve(root)
        mutated = add_phantom(bom, PHANTOM_PURL)
        g = D.bidirectional(mutated.get("components") or [], closure.get("components") or [])
        fired = PHANTOM_PURL in g["bill_minus_shipped"]
        return {
            "id": "phantom-bill-entry",
            "direction": "bill_minus_shipped",
            "fired": fired,
            "hit": PHANTOM_PURL,
            "closure_minus_bill": g["closure_minus_bill"],
            "bill_minus_shipped": g["bill_minus_shipped"],
            "pass": fired and g["counts"]["bill_minus_shipped"] >= 1,
        }


def control_clean() -> dict:
    with tempfile.TemporaryDirectory(prefix="rel0011-c-") as tmp:
        work = Path(tmp)
        src = copy_fixture(work / "src")
        root = pack_and_unpack(src, work)
        g = gate(root)
        empty = (
            g["counts"]["closure_minus_bill"] == 0
            and g["counts"]["bill_minus_shipped"] == 0
        )
        nc = g["not_checked"]
        has_peer = any(
            str(x.get("name")) == "unresolved-peer"
            and str(x.get("status")) == "NOT-CHECKED"
            for x in nc
        )
        return {
            "id": "clean-build",
            "direction": "both-empty",
            "pass": empty and g["walked_depth"] >= 3 and has_peer and g["tools_distinct"],
            "walked_depth": g["walked_depth"],
            "not_checked": nc,
            "counts": g["counts"],
            "bill": g["bill"],
            "closure": g["closure"],
            "bom": g["bom"],
            "closure_report": g["closure_report"],
            "generator_tool": g["generator_tool"],
            "resolver_tool": g["resolver_tool"],
            "tools_distinct": g["tools_distinct"],
            "closure_minus_bill": g["closure_minus_bill"],
            "bill_minus_shipped": g["bill_minus_shipped"],
        }


def run_all() -> dict:
    u = control_undeclared()
    d = control_hand_delete()
    p = control_phantom()
    c = control_clean()
    ok = all(x.get("pass") for x in (u, d, p, c))
    return {
        "pass": ok,
        "undeclared": u,
        "hand_delete": d,
        "phantom": p,
        "clean": c,
    }


if __name__ == "__main__":
    print(json.dumps(run_all(), indent=2, default=str)[:8000])
