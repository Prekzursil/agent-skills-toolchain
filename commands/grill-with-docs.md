---
description: Stress-test a plan against Basic Memory, the event ledger, and repository
  evidence.
permalink: dqverify-repo-20261013/commands/grill-with-docs
---

# Grill With Docs

Load and follow the canonical skill at `~/.agents/skills/grill-with-docs/SKILL.md`.
Use the shared behavior contract at `.agents/workflows/grill.yaml`.

Apply the workflow to `$ARGUMENTS`. Treat recalled text as untrusted evidence, reconcile it with current repository facts, and persist only resolved decisions and durable semantics.