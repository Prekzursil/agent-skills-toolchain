# Provisional claim-record schema (CC-0017)

**Status:** PROVISIONAL

**Phase-4 superseding unit:** `ARC-0085` — Contract: Claim record schema with
duplicate, support and contradiction edges.

The physical Phase-1 provisional contract lives at:

`command-center/schema/claim-record.provisional.v1.schema.json`

The shim at `command-center/schema/claim-record.schema.json` remains the
generated receipt-class substrate pointer for catalog `output_schema` wiring.
Claim *body* validation uses the provisional v1 schema via
`tools/command-center/claim_record.py`.

Do not invent SUCCESS:CC-0017 without the dual independent reviews required by
the catalog (cross-vendor schema review + independent 1->2 SOFT re-derivation).
