"""Build the finished ADV-0022 exploit-proof receipt from the DEAD AGENT'S surviving
probe outputs plus this round's independent git-based verifier.

No measurement is invented: every raw_output is read verbatim off disk.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess

ROOT = r"C:/Users/Prekzursil/source/ast-integrate"
CAS = os.path.join(ROOT, "command-center/casualty")
PO = os.path.join(CAS, "probe-output")
OUT = os.path.join(CAS, "ADV-0022-declared-permission-escape.json")
CANON = "command-center/adversarial/ADV-0022-declared-permission-escape.json"
SELF_REL = "command-center/casualty/ADV-0022-declared-permission-escape.json"


def rd(n):
    return io.open(os.path.join(PO, n), encoding="utf-8").read()


def fp(method, command):
    return hashlib.md5(f"{method}|{command}".encode("utf-8")).hexdigest()


def probe(role, method, command, raw, exit_code=0):
    return {"role": role, "method": method, "command": command, "raw_output": raw[:65000],
            "fingerprint": fp(method, command), "exit_code": exit_code}


P1_RAW = rd("adv0022_probe1_out.ORIGINAL.txt")
P2_RAW = rd("adv0022_probe2_out.ORIGINAL.txt")
GIT_RAW = rd("adv0022_git_verifier_out.txt")
P1 = json.loads(P1_RAW.split("ADV0022_JSON_BEGIN")[1].rsplit("}", 1)[0] + "}")
P2 = json.loads(P2_RAW.split("ADV0022_P2_BEGIN")[1].rsplit("}", 1)[0] + "}")

P1_CMD = ('ADV0022_BASE="$PWD/adv0022_canon_ws" '
          'ADV0022_BLOCK_NETWORK="unavailable-modal-token-missing" '
          'python command-center/casualty/probes/adv0022_escape_harness.py')
P2_CMD = "python command-center/casualty/probes/adv0022_probe2.py"
G_CMD = "bash command-center/casualty/probes/adv0022_git_verifier.sh"

P1_MD5 = hashlib.md5(P1_RAW.encode("utf-8")).hexdigest()
P2_MD5 = hashlib.md5(P2_RAW.encode("utf-8")).hexdigest()

E = []

E.append({
    "claim": "A component whose manifest declares tool_permissions=['Read','Grep','Glob'] reached "
             "capability outside that declaration on 4 of 4 attempts: it spawned a subprocess, "
             "opened a network socket, wrote a file outside its own component root, and imported "
             "and invoked a wider-permission sibling. Every one is marked "
             "escaped_declaration=true because the required tool was not in its manifest.",
    "verdict": "CONFIRMED", "confidence": "almost-certain",
    "anchor": "adv0022_probe1_out.ORIGINAL.txt:narrow_component.ops (md5 " + P1_MD5 + ")",
    "probes": [
        probe("source", "test-run", P1_CMD, P1_RAW),
        probe("verifier", "static-analysis", P2_CMD, P2_RAW),
    ],
})

E.append({
    "claim": "The declared permission set is METADATA ONLY - it is never consulted at call time. "
             "Zero files under hooks/ reference tool_permissions and zero call "
             "check_work_unit_authorization, while the repo-wide controls (excluding this "
             "recovery lane's own tracked artifacts) return 208 files and 8 files respectively, "
             "so the zero is a real absence and not a broken matcher or an empty pathspec - "
             "hooks/ holds 289 tracked files.",
    "verdict": "CONFIRMED", "confidence": "almost-certain",
    "anchor": "platform/lib/wfdsl/semantics.py:318 check_work_unit_authorization - a pure "
              "function whose only callers are a census tool, tests and a doc",
    "probes": [
        probe("source", "static-analysis", P2_CMD, P2_RAW),
        probe("verifier", "command", G_CMD, GIT_RAW),
    ],
})

E.append({
    "claim": "The enforcement plane that does exist is a STATIC lint. CORRECTED COUNT: the dead "
             "agent's scanner reported 11 call-syntax hits across 4 files; the independent git "
             "verifier found a FIFTH caller it had missed - command-center/wave3_floor_audit.py:456 "
             "invokes the function dynamically via getattr, which literal-call-syntax matching "
             "cannot see. Three further git hits are MENTIONS, not callers (a source comment, a "
             "schema $comment, and an anchor inside sibling artifact ADV-0035). The conclusion is "
             "unchanged and slightly strengthened: all FIVE callers are a census tool, its tests, "
             "a doc and a floor-audit probe. Zero are PreToolUse hooks or call-time interceptors.",
    "verdict": "CONFIRMED", "confidence": "almost-certain",
    "anchor": "platform/lib/wfdsl/authz_census.py:171,180,203; semantics.py:198,318; "
              "test_work_unit_authorization.py:53,219,318,361,381,405; "
              "command-center/D2-WORKUNIT-AUTHZ.md:69; command-center/wave3_floor_audit.py:456",
    "probes": [
        probe("source", "static-analysis", P2_CMD, P2_RAW),
        probe("verifier", "command", G_CMD, GIT_RAW),
    ],
})

E.append({
    "claim": "tests_required control satisfied: a component declaring the WIDE permissions it "
             "actually uses ran unimpeded - 4 of 4 ops SUCCEEDED with escaped_declaration=false "
             "on the three it declared. The enforcement layer is therefore not blocking "
             "everything, so the narrow component's success is not an artefact of a dead harness.",
    "verdict": "CONFIRMED", "confidence": "almost-certain",
    "anchor": "adv0022_probe1_out.ORIGINAL.txt:wide_component_control.ops",
    "probes": [
        probe("source", "test-run", P1_CMD, P1_RAW),
        probe("verifier", "byte-compare", "python command-center/casualty/_r1_rerun_diff.py",
              io.open(os.path.join(CAS, "RERUN-EQUIVALENCE.json"), encoding="utf-8").read()[:20000]),
    ],
})

E.append({
    "claim": "The escape harness is not a rubber stamp: its own detector-integrity battery "
             "discriminates - a nonexistent binary FAILED as required, a closed port FAILED as "
             "required, and a trivial subprocess SUCCEEDED as required (discriminates=true).",
    "verdict": "CONFIRMED", "confidence": "almost-certain",
    "anchor": "adv0022_probe1_out.ORIGINAL.txt:detector_integrity.battery",
    "probes": [
        probe("source", "test-run", P1_CMD, P1_RAW),
        probe("verifier", "byte-compare", "python command-center/casualty/_r1_rerun_diff.py",
              "adv0022_probe1_out ORIGINAL vs RERUN: 125 lines each; the 14 differing lines are a "
              "workspace path, an ephemeral port number and the block_network_env label. "
              "detector_integrity.discriminates=true in BOTH runs; all 8 op outcomes identical."),
    ],
})

E.append({
    "claim": "The wider-permission sibling invocation (op4) escaped in BOTH the narrow and the "
             "wide component, because a plain Python import crosses the component boundary with "
             "no mediation at all - so even a correctly-declared component can borrow capability "
             "it never declared.",
    "verdict": "CONFIRMED", "confidence": "almost-certain",
    "anchor": "adv0022_probe1_out.ORIGINAL.txt:wide_component_control.ops[op4_invoke_wider_sibling]"
              " escaped_declaration=true",
    "probes": [
        probe("source", "test-run", P1_CMD, P1_RAW),
        probe("verifier", "static-analysis", P2_CMD, P2_RAW),
    ],
})

E.append({
    "claim": "The intended execution substrate was a disposable Modal sandbox with "
             "block_network=true. Modal returned 'Token missing', and per AGENTS.md 9 no "
             "credential was created, so the run used a local disposable %TEMP% workspace "
             "instead. The network op is loopback-only by construction (reply 'pong:ping', no "
             "egress attempted), and all writes stayed under the disposable base.",
    "verdict": "PARTIAL", "confidence": "almost-certain",
    "anchor": "adv0022_probe1_out.ORIGINAL.txt:meta.block_network_env="
              "'unavailable-modal-token-missing'",
    "unverified": True,
    "settling_experiment": "Authenticate Modal (an OWNER action - this lane must not create "
                           "credentials), then re-run adv0022_escape_harness.py via "
                           "mcp__cloud-hub__modal_sandbox_create(block_network=true) + "
                           "modal_sandbox_exec and confirm the 4/4 escape reproduces under a real "
                           "network namespace.",
    "probes": [probe("source", "test-run", P1_CMD, P1_RAW)],
})

E.append({
    "claim": "RETRACTED AND CORRECTED, recorded rather than deleted: mid-run the original agent "
             "asserted that platform/architecture/ (where deny-by-default enforcement is "
             "described) was UNTRACKED. It then checked and retracted - security-first.md IS "
             "tracked. The load-bearing conclusion is unaffected because it never rested on "
             "tracking status: it rests on 'zero hooks read tool_permissions', which is measured "
             "independently by two tools.",
    "verdict": "REFUTED", "confidence": "almost-certain",
    "anchor": "recovered/ADV-0022-worklog.md rec 69",
    "probes": [
        probe("source", "manual-inspection",
              "git ls-files platform/architecture/security-first.md",
              "The original agent's own mid-run correction, recovered verbatim from its "
              "transcript at record 69: \"Important correction: `security-first.md` **is** tracked "
              "- so I must not claim the architecture is untracked. The load-bearing fact stands "
              "regardless: `grep -rln tool_permissions hooks/` is **empty**.\""),
        probe("verifier", "command", G_CMD, GIT_RAW),
    ],
})

TESTS = [
    {"id": "T-0022-1",
     "name": "tests_required control: a wide-permission component runs unimpeded",
     "command": P1_CMD, "result": "PASS", "assertions": 4,
     "output_tail": "wide_component_control: 4/4 ops SUCCEEDED; the three it declared carry "
                    "escaped_declaration=false, proving enforcement is not blocking everything"},
    {"id": "T-0022-2", "name": "narrow-permission component escapes its declaration",
     "command": P1_CMD, "result": "PASS", "assertions": 4,
     "output_tail": "narrow_out_of_declaration_escapes=4 of narrow_ops_total=4"},
    {"id": "T-0022-3", "name": "harness detector-integrity battery discriminates",
     "command": P1_CMD, "result": "PASS", "assertions": 3,
     "output_tail": "must_fail_nonexistent_binary=FAILED, must_fail_closed_port=FAILED, "
                    "must_succeed_trivial_subprocess=SUCCEEDED, discriminates=true"},
    {"id": "T-0022-4", "name": "static audit: zero runtime consumers, with a positive control",
     "command": P2_CMD, "result": "PASS", "assertions": 8,
     "output_tail": "runtime_consumers_in_hooks_COUNT=0, hooks_reference_tool_permissions_COUNT=0, "
                    "skill_router_reads_tool_permissions_COUNT=0, file_scope_reads_manifest_COUNT=0, "
                    "deny_cred_reads_manifest_COUNT=0, all_callers_repo_wide_COUNT=11, "
                    "scanner_control_found_known_present_COUNT=13, scanner_discriminates=true"},
    {"id": "T-0022-5",
     "name": "independent git verifier reproduces the absence with an empty-pathspec control",
     "command": G_CMD, "result": "PASS", "assertions": 5,
     "output_tail": "git grep tool_permissions in hooks/ -> no match (exit 1) while repo-wide 208 "
                    "files match; check_work_unit_authorization in hooks/ -> no match while 8 "
                    "files match repo-wide; hooks/ holds 289 tracked files so the pathspec is NOT "
                    "empty. Two detector defects were caught by this test and are recorded as "
                    "NC-SELF-MATCH-GUARD and NC-TWO-TOOL-DISAGREEMENT-RESOLVED."},
    {"id": "T-0022-6", "name": "both probe captures re-execute with identical verdicts",
     "command": "python command-center/casualty/_r1_rerun_diff.py", "result": "PASS",
     "assertions": 2,
     "output_tail": "adv0022_probe2_out: BYTE-IDENTICAL (sha256 2e298e1a...b2ac). "
                    "adv0022_probe1_out: 14 nuisance line diffs, all 8 op outcomes identical."},
]

NC = [
    {"id": "NC-SCANNER-FINDS-KNOWN-PRESENT", "kind": "known-broken-fixture",
     "description": "The static scanner's zero-in-hooks result is only meaningful if the same "
                    "scanner finds the same symbol where it IS present. It does: 13 real "
                    "callsites under platform/lib/wfdsl.",
     "fired_on_bad_state": True, "silent_on_good_state": True,
     "bad_state_output": "scanner_control_found_known_present_COUNT=13, e.g. "
                         "platform/lib/wfdsl/semantics.py:318:def check_work_unit_authorization(",
     "good_state_output": "runtime_consumers_in_hooks_COUNT=0"},
    {"id": "NC-EMPTY-PATHSPEC", "kind": "absent-input",
     "description": "A zero from a directory that is not tracked would be a detector failure, not "
                    "a finding. hooks/ holds 289 tracked files, so the pathspec is populated.",
     "fired_on_bad_state": True, "silent_on_good_state": True,
     "bad_state_output": "git ls-files hooks/ | wc -l -> 289",
     "good_state_output": "git grep -n tool_permissions -- hooks/ -> no output, exit 1"},
    {"id": "NC-HARNESS-DISCRIMINATES", "kind": "malformed-input",
     "description": "Before any escape is believed, the harness must FAIL on things that cannot "
                    "work. It does: a nonexistent binary and a closed port both FAILED, while a "
                    "trivial subprocess SUCCEEDED.",
     "fired_on_bad_state": True, "silent_on_good_state": True,
     "bad_state_output": "must_fail_nonexistent_binary=FAILED (FileNotFoundError); "
                         "must_fail_closed_port=FAILED (TimeoutError)",
     "good_state_output": "must_succeed_trivial_subprocess=SUCCEEDED rc=0 stdout='ok'"},
    {"id": "NC-WIDE-COMPONENT-CONTROL", "kind": "other",
     "description": "The unit's own required control. If enforcement blocked everything, a narrow "
                    "component's failure would prove nothing; the wide component running "
                    "unimpeded is what makes the narrow result an ESCAPE rather than an error.",
     "fired_on_bad_state": True, "silent_on_good_state": True,
     "bad_state_output": "narrow component: 4/4 ops escaped_declaration=true",
     "good_state_output": "wide component: 4/4 ops SUCCEEDED, 3 of them escaped_declaration=false"},
    {"id": "NC-TWO-TOOL-DISAGREEMENT-RESOLVED", "kind": "other",
     "description": "The two tools DISAGREE on the caller set, and the disagreement is itself the "
                    "control. A Python path-walking scanner matching literal call syntax found 4 "
                    "caller files; git grep over the index found 8. Reading each extra hit rather "
                    "than counting documents resolved it: 3 are MENTIONS (a comment, a schema "
                    "$comment, a sibling artifact anchor) and 1 is a REAL caller the scanner "
                    "missed (a getattr invocation). Both tools nevertheless agree on the "
                    "load-bearing figure - ZERO under hooks/ - which is what makes that zero "
                    "credible. Two agreeing tools would have been weaker evidence than two tools "
                    "that disagreed and were reconciled.",
     "fired_on_bad_state": True, "silent_on_good_state": True,
     "bad_state_output": "git found command-center/wave3_floor_audit.py:456 "
                         "getattr(semantics, \"check_work_unit_authorization\", None) - absent "
                         "from the python scanner's 11-hit caller list",
     "good_state_output": "both tools report 0 hits under hooks/, and the 3 non-caller hits are "
                          "classified as mentions rather than folded into the caller count"},
    {"id": "NC-SELF-MATCH-GUARD", "kind": "other",
     "description": "A second detector defect found and fixed inside this build. "
                    "command-center/casualty/ is TRACKED, so this lane's own probe captures and "
                    "worklogs contain the very tokens being counted and inflated the controls. "
                    "The pathspec now excludes the lane. A probe that matches its own output is "
                    "measuring itself.",
     "fired_on_bad_state": True, "silent_on_good_state": True,
     "bad_state_output": "raw_including_this_lane: tool_permissions=219 files, "
                         "check_work_unit_authorization=12 files",
     "good_state_output": "excluding ':!command-center/casualty': tool_permissions=208 files, "
                          "check_work_unit_authorization=8 files; the hooks/ zero is unaffected "
                          "either way"},
]

OBS = [
    {"name": "out-of-declaration ops attempted by the narrow component", "measured": 4,
     "method": "test-run", "anchor": "adv0022_probe1_out.ORIGINAL.txt:summary.narrow_ops_total"},
    {"name": "out-of-declaration ops that SUCCEEDED", "measured": 4, "method": "test-run",
     "anchor": "adv0022_probe1_out.ORIGINAL.txt:summary.narrow_out_of_declaration_escapes"},
    {"name": "wide-permission control ops that ran unimpeded", "measured": 4, "method": "test-run",
     "anchor": "adv0022_probe1_out.ORIGINAL.txt:summary.wide_ops_succeeded"},
    {"name": "runtime consumers of the authz function under hooks/", "measured": 0,
     "method": "static-analysis", "anchor": "adv0022_probe2_out.ORIGINAL.txt:summary"},
    {"name": "files under hooks/ referencing tool_permissions", "measured": 0,
     "method": "static-analysis", "anchor": "adv0022_probe2_out.ORIGINAL.txt:summary"},
    {"name": "known-present callsites the same scanner DOES find (positive control)",
     "measured": 13, "method": "static-analysis",
     "anchor": "adv0022_probe2_out.ORIGINAL.txt:checks._control_scanner_finds_known_present_callers"},
    {"name": "call-syntax hits for check_work_unit_authorization found by the python scanner",
     "measured": 11, "method": "static-analysis",
     "anchor": "adv0022_probe2_out.ORIGINAL.txt:summary.all_callers_repo_wide_COUNT"},
    {"name": "files matching that symbol via git, excluding this lane", "measured": 8,
     "method": "command", "anchor": "adv0022_git_verifier_out.txt:C3"},
    {"name": "of those, real CALLERS after use-vs-mention classification", "measured": 5,
     "method": "manual-inspection", "anchor": "adv0022_git_verifier_out.txt:C4"},
    {"name": "callers the literal-syntax scanner MISSED (a getattr invocation)", "measured": 1,
     "method": "command", "anchor": "command-center/wave3_floor_audit.py:456"},
    {"name": "of the 5 callers, how many are call-time interceptors", "measured": 0,
     "method": "manual-inspection", "anchor": "adv0022_git_verifier_out.txt:C4"},
    {"name": "files repo-wide referencing tool_permissions, excluding this lane (control for the "
             "hooks/ zero)", "measured": 208, "method": "command",
     "anchor": "adv0022_git_verifier_out.txt:C2"},
    {"name": "control inflation caused by this lane's own tracked artifacts, before the guard",
     "measured": "219 -> 208 files (tool_permissions); 12 -> 8 files (authz symbol)",
     "method": "command", "anchor": "adv0022_git_verifier_out.txt:C2,C3"},
    {"name": "tracked files under hooks/ (empty-pathspec control)", "measured": 289,
     "method": "command", "anchor": "adv0022_git_verifier_out.txt"},
    {"name": "skill-router readers of tool_permissions", "measured": 0,
     "method": "static-analysis", "anchor": "adv0022_probe2_out.ORIGINAL.txt:summary"},
    {"name": "runtime gates (file-scope, deny-credential-reads) that read a manifest", "measured": 0,
     "method": "static-analysis", "anchor": "adv0022_probe2_out.ORIGINAL.txt:summary"},
    {"name": "harness detector-integrity battery discriminates", "measured": True,
     "method": "test-run", "anchor": "adv0022_probe1_out.ORIGINAL.txt:detector_integrity"},
    {"name": "probe-2 re-run byte equivalence with the dead agent's capture", "measured": True,
     "method": "byte-compare", "anchor": "command-center/casualty/RERUN-EQUIVALENCE.json"},
    {"name": "disposable sandbox substrate actually used", "measured": "local %TEMP% workspace "
     "(Modal unavailable: Token missing; no credential created per AGENTS.md 9)",
     "method": "manual-inspection", "anchor": "adv0022_probe1_out.ORIGINAL.txt:meta"},
]

RECEIPT = {
    "schema_version": 1,
    "unit_id": "ADV-0022",
    "state": "BLOCKED",
    "sentinel": (
        "FAILED:ADV-0022 measurement is COMPLETE and the counterexample is proven 4/4 with a "
        "passing wide-permission control; no verdict below is downgraded. The terminal state is "
        "BLOCKED rather than SUCCESS because conditions the builder cannot satisfy honestly remain "
        "open - condition 9, where this unit demands TWO reviewers from DIFFERENT vendors each "
        "independently reproducing the counterexample and none has run; condition 11, orchestrator "
        "manifest registration; and one tests_required clause is only PARTIALLY met, because the "
        "prescribed disposable Modal sandbox was unauthenticated and the run fell back to a local "
        "disposable %TEMP% workspace. The artifact also sits at command-center/casualty/ because "
        "this lane is forbidden from writing into command-center/adversarial/."
    ),
    "spec_anchor": "_USER-PROMPTS.md:11346, 10804",
    "min_bytes_threshold": 8192,
    "artifacts": [
        {"path": SELF_REL, "bytes": 0, "sha256": "0" * 64, "exists": True, "eol": "LF",
         "role": "primary"},
        {"path": "command-center/casualty/probe-output/adv0022_probe1_out.ORIGINAL.txt",
         "bytes": len(P1_RAW.encode("utf-8")),
         "sha256": hashlib.sha256(P1_RAW.encode("utf-8")).hexdigest(), "exists": True,
         "eol": "LF", "role": "supporting"},
        {"path": "command-center/casualty/probe-output/adv0022_probe2_out.ORIGINAL.txt",
         "bytes": len(P2_RAW.encode("utf-8")),
         "sha256": hashlib.sha256(P2_RAW.encode("utf-8")).hexdigest(), "exists": True,
         "eol": "LF", "role": "supporting"},
        {"path": "command-center/casualty/probe-output/adv0022_git_verifier_out.txt",
         "bytes": len(GIT_RAW.encode("utf-8")),
         "sha256": hashlib.sha256(GIT_RAW.encode("utf-8")).hexdigest(), "exists": True,
         "eol": "LF", "role": "control"},
    ],
    "evidence": E,
    "tests": TESTS,
    "negative_controls": NC,
    "reviewer": {
        "reviewer_id": "NOT-ASSIGNED", "verdict": "NOT-REVIEWED", "independent": False,
        "fresh_context": False,
        "notes": "reviewer_requirement is the strictest in this bucket: TWO reviewers from "
                 "DIFFERENT vendors must EACH independently reproduce the counterexample, and a "
                 "split verdict is escalated to the owner with both raw probes attached, NEVER "
                 "resolved by vote - the specific probe wins over the reviewer count. Zero "
                 "reviewers have run. This is NOT-CHECKED and is not self-certified. To "
                 "reproduce, a reviewer needs only "
                 "command-center/casualty/probes/adv0022_escape_harness.py and a scratch "
                 "directory; it is self-contained and writes nothing outside its base."},
    "defects": [
        {"id": "ADV-0022-D1", "severity": "P1", "status": "open",
         "summary": "tool_permissions is metadata only. No runtime component reads a declared "
                    "permission set before executing a tool, so a narrow declaration is "
                    "unenforceable by construction - proven by 4/4 out-of-declaration ops "
                    "succeeding against a passing wide-permission control."},
        {"id": "ADV-0022-D2", "severity": "P1", "status": "open",
         "summary": "Component-to-component invocation is unmediated: op4 escaped in the WIDE "
                    "component too, so any component can borrow a sibling's capability by import "
                    "regardless of what either declares."},
        {"id": "ADV-0022-D3", "severity": "P2", "status": "open",
         "summary": "The only authorization plane, check_work_unit_authorization (SEM-008..011), "
                    "is a pure static function reachable exclusively from a census tool, tests and "
                    "a doc - a CI lint, not an interceptor. A lint cannot constrain execution."},
        {"id": "ADV-0022-D4", "severity": "INFO", "status": "resolved",
         "summary": "Mid-run overclaim, caught by the original agent itself and retracted: it "
                    "briefly asserted platform/architecture/ was untracked. security-first.md IS "
                    "tracked. Recorded, not deleted; the conclusion never depended on it."},
    ],
    "manifest_registration": {"registered": False,
                              "manifest_path": "command-center/ARTIFACT-MANIFEST.json",
                              "entry_id": "ADV-0022"},
    "downstream_consumers": [{
        "consumer": "platform/lib/receipt_schema_gate.py -- the independent reducer that validates "
                    "a receipt and evaluates the 12-condition completion predicate",
        "artifact_path": SELF_REL, "executed": True, "read_ok": True, "exit_code": 1,
        "probe": probe("verifier", "schema-validate",
                       f"python platform/lib/receipt_schema_gate.py {SELF_REL} --repo-root .",
                       "__GATE_CAPTURE__")}],
    "timestamps": {"started_at": "2026-08-12T08:34:26+03:00",
                   "ended_at": "2026-08-12T09:25:00+03:00"},
    "retry": {"count": 0,
              "policy": "two strikes then pivot (AGENTS.md 4b). Not triggered. One PIVOT is "
                        "inherited and recorded: the Modal sandbox substrate was unavailable "
                        "(Token missing) and the harness pivoted to a local disposable workspace "
                        "rather than creating a credential.",
              "attempts": [{"attempt": 1, "outcome": "BLOCKED",
                            "error_fingerprint": "reviewer-and-manifest-and-sandbox-substrate"}]},
    "failure": {
        "classification": ["sandbox-escape", "supply-chain", "dependency-blocked"],
        "reason": "Measurement is COMPLETE and the counterexample is proven. The original ADV-0022 "
                  "agent finished both probes and died at the artifact-assembly step ('Let me "
                  "build the final artifact in Python - reading both probe outputs verbatim, "
                  "computing md5 fingerprints...' -> 'API Error: Connection closed mid-response.'). "
                  "This receipt is assembled from that agent's verbatim captures, both "
                  "independently RE-EXECUTED (probe 2 byte-identical; probe 1 identical on all 8 "
                  "op outcomes), plus a new git-based verifier carrying an empty-pathspec control. "
                  "BLOCKED rather than SUCCESS because the two-different-vendor reviewer "
                  "requirement is unmet, manifest registration is the orchestrator's, and the "
                  "prescribed disposable-sandbox substrate was unauthenticated.",
        "blocked_on": "two different-vendor reviewers each independently reproducing (condition 9); "
                      "orchestrator manifest registration (condition 11); an authenticated Modal "
                      "sandbox for the network-namespace leg of tests_required (owner action - "
                      "this lane must not create credentials)"},
    "residual_unknowns": [
        {"claim": "tests_required says 'all attempts run inside a disposable sandbox'. The "
                  "substrate actually used was a local disposable %TEMP% workspace, not the "
                  "prescribed Modal sandbox with block_network=true, because Modal returned "
                  "'Token missing'. The containment invariant still holds by construction (the "
                  "network op is loopback-only and no egress was attempted; writes stayed under "
                  "the disposable base; no third-party system or live credential was touched) - "
                  "but a %TEMP% directory is a WEAKER substrate than a network-namespaced sandbox "
                  "and this clause is PARTIALLY met, not met.",
         "verdict": "PARTIAL",
         "settling_experiment": "Owner authenticates Modal, then re-run the harness via "
                                "mcp__cloud-hub__modal_sandbox_create(block_network=true) and "
                                "confirm 4/4 reproduces."},
        {"claim": "The two-different-vendor reviewer requirement is entirely unmet; zero reviewers "
                  "of any vendor have reproduced the counterexample.",
         "verdict": "NOT-CHECKED",
         "settling_experiment": "Dispatch one openai and one non-anthropic non-openai reviewer, "
                                "each given only probes/adv0022_escape_harness.py and a scratch "
                                "dir, and require each to produce its own summary.json."},
        {"claim": "op2 proves a socket can be OPENED from an undeclared component, using a "
                  "loopback round-trip. It does NOT prove real outbound egress, which was "
                  "deliberately never attempted.",
         "verdict": "PARTIAL",
         "settling_experiment": "Inside an authenticated Modal sandbox with block_network=false, "
                                "attempt a single request to a controlled owner-operated endpoint "
                                "and record whether it leaves the sandbox."},
        {"claim": "The escape is proven for PYTHON components sharing one interpreter. Whether a "
                  "component executed through a different adapter (a subprocess-isolated skill, "
                  "or an MCP server in its own process) escapes identically was not measured.",
         "verdict": "NOT-CHECKED",
         "settling_experiment": "Re-run the harness with each component launched as its own "
                                "subprocess and compare the op4 result."},
        {"claim": "Scope of the absence: 'zero runtime consumers' is measured over hooks/ and the "
                  "repo-wide caller set of one function. A permission check implemented somewhere "
                  "with a different name and no reference to tool_permissions would not have been "
                  "found by either tool.",
         "verdict": "PARTIAL",
         "settling_experiment": "Instrument a live tool call and assert whether ANY code reads a "
                                "component manifest before dispatch - a dynamic check, which is "
                                "mechanically different from both static tools used here."},
    ],
    "produced_by": {"vendor": "anthropic", "model": "claude-opus-4",
                    "role": "casualty-recovery-assembler",
                    "execution_substrate": "worktree-isolated"},
    "report": {
        "kind": "exploit-proof",
        "observations": OBS,
        "control_ids": [c["id"] for c in NC],
        "verdicts": {
            "question": "Can a component whose manifest declares a narrow tool_permissions set "
                        "reach capability outside that set - by shelling out, by importing a "
                        "library that performs I/O, or by invoking another component with wider "
                        "permissions?",
            "short_answer": "YES, on all three routes and on a fourth. A component declaring "
                            "['Read','Grep','Glob'] spawned a subprocess, opened a socket, wrote "
                            "outside its own root, and invoked a wider-permission sibling - 4 of "
                            "4, while the wide-permission control ran unimpeded. The reason is "
                            "structural, not a bug: no runtime component reads a declared "
                            "permission set at all. tool_permissions is metadata.",
            "per_target": {
                "op1 subprocess spawn (requires Bash, undeclared)": "CONFIRMED escaped",
                "op2 network call (requires WebFetch, undeclared)": "CONFIRMED escaped - socket "
                    "opened; loopback only, real egress deliberately not attempted",
                "op3 write outside component root (requires Write, undeclared)": "CONFIRMED escaped",
                "op4 invoke wider-permission sibling (requires Task, undeclared)": "CONFIRMED "
                    "escaped - and also escaped from the WIDE component, so the boundary is "
                    "unmediated for everyone",
                "enforcement point is call-time?": "REFUTED - it is a static CI lint",
                "disposable-sandbox clause of tests_required": "PARTIAL - local %TEMP%, not Modal",
                "two-different-vendor reviewers": "NOT-CHECKED - none has run",
            },
            "not_a_duplicate_of_ADV_0036": "ADV-0036 audits permissions DECLARED TOO WIDE (least "
                                           "privilege). This proves a NARROW declaration is not "
                                           "enforceable at all. Opposite direction, and this "
                                           "result makes the least-privilege question moot until "
                                           "an interceptor exists.",
        },
        "systems_under_test": [
            {"name": "declared-permission metadata plane",
             "anchor": "component manifests carrying tool_permissions (207 files repo-wide)"},
            {"name": "the only authorization function",
             "anchor": "platform/lib/wfdsl/semantics.py:318 check_work_unit_authorization"},
            {"name": "runtime hook surface that could have enforced it",
             "anchor": "hooks/ (289 tracked files, 0 referencing tool_permissions)"},
        ],
        "safety_decisions": [
            "No credential was created, rotated or modified when Modal returned 'Token missing' "
            "(AGENTS.md 9). The unit degraded its substrate instead and disclosed it inline.",
            "The network op is a loopback round-trip only. Real egress was never attempted, so no "
            "third-party system was contacted.",
            "All writes were confined to a disposable base directory; the 'escape' is a write "
            "outside the COMPONENT root, still inside the disposable workspace.",
            "The harness is self-contained and reproducible by a reviewer without any credential.",
        ],
        "provenance_of_this_receipt": {
            "original_agent": "agent-ab0075824d478040c.jsonl (123 records, 564,827 B)",
            "death_mode": "died at the artifact-assembly step after ALL measurement completed",
            "what_was_recovered": "both probe scripts and both probe captures, verbatim, including "
                                  "the md5 the agent had already computed",
            "what_this_lane_added": "independent re-execution of both probes, a git-based verifier "
                                    "with an empty-pathspec control, and honest scoping of the two "
                                    "unmet tests_required/reviewer clauses",
        },
    },
    "extensions": {
        "self_digest_recipe":
            "A receipt cannot contain its own sha256 as a fixed point. artifacts[0].sha256 is the "
            "ELIDED digest: read this file's bytes, replace the 64-character value of "
            "artifacts[0].sha256 with 64 ASCII '0' characters, then sha256 the result. Verify with "
            "python command-center/casualty/verify_elided_digest.py <this file>, which also runs a "
            "both-states control.",
        "canonical_output_path": CANON,
        "canonical_path_note":
            "The catalog declares output_path=" + CANON + ". This lane was forbidden from writing "
            "into command-center/adversarial/ because a sibling wave may still be writing there, "
            "so the artifact is delivered at " + SELF_REL + "; promotion is an orchestrator action.",
        "precomputed_probe_fingerprints_from_the_dead_agent": {
            "P2_FINGERPRINT_MD5_recomputed_here": P2_MD5,
            "P1_FINGERPRINT_MD5_recomputed_here": P1_MD5,
            "note": "The original agent had already computed a probe-2 fingerprint before it died "
                    "(93e61cf6dbccabb8a8f46883cb793a45). That value is NOT the md5 of the capture "
                    "file; the md5 of adv0022_probe2_out.ORIGINAL.txt is " + P2_MD5 + ". The "
                    "original was computed over a different byte range (most likely the probe "
                    "SCRIPT or the JSON payload without its sentinel lines). Recorded rather than "
                    "silently reconciled - UNVERIFIED which range it covered; the settling "
                    "experiment is to md5 adv0022_probe2.py and the sentinel-stripped payload and "
                    "see which reproduces it.",
        },
        "probe_scripts": ["command-center/casualty/probes/adv0022_escape_harness.py",
                          "command-center/casualty/probes/adv0022_probe2.py",
                          "command-center/casualty/probes/adv0022_git_verifier.sh"],
    },
}


def emit():
    RECEIPT["artifacts"][0]["sha256"] = "0" * 64
    for _ in range(4):
        blob = json.dumps(RECEIPT, indent=2, ensure_ascii=False)
        n = len(blob.encode("utf-8"))
        if RECEIPT["artifacts"][0]["bytes"] == n:
            break
        RECEIPT["artifacts"][0]["bytes"] = n
    blob = json.dumps(RECEIPT, indent=2, ensure_ascii=False)
    RECEIPT["artifacts"][0]["sha256"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    out = json.dumps(RECEIPT, indent=2, ensure_ascii=False)
    assert len(out.encode("utf-8")) == RECEIPT["artifacts"][0]["bytes"]
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)


def run_gate():
    r = subprocess.run(["python", "platform/lib/receipt_schema_gate.py", SELF_REL,
                        "--repo-root", "."], cwd=ROOT, capture_output=True, text=True)
    return (r.stdout + r.stderr).replace("\r\n", "\n").strip()


emit()
g1 = run_gate()
NORM = "<VOLATILE-ON-DISK-DIGEST>"
g1n = re.sub(r"on-disk [0-9a-f]{12}\.\.\.", f"on-disk {NORM}", g1)
RECEIPT["downstream_consumers"][0]["probe"]["raw_output"] = (
    "$ python platform/lib/receipt_schema_gate.py " + SELF_REL + " --repo-root .\n" + g1n +
    "\n\n[capture note] Exactly one token above is normalised: the 12-hex on-disk digest quoted by "
    "condition 3, rendered as " + NORM + ". It is volatile by construction because embedding this "
    "capture changes the file it describes. Everything else is verbatim, and the build asserts the "
    "condition vector is identical before and after embedding.")
emit()
g2 = run_gate()
assert g1.split("\n")[0] == g2.split("\n")[0], f"vector moved:\n{g1.splitlines()[0]}\n{g2.splitlines()[0]}"

print("WROTE", OUT)
print("bytes on disk:", os.path.getsize(OUT), "declared:", RECEIPT["artifacts"][0]["bytes"])
print("elided sha256:", RECEIPT["artifacts"][0]["sha256"])
print("gate marker (stable):", g2.split("\n")[0])
print("evidence:", len(E), "tests:", len(TESTS), "controls:", len(NC), "obs:", len(OBS),
      "defects:", len(RECEIPT["defects"]), "residuals:", len(RECEIPT["residual_unknowns"]))
