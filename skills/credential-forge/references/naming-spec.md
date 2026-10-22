# naming-spec — the ONE multi-account env form

## Canonical form

```
<BASE>__<account>        # double underscore separates base name from account tag
```

Example: `EXA_API_KEY__<account>` — this form already exists locally and is the
seed the whole estate converges on. The base is the provider's plain env name
(`EXA_API_KEY`); the account tag is a short stable slug (`main`, `backup2`,
`old1`, …).

## Alias folding (legacy forms → canonical)

Existing names in HKCU/HKLM are folded by `roster.py sync` via an alias map —
no env var is RENAMED in place (that would break running consumers); the roster
records `canonical` alongside the literal `env_name`:

| Legacy form | Example | Folds to |
|---|---|---|
| single-underscore account | `FIRECRAWL_API_KEY_main` | `FIRECRAWL_API_KEY__main` |
| numbered backup `_2.._N` | `EXA_API_KEY_2` | `EXA_API_KEY__backup2` — numbered forms are OFFLINE-VM only (they predate the spec; freeze, don't extend) |
| hash-suffixed + sidecar | `<NAME>_<hash>` with a `<NAME>_META` sidecar | base re-tagged from the META sidecar's account field; the hash suffix is absorbed into the roster's `env_name` record |

## Status vocabulary (resolves the legacy ambiguity)

Every roster entry carries exactly one of:

- `active` — present in env AND last materialization succeeded or is live in a
  store the ledger maps.
- `retired` — deliberately out of rotation; kept readable for audit history;
  `roster.py retire <name>` sets it (idempotent).
- `unknown` — name exists but no store, manifest, or owner action vouches for
  it; surfaced for owner triage, never auto-purged.

This vocabulary is what dissolves the historical `_old1` / `_real_not_used` /
`potential_1-2` naming mess: those names stay as literal `env_name` records,
but their roster `status` + `canonical` fields carry the truth. Renaming env
vars in the registry is NOT part of the spec — interpretation is.

## Rotation-manifest schema (what the audit gate reads)

`state/rotation-manifest.json` is emitted in EXACTLY the schema
`audit_secret_artifacts.py` consumes (confirmed at :195-198):

```json
{"providers": [{"name": "exa", "environmentVariables": ["EXA_API_KEY", "EXA_API_KEY__backup2"]}]}
```

- Values are env-var NAMES (never literals) — the gate greps files for the
  CURRENT VALUES of these names, so the manifest is what turns the audit from
  pattern-only into estate-aware.
- Names NOT in any provider list are reported by `roster.py status` as
  unmanifested — the gap that previously left 232 secret-ish names uncovered.

## Rotation semantics (adopted verbatim from searchhub rotation.py)

- **402** (quota/billing) → cool the key until UTC billing reset, then
  rotate-retry once.
- **429** (rate) → never cool long-term; honor `Retry-After`.
- **ambiguous** failure → probe the provider's usage API before deciding.
- Manual switch overrides any cooldown.
- NEVER flip a global active pointer — callers pick accounts; the farm rotates
  per-account state.
- Backup-key seeding stores `${ENV}` REFERENCES, "never the literal secret"
  (rotation.py:252-253), idempotently (:253).
