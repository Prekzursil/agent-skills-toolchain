# RFC: receipt-schema-gate

We propose a new workflow named receipt-schema-gate.

Proposed workflow: receipt-schema-gate

The system SHALL execute the following steps:
1. Load the declared output_schema
2. Validate the receipt bytes
3. Fail closed on garbage probes

Acceptance: each of the three garbage documents is invalid under the schema

This is a missing capability. Ship this workflow.
