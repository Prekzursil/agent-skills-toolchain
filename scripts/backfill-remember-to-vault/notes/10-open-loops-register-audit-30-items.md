---
type: note
status: active
valid_as_of: 2026-09-29
---

- [fact] The OPEN-LOOPS register was audited end to end at 30 items: 7 closed, 23 open. L-30 was closed on evidence (DPPD/ECDL came off the CV), and 6 further rows were found to need repair rather than closure.
- [decision] Promotion from TASKBOX to OPEN-LOOPS is the mechanism that stops a finished-with sprint from dropping live work: T-3 and T-4 were promoted as L-26 and L-27, each given an owner and a 2026-10-05 review-by date, and only then were the source tasks dropped. A list inside a document is not a tracked loop.
- [fact] The promotion commit hit a rebase conflict caused by concurrent remote edits to the same register; it was resolved and pushed as 2f9e7be87 and 4668b0413 with `knowledge/` left clean.
- [fact] L-21 and L-24 were later closed and L-14 fixed, with L-31 through L-33 added, so the register's live count moves within the window - the 30-item figure is a snapshot, not a steady state.
- [fact] Pending home transfers were the largest open cluster at the time of the audit (L-21, L-24, L-28), which is what later exposed the retry-task runaway.
- relates_to [[Backfill provenance 2026-09-23 to 2026-09-29]]
See also [[Harness reconcile offload-w2025 2026-09-23]].
<!-- backfill-id: L6-BF-10 src: .remember/today-2026-09-28.done.md 14:08, 00:44 sha256: c00e2e2531f9 -->
