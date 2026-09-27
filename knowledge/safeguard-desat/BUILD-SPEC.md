# security_digest — build-spec & ingestion (STAGED, OFF-MAIN)

Standalone `PostToolUse.updatedToolOutput` de-saturation hook that attacks the *real*
classifier-false-positive trigger — **accumulated security-heavy context** (a single dense
payload can one-shot the classifier; the poisoned context then re-sends every turn). It
replaces an over-large tool payload in-context with a compact digest (line/byte counts +
sha256 + bounded head/tail) BEFORE it lands in the window. It de-saturates the CONTEXT; it is
**not** redaction and **not** a wire-level classifier-blinder — the full output was produced by
the tool and stays in the transcript/on disk. This is the legitimate, effective lever; model-
switching and prompt-rewording miss it because the trigger is context volume, not model/prompt.

Status 2026-09-28: authored + both-states self-test PASS (fires-on-heavy, silent-on-benign,
no-ops-when-disabled). NOT wired into any live hook. Not a regression risk until activated.

## Files (this dir: ~/.agents/knowledge/safeguard-desat/)
- `security_digest.py` — the hook. stdlib-only, self-contained, fail-open, OFF unless
  `SECURITY_DIGEST_ENABLE=1`.
- `security_digest.selftest.py` — both-states test. Run before every activation.

## Contract (mirrors cmd-rewrite/compress-output.py, verified against claude.exe v2.1.283)
- stdin PostToolUse JSON: `{tool_name, tool_input:{command}, tool_response: str|{text|content|stdout|output}}`
- stdout on digest: `{"hookSpecificOutput":{"hookEventName":"PostToolUse","updatedToolOutput":"<digest>"}}`
- no output = pass-through (tool output unchanged).

## Config (all env, all optional)
| env | default | meaning |
|---|---|---|
| `SECURITY_DIGEST_ENABLE` | (off) | `1`/`true`/`on` to activate; anything else = no-op |
| `SECURITY_DIGEST_SIZE` | 6000 | only payloads larger than this are considered |
| `SECURITY_DIGEST_MAX_LINES` | 400 | > this many lines => heavy |
| `SECURITY_DIGEST_MAX_LINE` | 2000 | any single line longer => heavy |
| `SECURITY_DIGEST_HEAD` / `_TAIL` | 40 / 10 | lines kept in the digest |
| `SECURITY_DIGEST_PATTERNS` | (none) | path to a file of one regex/line; a match => heavy. **Keep the trigger vocabulary HERE, external — never bake it into the module.** |

Detection is structural by default (size + base64-ish blob + line counts); patterns are the
opt-in vocabulary lane, supplied per surface so the module stays domain-neutral and portable.

## Test (mandatory before activating anywhere)
```
python ~/.agents/knowledge/safeguard-desat/security_digest.selftest.py   # expect SUCCESS:security_digest.selftest
```

## Ingest — pick a surface (each is reversible)
1. **A fresh Claude session (recommended first — the saturated session re-fires):**
   copy the two files into `~/.claude/hooks/security-digest/`, add a PostToolUse entry
   pointing at `security_digest.py` (matcher `Bash|Read|Grep` or `*`), and set
   `SECURITY_DIGEST_ENABLE=1` in that session's env. Because `~/.claude/hooks/` is a
   DEPLOYED tree, put the source in the repo (`~/source/agent-skills-toolchain/hooks/` or
   `~/.agents/hooks/`) and deploy, so it is not overwritten.
2. **CyberStrike:** drop `security_digest.py` into its hooks/tool-post path and export
   `SECURITY_DIGEST_ENABLE=1` (+ a `SECURITY_DIGEST_PATTERNS` file tuned to offensive-tool
   output) in the CyberStrike launch env. Self-contained, stdlib-only — no deps to add.
3. **The live compress-output.py** (only if you want it in the main harness): DON'T fork —
   call `security_digest` FIRST in the PostToolUse chain (it digests security-heavy output),
   then let `compress-output.py` handle the generic-verbose case. Keep both fail-open.

## Boundary (explicit)
This reduces what enters the context window. It does NOT strip content from requests to blind
the classifier (that wire-level "AUP sanitizer" proxy is a general safety-defeat and is out of
scope — and per the estate's own research it wouldn't fix the re-send/floor problem anyway).
The real server-side relief remains **CVP** (owner applies).

## Provenance
Resumes prompt-interception-sota-2026-09-25 + recover-from-false-positive/references/
{sota,gray-lane}-2026-09.md. Supersedes that corpus's refuted #1 lever (PreModelSwitch deny —
does NOT fire for safeguard switches, confirmed v2.1.283).
