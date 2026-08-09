"""build/wfa-4 : emit platform/registry/workflow-candidates-4.json.

Mechanical fields (provenance paths, byte counts, mtimes, mirror commit dates, license
anchors, stage/role/tool/stop/failure/benchmark anchors, near-duplicate ratios) are read
from the probe outputs -- NOT hand-typed. Only `classification`, `classification_basis`
and `task_fit` are authored, and each cites the anchor it rests on.
"""

import json
import pathlib
import re
import subprocess

CC = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate/command-center")
OUT = pathlib.Path(
    r"C:/Users/Prekzursil/source/ast-integrate/platform/registry/workflow-candidates-4.json"
)
MIRROR = pathlib.Path(
    r"C:/Users/Prekzursil/.claude/harness-restore-20260806/main-mirror.git"
)
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"

prov = {r["skill_dir"]: r for r in json.loads((CC / "_wfa4_provenance.json").read_text("utf-8"))}
lic = json.loads((CC / "_wfa4_license.json").read_text("utf-8"))
lic_by = {r["skill_dir"]: r for r in lic["candidates"] if "skill_dir" in r}
dupe = json.loads((CC / "_wfa4_dupescan.json").read_text("utf-8"))
nn = {r["skill"]: r for r in dupe["nearest_neighbour"]}
spine = json.loads((CC / "_wfa4_spine.json").read_text("utf-8"))

# Broader second-pass stop-rule / failure net, so an empty first pass is not under-reporting.
STOP2 = re.compile(
    r"^[^\n]{0,160}(?:##+\s*Stop|stop rule|stopping|max[_ ]?(?:round|iter|attempt|reflection|"
    r"retr)|until\s|cap(?:ped)?\s+at|budget|abort|give up|escalat|two[- ]strikes|"
    r"exit\s+(?:code\s+)?\d|converg|saturat|threshold)[^\n]{0,160}$",
    re.I | re.M,
)


def git(*a):
    r = subprocess.run(
        ["git", "--git-dir", str(MIRROR), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout or ""


def body(rec):
    for want in ("agents-live", "claude-live"):
        for loc in rec["locations"]:
            if loc["kind"] == want:
                return pathlib.Path(loc["path"]).read_text("utf-8", errors="replace"), loc["path"]
    for loc in rec["locations"]:
        if loc["kind"].startswith("mirror:"):
            mp = loc["path"].split(":", 1)[1]
            rc, o = git("cat-file", "-p", f"{REF}:{mp}")
            if rc == 0:
                return o, loc["path"]
    return "", ""


def anch(text, pat, rel, limit=6):
    seen, out = set(), []
    for m in pat.finditer(text):
        ln = text.count("\n", 0, m.start()) + 1
        v = re.sub(r"\s+", " ", m.group(0)).strip()[:190]
        if v.lower() in seen:
            continue
        seen.add(v.lower())
        out.append(f"{v}  [{rel}:{ln}]")
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- curation table
# classification, basis (must cite a measured anchor), task_fit
C = {
    "two-tier-verify": (
        "ADOPT-AS-IS",
        "Cheap-INNER-per-edit / expensive-OUTER-at-commit split is exactly the shape of this "
        "program's two gates (12-condition per-unit gate A vs 21-condition program gate). "
        "Declares its own budget ('aim < 30s') and failure route ('fix, re-run INNER'); no "
        "external runtime beyond the test tools it already names.",
        "Per-work-unit verification cost control: run the affected tests + touched-file lint per "
        "edit, full suite once at the unit boundary.",
    ),
    "triage-dispatch": (
        "ADOPT-AS-IS",
        "Builds a defect graph from CAPTURED errors and dispatches parallel repair lanes; "
        "explicitly forbids inferring the failing stage from surviving artifacts, which is the "
        "same anti-pattern this program's evidence rules ban.",
        "Multi-defect repair scheduling across a work-unit cohort; produces the dependency order "
        "the orchestrator needs before fanning out fixers.",
    ),
    "team-builder": (
        "ADOPT-WITH-WRAPPER",
        "Five explicit stages (Discover / Menu / Selection / Spawn-parallel / Synthesize) are "
        "reusable, but stage 2-3 are an INTERACTIVE menu; an autonomous orchestrator needs a "
        "declarative selector substituted for the human choice.",
        "Composing a per-unit reviewer/implementer roster from the agent inventory.",
    ),
    "plan-orchestrate": (
        "ADOPT-WITH-WRAPPER",
        "Six phases from decompose to self-check, emitting dependency-aware agent chains without "
        "executing them - directly reusable - but Phase 0 detects 'ECC mode', an external harness "
        "this program does not run, so that phase must be stubbed.",
        "Turning a plan into the work-unit dependency graph and ready-to-run dispatch prompts.",
    ),
    "dispatching-parallel-agents": (
        "ADOPT-AS-IS",
        "Vendor-neutral rule for when tasks may be fanned out (2+ independent, no shared state, "
        "no sequential dependency) with worked Task() examples; no runtime dependency.",
        "The admission test for whether a set of work units may run concurrently.",
    ),
    "subagent-driven-development": (
        "ADOPT-AS-IS",
        "Fresh subagent per independent task plus a two-stage spec-then-quality review, and its "
        "own description states the boundary against executing-plans, so the two do not overlap.",
        "The per-unit execution loop this wave already uses: dispatch, then review independently.",
    ),
    "executing-plans": (
        "ADOPT-AS-IS",
        "Batch execution with a review checkpoint between batches and an explicit 'Stop when "
        "blocked, do not guess' rule. The checkpoint maps onto this program's PR-ONLY release "
        "mode (owner reviews the PR), so no wrapper is needed.",
        "Sequenced, checkpointed execution for units that are NOT independent.",
    ),
    "autonomous-loops": (
        "DISTILL",
        "628 lines / 26,319 bytes of loop and DAG ARCHITECTURE prose with no executable entry "
        "point; its one concrete artifact is an upstream installer URL "
        "(continuous-claude). Value is the extracted topologies, not the document.",
        "Source of loop/DAG topologies (sequential pipeline through RFC-driven multi-agent DAG) "
        "for the workflow blueprint library.",
    ),
    "ralph-loop": (
        "ADOPT-WITH-WRAPPER",
        "Operates an EXTERNAL runtime that is verified present on this box (ralph 2.9.3 at "
        "C:/Users/Prekzursil/.cargo/bin/ralph.exe, state dir ~/.ralph with agent/, specs/, "
        "loops.json). Adoptable only through that CLI, hence a wrapper, not as-is.",
        "Long-running resumable loop supervision (run / monitor / resume / merge) with recoverable "
        "suspended state.",
    ),
    "ralph-hats": (
        "TRANSLATE",
        "Declarative multi-hat workflow + event-topology spec in a FOREIGN schema "
        "(.ralph/hats/*.yml). The runtime is installed (ralph 2.9.3) but NO hat collection exists "
        "on this box - there is no ~/.ralph/hats directory - so nothing can be adopted directly; "
        "the model must be re-expressed in platform/schema/workflow-dsl.schema.json.",
        "Prior art for a declarative, role-routed, event-driven workflow schema - the closest "
        "existing analogue to this program's Workflow DSL.",
    ),
    "ralph-orchestrator-setup": (
        "ADOPT-AS-IS",
        "Install / update / validate / troubleshoot runbook for a runtime that is verified "
        "installed and registered (ralph 2.9.3 on PATH; 'ralph' present in ~/.claude.json), and it "
        "carries its own diagnostic escalation rule via ralph doctor.",
        "Bring-up and health-check procedure for the Ralph rail before any loop workflow runs.",
    ),
    "ralphinho-rfc-pipeline": (
        "DISTILL",
        "1,522 bytes / 68 lines naming exactly the primitives this program needs - RFC-driven "
        "multi-agent DAG, quality gates, merge queues, work-unit orchestration, rollback_plan - "
        "but at that size it is a pattern sketch, not an implementation.",
        "Reference topology for gated work-unit DAG execution with a merge queue and a declared "
        "rollback path.",
    ),
    "recursive-decision-ledger": (
        "ADOPT-AS-IS",
        "Repeated-rollout decision process with a visible evidence trail and per-rollout deltas "
        "(its own example reports 'Rollout 15 complete ... edge deteriorated 17%'), which is the "
        "audit shape a council needs; declares its tools in frontmatter.",
        "Recording and re-scoring council/decision rollouts so a superseded decision is retired "
        "rather than re-walked.",
    ),
    "claim-verify-gate": (
        "REPAIR",
        "MIRROR-ONLY: resolves at 07f465f37d49:.agents/skills/claim-verify-gate/SKILL.md and is "
        "absent from BOTH live vaults (1 of 1 locations is the mirror), yet a LIVE rule "
        "(rules/common/single-signal-verification.md) cites its script by file:line AND documents "
        "a specific hole - a CONFIRMED verdict with no source_probe passes. Undeployed and "
        "known-defective, so REPAIR, not ADOPT.",
        "The claim-decomposition + independent-verifier gate the program's honesty rules depend "
        "on; grounded in Chain-of-Verification and SAFE.",
    ),
    "delegated-build-verify": (
        "ADOPT-AS-IS",
        "REPO-ONLY (both locations are mirror paths; absent from the live vaults), but reading it "
        "settles the prior UNKNOWN-NEEDS-PROBE: it is a complete 'generator builds, you verify' "
        "contract that turns a converged plan into a build-spec doubling as the evaluation rubric. "
        "Nothing to repair - it needs deploying.",
        "Exactly this wave's shape: an orchestrator delegates a build to a fan-out and must verify "
        "the result against a rubric fixed BEFORE the build.",
    ),
    "parallel-execution-optimizer": (
        "ADOPT-AS-IS",
        "Prior UNKNOWN-NEEDS-PROBE settled by reading it: a concrete lane model over batched tool "
        "calls and isolated worktrees, with a blocked-lane report shape and an explicit "
        "anti-pattern ('Benchmarking the tool instead of the task'). Declares its tools.",
        "Deciding lane width and worktree isolation for a concurrent work-unit cohort.",
    ),
    "long-copy-orchestrator": (
        "DISTILL",
        "Prior UNKNOWN-NEEDS-PROBE settled: the subject is DATA MOVEMENT (rsync/tar/robocopy "
        "selection), not agent orchestration, so it is out of scope as a workflow. Its '## Stop "
        "Rules' section is however a reusable liveness rule - 'Stop and re-evaluate if throughput "
        "falls to zero across multiple sample windows' - and a resume-safe policy.",
        "Harvest only the zero-throughput stall rule and resume-safety policy for long-running "
        "unit supervision; reject the copy-tool decision tree.",
    ),
    "multi-agent-quickstart": (
        "MERGE",
        "1,272 bytes whose stated job is 'choose between the Codex multi-agent orchestration "
        "tools' - the SAME decision codex-orchestrate (position 115) claims as 'Route a task to "
        "the right Codex orchestration tool by intent - one skill, all modes'. Two routers for one "
        "decision; merge into the larger.",
        "Redundant entry point; its only unique content is the Windows-first framing.",
    ),
    "codex-orchestrate": (
        "ADOPT-WITH-WRAPPER",
        "One of only TWO candidates in this slice carrying a declared license (license: MIT in "
        "frontmatter). Routes by intent across all Codex modes, but every mode is a call into the "
        "codex-as-MCP mount, so it is adoptable only where that mount is up.",
        "The single dispatch surface for cross-vendor Codex work units (brainstorm / discuss / "
        "coordinate / review / audit / curate / triage).",
    ),
    "codex-databricks-fanout": (
        "SPECIALIZE",
        "Carries constraints MEASURED on a 608-unit production run plus a 48-unit re-prove, and "
        "states its own machine-readable twin (contract.py). Platform-specific to Databricks job "
        "clusters, so it specialises the generic fan-out rather than replacing it. DRIFT: three "
        "copies disagree in size - agents-live 15,390 B, claude-live 10,743 B, mirror 18,258 B.",
        "Scaling a fan-out past the local RAM ceiling; the source of the concurrency-cap and "
        "batch-env constraints.",
    ),
    "codex-fleet-github": (
        "SPECIALIZE",
        "Propose-only draft PRs plus a fail-closed auth model ('No usable token => the tool "
        "refuses') - directly aligned with this program's PR-ONLY release mode - but bound to one "
        "private runner (codex-runner.yml) and its four MCP tools.",
        "Remote autonomous fan-out that can only ever PROPOSE, never merge; the reference "
        "fail-closed auth pattern.",
    ),
    "mcp-code-orchestrate": (
        "ADOPT-AS-IS",
        "Second of the two license-declared candidates (license: MIT). 301 lines implementing the "
        "code-execution-over-MCP pattern - ONE script iterating many items instead of N model "
        "round-trips - with a measured ~98.7% token cut and a terse result contract "
        "('KEPT 12/4180 functions'). This is the mechanised form of the estate's own rule that a "
        "mechanical comparison must be an algorithm, not LLM judgement.",
        "Any sweep where the same tool-call shape repeats across many items - the token-efficient "
        "alternative to fanning the sweep out to agents.",
    ),
    "eval-harness": (
        "ADOPT-WITH-WRAPPER",
        "Four phases (Define / Implement / Evaluate / Report) with NUMERIC stopping thresholds - "
        "'pass@3 > 90%' for capability and 'pass^3 = 100%' for regression - but no runner: the "
        "phases are prose, so a harness must supply execution and scoring.",
        "Defining eval-driven acceptance thresholds for a work unit and reporting pass@k / pass^k.",
    ),
    "verification-loop": (
        "ADOPT-AS-IS",
        "Six ordered phases (Build / Type / Lint / Test / Security / Diff review) with a coverage "
        "floor ('# Target: 80% minimum') and a per-phase failure line; a directly runnable "
        "sequence needing no external runtime.",
        "The standard per-unit verification sequence before a completion claim.",
    ),
    "verification-before-completion": (
        "ADOPT-AS-IS",
        "Requires the verification command to be RUN and its output confirmed before any success "
        "claim, with a worked evidence example ('[Run test command] [See: 34/34 pass]'). Its "
        "'## Common Failures' section is the anti-pattern list. Note: my tombstone regex flagged "
        "this file, and the use-vs-mention check REFUTED that - 0 tombstone hits in the body.",
        "The gate between 'work done' and 'work claimed done' - condition-1/7 style evidence "
        "discipline.",
    ),
    "smallest-check-ladder": (
        "ADOPT-AS-IS",
        "Four named rungs (L0 edited-file lint, L1 impacted tests via deterministic selectors, L2 "
        "full suite via longrun, L3 e2e on the built artifact), a terminal-state output contract "
        "('FAILED:<id> L1 2 failed'), and an explicit shadow-mode posture. Frontmatter records its "
        "own provenance: origin: gem-hunt-2026-07-12 (A-Tier2, verification-g...).",
        "Choosing the proportionate check for a diff so 'tests pass' is a measured claim rather "
        "than a whole-suite reflex.",
    ),
    "packaged-artifact-smoke": (
        "ADOPT-AS-IS",
        "3-5 golden journeys driven against the PACKAGED artifact, each terminating in a "
        "DETERMINISTIC postcondition probe (ffprobe container/codec/resolution/duration, or "
        "existence + minimum size), emitting SUCCESS:<id>/FAILED:<id> per journey; advisory by "
        "default with an opt-in --enforce. Note: its description uses a YAML folded scalar "
        "(description: >-), which my naive frontmatter parser rendered as '>-' - a limitation of "
        "MY parser, NOT a defect in the file.",
        "Proving a built deliverable runs, not merely that its source tree is green - the gap a "
        "CI-green source tree hides.",
    ),
    "ui-invariant-walk": (
        "ADOPT-AS-IS",
        "Model-based random walk (fast-check fc.commands + asyncModelRun) driving Playwright, "
        "asserting 'no enabled button is a dead click' and 'no route errors', with automatic "
        "SHRINKING to a minimal reproducing sequence and 'Exit code is always 0 in shadow mode'. "
        "Carries a third-party licence caveat in-body: AGPL anchors at lines 272 and 279 (HypoFuzz) "
        "against MIT at 283 - the AGPL component is the OPTIONAL deepening, not the shipped oracle. "
        "My tombstone regex fired here and use-vs-mention REFUTED it (single hit, line 273, the "
        "word 'moved' in prose).",
        "Property-based liveness oracle for a driven UI; the counterexample-shrinking mechanism is "
        "the reusable part.",
    ),
    "refactor-equivalence": (
        "ADOPT-AS-IS",
        "External equivalence proof via CrossHair diffbehavior (Z3) with a Hypothesis differential "
        "fallback, an explicit escape route ('exit 2 / cannot analyze -> go to the fallback'), a "
        "hard scope limit (pure deterministic functions only) and an advisory posture ('never "
        "blocks').",
        "Checking a claimed no-op refactor with a counterexample search instead of the author's "
        "opinion.",
    ),
    "mutation-check": (
        "ADOPT-AS-IS",
        "Tests test-STRENGTH not coverage: applies a high-signal mutation set and asserts each "
        "mutation turns at least one test RED, with a red-baseline guard ('If the suite is already "
        "failing, exit 2 fires'). Cites bFinder finding 17.5% of expected behaviours untested at "
        ">90% line+mutation coverage. Every unit in this wave already runs a mutation battery, so "
        "this is the shared primitive.",
        "Gate-A condition 8 (negative controls / mutations fail as expected) - the executable form "
        "of the both-states rule.",
    ),
    "acceptance-review": (
        "ADOPT-AS-IS",
        "Dispatches an INDEPENDENT, preferably cross-model reviewer (Codex or Gemini, else a "
        "fresh-context Claude) with graceful degradation, and has a two-tier exit contract: "
        "advisory exit 0 by default, exit 20 on a dispatched BLOCK verdict under --strict. Maps "
        "one-to-one onto gate-A condition 9 (independent reviewer status is PASS).",
        "The independent-review condition of the completion predicate, with a real blocking mode "
        "when a gate wants one.",
    ),
    "design-review-loop": (
        "RETIRE",
        "SELF-DECLARED TOMBSTONE. Its own frontmatter description opens 'MOVED - renamed to "
        "design-studio. This is a redirect tombstone kept so in-flight invocations of the old name "
        "still resolve', and the use-vs-mention probe put 4 tombstone markers on line 3 of the "
        "body (in_description=True, in_first900=True). The spec forbids counting a renamed copy, "
        "so this entry is registered for spine completeness with materially_distinct=false and "
        "does NOT count toward the 32.",
        "None as a workflow: it is a name-compatibility shim whose behaviour lives in "
        "design-studio.",
    ),
}

rows = []
for pos in range(spine["slice_lo"], spine["slice_hi"] + 1):
    sid = spine["slice_ids"][pos - spine["slice_lo"]]
    name = None
    for k, r in prov.items():
        if r["canonical_position"] == pos:
            name, rec = k, r
            break
    assert name is not None, f"no probe record for position {pos}"
    txt, rel = body(rec)
    lrow = lic_by.get(name, {})
    cls, basis, fit = C[name]

    # license + its source, measured
    if lrow.get("fm_license"):
        license_val = lrow["fm_license"]
        lsrc = next(
            (a["at"] for a in lrow.get("license_lines", []) if "license" in a["v"].lower()),
            f"{rel}:frontmatter",
        )
        license_source = f"declared in SKILL.md frontmatter ({lsrc})"
    else:
        license_val = "UNDECLARED"
        license_source = (
            "no license field in frontmatter, no LICENSE/COPYING/NOTICE in the skill directory "
            "(measured: 0 such files live and 0 in the mirror subtree), and NO top-level LICENSE "
            "exists in agent-skills-toolchain at "
            f"{REF[:12]} - so the prior registry's 'owner-authored / private estate' is an "
            "assertion with no on-disk license source. Third-party SPDX tokens found in-body, if "
            "any, are listed under third_party_license_anchors and describe DEPENDENCIES."
        )

    live = [x for x in rec["locations"] if x["kind"] in ("agents-live", "claude-live")]
    mir = [x for x in rec["locations"] if x["kind"].startswith("mirror:")]
    maint = []
    for x in live:
        maint.append(f"{x['kind']} mtime {x['mtime_utc']} ({x['bytes']} B)")
    for x in mir:
        maint.append(f"{x['kind']} last commit {x.get('last_commit')} ({x['bytes']} B)")
    sizes = {x["bytes"] for x in rec["locations"]}
    drift = (
        f"BYTE DRIFT across {len(rec['locations'])} copies: sizes {sorted(sizes)}"
        if len(sizes) > 1
        else f"all {len(rec['locations'])} copies agree at {next(iter(sizes))} B"
    )

    stop = rec.get("stop_anchors") or []
    stop_list = [f"{a['v']}  [{a['at']}]" for a in stop]
    if not stop_list:
        stop_list = anch(txt, STOP2, rel, 4)
    if not stop_list:
        stop_list = ["NONE DECLARED - full-text regex over the SKILL.md found 0 stop/cap/until/"
                     "escalate/exit-code matches; absence of a stop rule is itself the finding"]

    fail_list = [f"{a['v']}  [{a['at']}]" for a in (rec.get("failure_anchors") or [])]
    if not fail_list:
        fail_list = [
            "NOT-EXTRACTED - no fail-open/fail-closed/advisory/never-blocks/exit-code sentence "
            "matched; failure posture is undeclared in the SKILL.md"
        ]
    bench_list = [f"{a['v']}  [{a['at']}]" for a in (rec.get("bench_anchors") or [])]
    if rec.get("arxiv_ids"):
        bench_list = [f"arXiv {i}" for i in rec["arxiv_ids"]] + bench_list
    if not bench_list:
        bench_list = ["NONE - no arXiv id, DOI, percentage, pass@k or N/N figure in the SKILL.md"]
    stages = [f"{a['v']}  [{a['at']}]" for a in (rec.get("stage_anchors") or [])]
    if not stages:
        stages = [
            "NOT-EXTRACTED - no Stage/Step/Phase/Gate/L-n/Round heading; the skill is written as "
            "prose rules rather than an ordered pipeline"
        ]

    d = nn.get(name)
    if d:
        distinct = (
            f"nearest neighbour among 328 vault skills = {d['nearest']} at similarity "
            f"{d['ratio']:.3f} (difflib ratio over full SKILL.md text); 0 byte-identical "
            "SKILL.md groups exist in the vault, so this is not a fork or renamed copy"
        )
    else:
        distinct = (
            "not present in the agents-live vault, so the vault near-duplicate scan does not "
            "apply; distinctness rests on the mirror path being unique"
        )

    rows.append(
        {
            "id": f"WFC-{pos:04d}",
            "name": name,
            "unit": "build/wfa-4",
            "registry_slice": "candidates 97-128 of 160",
            "registry_index": pos,
            "source_registry_id": sid,
            "family": rec["prior_name"].split("/")[0] if "/" in rec["prior_name"] else "G-skill",
            "kind": "agent-skill workflow mechanism (SKILL.md)",
            "runtime": rec["prior_runtime"],
            "what_it_does": (rec.get("fm_description") or rec["prior_does"])[:700],
            "provenance": [
                (
                    f"{x['kind']} :: {x['path']}"
                    + (f" :: last commit {x.get('last_commit')}" if x.get("last_commit") else "")
                )
                for x in rec["locations"]
            ],
            "primary_anchor": rel,
            "primary_size": f"{rec.get('primary_bytes')} B / {rec.get('primary_lines')} lines",
            "deployment_state": (
                "MIRROR-ONLY (undeployed: absent from both live skill vaults)"
                if not live
                else f"deployed in {len(live)} live vault(s) and present in {len(mir)} mirror path(s)"
            ),
            "license": license_val,
            "license_source": license_source,
            "third_party_license_anchors": [
                f"{a['v']}  [{a['at']}]" for a in lrow.get("spdx_anchors", [])
            ]
            or ["none found in body"],
            "vendoring_origin": lrow.get("fm_origin") or "not declared in frontmatter",
            "maintenance_state": maint,
            "copy_consistency": drift,
            "task_fit": fit,
            "stages": stages,
            "roles": rec.get("role_terms") or ["NOT-EXTRACTED - no role/persona vocabulary matched"],
            "tools": rec.get("tool_terms") or ["NOT-EXTRACTED - no known tool token matched"],
            "stop_rules": stop_list,
            "failure_behaviour": fail_list,
            "benchmark_evidence": bench_list,
            "classification": cls,
            "classification_basis": basis,
            "prior_classification": rec["prior_classification"],
            "classification_changed": cls != rec["prior_classification"],
            "distinctness": distinct,
            "materially_distinct": cls != "RETIRE" or name != "design-review-loop",
            "status": "VERIFIED-ON-DISK",
            "coverage_note": (
                "Provenance, byte sizes, mtimes, mirror commit dates, license anchors, "
                "stage/role/tool/stop/failure/benchmark anchors and the near-duplicate ratio are "
                "MEASURED by script (command-center/_wfa4_*.py) and carry file:line. "
                "classification / classification_basis / task_fit are authored judgement resting "
                "on those anchors. Behaviour was NOT executed - no skill in this slice was invoked, "
                "so every 'what it does' claim is a read of the SKILL.md, not an observed run "
                "(UNVERIFIED as behaviour; settled by actually invoking the skill and recording "
                "its output)."
            ),
        }
    )

OUT.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"wrote {OUT}  entries={len(rows)}")
print("SUCCESS:wfa4-build-registry" if len(rows) == 32 else "FAILED:wfa4-build-registry")
