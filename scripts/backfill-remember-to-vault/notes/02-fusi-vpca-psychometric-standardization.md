---
type: note
status: active
valid_as_of: 2026-09-29
---

- [fact] The Fusi VPCA psychometric work is a Z-score standardization verification whose raw input was 21 WhatsApp screenshots. The transcription was completed 81/81 across the VP, AC and EP variables and reproduces the AXON etalon exactly, so the transcription itself is not the defect.
- [fact] The delivered report's statistics CONTRADICT the AXON etalon ground truth. Measured discrepancies: the AC standard deviation is wrong, and the EP mean is 14.86 against the etalon's 18.88 with a maximum of 38 against 75 - i.e. the EP column was not computed from the stated dataset at all.
- [decision] Treat the etalon as ground truth and the report as the suspect artifact. The N=48-of-81 variant count was the tell that surfaced the mismatch: a partial-N reading silently rescales every derived statistic.
- [fact] Report reconstruction was in progress and incomplete at the end of the window; the corrected build was not finished.
- relates_to [[Backfill provenance 2026-09-23 to 2026-09-29]]
<!-- backfill-id: L6-BF-02 src: .remember/today-2026-09-24.done.md 05:41, 05:48 sha256: 2b760f0d76bb -->
