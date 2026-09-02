"""Measure the on-disk state that the generated-SSOT architecture must reuse or replace.

Read-only. Writes _probe_ssot_inventory_out.json next to itself.
Terminal state: SUCCESS:ssot-inventory / FAILED:ssot-inventory <reason>
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = Path(__file__).with_name("_probe_ssot_inventory_out.json")


def jload(p: Path):
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    r: dict = {"repo": str(REPO), "sections": {}}

    # ---- 1. tracked-file census by top-level area -------------------------
    import subprocess

    ls = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    r["sections"]["tracked_total"] = len(ls)
    areas = Counter()
    for f in ls:
        parts = f.split("/")
        key = "/".join(parts[:2]) if len(parts) > 1 else parts[0]
        areas[key] += 1
    r["sections"]["tracked_by_area"] = dict(
        sorted(areas.items(), key=lambda kv: -kv[1])
    )

    # ---- 2. the catalog ---------------------------------------------------
    cat_p = REPO / "command-center/WORK-UNIT-CATALOG.json"
    cat = jload(cat_p)
    wus = cat.get("work_units", [])
    items = cat.get("items", [])
    r["sections"]["catalog"] = {
        "path": str(cat_p),
        "bytes": cat_p.stat().st_size,
        "top_level_keys": sorted(cat.keys()),
        "work_units": len(wus),
        "items": len(items),
        "wu_field_names": sorted({k for w in wus for k in w.keys()}),
        "wu_field_presence": {
            k: sum(1 for w in wus if k in w)
            for k in sorted({k for w in wus for k in w.keys()})
        },
    }

    # per-field cardinality -> how much of the catalog is repeated boilerplate
    card = {}
    for k in r["sections"]["catalog"]["wu_field_names"]:
        vals = []
        for w in wus:
            v = w.get(k)
            vals.append(
                json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
            )
        card[k] = {
            "distinct": len(set(map(str, vals))),
            "present": sum(1 for v in vals if v is not None),
        }
    r["sections"]["catalog"]["wu_field_cardinality"] = card

    # phases / vendor roles / schema refs
    r["sections"]["catalog"]["distinct_output_schema"] = len(
        {w.get("output_schema") for w in wus if w.get("output_schema")}
    )
    r["sections"]["catalog"]["output_schema_refs"] = sum(
        1 for w in wus if w.get("output_schema")
    )

    # ---- 3. council specs -------------------------------------------------
    council = REPO / "platform/council"
    specs = sorted(council.rglob("*.councilspec.json"))
    proto, preset = [], []
    for p in specs:
        rel = p.relative_to(REPO).as_posix()
        (preset if "preset" in rel else proto).append(rel)

    # measure duplication: how many distinct *bodies* minus identity fields
    def body_key(p: Path):
        d = jload(p)
        d.pop("id", None)
        d.pop("name", None)
        d.pop("title", None)
        d.pop("description", None)
        return json.dumps(d, sort_keys=True)

    r["sections"]["council"] = {
        "dirs": sorted({str(p.parent.relative_to(REPO).as_posix()) for p in specs}),
        "total_specs": len(specs),
        "protocol_like": len(proto),
        "preset_like": len(preset),
        "total_bytes": sum(p.stat().st_size for p in specs),
        "distinct_bodies_ignoring_identity": len({body_key(p) for p in specs}),
    }
    # key-shape uniformity: do all specs share a key skeleton (=> generatable)?
    keysets = Counter(tuple(sorted(jload(p).keys())) for p in specs)
    r["sections"]["council"]["distinct_top_level_keysets"] = len(keysets)
    r["sections"]["council"]["most_common_keyset_count"] = keysets.most_common(1)[0][1]

    # ---- 4. generated shim tree ------------------------------------------
    shim_dir = REPO / "command-center/schema"
    shims = sorted(p for p in shim_dir.rglob("*.json"))
    prov = 0
    gen_markers = Counter()
    for p in shims:
        try:
            d = jload(p)
        except Exception:
            continue
        for marker in (
            "generated_by",
            "x-generated-by",
            "source_ref",
            "$comment",
            "x_generated",
        ):
            if isinstance(d, dict) and marker in d:
                gen_markers[marker] += 1
        if isinstance(d, dict) and any(
            m in d for m in ("generated_by", "x-generated-by", "x_generated")
        ):
            prov += 1
    r["sections"]["shim_tree"] = {
        "path": str(shim_dir),
        "json_files": len(shims),
        "total_bytes": sum(p.stat().st_size for p in shims),
        "carrying_provenance_field": prov,
        "marker_counts": dict(gen_markers),
    }

    # ---- 5. platform/lib packages + test counts --------------------------
    lib = REPO / "platform/lib"
    pkgs = {}
    for d in sorted(
        p for p in lib.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))
    ):
        py = sorted(d.rglob("*.py"))
        pkgs[d.name] = {
            "py_files": len(py),
            "loc": sum(
                sum(1 for _ in q.open("r", encoding="utf-8", errors="replace"))
                for q in py
            ),
            "test_files": len([q for q in py if q.name.startswith("test_")]),
        }
    loose = sorted(p for p in lib.glob("*.py") if not p.name.startswith("_"))
    r["sections"]["lib"] = {
        "packages": pkgs,
        "loose_modules": {
            p.name: sum(1 for _ in p.open("r", encoding="utf-8", errors="replace"))
            for p in loose
        },
    }

    # ---- 6. registry + workflows + corpus --------------------------------
    for name in ("registry", "workflows", "corpus", "schema", "architecture"):
        d = REPO / "platform" / name
        if not d.exists():
            r["sections"][f"platform_{name}"] = "ABSENT"
            continue
        files = sorted(p for p in d.rglob("*") if p.is_file())
        r["sections"][f"platform_{name}"] = {
            "files": len(files),
            "bytes": sum(p.stat().st_size for p in files),
            "names": [p.relative_to(d).as_posix() for p in files][:40],
        }

    # ---- 7. is there already a generator / render step? ------------------
    gens = []
    for p in REPO.rglob("*.py"):
        rel = p.relative_to(REPO).as_posix()
        if "/.git/" in rel or "__pycache__" in rel:
            continue
        n = p.name.lower()
        if "gen" in n or "render" in n or "emit" in n or "build" in n:
            gens.append({"path": rel, "bytes": p.stat().st_size})
    r["sections"]["existing_generators"] = gens

    OUT.write_text(json.dumps(r, indent=2, sort_keys=False), encoding="utf-8")
    print(
        json.dumps(
            {
                k: (v if not isinstance(v, dict) else "<dict>")
                for k, v in r["sections"].items()
            },
            indent=2,
        )
    )
    print("wrote", OUT)
    print("SUCCESS:ssot-inventory")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:ssot-inventory {type(exc).__name__}: {exc}")
        raise
