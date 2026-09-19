# CC-0019 r2 INDEPENDENT REVIEWER (c5-cc-0019-r2, fresh context)
# Draw: random.Random(7).sample over the 1046 emitted records EXCLUDING the
# author's seed=19 20 ids (from command-center/p2-wave/probes/CC-0019/sample-resolve.json).
# Per-anchor check: re-open the cited file at the cited line and CONTENT-verify
# that the record faithfully represents the source at that anchor:
#   forward  : the record TITLE appears verbatim in the cited line
#   reverse  : the cited line (stripped) appears verbatim in claim_text
#   fragment : for '#frag:line' json anchors, the fragment names a real top-level key
# Anchor convention (normalize-summary.json): md lines point at the heading line,
# json lines at the first verbatim occurrence of the record title.
import json
import random
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
REPO = r"C:\Users\Prekzursil\source\agent-skills-toolchain"

records = [
    json.loads(row)
    for row in open(
        REPO + r"\command-center\corpus\claim-records.jsonl", encoding="utf-8"
    )
    if row.strip()
]
author = json.load(
    open(
        REPO + r"\command-center\p2-wave\probes\CC-0019\sample-resolve.json",
        encoding="utf-8",
    )
)
author_ids = {r["claim_id"] for r in author["rows"]}

by_id = {r["claim_id"]: r for r in records}
dup_ids = len(records) - len(by_id)
overlap_ids = author_ids & set(by_id)
print(f"corpus records={len(records)} unique_ids={len(by_id)} dup_ids={dup_ids}")
print(f"author sample ids={len(author_ids)} all_present_in_corpus={len(overlap_ids)}")

pool = [r for r in records if r["claim_id"] not in author_ids]
rng = random.Random(7)
sample = rng.sample(pool, 20)
print(f"draw: seed=7, pool={len(pool)} (1046 minus author 20), sample=20")
print()


def parse_anchor(a):
    # forms: "path.md:92" | "path.json#evidence:66" | "path\\x:1"
    m = re.match(r"^(.*?)(?:#([^:]*))?:([0-9]+)$", a)
    if not m:
        return a.replace("\\", "/"), None, None
    return m.group(1).replace("\\", "/"), m.group(2), int(m.group(3))


results = []
for r in sample:
    cid = r["claim_id"]
    src = r["source_lineage"][0] if r.get("source_lineage") else {}
    anchor = src.get("anchor", "")
    path, frag, lineno = parse_anchor(anchor)
    rec = {
        "claim_id": cid,
        "anchor": anchor,
        "path": path,
        "frag": frag,
        "line": lineno,
        "title": None,
        "cited_line": None,
        "file_exists": None,
        "title_in_line": None,
        "line_in_claim": None,
        "frag_key_exists": None,
        "verdict": None,
        "reason": "",
    }
    # title: claim_text == "<title>: <canonical_mechanism>" when it decomposes
    mech = r.get("canonical_mechanism") or ""
    ct = r.get("claim_text") or ""
    title = None
    if mech and ct.endswith(": " + mech):
        title = ct[: -(len(mech) + 2)]
    rec["title"] = title
    try:
        full = REPO + "/" + path
        lines = open(full, encoding="utf-8", errors="replace").read().splitlines()
        rec["file_exists"] = True
        if lineno is None or lineno < 1 or lineno > len(lines):
            rec["verdict"] = "DEAD-ANCHOR"
            rec["reason"] = f"line {lineno} out of range (file has {len(lines)})"
        else:
            cited = lines[lineno - 1]
            rec["cited_line"] = cited.strip()[:160]
            til = title is not None and title.strip() in cited
            lic = cited.strip() != "" and cited.strip() in ct
            rec["title_in_line"], rec["line_in_claim"] = til, lic
            if frag:
                try:
                    j = json.loads("\n".join(lines))
                    rec["frag_key_exists"] = frag in j if isinstance(j, dict) else None
                except Exception:
                    rec["frag_key_exists"] = None
            if til or lic:
                rec["verdict"] = "RESOLVED"
                rec["reason"] = "title-at-line" if til else "line-verbatim-in-claim"
            else:
                rec["verdict"] = "CONTENT-MISMATCH"
                rec["reason"] = (
                    f"line='{cited.strip()[:80]}' does not carry title/claim text"
                )
    except FileNotFoundError:
        rec["file_exists"] = False
        rec["verdict"] = "DEAD-ANCHOR"
        rec["reason"] = "file missing"
    results.append(rec)
    print(f"[{rec['verdict']:>16}] {cid[:70]}")
    print(f"    anchor={anchor}")
    print(f"    title ={(title or '')[:110]!r}")
    print(
        f"    line {lineno} = {rec['cited_line']!r}   fwd={til if rec['cited_line'] else False} rev={rec['line_in_claim']} frag_key={rec['frag_key_exists']}"
    )
    print()

n_res = sum(1 for x in results if x["verdict"] == "RESOLVED")
n_mis = sum(1 for x in results if x["verdict"] == "CONTENT-MISMATCH")
n_dead = sum(1 for x in results if x["verdict"] == "DEAD-ANCHOR")
print(f"SUMMARY: resolved={n_res}/20 content_mismatch={n_mis} dead_anchor={n_dead}")

json.dump(
    {
        "mode": "independent-different-20",
        "seed": 7,
        "draw": "random.Random(7).sample(records minus author seed=19 ids, 20)",
        "author_sample_rows": "command-center/p2-wave/probes/CC-0019/sample-resolve.json",
        "overlap_with_author_ids": sorted(overlap_ids),
        "rows": results,
        "resolved": n_res,
        "content_mismatch": n_mis,
        "dead_anchor": n_dead,
    },
    open(
        REPO + r"\command-center\p2-wave\reviews\CC-0019\r2-sample-20.json",
        "w",
        encoding="utf-8",
    ),
    ensure_ascii=False,
    indent=1,
)
print("wrote r2-sample-20.json")
