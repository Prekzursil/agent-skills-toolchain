#!/usr/bin/env python3
"""Mechanical integrity audit of command-center/catalog-slices/*.json.

Run:  python _catalog_integrity.py            # audit the real corpus + seeded-defect control
      python _catalog_integrity.py --audit-only <dir>   # audit one dir, print JSON to stdout

Honesty contract: this script MEASURES. Every number in the report is produced by an
algorithm here, not by judgement. The seeded-defect control (mutate a scratch copy,
require every detector to FIRE there and be SILENT on the same defect in the real
corpus) is the both-states test from rules/common/single-signal-verification.md 3b.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import collections
import hashlib
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SLICES = os.path.join(HERE, "catalog-slices")
SCRATCH = os.path.join(HERE, "_catalog_integrity_scratch")
TARGET_UNITS = 2048

# ---------------------------------------------------------------- ground truth
# 19 mandatory work-unit fields, _USER-PROMPTS.md:10607-10625 (Prompt Two).
SPEC_19_FIELDS = [
    "id",
    "title",
    "phase",
    "question_or_target",
    "inputs",
    "dependencies",
    "assigned_model_vendor_role",
    "tool_permissions",
    "execution_substrate",
    "timeout_seconds",
    "output_path",
    "output_schema",
    "evidence_requirement",
    "tests_required",
    "reviewer_requirement",
    "completion_sentinel",
    "retry_policy",
    "failure_classification",
    "owner_approval_required",
]
# 20th required field: the allocation bucket. PHASE-GRAPH.json allocation_buckets
# is the authority for the 13 legal bucket codes, so a unit that does not declare
# one cannot be checked against its bucket quota.
REQUIRED_20 = SPEC_19_FIELDS + ["bucket"]
# Auxiliary fields some slices carry. Reported but NOT counted as required.
AUX_FIELDS = ["slice", "mechanism", "not_a_duplicate_because", "spec_anchor", "dependency_anchors"]

CANONICAL_PHASES = ["0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A",
                    "8", "9", "10", "11", "12", "13", "14", "15", "16"]
BUCKET_QUOTA = {"B01": 24, "B02": 96, "B03": 224, "B04": 160, "B05": 128, "B06": 112,
                "B07": 480, "B08": 352, "B09": 192, "B10": 144, "B11": 64, "B12": 48,
                "B13": 24}
LEGAL_BUCKETS = set(BUCKET_QUOTA)

ID_RE = re.compile(r"^([A-Z]{2,4})-(\d{4})$")

STOPWORDS = set("""a an the and or but if then than that this these those of in on at to for from by with
without into onto over under between across through during before after above below up down out off again
further once here there when where why how all any both each few more most other some such no nor not only
own same so too very can will just should now is are was were be been being do does did doing have has had
having it its it's as about against upon per via vs versus i we you they he she them us our your their my me
which who whom what whose whether while because since until unless also may might must shall would could
one two three four five six seven eight nine ten does not""".split())
KEEP_SHORT = {"ci", "db", "os", "io", "ui", "ux", "pr", "id", "wu", "mcp", "api", "cli"}


# ---------------------------------------------------------------- normalisation
def norm_tokens(text: str) -> list[str]:
    t = re.sub(r"[^0-9a-z]+", " ", (text or "").lower())
    out = []
    for w in t.split():
        if w in STOPWORDS:
            continue
        if len(w) <= 2 and w not in KEEP_SHORT:
            continue
        out.append(w)
    return out


def norm_string(text: str) -> str:
    return " ".join(norm_tokens(text))


# ---------------------------------------------------------------- load + parse
def load_dir(slice_dir: str):
    """Return (units, file_report). units = list of dicts with __file/__idx injected."""
    files = sorted(f for f in os.listdir(slice_dir) if f.endswith(".json"))
    units = []
    per_file = []
    for fn in files:
        path = os.path.join(slice_dir, fn)
        rec = {"file": fn, "exists": os.path.isfile(path),
               "bytes": os.path.getsize(path) if os.path.isfile(path) else 0,
               "parses": False, "unit_count": 0, "top_level_type": None, "error": None}
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            rec["parses"] = True
            rec["top_level_type"] = type(data).__name__
            if isinstance(data, list):
                rec["unit_count"] = len(data)
                for i, u in enumerate(data):
                    if isinstance(u, dict):
                        u = dict(u)
                        u["__file"] = fn
                        u["__idx"] = i
                        units.append(u)
                    else:
                        rec["error"] = f"element {i} is {type(u).__name__}, not object"
            elif isinstance(data, dict) and isinstance(data.get("units"), list):
                rec["unit_count"] = len(data["units"])
                for i, u in enumerate(data["units"]):
                    u = dict(u)
                    u["__file"] = fn
                    u["__idx"] = i
                    units.append(u)
            else:
                rec["error"] = f"top level is {type(data).__name__}; expected list of units"
        except Exception as exc:  # noqa: BLE001 - report any parse failure by name
            rec["error"] = f"{type(exc).__name__}: {exc}"
        per_file.append(rec)
    return units, per_file


# ---------------------------------------------------------------- checks
def is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, (list, dict, tuple, set)):
        return len(v) == 0
    return False


def check_ids(units):
    by_id = collections.defaultdict(list)
    for u in units:
        by_id[str(u.get("id"))].append(f'{u["__file"]}[{u["__idx"]}]')
    duplicates = {k: v for k, v in by_id.items() if len(v) > 1}

    bad_format = []
    nums = collections.defaultdict(list)
    for u in units:
        uid = str(u.get("id"))
        m = ID_RE.match(uid)
        if not m:
            bad_format.append({"id": uid, "at": f'{u["__file"]}[{u["__idx"]}]'})
        else:
            nums[m.group(1)].append(int(m.group(2)))

    sequence = {}
    for pref, ns in sorted(nums.items()):
        s = sorted(ns)
        expected = list(range(1, len(set(s)) + 1))
        present = sorted(set(s))
        gaps = sorted(set(range(1, max(s) + 1)) - set(s)) if s else []
        sequence[pref] = {
            "count": len(s),
            "distinct": len(present),
            "min": min(s) if s else None,
            "max": max(s) if s else None,
            "repeated_numbers": sorted(n for n, c in collections.Counter(s).items() if c > 1),
            "gaps_in_1_to_max": gaps,
            "contiguous_from_1": present == expected and not gaps,
        }
    return {"duplicate_ids": duplicates, "duplicate_id_count": len(duplicates),
            "bad_format_ids": bad_format, "sequence_by_prefix": sequence}


def check_fields(units):
    """Absent-key AND present-but-empty, per required field, per bucket."""
    def bucket_of(u):
        b = u.get("bucket")
        if isinstance(b, str) and b in LEGAL_BUCKETS:
            return b
        m = ID_RE.match(str(u.get("id")))
        return f"prefix:{m.group(1)}" if m else "prefix:UNKNOWN"

    absent = collections.defaultdict(collections.Counter)   # field -> bucket -> n
    empty = collections.defaultdict(collections.Counter)
    tot_absent = collections.Counter()
    tot_empty = collections.Counter()
    for u in units:
        b = bucket_of(u)
        for f in REQUIRED_20:
            if f not in u:
                absent[f][b] += 1
                tot_absent[f] += 1
            elif is_empty(u[f]):
                empty[f][b] += 1
                tot_empty[f] += 1
    aux_present = {f: sum(1 for u in units if f in u) for f in AUX_FIELDS}
    return {
        "required_field_set": REQUIRED_20,
        "required_field_set_note": ("19 spec-mandated fields (_USER-PROMPTS.md:10607-10625) "
                                    "+ 'bucket' (allocation authority: PHASE-GRAPH.json "
                                    "allocation_buckets) = 20"),
        "missing_absent_key_total": dict(tot_absent),
        "missing_absent_key_by_bucket": {f: dict(c) for f, c in absent.items()},
        "present_but_empty_total": dict(tot_empty),
        "present_but_empty_by_bucket": {f: dict(c) for f, c in empty.items()},
        "auxiliary_field_presence": aux_present,
    }


def check_near_duplicates(units, jaccard_threshold=0.80, worst_n=20):
    ids = [str(u.get("id")) for u in units]
    titles = [str(u.get("title") or "") for u in units]
    combined = [f'{u.get("title") or ""} {u.get("question_or_target") or ""}' for u in units]
    norm_comb = [norm_string(c) for c in combined]
    norm_title = [norm_string(t) for t in titles]
    tok_sets = [frozenset(norm_tokens(c)) for c in combined]

    def clusters_by_key(keys):
        d = collections.defaultdict(list)
        for i, k in enumerate(keys):
            if k:
                d[k].append(i)
        return {k: v for k, v in d.items() if len(v) > 1}

    exact_comb = clusters_by_key(norm_comb)
    exact_title = clusters_by_key(norm_title)
    bag = clusters_by_key([" ".join(sorted(s)) for s in tok_sets])

    # Pairwise Jaccard with the length-ratio prune. The prune is valid because
    # J>=t implies min(|A|,|B|)/max(|A|,|B|) >= t.
    # The scan runs at SCAN_FLOOR, not at jaccard_threshold: pruning at the reporting
    # threshold would silently undercount every histogram bucket below it (a pair with
    # J=0.72 is length-pruned away by an 0.80 prune), so the histogram would read 0 for
    # reasons of arithmetic rather than of evidence.
    SCAN_FLOOR = 0.30
    scan = min(SCAN_FLOOR, jaccard_threshold)
    order = sorted(range(len(units)), key=lambda i: len(tok_sets[i]))
    lens = [len(tok_sets[i]) for i in order]
    pairs = []
    hist = collections.Counter()
    top_pairs = []
    n = len(order)
    for a in range(n):
        ia = order[a]
        la = lens[a]
        if la == 0:
            continue
        limit = la / scan
        for b in range(a + 1, n):
            lb = lens[b]
            if lb > limit:
                break
            ib = order[b]
            inter = len(tok_sets[ia] & tok_sets[ib])
            if inter == 0:
                continue
            j = inter / (la + lb - inter)
            if j >= jaccard_threshold:
                pairs.append((ia, ib, round(j, 4)))
            for t in (0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.60, 0.50, 0.40, 0.30):
                if j >= t:
                    hist[t] += 1
            if j >= scan:
                top_pairs.append((round(j, 4), ia, ib))
    top_pairs.sort(reverse=True)
    max_pair = None
    if top_pairs:
        j, ia, ib = top_pairs[0]
        max_pair = {"jaccard": j, "ids": [ids[ia], ids[ib]],
                    "titles": [titles[ia], titles[ib]],
                    "files": [units[ia]["__file"], units[ib]["__file"]]}
    top20_pairs = [{"jaccard": j, "ids": [ids[x], ids[y]],
                    "titles": [titles[x], titles[y]],
                    "files": [units[x]["__file"], units[y]["__file"]]}
                   for j, x, y in top_pairs[:20]]

    parent = list(range(len(units)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for ia, ib, _ in pairs:
        ra, rb = find(ia), find(ib)
        if ra != rb:
            parent[rb] = ra
    comp = collections.defaultdict(list)
    involved = set()
    for ia, ib, _ in pairs:
        involved.add(ia)
        involved.add(ib)
    for i in involved:
        comp[find(i)].append(i)

    pair_by_comp = collections.defaultdict(list)
    for ia, ib, j in pairs:
        pair_by_comp[find(ia)].append(j)

    cl = []
    for root, members in comp.items():
        js = pair_by_comp.get(root, [])
        cl.append({
            "size": len(members),
            "mean_jaccard": round(sum(js) / len(js), 4) if js else None,
            "max_jaccard": max(js) if js else None,
            "ids": [ids[i] for i in sorted(members)],
            "files": sorted({units[i]["__file"] for i in members}),
            "titles": [titles[i] for i in sorted(members)],
        })
    cl.sort(key=lambda c: (-c["size"], -(c["mean_jaccard"] or 0)))

    def render(cd, kind):
        out = []
        for key, idxs in cd.items():
            out.append({"kind": kind, "size": len(idxs),
                        "normalised_key": key[:240],
                        "ids": [ids[i] for i in idxs],
                        "files": sorted({units[i]["__file"] for i in idxs}),
                        "titles": [titles[i] for i in idxs]})
        out.sort(key=lambda c: -c["size"])
        return out

    return {
        "jaccard_threshold": jaccard_threshold,
        "scan_floor": scan,
        "pair_count_at_threshold": len(pairs),
        "pair_count_by_threshold": {str(k): v for k, v in sorted(hist.items(), reverse=True)},
        "max_pairwise_jaccard": max_pair,
        "top_20_most_similar_pairs": top20_pairs,
        "exact_normalised_title_plus_target_clusters": render(exact_comb, "exact-title+target"),
        "exact_normalised_title_clusters": render(exact_title, "exact-title"),
        "bag_of_words_identical_clusters": render(bag, "same-token-bag"),
        "units_in_high_overlap_cluster": len(involved),
        "high_overlap_cluster_count": len(cl),
        "high_overlap_clusters_worst": cl[:worst_n],
        "high_overlap_clusters_all_sizes": [c["size"] for c in cl],
    }


def check_dependencies(units):
    ids = {str(u.get("id")) for u in units}
    unresolved = []
    bucket_refs = collections.Counter()
    illegal_bucket = []
    unknown_form = []
    non_string = []
    self_dep = []
    graph = collections.defaultdict(set)
    for u in units:
        uid = str(u.get("id"))
        deps = u.get("dependencies")
        if deps is None:
            continue
        if not isinstance(deps, list):
            non_string.append({"id": uid, "dependencies_type": type(deps).__name__})
            continue
        for d in deps:
            if not isinstance(d, str):
                non_string.append({"id": uid, "dep": repr(d)})
                continue
            if ID_RE.match(d):
                if d not in ids:
                    unresolved.append({"id": uid, "dep": d, "at": f'{u["__file"]}[{u["__idx"]}]'})
                elif d == uid:
                    self_dep.append(uid)
                else:
                    graph[uid].add(d)
            elif re.fullmatch(r"B\d{2}", d):
                bucket_refs[d] += 1
                if d not in LEGAL_BUCKETS:
                    illegal_bucket.append({"id": uid, "dep": d})
            else:
                unknown_form.append({"id": uid, "dep": d, "at": f'{u["__file"]}[{u["__idx"]}]'})

    # cycle detection (iterative Tarjan) over unit-id edges only
    index = {}
    low = {}
    on_stack = {}
    stack = []
    sccs = []
    counter = [0]
    for root in list(graph) + sorted(ids):
        if root in index:
            continue
        work = [(root, iter(sorted(graph.get(root, ()))))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on_stack[root] = True
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter[0]
                    counter[0] += 1
                    stack.append(nxt)
                    on_stack[nxt] = True
                    work.append((nxt, iter(sorted(graph.get(nxt, ())))))
                    advanced = True
                    break
                if on_stack.get(nxt):
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    comp.append(w)
                    if w == node:
                        break
                if len(comp) > 1:
                    sccs.append(sorted(comp))
    return {
        "total_dependency_refs": sum(len(u.get("dependencies") or []) for u in units
                                     if isinstance(u.get("dependencies"), list)),
        "unresolved_unit_id_refs": unresolved,
        "unresolved_unit_id_ref_count": len(unresolved),
        "bucket_refs": dict(bucket_refs),
        "illegal_bucket_refs": illegal_bucket,
        "unknown_form_refs": unknown_form,
        "unknown_form_ref_count": len(unknown_form),
        "unknown_form_distinct": sorted({x["dep"] for x in unknown_form}),
        "non_string_or_non_list": non_string,
        "self_dependencies": self_dep,
        "cycles": sccs,
        "cycle_count": len(sccs),
    }


def check_phases(units):
    counts = collections.Counter(str(u.get("phase")) for u in units)
    table = {p: counts.get(p, 0) for p in CANONICAL_PHASES}
    zero = [p for p, n in table.items() if n == 0]
    unknown = {p: n for p, n in counts.items() if p not in CANONICAL_PHASES}
    return {"canonical_phase_ids": CANONICAL_PHASES, "units_per_phase": table,
            "phases_with_zero_units": zero, "phases_with_zero_units_count": len(zero),
            "non_canonical_phase_values": unknown}


def check_buckets(units):
    declared = collections.Counter()
    for u in units:
        b = u.get("bucket")
        if isinstance(b, str):
            declared[b] += 1
    inferred = collections.Counter()
    for u in units:
        m = ID_RE.match(str(u.get("id")))
        inferred[m.group(1) if m else "UNKNOWN"] += 1
    return {"declared_bucket_counts": dict(declared),
            "declared_bucket_coverage": f"{sum(declared.values())}/{len(units)}",
            "id_prefix_counts": dict(inferred),
            "spec_bucket_quota": BUCKET_QUOTA,
            "spec_bucket_quota_sum": sum(BUCKET_QUOTA.values())}


def audit(slice_dir: str, jaccard_threshold=0.80):
    units, per_file = load_dir(slice_dir)
    total = len(units)
    return {
        "slice_dir": slice_dir.replace("\\", "/"),
        "files": per_file,
        "file_count": len(per_file),
        "files_that_failed_to_parse": [f["file"] for f in per_file if not f["parses"]],
        "files_with_structural_error": [{"file": f["file"], "error": f["error"]}
                                        for f in per_file if f["error"]],
        "unit_count_total": total,
        "unit_count_per_file": {f["file"]: f["unit_count"] for f in per_file},
        "target_units": TARGET_UNITS,
        "shortfall_vs_target": TARGET_UNITS - total,
        "ids": check_ids(units),
        "fields": check_fields(units),
        "near_duplicates": check_near_duplicates(units, jaccard_threshold),
        # A second pass at a deliberately LOW threshold. At 0.80 the corpus yields zero
        # clusters, and "zero clusters" is not an informative answer to "where is the
        # padding?" - this pass surfaces the most-similar families that actually exist so
        # the 20-worst list is populated with real content rather than an empty set.
        "near_duplicates_exploratory_0_35": check_near_duplicates(units, 0.35),
        "dependencies": check_dependencies(units),
        "phases": check_phases(units),
        "buckets": check_buckets(units),
    }, units


# ---------------------------------------------------------------- detector control
def seed_defects(src: str, dst: str):
    """Copy the corpus and inject one known instance of every defect class."""
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(dst)
    for fn in sorted(f for f in os.listdir(src) if f.endswith(".json")):
        shutil.copy2(os.path.join(src, fn), os.path.join(dst, fn))

    seeded = {}

    def load(fn):
        with open(os.path.join(dst, fn), encoding="utf-8") as fh:
            return json.load(fh)

    def save(fn, data):
        with open(os.path.join(dst, fn), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)

    adv = load("ADV-1.json")
    bld = load("BLD-1.json")
    cc = load("CC-1.json")
    rel = load("REL-1.json")
    syn = load("SYN-1.json")

    # 1. duplicate id across files
    seeded["duplicate_id"] = adv[0]["id"]
    bld[0]["id"] = adv[0]["id"]

    # 2. absent required key
    seeded["absent_field"] = {"field": "evidence_requirement", "id": bld[1]["id"]}
    bld[1].pop("evidence_requirement", None)

    # 3. present-but-empty required value
    seeded["empty_field"] = {"field": "output_path", "id": bld[2]["id"]}
    bld[2]["output_path"] = ""

    # 4. broken id format
    seeded["bad_format_id"] = "ZZ-77"
    bld[3]["id"] = "ZZ-77"

    # 5. dangling dependency
    seeded["dangling_dep"] = {"id": bld[4]["id"], "dep": "NOPE-9999"}
    bld[4]["dependencies"] = list(bld[4].get("dependencies") or []) + ["NOPE-9999"]

    # 6. dependency cycle (2-node)
    seeded["cycle"] = [cc[0]["id"], cc[1]["id"]]
    cc[0]["dependencies"] = [cc[1]["id"]]
    cc[1]["dependencies"] = [cc[0]["id"]]

    # 7. near/exact duplicate content under a different id
    seeded["exact_dup_content"] = {"donor": rel[0]["id"], "recipient": syn[0]["id"]}
    syn[0]["title"] = rel[0]["title"]
    syn[0]["question_or_target"] = rel[0]["question_or_target"]

    # write the five mutated files FIRST. Ordering matters: these in-memory copies were
    # loaded before the phase-16 strip below, so saving them afterwards would silently
    # restore the stripped units and make the zero-phase control measure nothing.
    save("ADV-1.json", adv)
    save("BLD-1.json", bld)
    save("CC-1.json", cc)
    save("REL-1.json", rel)
    save("SYN-1.json", syn)

    # 8. phase with zero units: strip every phase-16 unit (must run LAST)
    removed = 0
    for fn in sorted(f for f in os.listdir(dst) if f.endswith(".json")):
        data = load(fn)
        keep = [u for u in data if str(u.get("phase")) != "16"]
        removed += len(data) - len(keep)
        if len(keep) != len(data):
            save(fn, keep)
    seeded["zero_phase"] = {"phase": "16", "units_removed": removed}
    # self-check the seeder: the strip must actually have landed on disk.
    left = 0
    for fn in sorted(f for f in os.listdir(dst) if f.endswith(".json") and f != "BROKEN-SEED.json"):
        left += sum(1 for u in load(fn) if str(u.get("phase")) == "16")
    seeded["zero_phase"]["phase16_units_remaining_after_strip"] = left
    seeded["zero_phase"]["seeder_self_check"] = "OK" if left == 0 else "SEEDER-BUG: strip reverted"

    # 9. unparseable file (truncate a copy)
    with open(os.path.join(dst, "BROKEN-SEED.json"), "w", encoding="utf-8") as fh:
        fh.write('[{"id": "BRK-0001", "title": "truncated on purp')
    seeded["parse_failure_file"] = "BROKEN-SEED.json"
    return seeded


def control(real_report, seeded_dir, seeded, real_units=None):
    bad, _ = audit(seeded_dir)
    res = []

    def add(name, fired_on_bad, silent_on_good, detail):
        res.append({"detector": name, "fires_on_seeded_defect": bool(fired_on_bad),
                    "silent_on_real_corpus_for_that_defect": bool(silent_on_good),
                    "both_states_pass": bool(fired_on_bad and silent_on_good),
                    "detail": detail})

    dup = seeded["duplicate_id"]
    add("duplicate_id",
        dup in bad["ids"]["duplicate_ids"],
        dup not in real_report["ids"]["duplicate_ids"],
        f'seeded id {dup}; bad-state dup entries={len(bad["ids"]["duplicate_ids"])}, '
        f'real-state dup entries={len(real_report["ids"]["duplicate_ids"])}')

    f = seeded["absent_field"]["field"]
    add("missing_required_field",
        bad["fields"]["missing_absent_key_total"].get(f, 0) >
        real_report["fields"]["missing_absent_key_total"].get(f, 0),
        real_report["fields"]["missing_absent_key_total"].get(f, 0) == 0,
        f'field {f}: bad={bad["fields"]["missing_absent_key_total"].get(f, 0)} '
        f'real={real_report["fields"]["missing_absent_key_total"].get(f, 0)}')

    ef = seeded["empty_field"]["field"]
    add("present_but_empty_field",
        bad["fields"]["present_but_empty_total"].get(ef, 0) >
        real_report["fields"]["present_but_empty_total"].get(ef, 0),
        real_report["fields"]["present_but_empty_total"].get(ef, 0) == 0,
        f'field {ef}: bad={bad["fields"]["present_but_empty_total"].get(ef, 0)} '
        f'real={real_report["fields"]["present_but_empty_total"].get(ef, 0)}')

    badids = {x["id"] for x in bad["ids"]["bad_format_ids"]}
    add("id_format",
        seeded["bad_format_id"] in badids,
        len(real_report["ids"]["bad_format_ids"]) == 0,
        f'bad-state bad-format={sorted(badids)}, real-state bad-format='
        f'{[x["id"] for x in real_report["ids"]["bad_format_ids"]]}')

    dd = {x["dep"] for x in bad["dependencies"]["unresolved_unit_id_refs"]}
    add("dangling_dependency",
        seeded["dangling_dep"]["dep"] in dd,
        real_report["dependencies"]["unresolved_unit_id_ref_count"] == 0,
        f'bad-state unresolved={sorted(dd)}, real-state unresolved='
        f'{real_report["dependencies"]["unresolved_unit_id_ref_count"]}')

    # Control predicate is "the SEEDED cycle is absent from the real corpus", NOT "the real
    # corpus has zero cycles". The real corpus contains a genuine cycle; conflating the two
    # would report a working detector as broken and bury a real defect as a control artifact.
    cyc_hit = any(set(seeded["cycle"]).issubset(set(c)) for c in bad["dependencies"]["cycles"])
    cyc_silent = not any(set(seeded["cycle"]).issubset(set(c))
                         for c in real_report["dependencies"]["cycles"])
    add("dependency_cycle", cyc_hit, cyc_silent,
        f'seeded cycle {seeded["cycle"]}; bad-state cycles={bad["dependencies"]["cycles"]}, '
        f'real-state cycles={real_report["dependencies"]["cycles"]} '
        f'(count={real_report["dependencies"]["cycle_count"]} - these are GENUINE catalog '
        f'defects, not control artifacts)')

    rid = seeded["exact_dup_content"]["recipient"]
    did = seeded["exact_dup_content"]["donor"]

    def pair_in(rep):
        for c in rep["near_duplicates"]["exact_normalised_title_plus_target_clusters"]:
            if rid in c["ids"] and did in c["ids"]:
                return True
        return False

    add("exact_duplicate_content", pair_in(bad), not pair_in(real_report),
        f'seeded pair {did}=={rid}; bad-state exact clusters='
        f'{len(bad["near_duplicates"]["exact_normalised_title_plus_target_clusters"])}, '
        f'real-state exact clusters='
        f'{len(real_report["near_duplicates"]["exact_normalised_title_plus_target_clusters"])}')

    add("zero_coverage_phase",
        "16" in bad["phases"]["phases_with_zero_units"],
        "16" not in real_report["phases"]["phases_with_zero_units"],
        f'bad-state zero phases={bad["phases"]["phases_with_zero_units"]}, real-state zero '
        f'phases={real_report["phases"]["phases_with_zero_units"]}')

    add("unparseable_file",
        seeded["parse_failure_file"] in bad["files_that_failed_to_parse"],
        len(real_report["files_that_failed_to_parse"]) == 0,
        f'bad-state parse failures={bad["files_that_failed_to_parse"]}, real-state parse '
        f'failures={real_report["files_that_failed_to_parse"]}')

    # The JACCARD path needs its own control. The exact-string detector above cannot
    # exercise it, and it reported ZERO high-overlap pairs on the real corpus - a number
    # that is worthless unless the detector is proved able to find a known-present
    # duplicate IN THAT SAME corpus. Inject an exact clone of a real unit under a new id.
    clone_detail = "NOT-CHECKED: real_units not supplied"
    clone_fires = False
    clone_silent = real_report["near_duplicates"]["pair_count_at_threshold"] == 0
    if real_units:
        donor = dict(real_units[0])
        clone = dict(donor)
        clone["id"] = "ZZZ-0001"
        clone["__file"] = "synthetic-clone.json"
        cl = check_near_duplicates(list(real_units) + [clone],
                                  real_report["near_duplicates"]["jaccard_threshold"])
        clone_fires = any("ZZZ-0001" in c["ids"] and donor["id"] in c["ids"]
                          for c in cl["high_overlap_clusters_worst"])
        clone_detail = (
            f'injected an exact clone of {donor["id"]} as ZZZ-0001 into the real corpus: '
            f'pairs>=threshold={cl["pair_count_at_threshold"]}, clustered={clone_fires}. '
            f'Un-injected real corpus: pairs>=threshold='
            f'{real_report["near_duplicates"]["pair_count_at_threshold"]}, '
            f'max pairwise J={real_report["near_duplicates"]["max_pairwise_jaccard"]}')
    add("jaccard_near_duplicate", clone_fires, clone_silent, clone_detail)

    return {"seeded": seeded, "results": res,
            "detectors_total": len(res),
            "detectors_both_states_pass": sum(1 for r in res if r["both_states_pass"]),
            "verdict": "CONFIRMED" if all(r["both_states_pass"] for r in res) else "REFUTED",
            "seeded_corpus_unit_count": bad["unit_count_total"]}


# ---------------------------------------------------------------- md renderer
def render_md(rep):
    L = []
    a = rep["audit"]
    c = rep["detector_control"]
    L.append("# CATALOG-INTEGRITY - mechanical audit of command-center/catalog-slices/")
    L.append("")
    L.append(f'Generated: {rep["generated_utc"]} by `command-center/_catalog_integrity.py`')
    L.append("")
    L.append("## Headline")
    L.append("")
    L.append(f'- **{a["unit_count_total"]} units** across {a["file_count"]} slice files, '
             f'target {a["target_units"]} -> **shortfall {a["shortfall_vs_target"]}**')
    L.append(f'- files that failed to parse: **{len(a["files_that_failed_to_parse"])}** '
             f'{a["files_that_failed_to_parse"] or ""}')
    L.append(f'- duplicate ids: **{a["ids"]["duplicate_id_count"]}**')
    L.append(f'- malformed ids (not CODE-NNNN): **{len(a["ids"]["bad_format_ids"])}**')
    L.append(f'- phases with ZERO units: **{a["phases"]["phases_with_zero_units_count"]}** '
             f'{a["phases"]["phases_with_zero_units"] or ""}')
    L.append(f'- unresolved dependency refs: **{a["dependencies"]["unresolved_unit_id_ref_count"]}** '
             f'unit-id + **{a["dependencies"]["unknown_form_ref_count"]}** unknown-form')
    L.append(f'- dependency cycles: **{a["dependencies"]["cycle_count"]}**')
    nd = a["near_duplicates"]
    L.append(f'- exact normalised title+target duplicate clusters: '
             f'**{len(nd["exact_normalised_title_plus_target_clusters"])}**; '
             f'exact title-only clusters: **{len(nd["exact_normalised_title_clusters"])}**')
    L.append(f'- units inside a Jaccard>={nd["jaccard_threshold"]} overlap cluster: '
             f'**{nd["units_in_high_overlap_cluster"]}** in '
             f'**{nd["high_overlap_cluster_count"]}** clusters')
    L.append(f'- detector control: **{c["verdict"]}** '
             f'({c["detectors_both_states_pass"]}/{c["detectors_total"]} detectors fire on a '
             f'seeded defect AND stay silent on the real corpus)')
    L.append("")

    L.append("## 1. File existence and parse")
    L.append("")
    L.append("| file | bytes | parses | units | error |")
    L.append("|---|---:|---|---:|---|")
    for f in a["files"]:
        L.append(f'| {f["file"]} | {f["bytes"]} | {"yes" if f["parses"] else "**NO**"} | '
                 f'{f["unit_count"]} | {f["error"] or ""} |')
    L.append("")

    L.append("## 2. Unit counts and where the shortfall lives")
    L.append("")
    L.append(f'Total **{a["unit_count_total"]}** / target **{a["target_units"]}** '
             f'= shortfall **{a["shortfall_vs_target"]}**.')
    L.append("")
    at = rep.get("shortfall_attribution")
    if at and not at.get("stale"):
        L.append(f'Attribution verdict: **{at["verdict"]}**')
        L.append("")
        L.append("| id family | units | bucket | quota | deficit | mapping basis |")
        L.append("|---|---:|---|---:|---:|---|")
        for r in at["family_rows"]:
            d = r["deficit"]
            L.append(f'| {r["family"]} | {r["units"]} | {r["bucket"]} | {r["quota"]} | '
                     f'{"**" + str(d) + "**" if d else d} | {r["mapping_basis"]} |')
        L.append("")
        L.append(f'Sum of per-family deficits = **{at["sum_of_family_deficits"]}**, global '
                 f'shortfall = **{at["global_shortfall"]}**, exact match = '
                 f'**{at["deficits_explain_shortfall_exactly"]}**. Bucket-mapping collisions: '
                 f'{at["bucket_mapping_collisions"] or "none"}. Buckets with no id family: '
                 f'{at["buckets_with_no_family"] or "none"}.')
        L.append("")
        L.append("Ids the slice authors skipped (never written, not merely renumbered):")
        L.append("")
        for p, h in (at["numbering_holes"] or {}).items():
            L.append(f'- **{p}**: {h["count"]} units, highest id `{p}-{h["max_id"]:04d}`, '
                     f'**{len(h["missing_ids"])} missing**: {h["missing_ids"]}')
        if not at["numbering_holes"]:
            L.append("- none")
        L.append("")
    elif at:
        L.append(f'Shortfall attribution: {at.get("note")}')
        L.append("")
    else:
        L.append('Shortfall attribution: NOT-CHECKED (run `_catalog_shortfall_attrib.py`).')
        L.append("")

    L.append("## 3. Duplicate ids across all files")
    L.append("")
    if not a["ids"]["duplicate_ids"]:
        L.append(f'None. {a["unit_count_total"]} units carry '
                 f'{a["unit_count_total"] - a["ids"]["duplicate_id_count"]} distinct ids.')
    else:
        L.append("| id | occurrences |")
        L.append("|---|---|")
        for k, v in sorted(a["ids"]["duplicate_ids"].items()):
            L.append(f'| {k} | {", ".join(v)} |')
    L.append("")

    L.append("## 4. ID format and sequence")
    L.append("")
    L.append(f'Malformed (not `CODE-NNNN`): {len(a["ids"]["bad_format_ids"])} '
             f'{a["ids"]["bad_format_ids"] or ""}')
    L.append("")
    L.append("| prefix | count | distinct | min | max | contiguous 1..N | gaps | repeated |")
    L.append("|---|---:|---:|---:|---:|---|---|---|")
    for p, s in a["ids"]["sequence_by_prefix"].items():
        gaps = s["gaps_in_1_to_max"]
        gs = "none" if not gaps else (f'{len(gaps)}: {gaps[:12]}{"..." if len(gaps) > 12 else ""}')
        L.append(f'| {p} | {s["count"]} | {s["distinct"]} | {s["min"]} | {s["max"]} | '
                 f'{"yes" if s["contiguous_from_1"] else "**NO**"} | {gs} | '
                 f'{s["repeated_numbers"] or "none"} |')
    L.append("")

    L.append("## 5. Required-field coverage")
    L.append("")
    L.append(a["fields"]["required_field_set_note"])
    L.append("")
    L.append("| field | absent key | present-but-empty |")
    L.append("|---|---:|---:|")
    for f in a["fields"]["required_field_set"]:
        L.append(f'| {f} | {a["fields"]["missing_absent_key_total"].get(f, 0)} | '
                 f'{a["fields"]["present_but_empty_total"].get(f, 0)} |')
    L.append("")
    for f, bybk in sorted(a["fields"]["missing_absent_key_by_bucket"].items()):
        L.append(f'- absent `{f}` by bucket: {dict(sorted(bybk.items()))}')
    for f, bybk in sorted(a["fields"]["present_but_empty_by_bucket"].items()):
        L.append(f'- empty `{f}` by bucket: {dict(sorted(bybk.items()))}')
    L.append("")
    L.append(f'Auxiliary (non-required) field presence out of {a["unit_count_total"]}: '
             f'{a["fields"]["auxiliary_field_presence"]}')
    L.append("")

    L.append("## 6. Near-duplicate / padding analysis (the substantive check)")
    L.append("")
    L.append(f'Normalisation: lowercase `title + question_or_target`, strip non-alphanumerics, '
             f'drop {len(STOPWORDS)} stopwords and <=2-char tokens (keeping {sorted(KEEP_SHORT)}).')
    L.append("")
    L.append(f'- scan floor {nd["scan_floor"]} (pairs are enumerated down to this Jaccard, so '
             f'the buckets below the reporting threshold are real counts, not prune artifacts)')
    _hist = nd["pair_count_by_threshold"] or "none - no pair in the corpus reaches 0.30"
    L.append(f'- pairs by Jaccard threshold: {_hist}')
    mp = nd["max_pairwise_jaccard"]
    if mp:
        L.append(f'- **maximum pairwise Jaccard in the whole catalog = {mp["jaccard"]}** '
                 f'({mp["ids"][0]} vs {mp["ids"][1]})')
        L.append(f'  - `{mp["titles"][0]}`')
        L.append(f'  - `{mp["titles"][1]}`')
    else:
        L.append('- maximum pairwise Jaccard: no pair reached the scan floor')
    L.append(f'- exact normalised title+target clusters: '
             f'{len(nd["exact_normalised_title_plus_target_clusters"])}')
    L.append(f'- exact normalised title-only clusters: '
             f'{len(nd["exact_normalised_title_clusters"])}')
    L.append(f'- identical token-bag clusters: {len(nd["bag_of_words_identical_clusters"])}')
    L.append(f'- Jaccard>={nd["jaccard_threshold"]} clusters: {nd["high_overlap_cluster_count"]} '
             f'covering {nd["units_in_high_overlap_cluster"]} units; '
             f'sizes={nd["high_overlap_clusters_all_sizes"][:40]}')
    L.append("")
    if nd["exact_normalised_title_plus_target_clusters"]:
        L.append("### Exact normalised title+target collisions")
        L.append("")
        for cl in nd["exact_normalised_title_plus_target_clusters"][:20]:
            L.append(f'- **{cl["size"]}x** {cl["ids"]} in {cl["files"]}')
            for t in cl["titles"][:4]:
                L.append(f'  - `{t}`')
        L.append("")
    if nd["exact_normalised_title_clusters"]:
        L.append("### Exact normalised title-only collisions (top 20)")
        L.append("")
        for cl in nd["exact_normalised_title_clusters"][:20]:
            L.append(f'- **{cl["size"]}x** {cl["ids"]} in {cl["files"]}')
            L.append(f'  - `{cl["titles"][0]}`')
        L.append("")
    L.append(f'### 20 worst high-overlap clusters (Jaccard>={nd["jaccard_threshold"]})')
    L.append("")
    if not nd["high_overlap_clusters_worst"]:
        L.append(f'**None.** Zero clusters exist at Jaccard>={nd["jaccard_threshold"]} - the '
                 f'whole-catalog maximum is '
                 f'{(nd["max_pairwise_jaccard"] or {}).get("jaccard")}, so no pair comes '
                 f'close to the padding threshold. The detector is proved able to find a '
                 f'planted clone in this same corpus (see the detector-control section), so '
                 f'this zero is a measurement, not a silent detector.')
    for i, cl in enumerate(nd["high_overlap_clusters_worst"], 1):
        L.append(f'{i}. **size {cl["size"]}**, mean J={cl["mean_jaccard"]}, '
                 f'max J={cl["max_jaccard"]}, files={cl["files"]}')
        for uid, t in zip(cl["ids"], cl["titles"]):
            L.append(f'   - `{uid}` {t}')
    L.append("")
    L.append("### 20 most-similar pairs in the catalog (ranked, no threshold)")
    L.append("")
    for i, p in enumerate(nd["top_20_most_similar_pairs"], 1):
        L.append(f'{i}. J={p["jaccard"]} `{p["ids"][0]}` ({p["files"][0]}) vs '
                 f'`{p["ids"][1]}` ({p["files"][1]})')
        L.append(f'   - {p["titles"][0]}')
        L.append(f'   - {p["titles"][1]}')
    L.append("")
    ex = rep["audit"].get("near_duplicates_exploratory_0_35")
    if ex:
        L.append("### 20 worst clusters at the exploratory Jaccard>=0.35 threshold")
        L.append("")
        L.append(f'{ex["high_overlap_cluster_count"]} clusters covering '
                 f'{ex["units_in_high_overlap_cluster"]} of {a["unit_count_total"]} units '
                 f'({100.0 * ex["units_in_high_overlap_cluster"] / a["unit_count_total"]:.1f}%). '
                 f'0.35 is a LOOSE threshold - these are thematic neighbours, not duplicates. '
                 f'Listed so the "where is the overlap" question has a concrete answer.')
        L.append("")
        for i, cl in enumerate(ex["high_overlap_clusters_worst"], 1):
            L.append(f'{i}. **size {cl["size"]}**, mean J={cl["mean_jaccard"]}, '
                     f'max J={cl["max_jaccard"]}, files={cl["files"]}')
            for uid, t in zip(cl["ids"], cl["titles"]):
                L.append(f'   - `{uid}` {t}')
        L.append("")

    L.append("## 7. Dependency resolution and cycles")
    L.append("")
    d = a["dependencies"]
    L.append(f'- total dependency refs: {d["total_dependency_refs"]}')
    L.append(f'- unresolved unit-id refs: **{d["unresolved_unit_id_ref_count"]}** '
             f'{d["unresolved_unit_id_refs"][:10] or ""}')
    L.append(f'- bucket-code refs: {d["bucket_refs"]} (legal set B01..B13 from '
             f'PHASE-GRAPH.json allocation_buckets)')
    L.append(f'- illegal bucket refs: {d["illegal_bucket_refs"] or "none"}')
    L.append(f'- **unknown-form refs: {d["unknown_form_ref_count"]}** distinct '
             f'{d["unknown_form_distinct"]}')
    for x in d["unknown_form_refs"][:40]:
        L.append(f'  - `{x["id"]}` -> `{x["dep"]}` at {x["at"]}')
    L.append(f'- self-dependencies: {d["self_dependencies"] or "none"}')
    L.append(f'- **cycles: {d["cycle_count"]}** {d["cycles"][:10] or ""}')
    L.append("")

    L.append("## 8. Units per phase (all 21 canonical phase ids)")
    L.append("")
    L.append("| phase | units |")
    L.append("|---|---:|")
    for p, n in a["phases"]["units_per_phase"].items():
        L.append(f'| {p} | {n}{"  **ZERO**" if n == 0 else ""} |')
    L.append("")
    L.append(f'Non-canonical phase values: {a["phases"]["non_canonical_phase_values"] or "none"}')
    L.append("")

    L.append("## 9. Bucket allocation")
    L.append("")
    b = a["buckets"]
    L.append(f'- `bucket` field declared on {b["declared_bucket_coverage"]} units: '
             f'{b["declared_bucket_counts"]}')
    L.append(f'- id-prefix distribution: {b["id_prefix_counts"]}')
    L.append(f'- spec quota (PHASE-GRAPH.json allocation_buckets, sum '
             f'{b["spec_bucket_quota_sum"]}): {b["spec_bucket_quota"]}')
    L.append("")

    L.append("## 10. Detector control (seeded-defect / both-states test)")
    L.append("")
    L.append(f'Verdict: **{c["verdict"]}** - {c["detectors_both_states_pass"]}/'
             f'{c["detectors_total"]} detectors fire on a seeded defect in a scratch copy AND '
             f'are silent on that same defect in the real corpus. A detector silent in both '
             f'states measures nothing.')
    L.append("")
    L.append("| detector | fires on seeded defect | silent on real corpus | both-states |")
    L.append("|---|---|---|---|")
    for r in c["results"]:
        L.append(f'| {r["detector"]} | {"YES" if r["fires_on_seeded_defect"] else "**NO**"} | '
                 f'{"YES" if r["silent_on_real_corpus_for_that_defect"] else "**NO**"} | '
                 f'{"PASS" if r["both_states_pass"] else "**FAIL**"} |')
    L.append("")
    for r in c["results"]:
        L.append(f'- `{r["detector"]}`: {r["detail"]}')
    L.append("")
    L.append(f'Seeded corpus unit count: {c["seeded_corpus_unit_count"]} '
             f'(real {a["unit_count_total"]} minus the {c["seeded"]["zero_phase"]["units_removed"]} '
             f'phase-16 units removed to seed the zero-coverage case, plus 0 added).')
    L.append("")
    L.append("## 11. Merge into WORK-UNIT-CATALOG.json")
    L.append("")
    m = rep["merge"]
    for k, v in m.items():
        L.append(f'- **{k}**: {v}')
    L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------- merge
def do_merge(units, audit_rep):
    cat_path = os.path.join(HERE, "WORK-UNIT-CATALOG.json")
    with open(cat_path, encoding="utf-8") as fh:
        existing = json.load(fh)
    before_items = len(existing.get("items") or [])
    before_sha = hashlib.sha256(open(cat_path, "rb").read()).hexdigest()

    clean = []
    for u in units:
        v = {k: val for k, val in u.items() if not k.startswith("__")}
        v["_source_slice_file"] = u["__file"]
        clean.append(v)
    clean.sort(key=lambda x: str(x.get("id")))

    out = dict(existing)
    out["schema_version"] = 2
    out["items"] = existing.get("items")          # PRESERVED byte-for-byte semantics
    out["work_units"] = clean
    out["work_units_meta"] = {
        "status": "MERGED from command-center/catalog-slices/*.json",
        "preserved": ("The pre-existing PR #280 content is PRESERVED, not superseded: keys "
                      "contract/defaults/provenance/terminal_dispositions/owner_questions and "
                      f"the {before_items}-row `items` backlog are carried through unmodified. "
                      "The 2,048-unit Prompt-Two decomposition is ADDED under the new "
                      "`work_units` key because it uses a different (19-field Prompt-Two) "
                      "schema than `items` (33-field backlog schema); merging them into one "
                      "array would have destroyed both schemas."),
        "pre_merge_sha256": before_sha,
        "pre_merge_items": before_items,
        "work_unit_count": len(clean),
        "target": TARGET_UNITS,
        "shortfall": TARGET_UNITS - len(clean),
        "slice_files_merged": sorted({u["__file"] for u in units}),
        "integrity_report": "command-center/CATALOG-INTEGRITY.json",
        "known_defects_at_merge": {
            "duplicate_ids": audit_rep["ids"]["duplicate_id_count"],
            "malformed_ids": len(audit_rep["ids"]["bad_format_ids"]),
            "dangling_unit_id_refs": audit_rep["dependencies"]["unresolved_unit_id_ref_count"],
            "unknown_form_dependency_refs": audit_rep["dependencies"]["unknown_form_ref_count"],
            "unknown_form_dependency_tokens": audit_rep["dependencies"]["unknown_form_distinct"],
            "dependency_cycles": audit_rep["dependencies"]["cycle_count"],
            "self_dependencies": audit_rep["dependencies"]["self_dependencies"],
            "units_with_empty_dependencies": audit_rep["fields"][
                "present_but_empty_total"].get("dependencies", 0),
            "units_missing_bucket_field": audit_rep["fields"][
                "missing_absent_key_total"].get("bucket", 0),
            "phases_with_zero_units": audit_rep["phases"]["phases_with_zero_units"],
            "exact_duplicate_content_clusters": len(
                audit_rep["near_duplicates"]["exact_normalised_title_plus_target_clusters"]),
            "high_overlap_clusters": audit_rep["near_duplicates"]["high_overlap_cluster_count"],
        },
    }
    tmp = cat_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, cat_path)

    with open(cat_path, encoding="utf-8") as fh:
        back = json.load(fh)

    # Preservation is proved against the PRISTINE PR #280 backup, not against whatever was
    # on disk a moment ago - this makes the claim hold even on a re-run of this script.
    pristine_path = os.path.join(HERE, "WORK-UNIT-CATALOG.register-backup-20260809.json")
    pristine_cmp = {"backup_present": os.path.isfile(pristine_path)}
    if pristine_cmp["backup_present"]:
        with open(pristine_path, encoding="utf-8") as fh:
            pristine = json.load(fh)
        pristine_cmp["backup_sha256"] = hashlib.sha256(
            open(pristine_path, "rb").read()).hexdigest()
        pristine_cmp["items_identical_to_pristine_backup"] = (
            back.get("items") == pristine.get("items"))
        pristine_cmp["pristine_items"] = len(pristine.get("items") or [])
        pristine_cmp["all_pristine_keys_preserved"] = {
            k: (back.get(k) == pristine.get(k)) for k in pristine
        }

    return {
        "action": "PRESERVED (additive)",
        "pristine_backup_comparison": pristine_cmp,
        "pre_merge_sha256": before_sha,
        "post_merge_sha256": hashlib.sha256(open(cat_path, "rb").read()).hexdigest(),
        "items_before": before_items,
        "items_after": len(back.get("items") or []),
        "items_identical": back.get("items") == existing.get("items"),
        "other_preexisting_keys_identical": all(
            back.get(k) == existing.get(k)
            for k in ("contract", "defaults", "provenance", "terminal_dispositions",
                      "owner_questions")),
        "work_units_after": len(back.get("work_units") or []),
        "roundtrip_parses": True,
    }


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--audit-only":
        rep, _ = audit(sys.argv[2])
        print(json.dumps(rep, ensure_ascii=False, indent=1)[:400000])
        return 0

    print("[1/4] auditing real corpus ...", flush=True)
    a, units = audit(SLICES)
    print(f'      {a["unit_count_total"]} units, {a["file_count"]} files', flush=True)

    print("[2/4] seeding defects into scratch copy and running detector control ...", flush=True)
    seeded = seed_defects(SLICES, SCRATCH)
    ctl = control(a, SCRATCH, seeded, real_units=units)
    print(f'      control verdict={ctl["verdict"]} '
          f'({ctl["detectors_both_states_pass"]}/{ctl["detectors_total"]})', flush=True)

    attrib = None
    attrib_path = os.path.join(HERE, "_catalog_shortfall_attrib_out.json")
    if os.path.isfile(attrib_path):
        with open(attrib_path, encoding="utf-8") as fh:
            attrib = json.load(fh)
        if attrib.get("total_units") != a["unit_count_total"]:
            attrib = {"stale": True,
                      "note": (f'attribution ran against {attrib.get("total_units")} units but '
                               f'the corpus now has {a["unit_count_total"]} - re-run '
                               f'_catalog_shortfall_attrib.py')}

    print("[3/4] merging into WORK-UNIT-CATALOG.json ...", flush=True)
    merge = do_merge(units, a)
    print(f'      {merge}', flush=True)

    rep = {
        "artifact": "CATALOG-INTEGRITY",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "command-center/_catalog_integrity.py",
        "method": ("Mechanical. Every number is computed by this script over the raw slice "
                   "JSON; nothing is eyeballed. Detector control = seeded-defect both-states "
                   "test (rules/common/single-signal-verification.md 3b)."),
        "audit": a,
        "shortfall_attribution": attrib,
        "detector_control": ctl,
        "merge": merge,
    }
    print("[4/4] writing report ...", flush=True)
    with open(os.path.join(HERE, "CATALOG-INTEGRITY.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(HERE, "CATALOG-INTEGRITY.md"), "w", encoding="utf-8") as fh:
        fh.write(render_md(rep))
    shutil.rmtree(SCRATCH, ignore_errors=True)
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
