# Release bump contract (REL-0001)

Machine-checkable change-class rule table for the plugin package, its
marketplace registry entry, the blueprint pack and the CouncilSpec schema.

Rebuilt 2026-10-25 by the shard16-wave2 resume builder: the 21 table rows
below are copied VERBATIM from the closing receipt's own probe-1 citations
(command-center/receipts/REL-0001.json, named-probe-1-fresh
RULE_TABLE_CITATIONS, anchored at release-bump-contract.md:16-36). The
original file was lost with the rest of this probes directory; the receipt
independently confirmed the directory missing (present=0, absent=159).


| Surface | Change class | Required bump | Rule id(s) |
|---|---|---|---|
| Plugin package | Remove any prior public manifest key | MAJOR | `PLUGIN-KEY-REMOVED` |
| Plugin package | Widen declared permissions or capabilities | MAJOR | `PLUGIN-PERMISSION-WIDENED` |
| Plugin package | Change an existing hook event/path/interpreter/argv/input/output signature | MAJOR | `PLUGIN-HOOK-SIGNATURE-CHANGED` |
| Plugin package | Change an existing non-metadata public contract value | MAJOR | `PLUGIN-CONTRACT-VALUE-CHANGED` |
| Plugin package | Add a non-metadata optional public key | MINOR | `PLUGIN-OPTIONAL-KEY-ADDED` |
| Plugin package | Change only metadata or implementation bytes | PATCH | `PLUGIN-METADATA-OR-IMPLEMENTATION-CHANGED` |
| Registry entry | Remove a coordinate or rewrite immutable content at an existing coordinate | MAJOR | `REGISTRY-ENTRY-REMOVED-OR-REWRITTEN` |
| Registry entry | Widen permissions on an existing coordinate | MAJOR | `REGISTRY-PERMISSION-WIDENED` |
| Registry entry | Append a new coordinate while retaining all old coordinates | MINOR | `REGISTRY-ENTRY-ADDED` |
| Registry entry | Change only descriptive/discovery metadata | PATCH | `REGISTRY-METADATA-CHANGED` |
| Blueprint pack | Retire an exported blueprint id without a preserving alias | MAJOR | `BLUEPRINT-ID-RETIRED` |
| Blueprint pack | Widen a blueprint permission or change an existing hook signature | MAJOR | `BLUEPRINT-PERMISSION-WIDENED`, `BLUEPRINT-HOOK-SIGNATURE-CHANGED` |
| Blueprint pack | Change an existing exported execution contract | MAJOR | `BLUEPRINT-CONTRACT-CHANGED` |
| Blueprint pack | Add a new blueprint id while retaining all old ids | MINOR | `BLUEPRINT-ID-ADDED` |
| Blueprint pack | Change only descriptive metadata | PATCH | `BLUEPRINT-METADATA-CHANGED` |
| CouncilSpec schema | Make any existing or new field required | MAJOR | `SCHEMA-FIELD-BECAME-REQUIRED` |
| CouncilSpec schema | Remove a field, narrow enum/type, tighten a bound, close extras, or change a default | MAJOR | `SCHEMA-FIELD-REMOVED-OR-DOMAIN-NARROWED` |
| CouncilSpec schema | Add an optional field or widen an enum/type domain | MINOR | `SCHEMA-OPTIONAL-FIELD-OR-DOMAIN-ADDED` |
| CouncilSpec schema | Change only annotations or the schema-id version text | PATCH | `SCHEMA-ANNOTATION-CHANGED` |
| Every governed surface | Pure file rename with byte-identical content | NONE | `PURE-BYTE-IDENTICAL-RENAME` |
| Governed implementation roots | Change implementation bytes outside a public artifact | PATCH | `RELEVANT-IMPLEMENTATION-CHANGE` |

Binding: the executable form lives beside this file as
`release-bump-rules.json` (22 rule ids). Classification applies table order
with last-match-wins; see the receipt's recorded refutation for the masking
consequence on mixed diffs (defects D1-D3 open, candidate REFUTED).

UNIT-COMPLETE:REL-0001
