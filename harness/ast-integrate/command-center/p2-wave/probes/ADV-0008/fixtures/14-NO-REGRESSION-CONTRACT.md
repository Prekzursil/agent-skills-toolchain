# 14-NO-REGRESSION-CONTRACT (ADV-0008 fixture)

This file is a **labeled fixture**. Live `14-NO-REGRESSION-CONTRACT.md` (catalog
size 39,221 B under `~/.claude/harness-restore-20260806/`) is absent from this
Linux worktree. These atomic MUST clauses exist so Probe 1 can enumerate
assertions and Probe 2 can violate the SYSTEM (not the test) in a scratch
copy. They are reconstructed from catalog-cited failure classes plus planted
controls. They are not a byte-copy of the missing original.

Each `### CLAUSE-*` heading is one atomic assertion.

### CLAUSE-C1 require-complete-defaults-true

The gate `require_complete` MUST default to True so a payload that omits a
required field is rejected.

### CLAUSE-C2 reject-partial-without-sentinel

A payload that carries required fields but whose text lacks the completion
sentinel MUST be rejected as a partial artifact.

### CLAUSE-C3 no-secret-logging

The gate MUST NOT write API keys or other secret material into log lines.

### CLAUSE-C4 missing-artifact-exit-nonzero

When the output artifact is missing, the gate MUST return a non-zero process
exit code. Exit zero is reserved for a verified success.

### CLAUSE-C5 schema-must-reject-garbage

The schema validator MUST reject an object that is not a refutation-record
(for example `{"totally":"unrelated"}`).

### CLAUSE-C6 registry-mapping-must-be-load-bearing

Every TEST-REGISTRY mapping from a contract clause to a test id MUST name a
test that actually goes red when that clause is violated in the system.
