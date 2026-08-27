# Canonicalization Rules

Rank candidate copies using concrete signals:

1. parseable JSONL beats unreadable data
2. higher line count beats lower line count when the file still parses
3. larger size is only a tiebreaker after parse health and line count
4. current canonical target wins ties to avoid churn

## Reject conditions

- zero-byte files
- invalid UTF-8 when the canonical copy is healthy
- files that parse only partially when a full parseable copy exists

## Archive policy

Any replaced target must move to an archive or conflict folder with a deterministic suffix. Never discard the losing file during first promotion.
