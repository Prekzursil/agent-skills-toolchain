# Approval Semantics for Recursive Multi-Model Workflows

Generated: 29.08.2026  
Confidence: High for deterministic/software controls; Medium for multi-agent aggregation  
Providers: Firecrawl research/web, five independent model research lanes  
Status: Decision support for Cursor automation suite G-11

## Executive Summary

Multi-model agreement is not proof. Modern models share training data, prompting conventions,
and failure modes, so nominal panel size substantially overstates independent evidence. Use broad
multi-model exploration to discover evidence and dissent, but clear workflow gates through
deterministic receipts, reproduced blocking findings, explicit risk tiers, and accountable human
approval where consequential subjective judgment remains.

LLM judges remain useful for critique, routing, rubric checks, and hypothesis generation. They do
not independently certify correctness, safety, factual truth, merge readiness, deployment, or
publication. A reviewer finding becomes blocking only when a trusted deterministic check or an
independent execute-to-confirm run reproduces it.

## Core Findings

### 1. Reviewer count is not independent evidence

Cross-family and role diversity improve defect discovery, but shared errors sharply limit voting.
Majority consensus can suppress a correct minority and debate can reinforce an entrenched error.
Use additional agents as evidence scouts rather than additional votes.

### 2. Deterministic evidence has authority

Builds, tests, security scans, schema checks, citation retrieval, recomputation, artifact hashes,
and final-revision checks are pass/fail controls. Missing, stale, interrupted, untrusted-source, or
budget-aborted checks are not green.

### 3. LLM judges are advisory

LLM judging exhibits position, verbosity, self/family, style, authority, and agreeableness biases.
Repeatability and panel agreement can coexist with invalid conclusions. Agentic judges improve by
inspecting trajectories and running tools, but their interpretation remains advisory; reproduced
receipts carry authority.

### 4. Exploration and approval are separate

Exploration may use `small`, `medium`, `high`, or `limitless` breadth. Approval uses a compact,
blinded, cross-family core panel with distinct roles. Further reviewers may add findings, but do
not increase approval confidence by count.

### 5. Software delivery requires separation of duties

Internal agent repair loops are analysis and verification. Protected merge/release requires
independent review of the final revision. Sensitive code and production deployment require stronger
human separation of duties. General coding agents are not trusted merge robots.

## Approved Gate Protocol

### Step 1 — Classify risk and criteria

Classify every criterion as deterministic or subjective, and every action as reversible or
consequential.

- R0: advisory research, drafts, documentation, reversible local analysis
- R1: standard product code
- R2: authentication, cryptography, payments, personal data, policy/CI, security controls
- R3: production deployment, public high-stakes publication, irreversible external action

### Step 2 — Run deterministic gates first

Run the project-defined build/test/coverage/security/provenance checks against the exact final
artifact or revision. Any required failure blocks. No LLM may waive a failed or absent receipt.

### Step 3 — Independent review

Use a core panel of three reviewers from different provider families and distinct roles:

1. requirement/specification conformance
2. defect/security and adversarial failure search
3. regression/integration/evidence quality

Reviewers work independently and provenance-blinded before seeing one another's findings. Broader
small/medium/high/limitless scouts may feed evidence into the panel but are not counted as votes.

### Step 4 — Reproduce findings

Every potentially blocking finding enters execute-to-confirm. Store the command, inputs, outputs,
artifact hash, and result. A reproduced blocker vetoes approval regardless of panel majority.
Unreproduced subjective concerns remain advisory or escalate according to risk.

### Step 5 — Repair and re-review

Repair the artifact, rerun affected deterministic gates, then assign a fresh reviewer to the changed
surface. Review covers the final revision, not the author's summary. Continue until:

- every required deterministic receipt passes;
- every requirement has disk-verified evidence;
- no reproduced blocker remains;
- subjective disagreement is resolved or explicitly escalated;
- no required lane ended interrupted, missing, stale, or budget-aborted.

Additional debate rounds are not evidence. After one focused rebuttal/repair round, unresolved
material disagreement escalates rather than being outvoted.

### Step 6 — Clearance authority

- R0 internal workflow: may clear automatically when the protocol above passes and no material
  subjective residue remains.
- R1 protected merge: deterministic controls plus an independent human/CODEOWNER covering the final
  revision.
- R2 sensitive merge/release: R1 plus a second independent human with security or separation-of-duty
  responsibility; author/last pusher cannot self-approve.
- R3 deployment/publication: R2 plus an accountable deployer/domain expert distinct from the merger
  or author.

If only one human is available, record that two-party/high-assurance certification was not achieved;
do not relabel an agent panel as human independence.

### Step 7 — Overrides

Overrides are explicit, time-bounded, reasoned, and audited. The actor or agent that failed the gate
cannot grant its own override. Never use `--no-verify`, force-push, missing checks, or a judge's
opinion as an override.

## Optional Calibration

After collecting at least 100 representative expert-adjudicated decisions, measure each judge's
criterion-level chance-adjusted agreement, false-negative rate, counterfactual bias flips, and
calibration. Conformal act-versus-escalate methods may then increase safe automation. Until that
dataset exists, judge confidence is not a calibrated probability.

## Workflow Verdict Schema

```json
{
  "risk_tier": "R0|R1|R2|R3",
  "deterministic_gates": {
    "required": 0,
    "passed": 0,
    "failed": [],
    "missing_or_aborted": []
  },
  "requirements": {
    "total": 0,
    "disk_verified": 0,
    "unverified": []
  },
  "review": {
    "core_panel_complete": false,
    "providers": [],
    "roles": [],
    "reproduced_blockers": [],
    "advisory_concerns": [],
    "material_disagreement": false
  },
  "human_approvals": {
    "required": 0,
    "present": [],
    "final_revision_covered": false
  },
  "verdict": "PASS|BLOCKED|ESCALATE|FAILED_TO_RUN"
}
```

## Selected Sources

1. [Nine Judges, Two Effective Votes](https://arxiv.org/abs/2605.29800) (2026)
2. [The Ringelmann Effect in Multi-Agent LLM Systems](https://arxiv.org/abs/2606.02646) (2026)
3. [Debate or Vote](https://arxiv.org/abs/2508.17536) (2025)
4. [Voting or Consensus?](https://arxiv.org/abs/2502.19130) (2025)
5. [Minority Sentinel](https://arxiv.org/abs/2606.29270) (2026)
6. [Conformal Social Choice](https://arxiv.org/abs/2604.07667) (2026)
7. [Trust or Escalate](https://arxiv.org/abs/2407.18370) (2024)
8. [Replacing Judges with Juries](https://arxiv.org/abs/2404.18796) (2024)
9. [LLMs Are Not Fair Evaluators](https://aclanthology.org/2024.acl-long.511/) (2024)
10. [JudgeBench](https://proceedings.iclr.cc/paper_files/paper/2025/hash/9e720fce64f91114c49cfd640d821da3-Abstract-Conference.html) (2025)
11. [Rating Roulette](https://aclanthology.org/2025.findings-emnlp.1361/) (2025)
12. [Agent-as-a-Judge](https://proceedings.mlr.press/v267/zhuge25a.html) (2025)
13. [NIST Secure Software Development Framework](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218.pdf) (2022)
14. [NIST SP 800-218A](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218A.pdf) (2024)
15. [NIST AI RMF Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) (2024)
16. [SLSA Source Requirements v1.2](https://slsa.dev/spec/v1.2/source-requirements)
17. [GitHub ruleset rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
18. [GitHub code-scanning merge protection](https://docs.github.com/en/code-security/concepts/code-scanning/merge-protection)
19. [GitLab merge request approvals](https://docs.gitlab.com/user/project/merge_requests/approvals/)
20. [OWASP CI/CD Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/CI_CD_Security_Cheat_Sheet.html)

## Methodology

Five independent model lanes examined multi-agent aggregation, judge reliability, software approval
controls, orchestration architecture, and skeptical alternatives. Firecrawl searched research and
authoritative web indexes. Load-bearing conclusions required convergence across at least two lanes
or an authoritative standard. Basic Memory recall was unavailable (`Session not found`), so no
memory result was treated as evidence. Most 2026 multi-agent findings are preprints and remain
medium-confidence pending replication.

