# `hooks/hooks.json` provenance

## Subjects

- `hooks/hooks.json` -- canonical plugin hook manifest.
- `agent-self/config/hooks/hooks.json` -- portable agent-self mirror.

## Placement rule

These JSON files are consumer-owned strict manifests. Keep their top-level key set at
`description` and `hooks`. Put future incident notes, rationale, source links, and
generator metadata in this sidecar, not in either manifest.

## Incident record

Commit `4d056d0` replaced an unsupported top-level `$schema` key in
`hooks/hooks.json`. The Codex plugin-hooks parser rejects unknown top-level fields and
loads no hooks from that plugin, so provenance-only metadata must remain out of the
manifest schema.
