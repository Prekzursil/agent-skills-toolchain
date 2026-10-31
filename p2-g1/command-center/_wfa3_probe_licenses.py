"""wfa-3 probe 4: does the marketplace ROOT LICENSE govern the plugins?

The prior registry recorded, for every claude-plugins-official plugin:
    "third-party (per-plugin; see marketplace LICENSE) - NOT owner-authored"
Reading the ROOT LICENSE yields Apache-2.0. But each plugin dir also ships its OWN
LICENSE. If any per-plugin LICENSE is NOT Apache-2.0, then "see marketplace LICENSE"
routes an adopter to the wrong terms.

Exact algorithm: sha256 + first-line + keyword classification of all per-plugin LICENSE
files, compared against the root LICENSE hash.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

MK = Path("C:/Users/Prekzursil/.claude/plugins/marketplaces/claude-plugins-official")
OUT = Path(
    "C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa3_licenses_out.json"
)

ANCHORS = {"superpowers", "ralph-loop", "hookify", "remember", "skill-creator"}


def classify(txt: str) -> str:
    t = txt.lower()
    if "all rights reserved" in t and "proprietary" in t:
        return "PROPRIETARY-ALL-RIGHTS-RESERVED"
    if "apache license" in t:
        return "APACHE-2.0"
    if "mit license" in t:
        return "MIT"
    if "elastic license" in t:
        return "ELASTIC-2.0"
    if "cc by-sa" in t or "creative commons" in t:
        return "CC-BY-SA"
    return "UNCLASSIFIED"


def main():
    root_lic = MK / "LICENSE"
    root_txt = root_lic.read_text(encoding="utf-8", errors="replace")
    root_sha = hashlib.sha256(root_lic.read_bytes()).hexdigest()
    out = {
        "probe": "wfa3-licenses",
        "root_license_path": str(root_lic),
        "root_license_bytes": root_lic.stat().st_size,
        "root_license_sha256": root_sha,
        "root_license_class": classify(root_txt),
        "root_license_first_line": root_txt.splitlines()[0].strip(),
        "plugins": {},
    }
    classes = Counter()
    mismatch = []
    for group in ("plugins", "external_plugins"):
        gr = MK / group
        if not gr.is_dir():
            continue
        for p in sorted(gr.iterdir()):
            if not p.is_dir():
                continue
            lp = p / "LICENSE"
            rec = {"group": group, "license_file_exists": lp.is_file()}
            if lp.is_file():
                b = lp.read_bytes()
                txt = b.decode("utf-8", errors="replace")
                rec["bytes"] = len(b)
                rec["sha256"] = hashlib.sha256(b).hexdigest()
                rec["class"] = classify(txt)
                rec["first_line"] = txt.splitlines()[0].strip()
                rec["identical_to_root"] = rec["sha256"] == root_sha
                classes[rec["class"]] += 1
                if not rec["identical_to_root"]:
                    mismatch.append(p.name)
            else:
                rec["class"] = "NO-PER-PLUGIN-LICENSE"
                classes["NO-PER-PLUGIN-LICENSE"] += 1
            out["plugins"][p.name] = rec

    out["class_histogram"] = dict(classes)
    out["differs_from_root_count"] = len(mismatch)
    out["differs_from_root"] = sorted(mismatch)
    out["ANCHOR_PLUGINS"] = {
        k: {
            "present_in_marketplace_clone": k in out["plugins"],
            "class": out["plugins"].get(k, {}).get("class")
            or "BODY-NOT-IN-MARKETPLACE-CLONE",
            "identical_to_root": out["plugins"].get(k, {}).get("identical_to_root"),
            "first_line": out["plugins"].get(k, {}).get("first_line") or "",
            "path": str(MK / "plugins" / k / "LICENSE"),
        }
        for k in sorted(ANCHORS)
    }
    out["ANCHORS_WITH_NO_BODY_HERE"] = sorted(
        k for k in ANCHORS if k not in out["plugins"]
    )
    # detector control: a name that does not exist must be absent from the map
    out["detector_control_absent_key"] = "__nope__" in out["plugins"]

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print(
        "ROOT:",
        out["root_license_class"],
        out["root_license_bytes"],
        "B |",
        out["root_license_first_line"],
    )
    print("class histogram:", out["class_histogram"])
    print(
        "differs from root:",
        out["differs_from_root_count"],
        out["differs_from_root"][:50],
    )
    print("detector control (absent key present?):", out["detector_control_absent_key"])
    print("\n=== the 5 anchor plugins in my range ===")
    for k, v in out["ANCHOR_PLUGINS"].items():
        print(
            f"  {k:<16} {v['class']:<32} identical_to_root={v['identical_to_root']}  :: {v['first_line']}"
        )
    print("\n=== every non-Apache per-plugin license ===")
    for name, rec in sorted(out["plugins"].items()):
        if rec.get("class") not in ("APACHE-2.0",):
            print(f"  {name:<26} {rec.get('class')}  {rec.get('first_line', '')[:70]}")


if __name__ == "__main__":
    main()
