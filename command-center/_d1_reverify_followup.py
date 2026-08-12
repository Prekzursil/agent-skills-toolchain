"""LANE D1 follow-ups. Read-only. Prints JSON."""
import json
import os
import re
import sys

T1 = "C:/Users/Prekzursil/.claude/harness-restore-20260806"
T2 = "C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19"


def read(p):
    with open(p, "r", encoding="utf-8", errors="replace", newline="") as fh:
        return re.split(r"\r\n|\n", fh.read())


def a12():
    md = read(T1 + "/13-ARCHITECTURE-CANDIDATES.md")
    hits = [(i + 1, ln.strip()[:160]) for i, ln in enumerate(md) if re.search(r"\bA12\b", ln)]
    return {"A12_line_hits": hits}


def dangling_option_ids():
    md = read(T1 + "/07-OPTION-UNIVERSE.md")
    j = json.load(open(T1 + "/07-OPTION-UNIVERSE.json", encoding="utf-8"))
    ids = {o["id"] for o in j["options"]}
    body = "\n".join(md)
    anywhere = set(re.findall(r"`([A-Z]{1,3}-\d+)`", body))
    dangling = sorted(anywhere - ids)

    # is each dangling id explained by the JSON's own merge/absorb bookkeeping?
    jtxt = json.dumps(j)
    explained = {}
    for d in dangling:
        explained[d] = {
            "appears_in_json_text": d in jtxt,
            "md_context": [(i + 1, ln.strip()[:140]) for i, ln in enumerate(md)
                           if "`" + d + "`" in ln][:3],
        }
    ns = j.get("id_namespace", {})
    return {
        "dangling_ids": dangling,
        "count": len(dangling),
        "id_namespace_keys": sorted(ns.keys()) if isinstance(ns, dict) else None,
        "absorbed_not_dangling": ns.get("absorbed_not_dangling") if isinstance(ns, dict) else None,
        "merges_len": len(j.get("merges", [])) if isinstance(j.get("merges"), list) else None,
        "per_id": explained,
    }


def both_tree_divergence():
    names = ["03-PLUGIN-LIFECYCLE-MAP.md", "11-COUNCIL-SPECIFICATION.md",
             "13-ARCHITECTURE-CANDIDATES.md", "17-DECISION-LOG.md"]
    out = {}
    for n in names:
        p1, p2 = T1 + "/" + n, T2 + "/" + n
        b1, b2 = open(p1, "rb").read(), open(p2, "rb").read()
        l1, l2 = read(p1), read(p2)
        # LF-normalised compare, to separate line-ending noise from real content divergence
        n1 = b1.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        n2 = b2.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        s1, s2 = set(l1), set(l2)
        out[n] = {
            "tree1_bytes": len(b1), "tree2_bytes": len(b2),
            "byte_identical": b1 == b2,
            "identical_after_LF_normalisation": n1 == n2,
            "tree1_lines": len(l1), "tree2_lines": len(l2),
            "lines_only_in_tree1": len(s1 - s2), "lines_only_in_tree2": len(s2 - s1),
            "sample_only_in_tree1": [x.strip()[:110] for x in list(s1 - s2)[:4]],
            "sample_only_in_tree2": [x.strip()[:110] for x in list(s2 - s1)[:4]],
            "tree1_h3_count": sum(1 for x in l1 if x.startswith("### ")),
            "tree2_h3_count": sum(1 for x in l2 if x.startswith("### ")),
            "tree1_crlf": b1.count(b"\r\n"), "tree2_crlf": b2.count(b"\r\n"),
            "tree1_lone_cr": b1.count(b"\r") - b1.count(b"\r\n"),
            "tree2_lone_cr": b2.count(b"\r") - b2.count(b"\r\n"),
        }
    return out


def if1_bare_m():
    """CORRECTED detector: my earlier lookbehind (?<![A-Za-z0-9-]) excluded 'adopt-after-M-16'.
    Control: assert the corrected regex FIRES on a synthetic known-present string first."""
    ctrl_fire = bool(re.search(r"(?<!MECH-)\bM-\d+\b", "see adopt-after-M-16 here"))
    ctrl_silent = not bool(re.search(r"(?<!MECH-)\bM-\d+\b", "see MECH-16 here"))
    md = read(T1 + "/13-ARCHITECTURE-CANDIDATES.md")
    hits = [(i + 1, ln.strip()[:140]) for i, ln in enumerate(md)
            if re.search(r"(?<!MECH-)\bM-\d+\b", ln)]
    return {"control_fires_on_adopt_after": ctrl_fire,
            "control_silent_on_MECH": ctrl_silent,
            "bare_M_NN_line_count": len(hits), "hits": hits[:12]}


def diagram_triviality():
    d = T1 + "/diagrams"
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(".md"))
    rows = [{"f": f, "bytes": os.path.getsize(os.path.join(d, f))} for f in files]
    diag = [r for r in rows if r["f"] != "README.md"]
    return {"files": rows, "diagram_count": len(diag),
            "diagrams_under_2KB": [r["f"] for r in diag if r["bytes"] < 2048],
            "total_diagram_bytes": sum(r["bytes"] for r in diag)}


if __name__ == "__main__":
    json.dump({
        "A12": a12(),
        "dangling_option_ids": dangling_option_ids(),
        "both_tree_divergence": both_tree_divergence(),
        "IF1_bare_M_corrected": if1_bare_m(),
        "diagram_triviality": diagram_triviality(),
    }, sys.stdout, indent=1)
