# Independent claim-severity rubric (CNF-0142)

Frozen written rubric used when `command-center/RISK-REGISTER.md` is absent
on this worktree. If that file is present, it is preferred and this fixture
is the fallback plus the control-corpus key. Clause ids are stable citations
for every re-grade.

Severity ranks from most severe to least: P0 > P1 > P2 > P3.
The dangerous disagreement direction is **under-grade**: the author assigned
a weaker label than the rubric, so a P0/P1 claim can skip the exhaustive
census of CNF-0140.

## S-P0-DATA-LOSS
Assign P0 when the claim describes irreversible data loss, silent
truncation, or an integrity failure that drops records without a loud fail.

## S-P0-SECRETS
Assign P0 when a secret or credential is exposed in a way that enables
account or estate takeover.

## S-P1-CAPABILITY
Assign P1 when a required capability is lost (confirmation hole, gate skip,
unwired expansion) without meeting a P0 clause.

## S-P2-LOCAL
Assign P2 when impact is recoverable and local or developer-only, and no
P0 or P1 clause applies.

## S-P3-COSMETIC
Assign P3 when impact is documentation or cosmetic only.
