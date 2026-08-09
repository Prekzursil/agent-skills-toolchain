"""Compact digest of the provenance probe, to drive final registry authoring."""

import json
import pathlib

recs = json.loads(
    pathlib.Path(
        r"C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa4_provenance.json"
    ).read_text(encoding="utf-8")
)
for r in recs:
    print("=" * 100)
    print(f"POS {r['canonical_position']}  {r['prior_id']}  ({r['skill_dir']})")
    print(
        f"  prior_class={r['prior_classification']}  prior_prov={r['prior_provenance']!r}"
    )
    print(
        f"  primary={r.get('primary_anchor')}  bytes={r.get('primary_bytes')} lines={r.get('primary_lines')}"
    )
    for loc in r["locations"]:
        extra = loc.get("mtime_utc") or loc.get("last_commit") or ""
        print(f"    - {loc['kind']:22s} {loc['path']}  ({loc['bytes']}B) {extra}")
    print(f"  fm_keys={r.get('frontmatter_keys')}")
    print(f"  fm_license={r.get('fm_license')!r}")
    print(f"  desc={r.get('fm_description', '')[:320]!r}")
    print(
        f"  license_anchors={[(a['v'][:60], a['at'].split('/')[-1]) for a in r.get('license_anchors', [])]}"
    )
    print(f"  stages={[a['v'][:58] for a in r.get('stage_anchors', [])]}")
    print(f"  roles={r.get('role_terms')}")
    print(f"  tools={r.get('tool_terms')}")
    print(f"  stop={[a['v'][:110] for a in r.get('stop_anchors', [])]}")
    print(f"  fail={[a['v'][:110] for a in r.get('failure_anchors', [])]}")
    print(f"  bench={[a['v'][:110] for a in r.get('bench_anchors', [])]}")
    print(f"  arxiv={r.get('arxiv_ids')}  urls={r.get('urls', [])[:4]}")
    print(f"  signals={r.get('signals')}")
