# -*- coding: utf-8 -*-
"""Build + mechanically verify ADV-1.json (bucket B10, slice ADV-1of2, 128 units).

Verification performed here (mechanical, not judgement):
  V1 id sequence 1..128, zero-padded, unique
  V2 all 19 spec-mandated fields present and non-empty on every unit
  V3 enum validity: phase, execution_substrate
  V4 cross-vendor reviewer consistency (a single-vendor unit may not be reviewed by its own vendor)
  V5 within-slice near-duplicate detection (IDF-pruned token Jaccard) with a PLANTED-MUTANT control
  V6 cross-slice near-duplicate detection against every sibling slice
  V7 read-back from disk: parse + count (the count reported is read off disk, never from memory)
"""
import json
import os
import re
import sys
import itertools
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _adv_data1
import _adv_data2
import _adv_data3  # noqa: E402

OUT = os.path.join(HERE, "ADV-1.json")
BUCKET = "B10"
SLICE = "ADV-1of2"

VEND = {
 "a-ref":     {"model": "opus", "vendor": "anthropic", "role": "adversarial-refuter"},
 "o-ref":     {"model": "gpt-5-codex", "vendor": "openai", "role": "adversarial-refuter"},
 "a-sec":     {"model": "opus", "vendor": "anthropic", "role": "security-threat-modeler"},
 "o-sec":     {"model": "gpt-5-codex", "vendor": "openai", "role": "security-exploit-engineer"},
 "a-priv":    {"model": "opus", "vendor": "anthropic", "role": "privacy-analyst"},
 "a-legal":   {"model": "opus", "vendor": "anthropic", "role": "license-and-legal-analyst"},
 "o-sup":     {"model": "gpt-5-codex", "vendor": "openai", "role": "supply-chain-auditor"},
 "a-inj":     {"model": "opus", "vendor": "anthropic", "role": "prompt-injection-red-teamer"},
 "o-bench":   {"model": "gpt-5-codex", "vendor": "openai", "role": "benchmark-integrity-auditor"},
 "a-council": {"model": "opus", "vendor": "anthropic", "role": "groupthink-red-teamer"},
 "a-synth":   {"model": "opus", "vendor": "anthropic", "role": "synthesis-distortion-auditor"},
 "a-stale":   {"model": "opus", "vendor": "anthropic", "role": "stale-premise-refuter"},
 "o-plat":    {"model": "gpt-5-codex", "vendor": "openai", "role": "platform-fault-injector"},
 "mix":       {"model": "opus + gpt-5-codex (>=2 vendors, run independently, results compared not merged)",
               "vendor": "mixed", "role": "paired-independent-refuter"},
}

TOOLS = {
 "read":    ["Read", "Grep", "Glob"],
 "readbash":["Read", "Grep", "Glob", "Bash"],
 "code":    ["Read", "Grep", "Glob", "Bash", "Write", "Edit"],
 "web":     ["Read", "Grep", "Glob", "WebFetch", "WebSearch",
             "mcp__search-hub__tavily_search", "mcp__search-hub__web_search_exa"],
 "mem":     ["Read", "Grep", "Glob", "mcp__basic-memory__search_notes",
             "mcp__basic-memory__read_note", "mcp__basic-memory__recent_activity"],
 "mail":    ["Read", "Grep", "Glob", "Bash", "mcp__agent-mail__fetch_inbox",
             "mcp__agent-mail__send_message", "mcp__agent-mail__file_reservation_paths"],
 "sandbox": ["Read", "Grep", "Glob", "Bash", "Write",
             "mcp__cloud-hub__modal_sandbox_create", "mcp__cloud-hub__modal_sandbox_exec",
             "mcp__cloud-hub__modal_sandbox_terminate"],
}

SCHEMA = {
 "refutation": "command-center/schema/refutation-record.schema.json",
 "threat":     "command-center/schema/threat-model.schema.json",
 "exploit":    "command-center/schema/exploit-proof.schema.json",
 "privacy":    "command-center/schema/privacy-dataflow.schema.json",
 "license":    "command-center/schema/license-and-rights-record.schema.json",
 "supply":     "command-center/schema/supply-chain-attestation.schema.json",
 "injection":  "command-center/schema/injection-corpus-result.schema.json",
 "benchmark":  "command-center/schema/benchmark-integrity.schema.json",
 "council":    "command-center/schema/council-pathology-sim.schema.json",
 "stale":      "command-center/schema/stale-premise-reprobe.schema.json",
 "fault":      "command-center/schema/fault-injection-run.schema.json",
}

REVIEWER = {
 "xv-codex": ("one cross-vendor Codex (openai) refuter who re-derives the counterexample from the raw "
              "artifact and NOT from this unit's report; a same-vendor reviewer shares this unit's blind "
              "spots and does not satisfy the requirement"),
 "xv-claude":("one cross-vendor Anthropic (opus) refuter who re-derives the counterexample from the raw "
              "artifact and NOT from this unit's report; a same-vendor reviewer shares this unit's blind "
              "spots and does not satisfy the requirement"),
 "two":      ("two reviewers from DIFFERENT vendors must each independently reproduce the counterexample; "
              "a split verdict is escalated to the owner with both raw probes attached and is NEVER "
              "resolved by vote - the specific probe wins over the reviewer count"),
 "owner":    ("one cross-vendor refuter PLUS explicit owner sign-off, because the finding changes security "
              "posture, legal exposure, or an owner-controlled action; the reviewer may not approve the "
              "owner-gated part"),
}

RETRY = {
 "two-strikes": ("two strikes then pivot (AGENTS.md 4b): after the SECOND failure on the same hypothesis, "
                 "enumerate >=2 mechanically different attack vectors before any third attempt; consecutive "
                 "FAILED on the same error fingerprint is the trigger"),
 "reprobe":     ("retry ONLY with a mechanically different probe; re-running the identical probe is banned "
                 "and its result may never be reported as CONFIRMED (single-signal-verification rule 5). "
                 "Max 3 attempts, each with a distinct instrument recorded"),
 "backoff":     ("up to 3 attempts with staggered arrival (60s / 300s / 900s) because this unit depends on "
                 "external endpoints; a 429/529 is provider-side and is NOT a unit failure and must NOT "
                 "reduce concurrency"),
 "none-destructive": ("NO automatic retry: this unit performs a destructive, state-changing or "
                      "owner-gated drill. On failure STOP, preserve the partial artifact and the restore "
                      "point, and report BLOCKED with the exact missing prerequisite"),
}

PHASES = {"0","1","2","2A","2B","2C","3","4","5","6","7","7A","8","9","10","11","12","13","14","15","16"}
SUBSTRATES = {"local-serialized","local-parallel","worktree-isolated","cloud-batch"}
MANDATED = ["id","title","phase","question_or_target","inputs","dependencies",
            "assigned_model_vendor_role","tool_permissions","execution_substrate","timeout_seconds",
            "output_path","output_schema","evidence_requirement","tests_required",
            "reviewer_requirement","completion_sentinel","retry_policy","failure_classification",
            "owner_approval_required"]

raw = _adv_data1.UNITS + _adv_data2.UNITS + _adv_data3.UNITS
corrections = []

def build(u):
    uid = "ADV-%04d" % u["n"]
    amr = dict(VEND[u["v"]])
    rv = u["rv"]
    # V4: a single-vendor unit may not be reviewed by its own vendor.
    if rv == "xv-codex" and amr["vendor"] == "openai":
        corrections.append((uid, "reviewer xv-codex -> xv-claude (assignee is openai)")); rv = "xv-claude"
    if rv == "xv-claude" and amr["vendor"] == "anthropic":
        corrections.append((uid, "reviewer xv-claude -> xv-codex (assignee is anthropic)")); rv = "xv-codex"
    sentinel = ("SUCCESS:%s emitted ONLY when the artifact at output_path exists, is non-empty, parses "
                "against output_schema, records BOTH named probes verbatim with their raw output, carries "
                "exactly one verdict from {CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated "
                "target, and records the result of every listed control/negative test. Any missing control "
                "downgrades the unit's verdicts to NOT-CHECKED. Otherwise FAILED:%s <reason>." % (uid, uid))
    return {
        "id": uid,
        "title": u["t"],
        "phase": u["ph"],
        "question_or_target": u["q"],
        "inputs": list(u["inp"]),
        "dependencies": list(u["dep"]),
        "assigned_model_vendor_role": amr,
        "tool_permissions": list(TOOLS[u["tl"]]),
        "execution_substrate": u["sub"],
        "timeout_seconds": u["to"],
        "output_path": "command-center/adversarial/%s-%s.json" % (uid, u["sl"]),
        "output_schema": SCHEMA[u["sch"]],
        "evidence_requirement": u["ev"],
        "tests_required": list(u["ts"]),
        "reviewer_requirement": REVIEWER[rv],
        "completion_sentinel": sentinel,
        "retry_policy": RETRY[u["rt"]],
        "failure_classification": list(u["fc"]),
        "owner_approval_required": bool(u["oa"]),
        "bucket": BUCKET,
        "slice": SLICE,
        "mechanism": u["mech"],
        "not_a_duplicate_because": u["nd"],
        "spec_anchor": u["sa"],
    }

units = [build(u) for u in raw]

# ---------------------------------------------------------------- V1 id sequence
errs = []
ns = [u["n"] for u in raw]
if ns != list(range(1, len(ns) + 1)):
    errs.append("V1 FAIL: n sequence is not 1..%d contiguous" % len(ns))
if len(set(x["id"] for x in units)) != len(units):
    errs.append("V1 FAIL: duplicate ids")

# ---------------------------------------------------------------- V2/V3 fields + enums
for u in units:
    for f in MANDATED:
        if f not in u:
            errs.append("V2 FAIL %s missing %s" % (u["id"], f)); continue
        v = u[f]
        if isinstance(v, bool):
            continue
        if v is None or (hasattr(v, "__len__") and len(v) == 0):
            errs.append("V2 FAIL %s empty %s" % (u["id"], f))
        if isinstance(v, str) and len(v.strip()) < 8 and f != "phase":
            errs.append("V2 FAIL %s suspiciously short %s=%r" % (u["id"], f, v))
    if u["phase"] not in PHASES:
        errs.append("V3 FAIL %s bad phase %r" % (u["id"], u["phase"]))
    if u["execution_substrate"] not in SUBSTRATES:
        errs.append("V3 FAIL %s bad substrate %r" % (u["id"], u["execution_substrate"]))
    if not isinstance(u["timeout_seconds"], int) or u["timeout_seconds"] <= 0:
        errs.append("V3 FAIL %s bad timeout" % u["id"])
    a = u["assigned_model_vendor_role"]
    if not all(k in a and a[k] for k in ("model", "vendor", "role")):
        errs.append("V3 FAIL %s bad assigned_model_vendor_role" % u["id"])
    # forward/backward reference integrity inside not_a_duplicate_because
    for ref in re.findall(r"ADV-(\d{4})", u["not_a_duplicate_because"]):
        if not (1 <= int(ref) <= len(units)):
            errs.append("V3 FAIL %s references out-of-range %s" % (u["id"], ref))

# ---------------------------------------------------------------- V5/V6 near-duplicate detection
STOP = set("""the a an and or of to in on for with that this it is are be by as at from into over under not no
which what when where does do can any every each all their its they them we you your our than then so such
must may should would could will shall if else per via using use used unit units work program spec probe
probes record records result results report reports run runs ran test tests testing check checks checked
against between across without within before after during while whether against""".split())

def toks(s):
    return set(w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) >= 4 and w not in STOP)

def sig(u):
    return toks(u["title"] + " " + u["question_or_target"] + " " + u.get("mechanism", ""))

sigs = [sig(u) for u in units]
df = collections.Counter()
for s in sigs:
    for t in s:
        df[t] += 1
cut = max(2, int(0.30 * len(units)))
pruned = [set(t for t in s if df[t] <= cut) for s in sigs]

def jac(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))

# detector control: planted mutant (reworded copy of unit 1) + a known-distinct pair
mutant_src = units[0]
mutant_text = (mutant_src["title"].replace("Refute", "Disprove").replace("constructing", "building")
               + " " + mutant_src["question_or_target"] + " " + mutant_src["mechanism"])
mutant = set(t for t in toks(mutant_text) if df[t] <= cut)
ctrl_hi = jac(mutant, pruned[0])
ctrl_lo = jac(pruned[0], pruned[-1])
THRESH = 0.35
control_ok = (ctrl_hi >= 0.60) and (ctrl_lo < THRESH)
if not control_ok:
    errs.append("V5 FAIL detector control: planted-mutant sim=%.3f (need >=0.60), distinct-pair sim=%.3f "
                "(need <%.2f)" % (ctrl_hi, ctrl_lo, THRESH))

intra = []
for i, j in itertools.combinations(range(len(units)), 2):
    s = jac(pruned[i], pruned[j])
    if s >= THRESH:
        intra.append((round(s, 3), units[i]["id"], units[j]["id"], units[i]["title"], units[j]["title"]))
intra.sort(reverse=True)

# V6 cross-slice
cross = []
sib_count = 0
for fn in sorted(os.listdir(HERE)):
    if not fn.endswith(".json") or fn == "ADV-1.json":
        continue
    try:
        sib = json.load(open(os.path.join(HERE, fn), encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(sib, list):
        continue
    sib_count += 1
    for su in sib:
        st = set(t for t in toks(str(su.get("title", "")) + " " + str(su.get("question_or_target", "")))
                 if df[t] <= cut)
        for i, u in enumerate(units):
            s = jac(pruned[i], st)
            if s >= 0.45:
                cross.append((round(s, 3), u["id"], fn, su.get("id"), u["title"], su.get("title")))
cross.sort(reverse=True)

# ---------------------------------------------------------------- write + V7 read-back
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(units, fh, indent=1, ensure_ascii=True)
    fh.write("\n")

back = json.load(open(OUT, encoding="utf-8"))
on_disk = len(back)
ids = [u["id"] for u in back]

print("=" * 78)
print("BUILD %s" % OUT)
print("in-memory units : %d" % len(units))
print("ON-DISK units   : %d   (read back from the file)" % on_disk)
print("first / last id : %s / %s" % (ids[0], ids[-1]))
print("bytes on disk   : %d" % os.path.getsize(OUT))
print("-" * 78)
print("reviewer auto-corrections (V4): %d" % len(corrections))
for c in corrections:
    print("   ", c[0], c[1])
print("-" * 78)
print("V5 detector control : planted-mutant sim=%.3f  distinct-pair sim=%.3f  threshold=%.2f  -> %s"
      % (ctrl_hi, ctrl_lo, THRESH, "PASS" if control_ok else "FAIL"))
print("V5 intra-slice pairs >= %.2f : %d" % (THRESH, len(intra)))
for p in intra[:15]:
    print("    %.3f  %s | %s" % (p[0], p[1], p[2]))
    print("           A: %s" % p[3])
    print("           B: %s" % p[4])
print("V6 sibling slices scanned: %d ; cross-slice pairs >= 0.45 : %d" % (sib_count, len(cross)))
for p in cross[:15]:
    print("    %.3f  %s  vs  %s:%s" % (p[0], p[1], p[2], p[3]))
    print("           A: %s" % p[4])
    print("           B: %s" % p[5])
print("-" * 78)
dist = collections.Counter(u["phase"] for u in back)
print("phase       :", dict(sorted(dist.items(), key=lambda kv: (len(kv[0]), kv[0]))))
print("substrate   :", dict(collections.Counter(u["execution_substrate"] for u in back)))
print("vendor      :", dict(collections.Counter(u["assigned_model_vendor_role"]["vendor"] for u in back)))
print("owner-gated :", sum(1 for u in back if u["owner_approval_required"]))
print("schemas     :", len(set(u["output_schema"] for u in back)))
print("uniq outpath:", len(set(u["output_path"] for u in back)))
print("-" * 78)
if errs:
    print("ERRORS (%d):" % len(errs))
    for e in errs[:40]:
        print("   ", e)
    print("FAILED:catalog-ADV-1of2 validation errors")
    sys.exit(1)
print("SUCCESS:catalog-ADV-1of2 units_on_disk=%d ids=%s..%s" % (on_disk, ids[0], ids[-1]))
