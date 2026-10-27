"""build/wfa-5 : print a compact, readable per-candidate digest for classification."""

import json
import os
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
with open(
    os.path.join(REPO, "command-center", "_wfa5_skillfeat.json"), encoding="utf-8"
) as fh:
    rows = json.load(fh)["rows"]
with open(
    os.path.join(REPO, "command-center", "_wfa5_drift.json"), encoding="utf-8"
) as fh:
    drift = {d["registry_index"]: d for d in json.load(fh)["rows"]}

lo = int(sys.argv[1]) if len(sys.argv) > 1 else 129
hi = int(sys.argv[2]) if len(sys.argv) > 2 else 160

for r in rows:
    i = r["registry_index"]
    if not (lo <= i <= hi):
        continue
    d = drift[i]
    groups = {}
    for k, v in d["digests_lf_normalised"].items():
        if v:
            groups.setdefault(v, []).append(k)
    print("=" * 100)
    print(
        "[%d] %s   bytes=%d lines=%d  prior_class=%s"
        % (
            i,
            r["skill_dir_name"],
            r["bytes"],
            r["lines"],
            r["prior_record"].get("classification"),
        )
    )
    print("  path      :", r["primary_path"])
    print("  fm.name   :", r["frontmatter"].get("name"))
    desc = (r["frontmatter"].get("description") or "")[:400]
    print("  fm.desc   :", desc)
    print("  fm.keys   :", sorted(r["frontmatter"].keys()))
    print("  prior.does:", (r["prior_record"].get("does") or "")[:220])
    print("  prior.mech:", r["prior_record"].get("mechanisms"))
    print("  headings  :", " | ".join(h["text"][:46] for h in r["headings"][:14]))
    print("  steps     :", r["step_tokens"])
    print("  roles     :", r["roles"][:12])
    if r["role_lists"]:
        print("  role_lists:", r["role_lists"][:3])
    print("  tools     :", r["tools"], "| mcp:", r["mcp_tools"][:6])
    for x in r["stop_rule_hits"][:4]:
        print("  STOP  %5d: %s" % (x["line"], x["text"][:150]))
    for x in r["failure_hits"][:3]:
        print("  FAIL  %5d: %s" % (x["line"], x["text"][:150]))
    for x in r["measurement_hits"][:3]:
        print("  MEAS  %5d: %s" % (x["line"], x["text"][:150]))
    for x in r["licence_hits"][:3]:
        print("  LIC   %5d: %s" % (x["line"], x["text"][:150]))
    print("  lic files :", r["licence_files_in_dir"])
    print(
        "  git skills:",
        r["git_last_commit_skills"],
        "| .agents:",
        r["git_last_commit_agents_skills"],
    )
    print(
        "  usage     : scripts=%d runs=%d %s"
        % (
            r["usage"]["executed_scripts_naming_it"],
            r["usage"]["run_records_naming_it"],
            r["usage"]["example_scripts"][:2],
        )
    )
    print(
        "  drift     : versions=%d groups=%s"
        % (d["distinct_content_versions"], [sorted(v) for v in groups.values()])
    )
    print("  nearest   :", r["nearest_neighbour_in_slice"])
