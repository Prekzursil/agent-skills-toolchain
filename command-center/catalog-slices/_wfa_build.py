# -*- coding: utf-8 -*-
"""Build WFA-1.json from the three hand-authored part files.

Mechanical work only: id assignment, preset expansion, dependency-key resolution,
field-completeness validation, and a lexical near-duplicate self-check.
All distinct content is authored in _wfa_part{1,2,3}.py.
"""
import json, os, re, sys, itertools

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _wfa_part1, _wfa_part2, _wfa_part3  # noqa: E402

UNITS = _wfa_part1.UNITS + _wfa_part2.UNITS + _wfa_part3.UNITS

CORPUS = "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
REPO = "C:/Users/Prekzursil/source/ast-integrate/"
OUT_DIR = "command-center/wfa/"
SCHEMA_PACK = "command-center/wfa/schema/wfa-schema-pack.json"

TOOLS = {
    "ro":      ["Read", "Grep", "Glob"],
    "calc":    ["Read", "Grep", "Glob", "Write",
                "Bash(python analysis only; no network, no git write)"],
    "git":     ["Read", "Grep", "Glob", "Write",
                "Bash(git read-only: ls-tree/cat-file/show/log/diff/worktree list; NO add/commit/push/reset)"],
    "live":    ["Read", "Grep", "Glob", "Write",
                "PowerShell(read-only: Get-ChildItem/Get-Content/Get-Command/Get-FileHash)"],
    "web":     ["Read", "Write", "WebSearch", "WebFetch",
                "mcp__search-hub__* (read-only retrieval)"],
    "gh":      ["Read", "Write", "mcp__github__search_code", "mcp__github__get_file_contents",
                "Bash(gh read-only: gh api GET, gh search, gh release list; NO write subcommands)"],
    "papers":  ["Read", "Write", "mcp__paper-search__*", "mcp__scholarly-access__*", "WebFetch"],
    "code":    ["Read", "Grep", "Glob", "Write", "Edit",
                "Bash(python, pytest; git read-only; NO add/commit/push)"],
    "xvendor": ["Read", "Grep", "Glob", "Write", "mcp__codex__codex", "mcp__codex__codex-reply"],
}

REVIEWER = {
    "adv":   ("one independent adversarial reviewer in a fresh context who did not author the unit; "
              "the reviewer must re-run this unit's own both-states control before signing PASS"),
    "xven":  ("cross-vendor: one Codex (openai) verifier that re-derives the result from raw sources plus "
              "one Claude adversarial reviewer; a split verdict is resolved by reading both probes, never by vote"),
    "sec":   ("one security reviewer (threat-model lens) plus one independent adversarial reviewer; "
              "both must attempt the named bypass and fail to achieve it before PASS"),
    "owner": ("one independent adversarial reviewer plus explicit owner sign-off on the scope or terminal "
              "decision; this unit may not self-certify an irreversible or owner-controlled outcome"),
}

RETRY = {
    "two":   ("two strikes then pivot: after the second failure on the same error fingerprint, enumerate at least "
              "two alternative approaches before any third attempt (AGENTS.md 4b)"),
    "net":   ("transient network / 429 / 5xx: up to 3 retries with exponential backoff and jittered arrival through "
              "the acquisition scheduler; any non-transient 4xx falls straight to the two-strikes pivot and is never retried"),
    "bench": ("no retry on a RED result - a failing benchmark is data, not a unit failure; retry only on harness error "
              "(crash, missing artifact, budget mismatch), maximum 2, then pivot"),
    "none":  ("no automatic retry: this unit's failure mode is itself a finding that must be reported to the owner, "
              "not re-attempted"),
}

SUBSTRATES = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A", "8",
          "9", "10", "11", "12", "13", "14", "15", "16"}

FIELDS = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
          "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
          "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
          "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
          "failure_classification", "owner_approval_required"]

BUCKET_CODES = {"B01", "B02", "B03", "B04", "B05"}


def expand_input(s):
    if s.startswith("corpus:"):
        return CORPUS + s[len("corpus:"):]
    if s.startswith("repo:"):
        return REPO + s[len("repo:"):]
    if s.startswith("spec:"):
        return CORPUS + "_USER-PROMPTS.md :: " + s[len("spec:"):]
    return s


keys = [u["k"] for u in UNITS]
assert len(keys) == len(set(keys)), "duplicate unit key: " + str(
    [k for k in keys if keys.count(k) > 1])
KEY2ID = {k: "WFA-%04d" % (i + 1) for i, k in enumerate(keys)}

out = []
for i, u in enumerate(UNITS):
    n = i + 1
    uid = "WFA-%04d" % n
    fname = u["out"]
    if fname.startswith("WFA-"):
        fname = "WFA-%04d-%s" % (n, fname[len("WFA-"):])
    sch = u["sch"]
    if sch == "__META__":
        schema = "https://json-schema.org/draft/2020-12/schema"
    else:
        schema = SCHEMA_PACK + "#/$defs/" + sch
    vend = u.get("vend", "anthropic")
    model = ("codex-cli-default (gpt-5.x class, whatever the mounted codex mcp-server resolves)"
             if vend == "openai" else "opus")
    deps = []
    for d in u["dep"]:
        if d in BUCKET_CODES:
            deps.append(d)
        else:
            if d not in KEY2ID:
                raise SystemExit("unresolved dependency key %r in unit %s" % (d, u["k"]))
            deps.append(KEY2ID[d])
    rec = {
        "id": uid,
        "title": u["t"],
        "phase": u["ph"],
        "question_or_target": u["q"],
        "inputs": [expand_input(x) for x in u["inp"]],
        "dependencies": deps,
        "assigned_model_vendor_role": {"model": model, "vendor": vend, "role": u["role"]},
        "tool_permissions": TOOLS[u["tp"]],
        "execution_substrate": u["sub"],
        "timeout_seconds": u["to"],
        "output_path": OUT_DIR + fname,
        "output_schema": schema,
        "evidence_requirement": u["ev"],
        "tests_required": u["tr"],
        "reviewer_requirement": REVIEWER[u["rv"]],
        "completion_sentinel": "SUCCESS:" + uid,
        "retry_policy": RETRY[u["rt"]],
        "failure_classification": u["fc"],
        "owner_approval_required": bool(u["oa"]),
    }
    out.append(rec)

# ---- validation -----------------------------------------------------------
errs = []
seen_out = {}
for r in out:
    for f in FIELDS:
        if f not in r:
            errs.append("%s missing field %s" % (r["id"], f))
        v = r[f]
        if v is None or (isinstance(v, (list, str)) and len(v) == 0):
            if f != "dependencies":
                errs.append("%s empty field %s" % (r["id"], f))
    if list(r.keys()) != FIELDS:
        errs.append("%s field order/extra mismatch: %s" % (r["id"], list(r.keys())))
    if r["phase"] not in PHASES:
        errs.append("%s bad phase %s" % (r["id"], r["phase"]))
    if r["execution_substrate"] not in SUBSTRATES:
        errs.append("%s bad substrate %s" % (r["id"], r["execution_substrate"]))
    if not r["question_or_target"].endswith("?") and not r["question_or_target"].startswith(
            "Implementation target:"):
        errs.append("%s question_or_target is neither a question nor an implementation target" % r["id"])
    if r["output_path"] in seen_out:
        errs.append("%s duplicate output_path with %s" % (r["id"], seen_out[r["output_path"]]))
    seen_out[r["output_path"]] = r["id"]
    if len(r["tests_required"]) < 2:
        errs.append("%s fewer than 2 tests_required" % r["id"])
    if "A:" not in r["evidence_requirement"] or "B:" not in r["evidence_requirement"]:
        errs.append("%s evidence_requirement lacks two labelled signals" % r["id"])

ids = [r["id"] for r in out]
if ids != ["WFA-%04d" % (i + 1) for i in range(len(out))]:
    errs.append("ids are not sequential from 1")

# ---- lexical near-duplicate self-check ------------------------------------
STOP = set("the a an of to and or for in on by with that which is are be as it its this "
           "each every must not no any all from at into than then so does do".split())


def toks(r):
    s = (r["title"] + " " + r["question_or_target"]).lower()
    return {w for w in re.findall(r"[a-z0-9-]+", s) if w not in STOP and len(w) > 2}


pairs = []
T = {r["id"]: toks(r) for r in out}
for a, b in itertools.combinations(out, 2):
    ta, tb = T[a["id"]], T[b["id"]]
    j = len(ta & tb) / float(len(ta | tb))
    pairs.append((j, a["id"], b["id"], a["title"][:58], b["title"][:58]))
pairs.sort(reverse=True)

print("UNITS: %d" % len(out))
print("VALIDATION ERRORS: %d" % len(errs))
for e in errs[:40]:
    print("  ! " + e)
print("\nTOP 12 LEXICAL NEAR-DUPLICATE PAIRS (token-Jaccard over title+target):")
for j, a, b, ta, tb in pairs[:12]:
    print("  %.3f  %s / %s\n         %s\n         %s" % (j, a, b, ta, tb))

import collections
print("\nphase histogram:", dict(collections.Counter(r["phase"] for r in out)))
print("substrate histogram:", dict(collections.Counter(r["execution_substrate"] for r in out)))
print("owner_approval_required True:", sum(1 for r in out if r["owner_approval_required"]))
print("vendor histogram:", dict(collections.Counter(
    r["assigned_model_vendor_role"]["vendor"] for r in out)))
print("distinct roles:", len({r["assigned_model_vendor_role"]["role"] for r in out}))
print("distinct failure_classification sets:", len({tuple(r["failure_classification"]) for r in out}))
print("distinct timeouts:", sorted({r["timeout_seconds"] for r in out}))

if errs:
    raise SystemExit("REFUSING TO WRITE: validation failed")

dst = os.path.join(HERE, "WFA-1.json")
with open(dst, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(out, fh, indent=2, ensure_ascii=True)
    fh.write("\n")
print("\nWROTE %s (%d bytes)" % (dst, os.path.getsize(dst)))
