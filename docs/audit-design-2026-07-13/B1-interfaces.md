---
title: B1-interfaces
type: note
permalink: dqverify-repo-20261013/docs/audit-design-2026-07-13/b1-interfaces
---

# B1 — Interface Signatures (RFC Core)

**Twin of** [`B1-RFC-core.md`](./B1-RFC-core.md). Typed signatures for the authority model, logical
catalog, provider adapters, profiles, transactional deployer, and MCP scope matrix. **Design only —
no code is written.** Style matches the existing `ci/harness` codebase (frozen dataclasses, `from
__future__ import annotations`, full type hints, `Path`); every signature marked **[EXTENDS …]**
generalizes a symbol that **already exists and was read at HEAD `dd5366b` this session** — the SSOT
engine *widens proven code*, it does not add a new runtime.

Conventions: `Provider = Literal["claude", "codex"]` (Antigravity DROPPED per G-1). `Surface =
Literal["hooks","mcp","skills","profiles","settings","contract"]`. Secrets appear ONLY as `${VAR}`
strings — never a value, in any type below (D5).

---

## 1. Authority domains (the type system for "who may write what", §1)

```python
from enum import Enum

class AuthorityDomain(Enum):
    DESIRED_CONFIG = "git"            # D1 — the ONLY writable config source
    LIVE_CONFIG    = "manifest"       # D2 — receipts, never a source
    SEMANTIC       = "basic_memory"   # D3
    EVENTS         = "event_ledger"   # D4
    SECRETS        = "env_gitcrypt"   # D5 — ${VAR} refs only
    RUNTIME        = "runtime_dirs"   # D6 — ephemeral, never versioned

class WriteDirection(Enum):
    HUMAN_COMMIT   = "human_commit"       # → Git (D1)
    DEPLOYER_ONLY  = "deployer_only"      # Git → live via §4 ONLY (D1→D2)
    AGENT_APPEND   = "agent_append"       # D3/D4
    OWNER_MANAGED  = "owner_managed"      # D5
    PROCESS_LOCAL  = "process_local"      # D6

# The one-way invariant is a compile-time-checkable rule, not prose:
#   a config surface may be written to live ONLY by DEPLOYER_ONLY, sourced from a
#   committed D1 tree. Any live→Git flow is HUMAN_COMMIT (the enshrine path), never automatic.
ONE_WAY_INVARIANT: dict[Surface, WriteDirection] = {  # every surface deploys one-way
    "hooks": WriteDirection.DEPLOYER_ONLY, "mcp": WriteDirection.DEPLOYER_ONLY,
    "skills": WriteDirection.DEPLOYER_ONLY, "profiles": WriteDirection.DEPLOYER_ONLY,
    "settings": WriteDirection.DEPLOYER_ONLY, "contract": WriteDirection.DEPLOYER_ONLY,
}
```

---

## 2. Logical capability catalog (§2)

### 2.1 Base capability + provenance + native overrides

```python
from dataclasses import dataclass, field
from typing import Any, Literal

@dataclass(frozen=True)
class Provenance:
    """Where a capability is DEFINED + DOCUMENTED. Feeds the G-3 doc-reconciliation
    gate: a capability with no doc pointer fails the pre-commit block."""
    source_doc: str                 # repo-relative path to the owning doc
    decision: str | None = None     # e.g. "G-5", "R2-1", "D8"
    valid_as_of: str | None = None  # ISO date; supports basic-memory temporal validity

@dataclass(frozen=True)
class NativeOverride:
    """One INTENTIONAL, documented per-provider divergence (§2.3 invariant 2).
    Rendered deterministically so a divergence is generated, never churned (D8)."""
    provider: Provider
    reason: str                     # human rationale (e.g. "Claude hubs vs Codex raw exa")
    patch: dict[str, Any]           # provider-specific key overrides (${VAR}-safe)

@dataclass(frozen=True)
class LogicalCapability:
    """Provider-NEUTRAL declaration of one harness capability. Base for every domain
    entry below. `unknown_fields` round-trips any live key the catalog does not model
    (§2.3 invariant 3 — the unknown-field-preservation contract)."""
    id: str
    domain: Surface
    provenance: Provenance
    provider_only: tuple[Provider, ...] = ()      # () = both providers (parity default)
    native_overrides: tuple[NativeOverride, ...] = ()
    unknown_fields: dict[str, Any] = field(default_factory=dict)
```

### 2.2 Per-domain entries (each has a live seed — §2.2 table)

```python
@dataclass(frozen=True)
class EventCapability(LogicalCapability):        # [EXTENDS registration.EVENTS + _TIMEOUTS]
    timeout_s: int = 5
    matcher_class: Literal["all", "gated_tools", "none"] = "all"
    # Claude PreToolUse → "gated_tools" (matcher narrowing); Codex → "all". [reg:72,169]

@dataclass(frozen=True)
class McpCapability(LogicalCapability):          # [EXTENDS canonical-mcp-servers.json entry]
    transport: Literal["stdio", "http", "sse"] = "stdio"
    definition: dict[str, Any] = field(default_factory=dict)   # {type,url|command,args,env:${VAR}}
    scope_tier: "ScopeTier" = None                             # §5 (required in practice)
    lifecycle: "LifecycleClass" = None                         # §5

@dataclass(frozen=True)
class SkillCapability(LogicalCapability):
    in_daily: bool = False           # is it in the curated skills.daily derived view? (S-RC4)
    available_on: tuple[Provider, ...] = ("claude", "codex")

@dataclass(frozen=True)
class ModuleCapability(LogicalCapability):       # dispatcher module (the wired modules.py mixer)
    gate_mode: Literal["off", "shadow", "advise", "enforce"] = "shadow"  # SI-2 ladder default

@dataclass(frozen=True)
class ProfileCapability(LogicalCapability):      # a named profile — see §3 LogicalProfile
    profile: "LogicalProfile" = None

@dataclass(frozen=True)
class ContractCapability(LogicalCapability):     # an AGENTS.md section / memory-role binding
    section: str = ""                # e.g. "§8 Memory and continuity"
    memory_role: Literal["canonical", "secondary", "objective", "versioned", None] = None

@dataclass(frozen=True)
class Catalog:
    """The single writable representation of D1. One instance aggregates all six
    domain lists; the adapters (§2.3) render from it. Loadable from / dumpable to the
    versioned repo trees (the render-sources of C-config §1)."""
    events:   tuple[EventCapability, ...]
    modules:  tuple[ModuleCapability, ...]
    mcp:      tuple[McpCapability, ...]
    skills:   tuple[SkillCapability, ...]
    profiles: tuple[ProfileCapability, ...]
    contract: tuple[ContractCapability, ...]

    def by_id(self, surface: Surface, cap_id: str) -> LogicalCapability | None: ...
    def for_surface(self, surface: Surface) -> tuple[LogicalCapability, ...]: ...
```

### 2.3 Provider adapter protocol (§2.3) — [EXTENDS registration.build_hooks]

```python
from typing import Protocol

RenderedSurface = dict[str, Any]          # a concrete provider document (e.g. settings.json fragment)

class ProviderAdapter(Protocol):
    """Deterministic render(catalog, provider) → surface document. Generalizes
    `registration.build_hooks(provider)` [reg:146-178] from one surface to six.

    MUST satisfy, per surface (the three §2.3 invariants):
      (1) semantic parity   — every non-provider_only capability appears in the output
      (2) native diffs       — apply each NativeOverride for this provider, deterministically
      (3) unknown-field pass — merge into the LIVE document, round-tripping unmodeled keys
                               (exactly desired_documents(): claude=read(live); claude['hooks']=render)
    Determinism contract: render(catalog, p) is byte-stable → install.py --check stays drift-free."""
    provider: Provider

    def render(self, catalog: Catalog, surface: Surface,
               live_document: RenderedSurface | None = None) -> RenderedSurface: ...

    def render_all(self, catalog: Catalog,
                   live: dict[Surface, RenderedSurface]) -> dict[Surface, RenderedSurface]: ...

# The SSOT self-test — generalizes install.py --check from hooks to all surfaces.
@dataclass(frozen=True)
class ParityResult:
    ok: bool
    missing_on_claude: tuple[str, ...]      # capability ids absent from the Claude render
    missing_on_codex:  tuple[str, ...]
    undeclared_native_diffs: tuple[str, ...]  # a render divergence with NO NativeOverride → churn risk

def parity(catalog: Catalog,
           claude: ProviderAdapter, codex: ProviderAdapter) -> ParityResult: ...
```

---

## 3. Profiles + precedence + effective-config-explain (§3)

### 3.1 Logical profile (provider-neutral) — [EXTENDS tools/codex/profiles/*.scope.json]

```python
@dataclass(frozen=True)
class LogicalProfile:
    """Provider-neutral scoping intent. The Codex adapter materializes the existing
    two-file (config.toml + scope.json) M0/M1/M2 pattern; the Claude adapter
    materializes model+thinking + --mcp-config subset + --permission-mode (§3.2)."""
    name: str                                   # audit-max | build-sandboxed | fast | fanout | …
    reasoning_tier: Literal["max", "high", "medium"]
    mcp_allowlist: tuple[str, ...]              # server ids; () with sealed ⇒ zero-MCP
    skills_allowlist: tuple[str, ...]
    tools: dict[str, bool]                      # e.g. {"web_search": True}
    exec_capability: Literal["read_only", "workspace_write"]
    isolation: Literal["none", "scoped", "sealed"]   # sealed → Codex M2 / Claude --strict-mcp-config
    model: str                                  # ${MODEL} or a slug
    model_fallbacks: tuple[str, ...] = ()

@dataclass(frozen=True)
class CodexProfileMaterialization:              # the existing two-file pair (verified shape)
    config_toml: dict[str, Any]                 # strict-config-clean scalars only
    scope_json: dict[str, Any]                  # {mode:M0|M1|M2, mcp_allowlist, skills_allowlist,
                                                #  seal, model_fallbacks, captured_mcp_defs, …}

@dataclass(frozen=True)
class ClaudeProfileMaterialization:
    model: str
    thinking_budget: int | None
    mcp_config_subset: tuple[str, ...]          # → --mcp-config + --strict-mcp-config
    skill_subset: tuple[str, ...]
    permission_mode: Literal["default", "plan", "acceptEdits", "bypassPermissions"]
    isolation_ceiling_note: str | None          # documents the M2-seal gap (§3.2 native diff)
```

### 3.2 Precedence + effective-config-explain (§3.3–3.4)

```python
class PrecedenceLayer(Enum):        # 6 = lowest … 1 = highest; last-writer-wins per key
    CATALOG_DEFAULT      = 6
    PROVIDER_BASE        = 5
    NAMED_PROFILE        = 4
    SESSION_PROFILE      = 3
    WORKFLOW_AGENT       = 2
    INLINE_OVERRIDE      = 1

@dataclass(frozen=True)
class EffectiveConfig:
    """Output of `effective-config explain`. Value-free for secrets — only ${VAR}
    NAMES flow (mirrors install.py._summarize / _structured_diff redaction [inst:192-229])."""
    provider: Provider
    effective: dict[str, Any]                       # resolved config (secrets = ${VAR} names)
    resolved_from: dict[str, PrecedenceLayer]       # per-key: which layer won
    layers: tuple[tuple[PrecedenceLayer, dict[str, Any]], ...]   # each layer's contribution
    native_diff_notes: tuple[str, ...]              # e.g. the Claude M2-seal ceiling (OD-3)
    warnings: tuple[str, ...]

def effective_config_explain(
    provider: Provider,
    *,
    profile: str | None = None,
    session_profile: str | None = None,
    agent_profile: str | None = None,
    inline: dict[str, Any] | None = None,
) -> EffectiveConfig: ...
```

---

## 4. One-way transactional deployer (§4) — [EXTENDS install.py::deploy]

The single-surface engine already exists: `install.py::deploy(*, source_dir, live_dir, target,
source_commit, lock_stale_seconds, _after_stage, _after_write) -> int` [inst:700-811], with
`DEPLOY_TARGETS=("harness","skills","hooks")`, `DeployLockError`, `DeployCASConflict`, and the
LOCK→PLAN→BACKUP→STAGE→CAS→WRITE→PARITY→RECEIPT phases. The RFC adds **four bounded pieces** (§4.3):

```python
from typing import Callable

# ---- R8: provenance-required (turn the fail-open source_commit into a precondition) ----
class DirtySourceError(RuntimeError):
    """One-way (§1.2) forbids deploying an uncommitted tree. Raised when the source
    working tree is dirty or `git rev-parse HEAD` yields None."""

def require_committed_source(src: Path) -> str:      # returns the sha, or raises DirtySourceError
    ...

# ---- R7: local, deterministic, daemon-free semantic health probe (per surface) ----
@dataclass(frozen=True)
class HealthProbe:
    surface: Surface
    ok: bool
    detail: str                     # value-free; e.g. "settings.json parsed; Stop-smoke→{}"

def health_verify(surface: Surface, live_dir: Path) -> HealthProbe:
    """Fail-CLOSED on a broken surface, but NEVER touches a network daemon
    (agent-mail :8812 is DOWN; basic-memory can wedge — [conv§1.3/§6.6]).
    Probes only local loadability:
      settings  → json.loads(settings.json)
      hooks     → subprocess dispatcher.py --event Stop  ⇒ assert stdout == '{}\\n', exit 0
      mcp       → json.loads(~/.mcp.json) + schema-validate {mcpServers:{name:{type,…}}}
      skills    → SKILL.md front-matter parse for the changed set
    """

# ---- R9 + R2: multi-surface transaction under ONE root lease (all-or-nothing, OD-2) ----
@dataclass(frozen=True)
class SurfacePlan:
    surface: Surface
    provider: Provider
    source_dir: Path
    live_dir: Path

@dataclass(frozen=True)
class SurfaceResult:
    surface: Surface
    status: Literal["deployed", "cas_conflict", "parity_mismatch", "health_failed", "skipped"]
    receipt: dict[str, Any] | None
    backup: Path | None

@dataclass(frozen=True)
class TxReceipt:
    transaction_id: str
    source_commit: str                          # non-null (R8) — the durable "journal" (§4.3)
    deployed_at: str
    surfaces: tuple[SurfaceResult, ...]
    rolled_back: bool
    lease_held_s: float

def deploy_transaction(
    plans: tuple[SurfacePlan, ...],             # ordered leaf-first (mcp/skills before settings/hooks)
    *,
    all_or_nothing: bool = True,                # OD-2: True = compensating-restore ALL on any failure
    root_lease_dir: Path | None = None,         # R2: ONE harness-root lease spans the whole tx
    lock_stale_seconds: float = 600.0,          # reuse install.py's stale-steal semantics
) -> TxReceipt:
    """Orchestrate N single-surface deploy() calls under ONE root lease. Each surface:
    require_committed_source → deploy() (LOCK..RECEIPT) → health_verify(). On ANY surface
    failure with all_or_nothing=True, restore every already-written surface's pre-deploy
    backup (bounded compensating-restore, NOT a durable journal). Crash-safe by idempotent
    re-render from `source_commit` (§4.3): re-running no-ops surfaces already at target."""
```

**Why no journal (R5):** `deploy_transaction` is deterministic + idempotent (same commit → same
bytes) and every surface has a backup; a mid-transaction crash recovers by restoring backups or simply
re-running. The Git commit is the durable record. This is the §4.5 recommendation (Option A,
CAS-lite-extend) — HIGH confidence (~85–90%) it meets R1–R9 for this single-user box.

---

## 5. MCP scope / lifecycle matrix (§5)

```python
class ScopeTier(Enum):
    USER_DEFAULT   = "user_default"     # light, concurrency-safe shared utility → USER scope
    USER_HUB       = "user_hub"         # Claude-canonical aggregator (Codex/Gemini use raw — native diff)
    USER_DAEMON    = "user_daemon"      # ONE shared process serves N sessions; deploy must NOT hard-depend
    USER_RAIL      = "user_rail"        # fan-out rail (codex)
    LAZY_FLIP_ON   = "lazy_flip_on"     # heavy/backend-gated → default-OFF per tree; re-ensure on demand
    PROJECT_SCOPED = "project_scoped"   # proven per-project need; NEVER promote
    PARKED_PRUNE   = "parked_prune"     # superseded; parked-disabled; prune at the PLUGIN layer

class LifecycleClass(Enum):
    ALWAYS_ON_USER  = "always_on_user"
    SHARED_DAEMON   = "shared_daemon"
    LAZY_ENSURE     = "lazy_ensure"     # re-ensure pattern (NOT a supervisor — G-5: angr on-demand)
    PROJECT_LOCAL   = "project_local"
    PARKED_DISABLED = "parked_disabled"

@dataclass(frozen=True)
class McpScopeEntry:
    server: str
    scope_tier: ScopeTier
    lifecycle: LifecycleClass
    available_on: tuple[Provider, ...] = ("claude", "codex")
    health_contract: bool = False       # True for lazy_ensure servers with a DOWN backend (angr — D3)
    prune_disposition: Literal["keep", "hold", "prune"] | None = None  # codacy="hold" (R2-1)
    native_overrides: tuple[NativeOverride, ...] = ()   # hub-vs-raw, ralph-WSL, playwright, github (D8)

@dataclass(frozen=True)
class McpScopePolicy:
    """The typed matrix. Drives the MCP adapter's render (§5.1): a server's
    (scope_tier, lifecycle) decides whether it is emitted enabled inline, parked in
    ~/.mcp.disabled.json / .mcp-disabled-defaults.json, or re-ensured on call."""
    entries: tuple[McpScopeEntry, ...]

    def render_claude(self) -> RenderedSurface: ...     # → ~/.mcp.json {mcpServers}
    def render_codex(self) -> RenderedSurface: ...      # → config.toml [mcp_servers.*]
    def parked(self) -> tuple[str, ...]: ...            # → ~/.mcp.disabled.json set
    def lazy_ensure_set(self) -> tuple[str, ...]: ...   # re-ensure-on-demand servers

# Policy invariant (§5.4.3): pruning superseded cloud-quality happens at the PLUGIN-BRIDGE +
# user-scope layer (Claude-closed `promote -PruneExtraUserServers`), NEVER by editing .mcp.json.
# Represented as an out-of-band action, not an adapter render, so the catalog never encodes an
# .mcp.json edit for a plugin-layer problem (A3§4, conv§6).
def prune_plan(policy: McpScopePolicy) -> dict[str, list[str]]:
    """→ {'plugin_bridge_prune': [...], 'user_scope_prune': [...], 'hold': ['codacy']}."""
```

---

## 6. Traceability

| Interface | Extends (live symbol, verified) | Decision / evidence |
|---|---|---|
| `ProviderAdapter.render` | `registration.build_hooks(provider)` [reg:146] | G-1; §2.3 |
| `parity()` | `install.py --check` / `build_reconcile_report` [inst:356] | G-1; §2.3 inv.1 |
| unknown-field preservation | `desired_documents()` [inst:125] | §2.3 inv.3 |
| `deploy_transaction` | `install.py::deploy` + `DeployLockError`/`DeployCASConflict` [inst:700] | G-2; §4.3 |
| `health_verify` (daemon-free) | (new; fail-closed local probe) | R7; conv§6.6 |
| `require_committed_source` | `install.py::_source_commit` [inst:657] (fail-open → precondition) | R8; A1§6 req#6 |
| `LogicalProfile` / `Codex…Materialization` | `tools/codex/profiles/*.scope.json` (5 profiles) | G-10; §3.1 |
| `effective_config_explain` redaction | `install.py::_summarize`/`_structured_diff` [inst:192] | G-10; §3.4 |
| `McpScopePolicy` | `canonical-mcp-servers.json` (43) + A3§5 tiers | G-5/R2-1; §5 |

`SUCCESS:B1-interfaces` — design-only signatures; no code written; every extend-point verified against
live source at HEAD `dd5366b`.