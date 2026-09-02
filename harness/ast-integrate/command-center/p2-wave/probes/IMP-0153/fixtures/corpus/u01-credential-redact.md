# RFC: credential-redact

We propose a new workflow named credential-redact.

Proposed workflow: credential-redact

The system SHALL execute the following steps:
1. Scan receipt JSON for secret-shaped strings
2. Replace each hit with a placeholder
3. Write the redacted copy beside the original

Acceptance: a planted token does not survive in the output bytes

This is a missing capability. Ship this workflow.
