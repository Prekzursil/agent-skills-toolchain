# Requirement: empty source_probe must not confirm

A confirmation receipt with verdict CONFIRMED must be rejected when source_probe
is missing or is the empty string. The public API function validate_receipt in
module receipt_gate must return ok=false and reason=empty-source-probe.

This is the measured hole where an absent source normalises to empty strings
that any verifier trivially differs from. The requirement text — not an author
test and not a diff — is the contract.

## Blind-synthesis cases (normative)

### CASE id=missing-source-probe
INPUT={"verdict":"CONFIRMED","verifier_probe":"verifier-alpha"}
EXPECT_OK=false
EXPECT_REASON=empty-source-probe

### CASE id=empty-source-probe
INPUT={"verdict":"CONFIRMED","source_probe":"","verifier_probe":"verifier-alpha"}
EXPECT_OK=false
EXPECT_REASON=empty-source-probe
