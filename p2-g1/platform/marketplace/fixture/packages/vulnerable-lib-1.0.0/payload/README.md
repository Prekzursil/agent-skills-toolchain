# vulnerable-lib 1.0.0

A structurally perfect package with an open `high` advisory against it (`adv:2026-0001`).

It exists to keep two things honest:

1. **Vulnerability status is derived, never stored.** Nothing in this package says "vulnerable".
   The advisory lives in the registry's separately signed `advisories.json`, and the installer
   computes the status at install time. A status field on the package would go stale the moment a
   new advisory landed, and staleness there is indistinguishable from safety.
2. **An override must be auditable.** `--allow-vulnerable` works only when the trust policy sets
   `allow_vulnerable_override: true`, and its use is written into the install receipt as
   `overrides_used: ["allow-vulnerable"]`. An override nobody can audit is not an override.
