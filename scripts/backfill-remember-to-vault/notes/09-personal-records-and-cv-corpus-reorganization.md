---
type: note
status: active
valid_as_of: 2026-09-29
---

- [fact] `personal-records/` was reorganized with 77 moves, and the reorganization shipped with a MANIFEST plus an UNDO script and a README carrying 18 corrections. Nothing was deleted: 6 exact-duplicate thesis sets were IDENTIFIED and left in place pending owner confirmation.
- [decision] Files are classified by CONTENT, never by incoming filename. The corpus contained document-scans, diplomas and a foaie matricola whose names did not describe them, so a contact-sheet pass over every file is the only honest input to a move plan.
- [fact] Owner answers were reconciled into `~/.agents/cv/profile.yaml`: the Dinu Plast endDate moved 2021-05 -> 2023-06 and English was set to C2, with the open questions tracked in `TODO-CONFIRM.md` rather than guessed. A later pass added GitHub URL evidence (commit b0ea5f759).
- [fact] Validation state after reconciliation: zerofab passed with 0 errors and 14 warnings, and all 10 PDFs built.
- [decision] `test_contradictory_end_date_does_not_become_present` was failing BECAUSE the data got fixed - the test asserted a TODO span that no longer existed. Resolved by splitting the defect-as-fixture, not by relaxing the assertion; suite green at 71 passed (commit eeeb31089). A gate that reddens when you fix a bug is the tell.
- relates_to [[CV programme decisions G-1 G-2 G-18 2026-09-24]]
- relates_to [[Backfill provenance 2026-09-23 to 2026-09-29]]
<!-- backfill-id: L6-BF-09 src: .remember/today-2026-09-28.done.md 15:43, 15:58, 16:21, 00:44 sha256: b3a2b98e4aa1 -->
