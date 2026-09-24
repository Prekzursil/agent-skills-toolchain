# Decision records

One file per decision. Every prune, disable, retire and merge-or-close call about this repository, its branches or its harness is a file here named `<YYYY-MM-DD>-<slug>.md`, written before the action it records. A decision that lives only in a chat, a commit message or a PR thread does not count.

Why: without a record, each new session re-derives and re-dismisses what an earlier one settled. With one, the answer is a file with evidence and a date. This directory is Phase 4a of `docs/RUNBOOK-2026-09-24-settle-and-harden.md`.

## Rules

- Accepted decisions are not open questions. Act on them; do not reopen one in a session, an audit or a review.
- To change a decision, write a new record whose `supersedes:` names the old file, and set the old record's `status:` to `superseded`. Do not rewrite an accepted record's Decision or Rationale in place.
- Every record carries `review_by`. From the day after that date, CI fails for an `accepted` record until someone re-runs its "How to verify it is still in force" and adds a `retested:` line dated on or after `review_by`. Set the next `review_by` in the same edit to keep the cadence.
- A `proposed` record is a draft awaiting the owner. Only the owner moves it to `accepted`.

## Format

Copy `TEMPLATE.md`. Frontmatter keys (no others are allowed):

| key | required | value |
|---|---|---|
| `title` | yes | one line |
| `date` | yes | `YYYY-MM-DD`, the day the decision was recorded |
| `status` | yes | `proposed`, `accepted`, `superseded` or `retired` (no longer in force, not replaced) |
| `review_by` | yes | `YYYY-MM-DD` |
| `supersedes` | no | repo-relative path of the record this one replaces; it must exist |
| `evidence` | yes | a `- item` list of repo-relative paths or URLs, at least one |
| `retested` | no | `YYYY-MM-DD <one-line result>`, dated no later than today |

Body sections, in this order: Decision, Rationale, What this replaces, How to verify it is still in force.

The frontmatter is a YAML subset read without dependencies: `key: value` lines, `- item` lines under a key whose value is empty, blank lines and `#` comments. Quote any value that contains `: `.

## The check

`python ci/check_decisions.py` reads every `*.md` here except this file and `TEMPLATE.md`. It prints one line per problem and exits 1 on missing or malformed frontmatter, an expired `accepted` record or a `supersedes` path that does not exist; otherwise it prints a one-line summary. `--today YYYY-MM-DD` evaluates another date. `.github/workflows/decisions.yml` runs it, then its tests (`ci/tests/test_check_decisions.py`), on every pull request and every push to `main`.

Limits: the check runs only when a pull request or push triggers it, so an expiry surfaces on the next one rather than on the date itself. The runbook's second arm, failing a deletion or retirement commit that adds no record here, is not built yet.
