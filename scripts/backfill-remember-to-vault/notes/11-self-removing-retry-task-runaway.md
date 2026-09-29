---
type: note
status: active
valid_as_of: 2026-09-29
---

- [bug] A retry mechanism whose self-removal step was SILENCED re-sent a 66 MiB zip 903 times over 4 days, while the tracking row L-24 still read "not delivered". The delivery had in fact succeeded early; the receipt never persisted, so the retry logic was correct given what it could see.
- [decision] Check the CLEANUP postcondition, not just the action's exit code. A mechanism that removes itself on success must be verified to have actually removed itself; a swallowed exception in that step converts a one-shot into an unbounded loop with no error anywhere.
- [decision] Read the MECHANISM'S OWN LOG, not only the tracker. The register said "not delivered" for four days while the mechanism's log showed 903 successful sends - two carriers disagreeing is the signal, and the tracker was the wrong one to trust.
- [fact] Resolution: the retry was disabled (pushed 78c9886fa), the transfer was completed over Taildrop (903x bundle, 51.6 MB of records), L-21 and L-24 were closed, L-14 fixed, and L-31 through L-33 added to the register.
- [fact] The OPEN-LOOPS register had DRIFTED from TASKBOX, which is what allowed the stale "not delivered" row to survive; residual cleanup at the end of the window was the 903-copy bundle and about 2.1 GB of archives.
- relates_to [[Backfill provenance 2026-09-23 to 2026-09-29]]
See also [[Home rclone serve outage root cause 2026-09-25]].
<!-- backfill-id: L6-BF-11 src: .remember/today-2026-09-29.md 02:55 sha256: b716670acad7 -->
