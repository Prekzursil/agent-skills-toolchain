"""LANE D1: independent re-verification of the floor-audit's five self-corrected probes.

Every counter here is MECHANICALLY DIFFERENT from the audit's counter for the same quantity
(different anchor / different field / different file), per single-signal-verification rule 2.
Read-only. Prints JSON.
"""
import json
import os
import re
import sys

T1 = "C:/Users/Prekzursil/.claude/harness-restore-20260806"
T2 = "C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19"


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        raw = fh.read()
    return re.split(r"\r\n|\n", raw)


def f1_options():
    """AUDIT method: `^#### \\`([A-Z]{1,3}-\\d+)\\`` h4 headings vs JSON options[].id.
    MY method A: count per-card REQUIRED FIELD lines (`- **default:**`) -- a different anchor.
    MY method B: set-membership of every JSON id against the MD text ANYWHERE (not h4-bound).
    """
    md = read(T1 + "/07-OPTION-UNIVERSE.md")
    j = json.load(open(T1 + "/07-OPTION-UNIVERSE.json", encoding="utf-8"))
    ids_json = [o["id"] for o in j["options"]]
    set_json = set(ids_json)

    # audit's own anchor, reproduced only as a cross-check
    h4 = [m.group(1) for m in
          (re.match(r"^#### `([A-Z]{1,3}-\d+)`", ln) for ln in md) if m]

    # MY method A: per-card field lines
    field_default = sum(1 for ln in md if re.match(r"^- \*\*default:\*\*", ln))
    field_problem = sum(1 for ln in md if re.match(r"^- \*\*problem:\*\*", ln))
    field_mech = sum(1 for ln in md if re.match(r"^- \*\*mechanism:\*\*", ln))
    field_notdup = sum(1 for ln in md if re.match(r"^- \*\*not a duplicate:\*\*", ln))

    # MY method B: every backticked id-shaped token ANYWHERE in the MD
    body = "\n".join(md)
    anywhere = set(re.findall(r"`([A-Z]{1,3}-\d+)`", body))

    return {
        "json_options_len": len(ids_json),
        "json_unique_ids": len(set_json),
        "json_has_dupes": len(ids_json) != len(set_json),
        "audit_anchor_h4_count": len(h4),
        "audit_anchor_h4_unique": len(set(h4)),
        "MY_A_field_default_lines": field_default,
        "MY_A_field_problem_lines": field_problem,
        "MY_A_field_mechanism_lines": field_mech,
        "MY_A_field_notaduplicate_lines": field_notdup,
        "MY_B_ids_backticked_anywhere_in_md": len(anywhere),
        "MY_B_json_ids_absent_from_md": sorted(set_json - anywhere),
        "MY_B_md_ids_absent_from_json": sorted(anywhere - set_json),
        "set_equal_h4_vs_json": set(h4) == set_json,
    }


def f2_candidates():
    """AUDIT: `^### \\`id\\`` in 08-WORKFLOW-ARCHAEOLOGY... vs JSON candidates[].id.
    MY method: JSON id set vs the SECOND json (provenance graph) + per-card field line count.
    """
    md = read(T1 + "/08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md")
    j = json.load(open(T1 + "/08-WORKFLOW-CANDIDATE-REGISTRY.json", encoding="utf-8"))
    ids = [c["id"] for c in j["candidates"]]
    h3 = [m.group(1) for m in
          (re.match(r"^### `([A-Za-z0-9][A-Za-z0-9._-]*)`", ln) for ln in md) if m]
    # MY independent anchor: count h3 headings of ANY shape, then subtract non-card h3s
    all_h3 = [ln for ln in md if ln.startswith("### ")]
    backticked_h3 = [ln for ln in all_h3 if ln.startswith("### `")]
    unbackticked_h3 = [ln for ln in all_h3 if not ln.startswith("### `")]
    prov = None
    ppath = T1 + "/08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json"
    if os.path.isfile(ppath):
        pj = json.load(open(ppath, encoding="utf-8"))
        for k in ("nodes", "entries", "candidates", "workflows", "records"):
            if isinstance(pj.get(k), list):
                got = {r.get("id") for r in pj[k] if isinstance(r, dict) and r.get("id")}
                if got:
                    prov = {"key": k, "count": len(got),
                            "not_in_registry": sorted(got - set(ids))[:10],
                            "registry_not_in_prov": sorted(set(ids) - got)[:10]}
                    break
        if prov is None:
            prov = {"top_level_keys": sorted(pj.keys())[:20]}
    return {
        "json_candidates_len": len(ids),
        "json_unique_ids": len(set(ids)),
        "audit_anchor_h3_backticked": len(h3),
        "MY_all_h3_headings": len(all_h3),
        "MY_backticked_h3": len(backticked_h3),
        "MY_unbackticked_h3": len(unbackticked_h3),
        "MY_unbackticked_h3_sample": unbackticked_h3[:8],
        "set_equal_h3_vs_json": set(h3) == set(ids),
        "provenance_cross_check": prov,
    }


def f6_architectures():
    """AUDIT probes: h3 count, hazard-matrix COLUMN headers, ranking sentence -> all 11.
    MY methods: (a) distinct A\\d+ tokens in every markdown TABLE header row in the file;
                (b) distinct A\\d+ ids that appear in the doc's own dependency/ranking prose;
                (c) tree2's copy of the SAME file -- a different tree = a different artifact.
    """
    p1 = T1 + "/13-ARCHITECTURE-CANDIDATES.md"
    md = read(p1)
    h3 = [m.group(1) for m in (re.match(r"^### (A\d+) —", ln) for ln in md) if m]
    h3_any_dash = [m.group(1) for m in (re.match(r"^### (A\d+)\s", ln) for ln in md) if m]

    # MY (a): union of A\d+ tokens across ALL table header rows
    table_hdr_ids = set()
    hdr_rows = 0
    for i, ln in enumerate(md):
        if ln.strip().startswith("|") and i + 1 < len(md) and re.match(r"^\|[\s:|-]+\|\s*$", md[i + 1].strip()):
            hdr_rows += 1
            table_hdr_ids |= set(re.findall(r"\bA(\d+)\b", ln))
    # MY (b): every A\d+ token anywhere
    body = "\n".join(md)
    anywhere = set(re.findall(r"\bA(\d+)\b", body))

    out = {
        "audit_h3_emdash_count": len(h3),
        "MY_h3_any_whitespace_count": len(h3_any_dash),
        "MY_table_header_rows_scanned": hdr_rows,
        "MY_table_header_A_ids": sorted(int(x) for x in table_hdr_ids),
        "MY_table_header_A_ids_count": len(table_hdr_ids),
        "MY_A_ids_anywhere": sorted(int(x) for x in anywhere),
        "MY_A_ids_anywhere_count": len(anywhere),
    }
    p2 = T2 + "/13-ARCHITECTURE-CANDIDATES.md"
    if os.path.isfile(p2):
        md2 = read(p2)
        h3b = [m.group(1) for m in (re.match(r"^### (A\d+)", ln) for ln in md2) if m]
        out["tree2_same_file_h3_count"] = len(h3b)
        out["tree2_same_file_ids"] = h3b
        out["tree2_bytes"] = os.path.getsize(p2)
        out["tree1_bytes"] = os.path.getsize(p1)
        out["trees_identical_bytes"] = (open(p1, "rb").read() == open(p2, "rb").read())
    return out


def ifp1_collision():
    """IF-1: 38 MECH-NN ids, only 2 bare M-NN strings (both adopt-after-*)."""
    md = read(T1 + "/13-ARCHITECTURE-CANDIDATES.md")
    body = "\n".join(md)
    mech = set(re.findall(r"\bMECH-(\d+)\b", body))
    # bare M-NN NOT preceded by 'MECH-' -- negative lookbehind on the literal prefix
    bare = [(i + 1, ln.strip()[:120]) for i, ln in enumerate(md)
            if re.search(r"(?<!MECH-)(?<![A-Za-z0-9-])M-\d+\b", ln)]
    return {
        "MECH_ids_distinct": len(mech),
        "bare_M_NN_lines": len(bare),
        "bare_M_NN_detail": bare[:10],
    }


def detector_controls():
    """Verify each counter FIRES on a known-present case before its silence is trusted."""
    md = read(T1 + "/07-OPTION-UNIVERSE.md")
    body = "\n".join(md)
    return {
        "f1_h4_regex_fires_on_A01": bool(re.search(r"^#### `A-01`", body, re.M)),
        "f1_field_regex_fires": bool(re.search(r"^- \*\*default:\*\*", body, re.M)),
        "f1_regex_silent_on_fake": not bool(re.search(r"^#### `ZZ-99`", body, re.M)),
        "f6_h3_regex_fires_on_A1": bool(re.search(r"^### A1 ",
                                                  "\n".join(read(T1 + "/13-ARCHITECTURE-CANDIDATES.md")), re.M)),
    }


if __name__ == "__main__":
    json.dump({
        "detector_controls": detector_controls(),
        "F1_options": f1_options(),
        "F2_candidates": f2_candidates(),
        "F6_architectures": f6_architectures(),
        "IF1_id_collision": ifp1_collision(),
    }, sys.stdout, indent=1)
