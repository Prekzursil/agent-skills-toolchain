# Identifier surface (BLD-0004 detector controls)

Live documentation claims (these are implementing contracts, not examples):

- workflow `wf.paired-live` is the pairing workflow.
- council preset `cp-live-general` is the default panel.
- hook event SessionStart is registered.
- schema field `engagement_budget` is required.

Documented identifiers whose implementations were deleted from code:

- workflow `wf.doc-only` remains in this guide.
- council preset `cp-doc-only` is listed for operators.
- hook event DocOnlyHook is described here.
- schema field `doc_only_schema_field` is documented.

## Removed in v2

The workflow `wf.removed-v2` was withdrawn.
The council preset `cp-removed-v2` was withdrawn.

## Example of what not to do

Do not invoke hook event FakeLegacyHook.
Do not set schema field `removed_example_field`.
