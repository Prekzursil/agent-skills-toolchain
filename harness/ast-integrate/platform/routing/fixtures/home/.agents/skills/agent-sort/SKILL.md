---
name: agent-sort
description: Build an evidence-backed ECC install plan for a specific repo by sorting skills, commands, rules, hooks, and extras into DAILY vs LIBRARY buckets using parallel repo-aware review passes. Use when ECC should be trimmed to what a project actually needs instead of loading the full bundle.
origin: ECC
---

# Agent Sort

Use this skill when a repo needs a project-specific ECC surface instead of the default full install.

The goal is not to guess what "feels useful." The goal is to classify ECC components with evidence from the actual codebase.

## When to Use

- A project only needs a subset of ECC and full installs are too noisy
- The repo stack is clear, but nobody wants to hand-curate skills one by one
- A team wants a repeatable install decision backed by grep evidence instead of opinion
- You need to separate always-loaded daily workflow surfaces from searchable library/reference surfaces
- A repo has drifted into the wrong language, rule, or hook set and needs cleanup

## Non-Negotiable Rules

- Use the current repository as the source of truth, not generic preferences
- Every DAILY decision must cite concrete repo evidence
- LIBRARY does not mean "delete"; it means "keep accessible without loading by default"
- Do not install hooks, rules, or scripts that the current repo cannot use
- Prefer ECC-native surfaces; do not introduce a second install system

## Outputs

Produce these artifacts in order:

1. DAILY inventory
2. LIBRARY inventory
3. install plan
4. verification report
5. optional `skill-library` router if the project wants one

## Classification Model

Use two buckets only:

- `DAILY`
  - should load every session for this repo
  - strongly matched to the repo's language, framework, workflow, or operator surface
- `LIBRARY`
  - useful to retain, but not worth loading by default

### Evidence Sources
### Parallel Review Passes
### Core Workflow
### 1. Read the repo
### 2. Build the evidence table
### 3. Decide DAILY vs LIBRARY
### 4. Build the install plan
### 5. Create the optional library router
### 6. Verify the result
