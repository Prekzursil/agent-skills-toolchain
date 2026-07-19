# triage-dispatch

The multi-bug repair methodology skill from the agentic-repair-reliability program: **audit-first →
capture the real error → defect graph → parallel bounded-scope fixes → inner/outer verify → independent
acceptance review.** See [`SKILL.md`](SKILL.md).

It replaces blind edit-one-file / rerun-the-whole-suite / chase-symptoms repair (which wastes tokens and
expands scope instead of precision) with localized, parallel, evidence-driven fixing. Grounded in
ProjDevBench (token cost per problem), GraphLocator (defect-graph localization, FSE'26), the 20,574-session
developer-agent misalignment study, and Ekstazi/TIA test-impact selection.

Companions: `seed-golden-journey` (the done-signal), `two-tier-verify` (the loops), `acceptance-review`
(the independent verifier), `mutation-check` (test-strength), `fresh-context-verify` (anchor re-derivation).

Install: canonical `~/.agents/skills/triage-dispatch/` (deployed by `scripts/sync-skills.ps1`); mirror to
`~/.claude/skills/triage-dispatch/` for Claude Code discovery. Invoke `/triage-dispatch`.
