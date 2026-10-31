# -*- coding: utf-8 -*-
"""Expand the BLD unit specs into the 19 contract fields and write BLD-1.json.

Field names are taken from the on-disk convention shared by all 13 existing
catalog slices (verified: every slice uses the same 19 keys, with
`question_or_target` and `assigned_model_vendor_role` as the long forms of the
contract's `target` / `assignment`).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _bld_data1 import UNITS_1  # noqa: E402
from _bld_data2 import UNITS_2  # noqa: E402

SPECS = UNITS_1 + UNITS_2

CROSS_VENDOR_BASIS = (
    "cross-vendor independence: this unit audits work the Anthropic-vendor corpus "
    "produced, so the reader must not share the author's blind spots "
    "(C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10579)"
)
OPUS_BASIS = "substantive subagent - Opus floor (rules/common/performance.md)"

# The eleven Phase 13 questions, _USER-PROMPTS.md:11069-11080.
QUESTIONS = {
    "files-never-read": "what files were never read",
    "clients-never-tested": "what clients were never tested",
    "platforms-never-tested": "what platforms were never tested",
    "owner-requirements-disappeared": "what owner requirements disappeared",
    "option-ids-dropped": "what option IDs were silently dropped",
    "failures-normalized-away": "what failures were normalized away",
    "unknowns-remain": "what unknowns remain",
    "existing-work-ignored": "what existing work was ignored",
    "test-could-falsely-pass": "what test could falsely pass",
    "threat-actor-not-modeled": "what threat actor was not modeled",
    "ten-x-scale": "what would break at 10x scale",
    "meta": "meta: completeness of the blind-spot review itself (disposition rule, _USER-PROMPTS.md:11082)",
}

SUBSTRATES = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}

# ---------------------------------------------------------------------------
# CROSS-BUCKET ADJUDICATION MAP
#
# Measured 2026-08-09 against the 21 sibling slices then on disk (1,943 units). A lexical
# duplicate detector CANNOT be trusted here: the siblings write one-sentence targets, so
# Jaccard is structurally deflated, and even a containment coefficient scored only 0.294 on a
# pair CONFIRMED duplicate by reading both texts. Every entry below was therefore adjudicated by
# READING both units, with the metric used only as a recall screen (containment >= 0.29).
#
# Four confirmed FULL duplicates were merged away inside the unit data (see the MERGE NOTE
# comments on BLD-0013/0040/0050/0052). The entries here are the PARTIAL overlaps: the sibling
# owns part of the ground, and the boundary states what this unit contributes on top and which
# receipt it consumes. They are appended to question_or_target so the boundary ships WITH the
# unit, and the verifier requires every high-containment pair to be named in one of them.
#
# NOT unilaterally deleted: the sibling corpus was still GROWING during this run (1,815 -> 1,943
# units), and if two concurrent agents both delete "their" copy of a shared mechanism it ends up
# owned by nobody. Deletion across buckets is the orchestrator's call, not a slice author's.
# ---------------------------------------------------------------------------
BOUNDARIES = {
    "BLD-0002": "SCOPE BOUNDARY: AUD-0032 censuses unreferenced modules and dead code. This unit consumes that receipt and contributes ENTRY-POINT reachability, which is a different question - a module can be referenced by a test and still be reachable from no CLI command, hook registration or MCP export. Report only the delta.",
    "BLD-0003": "SCOPE BOUNDARY: AUD-0082, TST-0197 and IMP-0467 own the Windows reserved-name, long-path and case-collision surface. The subject here is the STRUCTURALLY UNREADABLE content classes - binary, encrypted, oversized, gitignored - and the hostile-path classes appear only as the enumerator-robustness control.",
    "BLD-0004": "SCOPE BOUNDARY: TST-0112, TST-0251, IMP-0120 and CNF-0191 own docs-versus-code parity for flags, the package surface and executed commands. This unit contributes the identifier space none of them covers - workflow ids, council preset ids, hook event names and schema field names - and reports only that delta.",
    "BLD-0006": "SCOPE BOUNDARY: TST-0049 executes the compatibility-matrix conformance tests and ARC-0095 defines how an untested cell is represented. This unit contributes the EVIDENCE-QUALITY audit of the filled matrix: a cell may read RUN only on an observation from inside the client, never on an installer exit code.",
    "BLD-0011": "SCOPE BOUNDARY: AUD-0042 executes the 32 never-executed CI test steps. This unit contributes the INTERPRETER-VERSION axis - which declared runtime versions were never executed at all - which step coverage does not measure.",
    "BLD-0012": "SCOPE BOUNDARY: RES-0009 maps the hook contract and RES-0013 is the breaking-change archaeology. This unit consumes both and contributes the forward and backward one-release DRIFT PREDICTION for the surfaces they document.",
    "BLD-0014": "SCOPE BOUNDARY: AUD-0076 EXTRACTS owner requirements from the transcript. This unit detects CONTRADICTION - a shipped artifact that does the opposite of a binding decision - which extraction cannot surface.",
    "BLD-0015": "SCOPE BOUNDARY: CC-0024 extracts the floor statements and CNF-0188 recounts them with an independent extractor. This unit contributes the ANTI-PADDING control - proof that a renamed or near-duplicate entry does not increment a floor - which a recount alone cannot supply.",
    "BLD-0016": "SCOPE BOUNDARY: AUD-0076 covers owner requirements stated in the transcript. This unit probes the FINAL DELIVERABLES list for on-disk existence, byte size and sha256.",
    "BLD-0018": "SCOPE BOUNDARY: AUD-0076 extracts requirements at one point in time. This unit measures the TEMPORAL DIFF - capability present in an earlier scope statement and absent now - which a single-snapshot extraction cannot see.",
    "BLD-0019": "SCOPE BOUNDARY: SYN-0028 performs the terminal option-id closure at synthesis time. This unit runs the same closure EARLY, at Phase 13, so a missing disposition becomes a work unit instead of a release-time surprise. On any conflict SYN-0028's terminal verdict wins.",
    "BLD-0020": "SCOPE BOUNDARY: CC-0021 builds the namespace registry and its gate, CNF-0072 re-extracts it independently and CNF-0190 confirms single-meaning resolution. This unit consumes all three and contributes only the count of namespaces NOT yet in that registry - the wave-1 single-digit M-1/M-3 namespace is the known example.",
    "BLD-0021": "SCOPE BOUNDARY: AUD-0034 resolves option-ID cross-references corpus-wide. This unit contributes the UNDECIDABLE class specifically - references no algorithm can settle - and the owner escalation packet for them, which resolution alone does not produce.",
    "BLD-0023": "SCOPE BOUNDARY: AUD-0055 censuses skip and xfail markers with reason validity. This unit consumes that receipt and is the superset over NON-test suppression constructs: continue-on-error, || true, bare except: pass, -ErrorAction SilentlyContinue and warning filters.",
    "BLD-0028": "SCOPE BOUNDARY: ADV-0009 audits whether each DETECTOR can fire. This unit audits reported ZEROS - results already published without a recorded control - and re-queues each to its producing unit.",
    "BLD-0031": "SCOPE BOUNDARY: ADV-0108 audits unsupported certainty, comparing a stated band against its evidence. This unit contributes the MISSING-band population - claims carrying no band at all - which a band-versus-evidence audit structurally cannot see.",
    "BLD-0033": "SCOPE BOUNDARY: WFA-0120 is the anti-rebuild GATE for workflows specifically. This unit is the retrospective census across every artifact type the program built, and consumes WFA-0120 for the workflow rows.",
    "BLD-0035": "SCOPE BOUNDARY: CNF-0056 diffs the exported-symbol surface and WFA-0022 and WFA-0071 re-adjudicate the retirement candidates. This unit's subject is narrower and specific: for each of the 77 DELETED paths, does its behaviour still exist anywhere.",
    "BLD-0036": "SCOPE BOUNDARY: TST-0079 tests that live-deployment synchronisation is non-destructive under two-directional drift. This unit does not test the sync - it produces the per-file authority RULING and merge patch for the 28 files already diverged.",
    "BLD-0037": "SCOPE BOUNDARY: ADV-0018 sweeps the memory vault for contradictions against measured truth. This unit contributes the UNCONSULTED set - topically relevant notes that no program artifact ever cited - which a contradiction sweep does not measure.",
    "BLD-0038": "SCOPE BOUNDARY: AUD-0076 extracts owner requirements from the transcript. This unit consumes that extraction and contributes SPEAKER ATTRIBUTION plus reconciliation against the decision log, so an agent-authored sentence is never promoted into an owner requirement.",
    "BLD-0041": "SCOPE BOUNDARY: TST-0105 builds the benchmark non-empty-input control. This unit contributes the tree-wide tautological-test census in which the empty-input benchmark is one class.",
    "BLD-0042": "SCOPE BOUNDARY: AUD-0057 is the assertion-strength census of defaults a test never exercises. This unit consumes it and contributes the CI-INVOCATION join: a default is unexercised in the SHIPPED configuration when CI itself never passes the flag, which a test-side census cannot see.",
    "BLD-0044": "SCOPE BOUNDARY: AUD-0052 owns order-dependence and flake; CNF-0106 and CNF-0147 own the egress-blocked runs. This unit consumes all three single-axis receipts and contributes only the INTERACTION cross-product - timezone by cwd by cold-cache by order - where a defect appears in no single axis alone.",
    "BLD-0047": "SCOPE BOUNDARY: IMP-0437 arms the one disarmed check and TST-0076 mutation-tests that one validator. This unit consumes both and contributes the tree-wide census over every gate.",
    "BLD-0049": "SCOPE BOUNDARY: CNL-0100, WFA-0158 and CNF-0114 each defend one specific injection path. This unit contributes the whole-system INGRESS census plus the canary-reachability control that proves each payload actually reached the boundary under test.",
    "BLD-0051": "SCOPE BOUNDARY: IMP-0061 enforces the injected-environment credential boundary; ADV-0040 and AUD-0078 scan existing artifacts for secrets and PII. This unit contributes the WRITER-by-SOURCE egress MAP - which writer could carry which credential source - which scanning finished artifacts cannot show.",
    "BLD-0052": "SCOPE BOUNDARY: TST-0099, TST-0345 and ADV-0123 test the shared-git-index contamination case specifically. This unit contributes the full irreversible-capability inventory, in which that case is one row.",
    "BLD-0053": "SCOPE BOUNDARY: ADV-0058 plants an undeclared transitive dependency to test SBOM completeness and AUD-0020 inventories Python dependencies. This unit contributes the per-gap-class census across ALL shipped artifacts: pin, hash, SBOM entry, license record and advisory query.",
    "BLD-0054": "SCOPE BOUNDARY: CNL-0099, CNL-0100, ADV-0071 and ADV-0100 each test ONE council abuse. This unit contributes the coverage MATRIX over the spec's full abuse list and reports only the abuses none of them covers.",
    "BLD-0057": "SCOPE BOUNDARY: TST-0103 and TST-0242 test the guard behaviour and ARC-0037 refutes local operation of the distributed runtime. This unit contributes the numeric CEILING for this box and whether the scheduler's own bound sits below it at 10x.",
    "BLD-0059": "SCOPE BOUNDARY: CNF-0139 implements the class-expansion trigger and proves it fires. This unit contributes the reviewer-throughput MAKESPAN model that decides whether sampling is needed at all, and at what size.",
}


def expand(spec, all_ids):
    n = spec["n"]
    uid = "BLD-%04d" % n
    vendor = spec.get("vendor", "anthropic")
    model = "gpt-5-codex" if vendor == "openai" else "opus"
    assignment = {
        "model": model,
        "vendor": vendor,
        "role": spec["role"],
        "basis": CROSS_VENDOR_BASIS if vendor == "openai" else OPUS_BASIS,
    }
    deps = []
    for d in spec["deps"]:
        if d == "BLD-ALL-PRECEDING":
            deps.extend([i for i in all_ids if i < uid])
        else:
            deps.append(d)
    q = spec["q"]
    assert q in QUESTIONS, q
    assert spec["sub"] in SUBSTRATES, spec["sub"]
    target = spec["target"]
    if uid in BOUNDARIES and "SCOPE BOUNDARY" not in target:
        target += "  " + BOUNDARIES[uid]
    target += "  [Phase 13 question answered: %s]" % QUESTIONS[q]
    return {
        "id": uid,
        "title": spec["title"],
        "phase": "13",
        "question_or_target": target,
        "inputs": spec["inputs"],
        "dependencies": deps,
        "assigned_model_vendor_role": assignment,
        "tool_permissions": spec["perms"],
        "execution_substrate": spec["sub"],
        "timeout_seconds": spec["to"],
        "output_path": "command-center/receipts/%s.json" % uid,
        "output_schema": "command-center/schema/%s.schema.json" % spec["schema"],
        "evidence_requirement": spec["ev"],
        "tests_required": spec["tests"],
        "reviewer_requirement": spec["rev"],
        "completion_sentinel": "SUCCESS:%s" % uid,
        "retry_policy": spec["retry"],
        "failure_classification": spec["fc"],
        "owner_approval_required": bool(spec.get("owner", False)),
    }


def main():
    ns = [s["n"] for s in SPECS]
    assert ns == list(range(1, len(SPECS) + 1)), "n must be sequential from 1: %r" % ns[:5]
    all_ids = ["BLD-%04d" % s["n"] for s in SPECS]
    units = [expand(s, all_ids) for s in SPECS]

    out = HERE / "BLD-1.json"
    out.write_text(json.dumps(units, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("WROTE %s  units=%d  bytes=%d" % (out, len(units), out.stat().st_size))


if __name__ == "__main__":
    main()
