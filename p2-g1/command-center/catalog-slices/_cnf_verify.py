#!/usr/bin/env python3
"""Independent read-back verification of CNF-1.json.

Deliberately does NOT import the generator or its data modules: it reads the
bytes off disk and re-derives every count, so a generator bug cannot certify
itself. Includes planted-mutant DETECTOR CONTROLS (a zero is only meaningful
once the detector is shown to fire on a known-broken input).
"""
import collections
import json
import pathlib
import re
import sys
from itertools import combinations

p = pathlib.Path(__file__).with_name("CNF-1.json")
raw = p.read_bytes()
units = json.loads(raw.decode("utf-8"))

print("file          :", p)
print("bytes on disk :", len(raw))
print("units on disk :", len(units))
print("first id      :", units[0]["id"])
print("last id       :", units[-1]["id"])

REQUIRED = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
            "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
            "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
            "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
            "failure_classification", "owner_approval_required"]

problems = []
for u in units:
    missing = [f for f in REQUIRED if f not in u]
    extra = [f for f in u if f not in REQUIRED]
    if missing:
        problems.append("%s missing %s" % (u.get("id"), missing))
    if extra:
        problems.append("%s extra %s" % (u.get("id"), extra))
    if u["id"] not in u["completion_sentinel"]:
        problems.append("%s sentinel does not name its own id" % u["id"])
    if u["id"][4:] not in u["output_path"] and not u["output_path"].endswith(".schema.json"):
        problems.append("%s output_path does not carry its id" % u["id"])
print("fields per unit:", sorted({len(u) for u in units}))
print("field problems :", problems or "NONE")

ids = [u["id"] for u in units]
seq_ok = ids == ["CNF-%04d" % i for i in range(1, len(units) + 1)]
print("ids unique     :", len(set(ids)) == len(ids))
print("ids sequential :", seq_ok)
print("output_path uniq:", len({u["output_path"] for u in units}) == len(units))

# ---- distributions: a field with 1 distinct value is a global default in disguise
print()
print("DISTRIBUTIONS")
for label, fn in [
    ("phase", lambda u: u["phase"]),
    ("substrate", lambda u: u["execution_substrate"]),
    ("vendor", lambda u: u["assigned_model_vendor_role"]["vendor"]),
    ("model", lambda u: u["assigned_model_vendor_role"]["model"]),
    ("timeout_seconds", lambda u: u["timeout_seconds"]),
    ("tool_permissions(len)", lambda u: len(u["tool_permissions"])),
    ("owner_approval_required", lambda u: u["owner_approval_required"]),
    ("retry_policy(head)", lambda u: u["retry_policy"][:18]),
    ("reviewer(head)", lambda u: u["reviewer_requirement"][:22]),
    ("output_schema", lambda u: u["output_schema"].split("/")[-1]),
]:
    c = collections.Counter(fn(u) for u in units)
    print("  %-24s distinct=%-3d %s" % (label, len(c), dict(c.most_common(8))))
print("  %-24s distinct=%-3d" % ("role", len({u["assigned_model_vendor_role"]["role"] for u in units})))
print("  %-24s distinct=%-3d" % ("failure_classification set",
                                 len({tuple(u["failure_classification"]) for u in units})))

# ---- dependency integrity ------------------------------------------------
idset = set(ids)
bad = []
buckets = collections.Counter()
for u in units:
    for d in u["dependencies"]:
        if d.startswith("CNF-"):
            if d not in idset:
                bad.append((u["id"], d, "dangling"))
            elif d >= u["id"]:
                bad.append((u["id"], d, "forward-or-self"))
        elif re.fullmatch(r"B(0[1-9]|1[0-3])", d):
            buckets[d] += 1
        else:
            bad.append((u["id"], d, "unknown-code"))
print()
print("dep problems   :", bad or "NONE")
print("bucket deps    :", dict(sorted(buckets.items())))

# ---- MECHANICAL near-duplicate scan --------------------------------------
STOP = set(("the a an and or of to in for that this with must be is are on by not it its as at from "
            "into then than which what when where any every each per does do can no non one two unit "
            "units work spec target question implementation confirm confirmation must-be").split())


def toks(text):
    return {w for w in re.findall(r"[a-z0-9_.-]{3,}", text.lower()) if w not in STOP}


def body(u):
    return u["title"] + " " + u["question_or_target"]


def jac(a, b):
    return len(a & b) / len(a | b) if (a | b) else 0.0


# Review threshold is CALIBRATED from the planted-paraphrase control below
# (measured 0.189 on the first pass), not chosen to make the corpus look clean.
REVIEW_T = 0.18

T = {u["id"]: toks(body(u)) for u in units}
title_by = {u["id"]: u["title"] for u in units}
pairs = []
for a, b in combinations(ids, 2):
    s = jac(T[a], T[b])
    if s >= REVIEW_T:
        pairs.append((round(s, 3), a, b))
pairs.sort(reverse=True)
print()
print("NEAR-DUPLICATE SCAN (token Jaccard over title+target, >= %.2f): %d pairs" % (REVIEW_T, len(pairs)))
for s, a, b in pairs[:20]:
    print("   %.3f  %s / %s" % (s, a, b))
    print("          %s" % title_by[a][:88])
    print("          %s" % title_by[b][:88])
worst = max(jac(T[a], T[b]) for a, b in combinations(ids, 2))
print("   corpus max jaccard: %.3f" % worst)

# ---- DETECTOR CONTROLS ---------------------------------------------------
# The scan above reporting few pairs means nothing unless it fires on a planted
# duplicate. Three mutant classes, mirroring the sibling CC-1 control.
base = {u["id"]: body(u) for u in units}
m_rename = "A different heading entirely " + units[40]["question_or_target"]          # exact rename
m_para = ("Re-run the security scan across the whole repository history rather than only the current "
          "checkout, using two different scanners, and require a synthetic planted canary to be found "
          "by both before any empty result is believed. Never print a value and never rotate anything.")
m_rewrite = ("Take the deliverable that was actually built and drive a handful of realistic end to end "
             "journeys through it, finishing each one by inspecting the file it wrote on disk for "
             "existence, size and format rather than trusting the process exit status.")
controls = [("exact-rename", "CNF-0041", m_rename),
            ("paraphrase", "CNF-0108", m_para),
            ("full-rewrite", "CNF-0039", m_rewrite)]
print()
print("DETECTOR CONTROL (same tokenizer, review threshold %.2f)" % REVIEW_T)
ctrl_ok = True
for name, target, mutant in controls:
    s = jac(toks(base[target]), toks(mutant))
    fired = s >= REVIEW_T
    if name in ("exact-rename", "paraphrase") and not fired:
        ctrl_ok = False
    print("   %-13s vs %s : %.3f -> %s" % (name, target, s, "FIRES" if fired else "SILENT"))
print("   SCOPE: this detector is LEXICAL and its paraphrase margin is thin (control ~0.19 against a")
print("   0.18 threshold). A heavier paraphrase or a full vocabulary rewrite lands in the same band as a")
print("   genuinely distinct unit, so a clean reading rules out LEXICAL near-duplication only. Settling")
print("   experiment: rescan with embedding cosine using these same three planted mutants as controls.")

ok = (not problems and not bad and len(units) == 128 and seq_ok and ctrl_ok
      and len({u["output_path"] for u in units}) == len(units))
print()
print("VERDICT:", "SUCCESS:verify-CNF-1" if ok else "FAILED:verify-CNF-1")
sys.exit(0 if ok else 1)
