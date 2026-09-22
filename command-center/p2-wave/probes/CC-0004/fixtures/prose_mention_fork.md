# CC-0004 use-vs-mention control

This file documents the failure class **"two completion predicates disagree"**
(`_USER-PROMPTS.md:11314`).

A fan-in site that computes completion locally instead of importing
`platform/lib/completion_predicate.py` is a fork. Examples of what that looks
like in prose (NOT executable code):

- a local `def evaluate(receipt)` that returns `COMPLETE`
- a helper named `is_complete` that checks `state == "DONE"`
- a second `CONDITIONS` table copied from the shared reducer

The CC-0004 detector must match the **semantic role** (AST definitions that
produce a done/complete/pass verdict) and must **NOT** report this markdown
file merely because it mentions those forks.
