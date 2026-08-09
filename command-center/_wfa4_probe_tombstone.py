"""Resolve the tombstone/fork question mechanically (use-vs-mention discrimination).

A TOMBSTONE self-declares in its own frontmatter description or opening prose that it
is MOVED/renamed/a redirect. A skill that merely MENTIONS the word elsewhere is not one.
Also measures byte-level near-duplication against every sibling in the same vault, to
test the spec's 'no trivial forks or renamed copies' rule with an algorithm rather than
an opinion.
"""

import difflib
import hashlib
import json
import pathlib
import re

PROV = pathlib.Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa4_provenance.json"
)
AGENTS_VAULT = pathlib.Path(r"C:/Users/Prekzursil/.agents/skills")
recs = json.loads(PROV.read_text(encoding="utf-8"))

TOMB = re.compile(r"\b(tombstone|MOVED\b|renamed to|is a redirect|redirect tombstone)\b", re.I)


def read_primary(rec):
    for loc in rec["locations"]:
        if loc["kind"] == "agents-live":
            return pathlib.Path(loc["path"]).read_text(encoding="utf-8", errors="replace")
    for loc in rec["locations"]:
        if loc["kind"] == "claude-live":
            return pathlib.Path(loc["path"]).read_text(encoding="utf-8", errors="replace")
    return None


print("=== TOMBSTONE USE-vs-MENTION ===")
tomb_verdicts = {}
for rec in recs:
    if not rec.get("signals", {}).get("is_tombstone"):
        continue
    txt = read_primary(rec)
    if txt is None:
        print(f"{rec['skill_dir']}: live text unavailable -> NOT-CHECKED")
        continue
    desc = rec.get("fm_description", "")
    head = txt[:900]
    in_desc = bool(TOMB.search(desc))
    in_head = bool(TOMB.search(head))
    hits = [
        (txt.count("\n", 0, m.start()) + 1, re.sub(r"\s+", " ", m.group(0)))
        for m in TOMB.finditer(txt)
    ]
    verdict = "SELF-DECLARED-TOMBSTONE" if (in_desc or in_head) else "MENTION-ONLY"
    tomb_verdicts[rec["skill_dir"]] = verdict
    print(
        f"{rec['skill_dir']:34s} in_description={in_desc} in_first900={in_head} "
        f"hits={hits[:4]} -> {verdict}"
    )

print("\n=== NEAR-DUPLICATE / TRIVIAL-FORK SCAN (agents-live vault) ===")
# Hash + similarity of each slice member against every other skill in the vault.
slice_names = [r["skill_dir"] for r in recs]
vault_texts = {}
for d in AGENTS_VAULT.iterdir():
    p = d / "SKILL.md"
    if p.is_file():
        try:
            vault_texts[d.name] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
print(f"vault skills readable: {len(vault_texts)}")
digests = {n: hashlib.sha256(t.encode("utf-8", "replace")).hexdigest() for n, t in vault_texts.items()}
by_digest = {}
for n, h in digests.items():
    by_digest.setdefault(h, []).append(n)
exact_dupes = {h: ns for h, ns in by_digest.items() if len(ns) > 1}
print(f"exact byte-identical SKILL.md groups in vault: {len(exact_dupes)}")
for h, ns in exact_dupes.items():
    print(f"  {h[:12]} -> {ns}")

print("\nsimilarity of each slice member vs its nearest vault neighbour:")
sim_rows = []
for n in slice_names:
    t = vault_texts.get(n)
    if t is None:
        print(f"  {n:34s} NOT-IN-agents-live -> skipped")
        continue
    best, bestr = None, 0.0
    for m, tm in vault_texts.items():
        if m == n:
            continue
        # cheap length gate first, then real ratio
        if not (0.55 <= len(tm) / max(1, len(t)) <= 1.8):
            continue
        r = difflib.SequenceMatcher(None, t, tm).quick_ratio()
        if r > bestr:
            best, bestr = m, r
    if best is not None:
        real = difflib.SequenceMatcher(None, t, vault_texts[best]).ratio()
    else:
        real = 0.0
    sim_rows.append({"skill": n, "nearest": best, "quick": round(bestr, 3), "ratio": round(real, 3)})
    flag = "  <-- REVIEW near-dup" if real >= 0.70 else ""
    print(f"  {n:34s} nearest={str(best):34s} ratio={real:.3f}{flag}")

out = pathlib.Path(
    r"C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa4_dupescan.json"
)
out.write_text(
    json.dumps(
        {
            "tombstone_verdicts": tomb_verdicts,
            "exact_duplicate_groups": exact_dupes,
            "nearest_neighbour": sim_rows,
        },
        indent=1,
    ),
    encoding="utf-8",
)
print(f"\nwrote {out}")
print("SUCCESS:wfa4-dupescan")
