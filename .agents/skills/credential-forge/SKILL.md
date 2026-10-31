---
name: credential-forge
description: One discipline that harvests, farms, vaults, captures, and lifecycle-manages
  every credential the owner already owns — 12-store auth harvester (grok/claude/zcode/
  gemini/cursor/gcloud/aws/gh/scw/opencode), key-farm roster + rotation manifest
  (<BASE>__<account>), 1Password op:// materialize (forge-run), browser-assisted OAuth
  capture ladder (device-code first), JWT expiry ledger + refresh watchdog + statusline
  telemetry. Secret VALUES live in process memory only; names/shapes/paths on disk.
  Use for credential inventory, harvesting auth stores, env-var key farming, vault
  sync, OAuth device-code capture, token expiry checks, rotation cooldowns, or
  secret-hygiene audits.
---

# credential-forge — harvest · farm · vault · capture · lifecycle

One discipline for every credential the owner **already possesses**. It moves the
owner's existing credentials between the places the owner controls (auth stores ↔
env vars ↔ 1Password vault ↔ tool runtimes), inventories them, materializes them
into child processes at exec time, captures fresh OAuth grants when the owner
consents, and keeps expiries visible. It never creates, cracks, guesses, or
touches credentials the owner does not already own.

Honesty about what this is: harvesting credentials from local stores is exactly
what info-stealer malware does. The two differences are **ownership** (owner's own
accounts, owner-initiated) and **hygiene** (the verbatim rules below — enforced
mechanically by the nightly audit gate, not by good intentions). Both are
load-bearing; drop either and this discipline is a stealer.

## The five laws

1. **Values in process memory only.** Secret VALUES never appear in any file,
   commit, log, transcript, or reply — env-var NAMES, file paths, key SHAPES,
   lengths, and masks (≤4 chars) only.
2. **Reference-not-literal.** Configs carry `${ENV}` refs or `op://` URIs,
   resolved at runtime — never literal secrets. The audit gate's
   REFERENCE_RE whitelist enforces this mechanically.
3. **Backup-first.** Every config-file edit gets a dated `.bak-<op>-<YYYYMMDD>`
   copy plus JSON/TOML re-validation before and after.
4. **Owner-consent gates.** Every browser lane is owner-initiated and
   owner-visible; device codes are typed by the owner. Silent consent automation
   is forbidden (phishing-kit equivalence).
5. **Provider-native refresh.** The owning CLI refreshes its own store; we never
   hand-roll token POSTs against inferred endpoints. Unrefreshable stores are
   marked stale + alerted, not poked.

## Where things live

| What | Where | Rule |
|---|---|---|
| Doctrine (this file) + references | `~/.zcode/skills/credential-forge/` AND `~/.agents/skills/credential-forge/` | Dual tree, docs byte-identical (`diff` clean); value-free and committable |
| Scripts | `~/.agents/skills/credential-forge/scripts/` — `harvest.py`, `roster.py`, `materialize.py`, `capture.py`, `lifecycle.py`, `telemetry.py`, `_common.py` | Sibling-built (the `.agents` tree is canonical; observed landing there 2026-10-22, mid-write during this doc pass — not mirrored to `.zcode` until finalized). This doc references them by path, never duplicates code. Shorthand below: `SCRIPTS/x.py` = that dir |
| Audit gate | `~/.agents/scripts/audit_secret_artifacts.py` | Pre-existing estate script — genuinely at `~/.agents/scripts/` |
| State | `~/.agents/state/credential-forge/` → `roster.json`, `ledger.json`, `rotation-manifest.json` | OUTSIDE the skill tree; names, shapes, expiries, liveness ONLY — never values |

## Routing table

| Trigger | Capability | Entry point |
|---|---|---|
| "what's in ~/.grok / .claude / .gemini …", harvest a store, import a credential somewhere | (1) Harvester | `python SCRIPTS/harvest.py --store <id> --dry-shape` then `--sink env\|bridge\|vault` → [references/store-map.md](references/store-map.md) |
| "which keys do I have", env-var inventory, retire a key, rotation manifest | (2) Key-farm roster | `python SCRIPTS/roster.py sync \| status \| retire <name>` → [references/naming-spec.md](references/naming-spec.md) |
| "run X with the key from the vault", resolve op:// into a child process | (3) 1P vault SSOT | `python SCRIPTS/materialize.py forge-run -- <cmd…>` / `vault-sync` |
| "log in / re-consent provider Y", capture a fresh OAuth grant | (4) OAuth capture | `python SCRIPTS/capture.py --provider <id>` → [references/oauth-flows.md](references/oauth-flows.md) |
| "when does my … token expire", stale-store alert, refresh pass | (5a) Lifecycle | `python SCRIPTS/lifecycle.py ledger build \| show` / `watchdog` |
| "key/expiry segment for the statusline" | (5b) Telemetry | `python SCRIPTS/telemetry.py` (`forge:<n>keys exp:<min>d`) |
| Nightly "are any trees leaking values" | Hygiene gate | `~/.agents/scripts/audit_secret_artifacts.py … --rotation-manifest …` → [references/hygiene.md](references/hygiene.md) |

## Capability 1 — store harvester (`harvest.py`)

Generalizes the proven grok 8-step (estate `grokPattern`, executed live
2026-10-21) to any store in [references/store-map.md](references/store-map.md).
Pipeline, per store:

**detect** (path probe + mtime; a store rewritten since the last ledger pass is
LIVE evidence) → **shape** (the `Temp\authmap\shape_json.py` walker: strings →
`string(len=N)`, numbers → `number`, never values) → **classify**
(`oauth-pair | api-key | cookie | password-shaped`) → **normalize** in memory to
`{provider, account, kind, access_len, refresh_len, expires_at, issuer}` — bridge
sinks get the single-entry doc; the raw issuer-map shape is rejected by the
bridge (estate-verified) → **sink** (bridge admin API import / winreg env-persist
/ 1P vault write).

```bash
python SCRIPTS/harvest.py --store gemini --dry-shape          # names/types/lengths + offline JWT exp
python SCRIPTS/harvest.py --store gemini --sink env --dry-run # prints target name+scope only, writes nothing
python SCRIPTS/harvest.py --store grok  --sink bridge         # live (already wired — see store-map)
```

All prints are statuses/counts/lengths (the `grok-lane-import.py` convention).
Idempotent: re-run reveals rather than re-mints. Per-store irreversibility rules
inherited from grok-lane: never rotate `credentialEncryptionKey` after import,
never delete `runtime/data/`, never share one Build credential across bridge
instances (grok-lane/SKILL.md:105-107).

## Capability 2 — key-farm roster (`roster.py`)

Enumerates HKCU+HKLM env **names only** (the names-only PowerShell enumeration is
the proven safe form; 339 names / 232 secret-ish already mapped in the estate),
unifies all naming forms to `<BASE>__<account>` via the alias map in
[references/naming-spec.md](references/naming-spec.md), and emits:

- `state/roster.json` — per key: env name, provider, account tag,
  `status(active|retired|unknown)`, `vault_ref(op://… or null)`, `last_seen`,
  `vault_sync(synced|blocked)`
- `state/rotation-manifest.json` — `providers[].environmentVariables`, exactly
  the schema the audit gate reads (audit_secret_artifacts.py:195-198). This
  closes the estate gap that NO manifest covered the 232 names.

```bash
python SCRIPTS/roster.py sync        # names-only env scan → roster + manifest
python SCRIPTS/roster.py status
python SCRIPTS/roster.py retire EXA_API_KEY__old1
```

Rotation semantics (adopted verbatim from searchhub `rotation.py`, read
2026-10-22): **402** → cool until UTC billing reset + rotate-retry-once; **429**
→ never cool, honor `Retry-After`; **ambiguous** → probe the usage API; manual
switch overrides cooldown; never flip a global active pointer. Seeding stores
`${ENV}` REFERENCES — "never the literal secret" (rotation.py:252-253), idempotent
(:253) — the same doctrine as `op://` URIs, proven twice.

## Capability 3 — 1Password vault SSOT (`materialize.py`)

`forge-run` is the estate's `op run`: it resolves `op://vault/item/field` refs
AND plain env names (via the roster) into a child process's environment at exec
time, then execs. Values exist only in the child's env — never in dotfiles,
never in the skill tree.

```bash
python SCRIPTS/materialize.py forge-run -- ./tool --flag  # refs+roster → child env
python SCRIPTS/materialize.py vault-sync                  # push new harvests to 1P (gated, below)
```

Vault access via the `op-personal` wrapper (`~/.local/bin/op-personal` —
Connect-bypass for full vault reads, one Windows Hello per unlock window).
Python callers strip `OP_CONNECT_*` inline in the env dict (the bash wrapper is
not exec-able from Windows python — estate gotcha).

**HONEST LIMIT (baked in):** only the `Shared with Grok Bot` vault is
CLI-visible; the 9 fleet Login items are NOT (1password-ops/SKILL.md:28,32).
So the vault is SSOT-of-record while HKCU registry remains the materialized
cache; roster entries carry `vault_sync: synced|blocked`, and `vault-sync`
never force-migrates password-shaped vars (`INSTITUTIONAL_PASSWORD` etc.) —
they are listed as op:// migration candidates with a documented-exception path.

## Capability 4 — browser-assisted OAuth capture (`capture.py`)

Strict preference ladder, owner-in-the-loop (full verdicts in
[references/oauth-flows.md](references/oauth-flows.md)):

1. **DEVICE-CODE first** wherever the IdP offers it (Entra devicecode endpoint
   verified live 2026-10-22: HTTP 200, `expires_in` 900, poll 5 s; owner types
   the code at login.microsoft.com/devicelogin themselves). `az` /
   `gcloud --no-launch-browser` / `gh` web flows need zero browser automation.
2. **SSO-COOKIE** via env-held credentials POSTed to the portal
   (institutional-literature-access recipe, owner-sanctioned, no bot-wall).
3. **BROWSER-ATTACH consent-click LAST** — only for IdPs with no device flow
   AND no bot-wall, owner-initiated and owner-visible, driven by shelling out
   to `python playwright` (attach MCP tools are not mounted in workflow
   subagents).

**Anti-phishing-equivalence rule (verbatim):** silent consent-click automation
in a logged-in real profile is functionally an OAuth-phishing kit — owner's
own-accounts, owner-initiated, owner-visible only. Hard refusals encoded as
refuse-paths: never automate accounts.google.com; never headless capture
against Cloudflare/Akamai-fronted IdPs; never extract httpOnly cookies via
attach (the cookie-bridge phone-side lane owns that); cdp-endpoint fallback
stays OFF; downloads-throwing flows route to browser-rail.

```bash
python SCRIPTS/capture.py --provider google-oauth  # REFUSES (hard wall)
python SCRIPTS/capture.py --provider entra-device  # prints owner steps; polls only with --owner-present
```

## Capability 5 — lifecycle (`lifecycle.py` + `telemetry.py`)

- **Expiry ledger:** decodes JWT `exp` claims OFFLINE (base64 payload split, no
  network). Every store's exp source is known from the store-map (.grok
  `expires_at` RFC3339, .gemini `expiry_date` unix-ms + id_token JWT, .claude
  `refreshTokenExpiresAt`, .zcode none → derive from JWT, AWS sso cache
  `expiresAt`, manifest `expiresAt` for static keys). Emits `days_to_expiry`
  with `expiring_soon` thresholds at 7 d / 1 d.
- **Refresh watchdog:** a Scheduled Task runs `lifecycle.py watchdog` — one pass
  of PROVIDER-NATIVE refresh only (the owning CLI rewrites its own store; CLI
  mtimes verified live 2026-10-22). Stores this box cannot refresh
  (cursor-agent STALE since 09-02, opencode STALE since 04-27) are marked stale
  and alerted, never acted on. Failures auto-quarantine in the roster with an
  alert — never a 3 a.m. stack trace.
- **Telemetry:** `telemetry.py` fuses ledger expiry + hub/bridge usage into
  statusline segments (`forge:<n>keys exp:<min>d`), extending the existing
  5h/wk `rate_limits` statusline pattern.
- **Hygiene enforcement:** nightly schtask runs
  `~/.agents/scripts/audit_secret_artifacts.py` over both skill trees + the
  state dir with `--rotation-manifest` (exit 2 = findings/errors → alert,
  audit_secret_artifacts.py:212). Its REFERENCE_RE whitelist (:34-38) is what
  lets `${ENV}`/op:// references pass while literals fail — **the gate IS the
  doctrine.**

```bash
python SCRIPTS/lifecycle.py ledger build
python SCRIPTS/lifecycle.py ledger show --store gemini
python SCRIPTS/telemetry.py
```

## Auth-store map (summary — full registry in references/store-map.md)

| id | Path | Kind | Status 2026-10-22 | Refresh owner |
|---|---|---|---|---|
| grok | `~/.grok/auth.json` | issuer-keyed OAuth | LIVE (mtime 10-22) | grok CLI / bridge |
| codex | `~/.codex` | env-key only, no auth file | n/a (roster-relevant) | — |
| claude | `~/.claude/.credentials.json` | designOauth live, claudeAiOauth EMPTY | LIVE (mtime 10-21) | claude CLI |
| zcode | `~/.zcode/v2/credentials.json` | flat KV | LIVE (mtime 10-22) | zcode CLI |
| gemini | `~/.gemini/oauth_creds.json` | standard OIDC pair | LIVE (mtime 10-21) | gemini-cli |
| cursor | `%APPDATA%\Cursor\User\globalStorage\state.vscdb` (3.01 GB SQLite) | desktop keyring | LIVE desktop / STALE cli | Cursor app |
| cursor-agent | auth.json (stores-research locator) | OAuth | STALE 2026-09-02 | none on this box |
| opencode | `~/.local/share/opencode/auth.json` | OAuth | STALE 2026-04-27 (mtime-confirmed) | none on this box |
| gcloud | `%APPDATA%\gcloud\credentials.db` + `legacy_credentials/` | 6 accounts | LIVE (mtime 10-21) | gcloud CLI |
| aws | `~/.aws/sso/cache/*.json` | SSO | cached | aws sso login |
| gh | `%APPDATA%\GitHub CLI\hosts.yml` | env-token form | env-keyed | gh CLI |
| scw / op | `~/.config/scw/config.yaml` / `~/.op` | provider configs | scw present; op ABSENT this pass | provider CLI |

## Token hygiene (verbatim rules)

- Values in process memory only: secret VALUES never appear in any file,
  commit, log, transcript, or reply — env-var NAMES, file paths, key SHAPES,
  lengths, and masks (≤4 chars) only.
- Reference-not-literal is estate law: configs carry `${ENV}` refs or `op://`
  URIs, resolved at runtime (rotation.py:252-253); the audit gate's
  REFERENCE_RE whitelist (audit_secret_artifacts.py:34-38) enforces it
  mechanically.
- Harvest reads store bytes → process memory → target store's native API. No
  intermediate temp files, no value-bearing dumps; shape output is
  names/types/lengths only.
- Backup-first on every config-file edit: dated `.bak-<op>-<YYYYMMDD>` copy +
  JSON/TOML re-validation before and after.
- Env persistence via winreg SetValueEx to User+Machine with zero shell echo;
  Machine-scope writes reserved for named client keys on the GROK_LANE_KEY
  precedent — never replicate the PLAYWRIGHT_MCP_EXTENSION_TOKEN machine-scope
  exposure pattern blindly.
- Irreversibility inherited: never rotate `credentialEncryptionKey` after
  import, never delete `runtime/data`, never share one Build credential across
  bridge instances.
- Owner-consent gates on every browser lane: device codes entered by the owner;
  consent-click capture is owner-initiated, owner-visible, own-accounts-only;
  first per-client extension connect (tab-drag) and first rail sign-in are
  owner acts. Silent consent automation = OAuth-phishing-kit equivalence →
  forbidden.
- Hard capture refusals: no automation of accounts.google.com; no headless
  OAuth/cookie capture against Cloudflare/Akamai-fronted IdPs; no profile-file
  session seeding (Chrome holds the Cookies file under exclusive lock);
  cdp-endpoint fallback stays OFF.
- Device-code flows preferred over consent-click automation wherever the IdP
  offers them — the code is visible to the owner; the automation never sees
  credentials.
- No cross-account contamination: never copy auth.json between accounts;
  per-account isolation via isolated HOME dirs / profiles (grok-fleet
  GROK_HOME precedent).
- Refresh is provider-native only: the owning CLI refreshes its own store;
  never hand-rolled token POSTs against inferred endpoints; unrefreshable
  stores are marked stale + alerted, not poked.
- ToS honesty: bridge-backed (cookie/device reverse-engineered) accounts are
  rate-capped, segregated from primary accounts, and carry research-use
  disclaimers forward; official API keys preferred wherever one exists.
- Nightly hygiene gate: audit_secret_artifacts.py with --rotation-manifest over
  skill trees + state dir; exit 2 blocks/alerts; findings are
  path+sha256+line+detector+name only — the gate never becomes a leak itself.
- Vault SSOT honestly gated: until the 9 fleet Login items are CLI-visible,
  registry remains the materialized cache and roster entries carry
  `vault_sync: blocked` — no pretending the vault is authoritative while it
  cannot be read.
- Password-shaped env vars are never force-rotated or auto-migrated; they are
  inventoried as op:// migration candidates with a documented-exception path.

## Demo (target store: gemini) — transcript placeholder

Why gemini: shape fully known and non-sensitive to parse; the `id_token` JWT
demonstrates OFFLINE exp decoding with zero network and zero owner interaction;
it does NOT disturb the already-wired grok lane (re-importing `.grok/auth.json`
to a second bridge would violate the never-share-one-Build-credential rule, and
its client-key lane is already live — it would prove nothing new); the sibling
`~/.gemini/google_accounts.json` gives the account tag for roster registration.

Sequence (all unattended, no owner steps):

1. `python SCRIPTS/harvest.py --store gemini --dry-shape` → expects
   `gemini: oauth-pair, access len=261, refresh len=103, exp=<ISO>,
   days_to_expiry=N` — never a value.
2. Pipe step-1 output through the leak-grep (references/hygiene.md) → 0 hits.
3. `python SCRIPTS/roster.py sync` → registers the gemini lane
   (status active + expiry) and emits rotation-manifest.json.
4. `python SCRIPTS/lifecycle.py ledger build` → ledger gains the
   gemini entry alongside every other mapped store.
5. `python ~/.agents/scripts/audit_secret_artifacts.py <both trees> <state dir>
   --rotation-manifest <state>/rotation-manifest.json` → SUCCESS, exit 0.
6. `--sink env --dry-run` ONLY — a live sink write without the owner present is
   unnecessary for proof; the grok lane already proved the live sink path
   end-to-end on 2026-10-21 (grokPattern steps 3-5, real-completion smoke).

```
<!-- DEMO TRANSCRIPT PLACEHOLDER — paste step outputs here after the first live
     demo run. Lengths, dates, and statuses ONLY; never values. -->
```

## Validation (post-build gate — run once the sibling scripts are final)

```bash
# 1. leak-grep over trees+state → must be 0 hits (grep exit 1)
grep -rEn '(github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|tvly-[A-Za-z0-9_-]{20,}|fc-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)' \
  ~/.zcode/skills/credential-forge ~/.agents/skills/credential-forge ~/.agents/state/credential-forge
# 2. the audit gate itself (exit 0 = clean; exit 2 = a real finding)
python ~/.agents/scripts/audit_secret_artifacts.py \
  C:/Users/Prekzursil/.zcode/skills/credential-forge C:/Users/Prekzursil/.agents/skills/credential-forge \
  C:/Users/Prekzursil/.agents/state/credential-forge \
  --rotation-manifest C:/Users/Prekzursil/.agents/state/credential-forge/rotation-manifest.json \
  --report C:/Users/Prekzursil/.agents/state/credential-forge/last-audit.json
# 3. manifest schema round-trip (must print manifest-schema-ok N)
python -c "import json;m=json.load(open(r'C:/Users/Prekzursil/.agents/state/credential-forge/rotation-manifest.json'));assert all(isinstance(p.get('environmentVariables'),list) for p in m['providers']);print('manifest-schema-ok', sum(len(p['environmentVariables']) for p in m['providers']))"
# 4. dual-tree doc identity
diff ~/.zcode/skills/credential-forge/SKILL.md ~/.agents/skills/credential-forge/SKILL.md
diff -r ~/.zcode/skills/credential-forge/references ~/.agents/skills/credential-forge/references
# 5. mask-width conformance (no wider-than-4 slices anywhere in the trees) → 0 hits
grep -rnE '\[:(8|7)\]' ~/.zcode/skills/credential-forge ~/.agents/skills/credential-forge
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| harvest `ABSENT <store>` | path moved — re-probe per references/store-map.md; store-map carries the stores-research locator for cursor-agent |
| bridge import `authImportFailed` | wrong document shape — use the normalized single-entry doc (grok-lane/SKILL.md:94-104), not the raw issuer map |
| roster sync finds 0 names | run from a shell with PowerShell available; enumeration is names-only HKCU+HKLM |
| `forge-run` cannot resolve a ref | ref not in roster and not op://-shaped → run `roster.py sync`; check `vault_sync: blocked` (vault item not CLI-visible) |
| op wrapper yields nothing / Connect errors | `op-personal` bypass missing (OP_CONNECT_* must be unset per-call, never deleted globally); desktop app must be running with CLI integration enabled |
| ledger shows epoch-zero / 1970 expiry | store lacks a native exp → lifecycle derives from JWT; if the value isn't a JWT either, entry is marked `unknown-expiry`, not guessed |
| watchdog alerts STALE cursor-agent/opencode | expected — no refresh owner on this box; owner re-auth via the owning CLI when needed |
| capture.py refuses a provider | that's a hard wall, not a bug — see references/oauth-flows.md before considering ANY workaround |
| audit exit 2 on skill/state files | a real leak-shaped literal — fix the file; never widen REFERENCE_RE to pass |
| trees differ | docs: re-mirror (`cp` SKILL.md + references/ across); scripts: the .agents tree is canonical while sibling work is in flight — reconcile with skill-tree-reconcile once finalized |
