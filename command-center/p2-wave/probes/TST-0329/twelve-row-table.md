| # | condition | mutation | reducer_verdict | unsatisfied | independent |
|---|-----------|----------|-----------------|-------------|-------------|
| 1 | process/task reached a valid terminal state | state=TIMEOUT (non-success terminal); sentinel family left coherent | FALSE | [1] | False |
| 2 | expected artifact exists | exit_code=0 with primary artifact deleted on disk (spec :10646 — exit code zero alone is never success) | FALSE | [2] | True |
| 3 | artifact is non-empty and exceeds a meaningful minimum size | min_bytes_threshold raised above on-disk artifact size | FALSE | [3] | False |
| 4 | artifact parses against its schema | required schema field 'verdict' dropped from artifact bytes | FALSE | [] | False |
| 5 | required sentinel is present | artifact sentinel field replaced with non-matching string | FALSE | [5] | False |
| 6 | required evidence anchors exist | source and verifier probes share one fingerprint (same-probe-rerun) | FALSE | [6] | False |
| 7 | required tests ran and passed | required test result rewritten from PASS to SKIP | FALSE | [7] | False |
| 8 | negative controls or mutations fail as expected | negative control fired_on_bad_state forced False (inert detector) | FALSE | [8] | False |
| 9 | independent reviewer status is PASS | reviewer.vendor set equal to produced_by.vendor (same-vendor) | FALSE | [9] | False |
| 10 | no unresolved P0/P1 defect is attached | open P1 defect appended to defects[] | FALSE | [10] | False |
| 11 | output was registered in the artifact manifest | ARTIFACT-MANIFEST.json rewritten to empty artifacts list | FALSE | [11] | False |
| 12 | downstream consumers can read it | downstream_consumers[0].read_ok=False with exit_code=1 | FALSE | [12] | False |
