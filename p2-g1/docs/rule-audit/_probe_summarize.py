import json

d = json.load(
    open(
        r"C:/Users/Prekzursil/source/ast-integrate/docs/rule-audit/_rule-inventory.json",
        encoding="utf-8",
    )
)

print("tokenizer:", d["tokenizer"])
repo = d["repo"]
print("\n=== REPO rules/ : %d files ===" % len(repo))
nofm = [k for k, v in repo.items() if not v["has_frontmatter"]]
fm = [k for k, v in repo.items() if v["has_frontmatter"]]
print("NO frontmatter (=> always-on candidates): %d" % len(nofm))
for k in nofm:
    v = repo[k]
    print(
        "   %-52s bytes=%-7d words=%-6d tok~%s"
        % (k, v["bytes_raw"], v["words"], v.get("tok_tiktoken", v["tok_char_div4"]))
    )
print("WITH frontmatter: %d" % len(fm))
haspaths = [k for k in fm if repo[k]["has_paths_key"]]
nopaths = [k for k in fm if not repo[k]["has_paths_key"]]
print("   with paths: key: %d ; without paths: key: %d" % (len(haspaths), len(nopaths)))
for k in nopaths:
    print("     NO-PATHS-BUT-FM:", k, repo[k]["frontmatter"])

tokkey = (
    "tok_tiktoken"
    if d["tokenizer"] and d["tokenizer"].startswith("tiktoken")
    else "tok_char_div4"
)
tot_nofm = sum(repo[k][tokkey] for k in nofm)
tot_fm = sum(repo[k][tokkey] for k in fm)
print(
    "\nTOKENS (%s): always-on-candidates=%d  lazy=%d  ALL=%d"
    % (tokkey, tot_nofm, tot_fm, tot_nofm + tot_fm)
)

print("\n--- per-file paths: values (common only) ---")
for k in sorted(fm):
    if k.startswith("common/") or k == "README.md":
        print("  %-46s paths=%s" % (k, repo[k]["paths_value"]))

print("\n=== LIVE roots ===")
for lr, files in d["live"].items():
    if "__MISSING__" in files:
        print(lr, "MISSING")
        continue
    print("%s : %d files" % (lr, len(files)))
    lnofm = [k for k, v in files.items() if not v["has_frontmatter"]]
    print("   NO frontmatter: %d -> %s" % (len(lnofm), sorted(lnofm)))
    ltot = sum(files[k].get(tokkey, files[k]["tok_char_div4"]) for k in lnofm)
    print("   always-on token total: %d" % ltot)

print("\n=== DRIFT repo vs live ~/.claude/rules ===")
live = d["live"].get(r"C:/Users/Prekzursil/.claude/rules", {})
if "__MISSING__" not in live:
    only_repo = sorted(set(repo) - set(live))
    only_live = sorted(set(live) - set(repo))
    diff = sorted(
        k for k in set(repo) & set(live) if repo[k]["sha256_lf"] != live[k]["sha256_lf"]
    )
    print("only-in-repo (%d): %s" % (len(only_repo), only_repo))
    print("only-in-live (%d): %s" % (len(only_live), only_live))
    print("content-differs (%d):" % len(diff))
    for k in diff:
        print(
            "   %-46s repo=%d live=%d bytes ; repoFM=%s liveFM=%s"
            % (
                k,
                repo[k]["bytes_raw"],
                live[k]["bytes_raw"],
                repo[k]["has_frontmatter"],
                live[k]["has_frontmatter"],
            )
        )

print("\n=== EXTRAS ===")
for k, v in d["extras"].items():
    if "__MISSING__" in v:
        print("  %-30s MISSING" % k)
    else:
        print(
            "  %-30s bytes=%-7d words=%-6d tok~%s fm=%s sha=%s"
            % (
                k,
                v["bytes_raw"],
                v["words"],
                v.get("tok_char_div4"),
                v["has_frontmatter"],
                v["sha256_lf"][:12],
            )
        )
