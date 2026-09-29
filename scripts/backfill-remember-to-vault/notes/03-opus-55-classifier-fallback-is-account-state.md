---
type: note
status: active
valid_as_of: 2026-09-29
---

- [fact] Opus 5.5 silently falls back to Opus 4.8 when a safety classifier fires, and across the 2026-09-25 probe series the fallback rate reached 100% at the ACCOUNT level and was content-independent: trivial prompts tripped 8/8, and 42+ probes of `/release-notes` tripped about 60%.
- [fact] The rate ESCALATED within a single day, 0% at 07:00 to 100% by 10:20, which is the observation that kills a content/style explanation: the prompts did not change, the account's state did.
- [fact] A 28-to-34-run controlled comparison (analytic security prose vs verbatim text, 2 per run, Fisher's exact) put the analytic-prose trip rate near 25% against 0% verbatim. That is a real input-side effect, but it is far too small to explain a 100% account-level rate - so the two findings are separate, not one.
- [decision] Practical remediation adopted: run Opus 4.8 explicitly, file `/feedback`, and keep sessions short. Disabling the auto-switch is NOT an option - it converts the silent downgrade into a hard failure.
- [decision] Root cause remains UNRESOLVED between account-state ratchet and global tightening, with account-ratchet favoured and unproven. The settling experiment is a clean second account probed with the identical trivial prompt in the same wall-clock window; a per-account divergence confirms the ratchet.
- [fact] Interrupt tests on `sota-2026-09.md` distinguished the two failure shapes: Opus 5.5 COMPLETED with no interrupt, Opus 4.8 run-2 INTERRUPTED, run-3 completed but with injected context that did not match actual - so "completed" alone is not evidence the run was clean.
- relates_to [[Model Routing Decision - GLM-5.3 default, Kimi K3 escalation]]
- relates_to [[Backfill provenance 2026-09-23 to 2026-09-29]]
<!-- backfill-id: L6-BF-03 src: .remember/today-2026-09-25.done.md 09:39-10:00, 10:30-10:36, 10:40, 10:42, 11:04 sha256: d173f2edf79c -->
