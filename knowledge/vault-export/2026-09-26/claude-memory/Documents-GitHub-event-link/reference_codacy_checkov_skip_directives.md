---
name: Codacy Checkov honors `# checkov:skip=` directives in YAML
description: Codacy's Checkov invocation honors inline `# checkov:skip=CKV_<ID>:<reason>`
  directives placed above the offending YAML block. Verified on QZP commit 342675b
  (PR
type: reference
originSessionId: 7e07bd36-c338-4890-8179-e112e67d5844
permalink: main/claude-memory/documents-git-hub-event-link/reference-codacy-checkov-skip-directives
---

Unlike Codacy's Bandit (which doesn't honor `# nosec B<ID>,B<ID>`),
Codacy's Checkov **does** honor inline skip directives in the standard
form:

```yaml
# checkov:skip=CKV_GHA_7:operator-dispatched fleet sweep; inputs are
# control-plane params (target SHA, dry-run flag, slug filter), not
# build-output mutators
on:
  workflow_dispatch:
    inputs:
      ...
```

Place the comment above the block that triggers the rule (typically
`on:` for `CKV_GHA_7`). The format is `# checkov:skip=CKV_<ID>:<reason>`.

Verified on QZP PR #210: 5 CKV_GHA_7 findings on workflow inputs
were silenced via per-file directives. Codacy's PR-scope diff did
NOT report them as `fixedIssues` (showed 0 fixed), but main reanalysis
confirmed the count dropped 24 → 19.

This is the inverse of the Bandit pattern (per
`reference_codacy_nosec_id_tagged_ignored.md`): for Checkov, the
ID-tagged form IS honored — the rule-name in the directive is what
the parser keys on.