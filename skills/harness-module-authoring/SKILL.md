---
name: harness-module-authoring
description: Author, register, test, or review lifecycle harness modules and hook
  checks in agent-skills-toolchain. Use when changing ci/harness HookEvent or HookResult
  modules, hooks/_dispatch/manifest.json checks, fail-open behavior, redaction, persistent
  side effects, deduplication, calibrated-silence confidence gates, contraindication
  registry rows, or block-versus-inject policy.
permalink: dqverify-repo-20261013/skills/harness-module-authoring/skill
---

# Harness Module Authoring

Use the repository code as the contract. Read the exact files named below before
editing; historical READMEs and changelog entries can lag behavior.

## Start with the correct execution lane

This repository has two related but different hook systems:

| Need | Runtime surface | Registration |
|---|---|---|
| Cross-provider Claude/Codex lifecycle behavior | `ci/harness/` | Add a module to `ci/harness/modules.py`, keep `MODULE_ORDER` aligned, and instantiate it in `build_default_modules()` |
| Existing Claude hook script consolidated behind one process | `hooks/<name>/` | Add a non-blocking inject-or-side-effect-only row to `hooks/_dispatch/manifest.json` |
| A true blocking legacy gate | Standalone `hooks/<name>/` command hook | Wire it outside `_dispatch`; the consolidated dispatcher cannot preserve a block |
| A known tool/action hazard with no new algorithm | `hooks/contraindication/contraindications.json` | Add a data row; do not add matching code |
| A fatigue-aware advisory | A hook check plus `hooks/calibrated-silence/` | Gate repeats inside the check; there is no magic `confidence_gate` manifest field |

Do not conflate `hooks/_dispatch/manifest.json` with
`skills/SKILLS-MANIFEST.md`. The former controls legacy hook checks; the latter is
the human-maintained skill inventory.

## Provider-neutral harness contract

Read these source-of-truth files together:

- `ci/harness/models.py`: `HookEvent`, `HookResult`, and envelope types.
- `ci/harness/adapters.py`: provider input normalization and native output rendering.
- `ci/harness/dispatcher.py`: ordering, aggregation, redaction, failure handling, and terminal logging.
- `ci/harness/modules.py`: current module patterns and runtime registration.
- `ci/harness/ledger.py`, `redaction.py`, and `storage.py`: durable state primitives.

### Consume `HookEvent`, not provider-shaped dictionaries

`normalize_event()` converts provider input to schema version 1. Match on
`event.event` and read normalized fields:

```text
schema_version, provider, event, session_id, turn_id, cwd, permission_mode
tool.name, tool.id, tool.input, tool.result
last_assistant_message, prompt, source, trigger
agent.id, agent.type, agent.transcript_path
```

Treat every field as untrusted and possibly empty. Gate on the event first, then
validate the narrow input needed by the module. Keep provider-native field names and
JSON out of module logic; adapters own that boundary.

### Return one `HookResult` on every path

Use `HookResult.success()` for normal outcomes and
`HookResult.failed_open(event.event)` when a caught internal failure should be visible
in the terminal ledger without blocking the host.

| Action | Meaning in the current adapter |
|---|---|
| `allow` | No provider output; continue normally |
| `inject` | Add context through `additionalContext` on context events and Claude `Stop`/`SubagentStop`, or a `systemMessage` elsewhere |
| `block` | Deny `PreToolUse` or `PermissionRequest`; render `decision: block` for other events |
| `continue` | Render `decision: block` with continuation text; reserve for stop-like events that must keep the agent working |

`status` is operational, not a provider action. Successful modules use
`SUCCESS:hook`; failed-open results use `FAILED:hook-<event>`. Never put provider wire
fields or diagnostic blobs in `HookResult`.

The dispatcher combines results with this priority:

```text
allow < inject < continue < block
```

It preserves contexts in module order, removes exact duplicate context strings within
that one dispatch, and stops running later modules after a block. Put affirmative
security blockers before any module that could persist the blocked payload.

Use this minimal shape inside `ci/harness/modules.py`:

```python
class ExampleModule:
    name = "example"

    def run(self, event: HookEvent) -> HookResult:
        try:
            if event.event != "PostToolUse" or event.tool.name != "Example":
                return HookResult.success()
            message = redact_text(
                f"Example result: {event.tool.result}", max_chars=1000
            )
            return HookResult.success(
                action="inject",
                reason_code="example_finding",
                additional_context=[message],
            )
        except (OSError, TypeError, ValueError):
            return HookResult.failed_open(event.event)
```

Then add the name to `MODULE_ORDER` and the instance to the list returned by
`build_default_modules()` in the same position. Runtime order comes from that returned
list; `MODULE_ORDER` documents the invariant but does not instantiate anything.

### Keep aggregation behavior in mind

- A later result wins only when its action has higher priority. For equal actions, a
  later non-`ok` reason code can replace the earlier reason code.
- All non-empty contexts survive unless they are exact duplicates. Do not make two
  modules emit contradictory instructions.
- An exception from one module is recorded as a failed module and otherwise fails open.
- `dispatcher.main()` returns zero even on malformed input or an internal failure.
- The terminal log stores redacted module names and metadata, never raw event payloads.

## Legacy `_dispatch` check contract

Read `hooks/_dispatch/dispatch.py` and `manifest.json` before adding a check. The
dispatcher supports `SessionStart`, `Stop`, `PostToolUse`, and `PreToolUse` only. It:

1. Reads stdin once.
2. Selects rows with `re.search(row.matcher, tool_name)`; matching is case-sensitive.
3. Imports selected scripts serially under synthetic module names.
4. Runs each script's `main()` in a daemon thread with thread-local stdin/stdout.
5. Extracts only JSON `additionalContext` values from stdout.
6. Joins them in manifest order and exits zero.

A compatible script exposes `main()` or `main(argv)`. If `main` accepts a parameter,
the dispatcher passes the row's `args` list. Read one JSON object from stdin and emit
at most one canonical JSON line:

```python
def main(argv=None) -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not matches(payload):
            return 0
        message = build_redacted_message(payload)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": message,
            }
        }))
    except Exception:
        pass
    return 0
```

Do not print debug text on stdout. The extractor ignores non-JSON lines, but they make
standalone behavior ambiguous. Send diagnostics to a redacted sidecar or stderr only
when the standalone host contract calls for it.

### Understand every manifest field

An ordinary check row uses:

```json
{
  "name": "example/check",
  "script": "example/check.py",
  "args": [],
  "timeout": 8,
  "matcher": "Bash|PowerShell",
  "isolate": null,
  "side_effect": "none",
  "emits": true
}
```

| Field | Runtime meaning |
|---|---|
| `name` | Logical identity and basis for the synthetic import name |
| `script` | Path relative to top-level `hooks_root` |
| `args` | Passed only when `main` accepts at least one parameter |
| `timeout` | Seconds allowed for that thread's result before its output is dropped |
| `matcher` | Optional regex over normalized `tool_name`; absent means always |
| `isolate` | Descriptive today; the dispatcher only clears the hard-coded `_common` and `stubscan` names |
| `side_effect` | Descriptive audit label; it does not provide locking, rollback, or dedupe |
| `emits` | Descriptive expectation; it is not runtime-enforced |
| `slow` | Optional descriptive flag used by reviews, not scheduling logic |

The event-level `settings_matcher` and `settings_timeout` mirror intended live wiring;
`dispatch.py` does not read them. If a new check needs a tool excluded by the live outer
matcher, changing only the row's matcher leaves the check unreachable. Update and verify
the actual hook registration during deployment.

The repository manifest's `hooks_root` points to the deployed live hook directory.
Repository tests must call `dispatch.run()` with a test manifest or otherwise replace
the root; invoking the entry point from a clone can import live files instead of the
files under test.

### Timeouts do not cancel work

All selected threads start together. The join budget is measured from a shared start,
and a timed-out daemon thread is abandoned, not killed. Its incomplete output is
dropped, but its file or process side effect can still finish later. Therefore:

- Make every side effect idempotent and replay-safe.
- Bound all I/O inside the check; do not rely on the dispatcher to stop it.
- Use atomic replacement for mutable state and append locks for ledgers.
- Never assume `timeout` provides transaction rollback.

### Never put a blocker behind `_dispatch`

The legacy dispatcher ignores a check's return value and always exits zero. It only
extracts `additionalContext`; an inner `return 2` or `sys.exit(2)` cannot block the
pending tool. Keep a dangerous-operation gate standalone, where exit 2 and a concise
stderr reason reach the host. Use the consolidated manifest only for inject-only or
side-effect-only checks.

## Block versus inject

Use the narrowest action supported by evidence:

| Finding | Action |
|---|---|
| Positive match for an irreversible or security-dangerous pending operation | Block |
| Recoverable error, quality issue, route, reminder, uncertainty, or safer alternative | Inject |
| Missing state, corrupt config, timeout, classifier exception, or ambiguous match | Allow and record a failed-open terminal where available |
| Stop-time unfinished work that must resume | `continue`, not a fake PreToolUse denial |

Do not block because a prompt merely mentions a dangerous command. Inspect the actual
shell command field at the system boundary. The current harness also treats user prompts
as trusted for execution: redact secrets before persistence instead of rejecting the
prompt on a broad secret regex.

In `ci/harness`, return `action="block"` and let `adapters.py` render provider JSON. In a
standalone legacy gate, return exit 2 with the human-readable reason on stderr. Never
use exit 2 for advice.

## Redact before every output and persistence boundary

Use `ci/harness/redaction.py` rather than inventing a partial token regex:

- Call `contains_secret()` only for a narrowly scoped affirmative security decision.
- Call `redact_text()` before storing prompts, results, context, errors, or paths.
- Set `redact_paths=True` for checkpoints, shared ledgers, and exported diagnostics.
- Set `max_chars` on every model-facing or durable free-text value.

The provider-neutral dispatcher redacts returned contexts again at 4000 characters,
but that does not protect a module's own side effects. The legacy `_dispatch` performs
no redaction. Redact at store time and emit time even when a later layer also redacts.
Persist a digest or bounded classification when the raw payload is unnecessary.

Do not log raw stdin, `tool.input`, `tool.result`, prompts, environment values, or
exception representations. A failure record needs the module name and reason code, not
the sensitive value that caused it.

## Design dedupe and side effects explicitly

Context dedupe and durable dedupe are different:

- `ci/harness/dispatcher.py` removes exact duplicate context strings only within one
  dispatch.
- `hooks/_dispatch/dispatch.py` does not dedupe contexts.
- Neither dispatcher dedupes file writes, process launches, or ledger appends.

For event-ledger writes, prefer `EventLedger.append(..., dedupe_key=stable_key)`. The
ledger SHA-256 hashes the key and returns `None` when that event id already exists.
Construct the key from stable identity such as provider, session, event, turn, and tool
id; use a deterministic digest only as a fallback when the provider omitted an id.

For other state:

1. Scope by session or project as the behavior requires.
2. Use a stable action/finding id, not the full raw payload, as the key.
3. Write through `atomic_write_json()` or `atomic_write_text()`.
4. Add a TTL only when the behavior is genuinely time-bounded.
5. Test the same event twice and a replay after partial state.

Set the manifest `side_effect` label truthfully (`none`, `ledger-append`,
`seen-map`, `launch`, or another concise value). It is an audit promise, not a safety
mechanism. A row marked `none` must be observationally pure.

## Confidence-gated advisories

`hooks/calibrated-silence/calibrated_silence.py` is the current adaptive confidence
gate. It uses external user-reaction history, not an LLM's self-reported confidence.
Consumers unpack `allow, reason = should_interject(type, context)` before an advisory
and call `record_interjection(type, context_key, session_id)` only after actually
emitting it.

Preserve these invariants:

- Cold start allows until `acted + ignored` reaches `MIN_SAMPLES`; `annoyed` and
  `unknown` rows do not advance that sample count. Once out of cold start, recent
  `annoyed` reactions can still raise the fatigue criterion.
- A complete ledger-read failure or top-level gate exception allows the advisory.
  Individual malformed JSONL rows are skipped; remaining valid history can still
  suppress.
- An environment kill switch also allows rather than suppresses.
- Fatigue can suppress low-value repeats, not novel safety information.
- A distinct harm finding bypasses calibrated silence. Only a repeat under the
  consumer's explicit finding identity may enter the suppression gate.

The iatrogenics check demonstrates a recurrence gate: high-severity model-initiated
live mutations advise on the first occurrence, while command-pattern advisories get a
first-use grace; counters still advance when an advisory is suppressed. Keep thresholds
environment-tunable and test the count boundaries.

There is no `confidence_gate` property understood by `_dispatch/manifest.json`.
Implement confidence logic in the check and describe its state in `side_effect`.

## Add contraindication rows without changing code

Use `hooks/contraindication/contraindications.json` only for a real, documented
tool/action combination with a known harm and a usable alternative. The canonical row
is:

```json
{
  "id": "STABLE-UNIQUE-ID",
  "tool_pattern": "Bash|PowerShell",
  "input_pattern": "escaped-regex-over-serialized-tool-input",
  "require_bg_active": false,
  "harm": "What fails, under which combined preconditions, and why it matters.",
  "safe_alternative": "A concrete lower-risk route that still advances the goal."
}
```

`check.py` applies all supplied predicates with AND semantics and `re.IGNORECASE`.
`tool_pattern` matches the tool name; `input_pattern` matches
`json.dumps(tool_input)`; `require_bg_active` also requires a recent running
asynchronous registry entry. A malformed regex or row is skipped as a non-match; the
hook emits no warning for it and exits zero. Multiple matching rows are aggregated into
one advisory.

The check keeps a TTL-scoped per-session seen map by row id. If any matched id is new,
the whole finding bypasses calibrated silence and surfaces. Only when every matched row
id was already seen may calibrated silence dedupe the repeat. This is row-ID identity,
not exact tool/input identity: a different call matching an already-seen row is repeat-
eligible. The contraindication hook is advisory and exits zero; a row does not become a
blocker because its harm is severe.

For each row, add tests for:

- one exact positive payload;
- a close non-match that protects legitimate work;
- the `require_bg_active` true and false cases when used;
- the id, harm, and safe alternative in emitted context;
- distinct-row-id bypass and previously-seen-row-id dedupe;
- corrupt registry and malformed stdin fail-open behavior.

## Verification protocol

Prove the smallest relevant contract before broad validation.

### Module or check tests

1. Positive: the exact trigger returns the intended action and reason code.
2. Negative: a close legitimate input stays silent and allows.
3. Boundary: wrong event, tool, provider, or missing field stays silent.
4. Failure: malformed input and mocked I/O errors allow with no traceback or secret.
5. Redaction: seed representative token and absolute-path shapes; assert raw values are
   absent from stdout, durable state, and terminal logs.
6. Dedupe: replay the same event and assert one durable effect; use a distinct id and
   assert a second effect.
7. Adapter: assert provider-native rendering for every action the module can return.
8. Wiring: run through `HarnessDispatcher` or `_dispatch.run()`, not only the predicate.

For a blocking legacy gate, execute the real subprocess and assert exit 2 plus a stderr
reason on the positive case, exit zero on the negative and garbage cases. Do not test a
blocker through the inject-only dispatcher.

For a manifest change, parse JSON, assert the script exists under the intended
`hooks_root`, compile the matcher, verify the outer matcher can reach it, and compare
`emits` and `side_effect` against observed behavior. Use a temporary state root and
hermetic calibrated-silence ledger; never read or write live state during tests.

### Final review

- Re-read `models.py`, `adapters.py`, `dispatcher.py`, and the exact neighboring hook.
- Confirm every module path returns a `HookResult`; confirm every legacy path exits zero
  on internal failure.
- Confirm only dangerous, positively identified operations block.
- Confirm all guidance is inject-only and factual.
- Confirm raw secrets and paths cannot reach output or state.
- Confirm side effects are bounded, atomic, and replay-safe.
- Confirm novel harm cannot be suppressed by confidence or fatigue logic.
- Confirm manifest metadata describes what runtime tests observed.
- Run targeted tests, then the repository's relevant validation command.
- Report `SUCCESS:<id>` or `FAILED:<id> reason`; never call an unverified hook installed.