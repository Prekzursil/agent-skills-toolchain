"""wfa-3 probe 3: mine the plugin bodies the prior archaeology declared UNSEARCHED.

08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md, 'NOT searched' section:
  "The plugin CACHE (~/.claude/plugins/cache/), where the enabled plugins' real bodies live -
   only the marketplace clones were listed."
The prior registry catalogued the 9 ENABLED plugins and the 11 marketplaces, but never the
39 first-party + 15 external plugin BODIES inside claude-plugins-official.

For each body: plugin.json (name/description/version/license), and the on-disk orchestration
surface -- agents/ commands/ skills/ hooks/ counts, which is what makes it a workflow candidate
rather than a name.
"""

import json
from pathlib import Path

MK = Path("C:/Users/Prekzursil/.claude/plugins/marketplaces/claude-plugins-official")
OUT = Path(
    "C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa3_plugincache_out.json"
)

SURFACE = ("agents", "commands", "skills", "hooks", "scripts", "mcp")


def plugin_row(p: Path, group: str):
    row = {"group": group, "dir": p.name, "path": str(p), "exists": p.exists()}
    if not p.exists():
        return row
    row["top_level"] = sorted(x.name for x in p.iterdir())[:20]
    for name in (".claude-plugin/plugin.json", "plugin.json", "package.json"):
        f = p / name
        if f.is_file():
            try:
                j = json.loads(f.read_text(encoding="utf-8", errors="replace"))
            except Exception as e:  # noqa: BLE001
                row.setdefault("manifest_errors", []).append(f"{name}: {e}")
                continue
            row["manifest_file"] = str(f)
            for k in (
                "name",
                "description",
                "version",
                "license",
                "author",
                "homepage",
            ):
                if isinstance(j, dict) and j.get(k):
                    row[f"manifest_{k}"] = j[k]
            if isinstance(j, dict) and "mcpServers" in j:
                row["manifest_mcpServers"] = list(j["mcpServers"].keys())[:10]
            break
    surf = {}
    for s in SURFACE:
        d = p / s
        if d.is_dir():
            files = [x for x in d.rglob("*") if x.is_file()]
            surf[s] = {
                "count": len(files),
                "names": sorted(x.name for x in files)[:14],
                "bytes": sum(x.stat().st_size for x in files),
            }
        f = p / f"{s}.json"
        if f.is_file():
            surf[f"{s}.json"] = {"bytes": f.stat().st_size}
    row["surface"] = surf
    row["orchestration_score"] = sum(
        v["count"] for k, v in surf.items() if isinstance(v, dict) and "count" in v
    )
    md = [x for x in p.rglob("*.md") if x.is_file()]
    row["md_files"] = len(md)
    row["total_bytes"] = sum(x.stat().st_size for x in p.rglob("*") if x.is_file())
    return row


def main():
    out = {"probe": "wfa3-plugincache", "marketplace": str(MK), "rows": []}
    for group, sub in (("first-party", "plugins"), ("external", "external_plugins")):
        root = MK / sub
        if not root.is_dir():
            out.setdefault("errors", []).append(f"missing {root}")
            continue
        for p in sorted(root.iterdir()):
            if p.is_dir():
                out["rows"].append(plugin_row(p, group))
    # detector control: a plugin dir that does not exist must report exists=False
    out["detector_control_absent"] = plugin_row(MK / "plugins" / "__nope__", "control")[
        "exists"
    ]
    out["detector_control_present"] = plugin_row(MK / "plugins" / "hookify", "control")[
        "exists"
    ]

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} B); rows={len(out['rows'])}")
    print(
        "detector controls: absent=%s present=%s"
        % (out["detector_control_absent"], out["detector_control_present"])
    )
    print()
    rows = sorted(out["rows"], key=lambda r: -r.get("orchestration_score", 0))
    for r in rows:
        surf = ",".join(
            f"{k}={v['count']}"
            for k, v in (r.get("surface") or {}).items()
            if isinstance(v, dict) and "count" in v
        )
        print(
            f"{r.get('orchestration_score', 0):>4} {r['group']:<12} {r['dir']:<26} "
            f"v={r.get('manifest_version', '-'):<8} lic={r.get('manifest_license', '-'):<12} {surf}"
        )
        if r.get("manifest_description"):
            print(f"        {str(r['manifest_description'])[:180]}")


if __name__ == "__main__":
    main()
