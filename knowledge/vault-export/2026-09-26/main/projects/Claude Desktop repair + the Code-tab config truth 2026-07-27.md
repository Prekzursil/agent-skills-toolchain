---
title: Claude Desktop repair + the Code-tab config truth 2026-07-27
type: project
permalink: main/projects/claude-desktop-repair-the-code-tab-config-truth-2026-07-27
tags:
- claude-desktop
- msix
- harness
- hooks
- mcp
- skills
- corrections
- windows
---

# Claude Desktop repair + the Code-tab config truth (2026-07-27)

Repaired Claude Desktop on the Windows box and settled — from primary docs — what the CLI and
Desktop actually share. **Three of my four hypotheses were refuted by controls**; only the fourth
survived. Recording the refutations, because each was plausible and cost real time.

## THE BIG CORRECTION — Desktop DOES share the harness

I told the owner "hooks and rules can never be shared with Desktop." **That is wrong.**
`code.claude.com/docs/en/desktop` states Desktop *"runs the same underlying engine"* and:

- `CLAUDE.md` / `CLAUDE.local.md` — used by both
- MCP servers in `~/.claude.json` / `.mcp.json` — **work in both**
- **Hooks and skills** defined in settings — **apply to both**
- `~/.claude/settings.json` — **shared**, incl. permission rules

The app has **three tabs** and the split is PER TAB, not per app:

| tab | MCP | skills | hooks/rules |
|---|---|---|---|
| **Code** | `~/.claude.json` **+ UNION with** `claude_desktop_config.json` | `~/.claude/skills` | **yes, same settings.json** |
| **Cowork** | account connectors | account-synced | no |
| **Chat** | `claude_desktop_config.json` | account | no |

I generalised a REAL Cowork limitation ("Cowork sessions don't read `~/.claude/skills/`") into a
false claim about the whole app. **Read which SURFACE a doc sentence scopes to before generalising.**

## Install architecture — it is MSIX now, not Squirrel

- Live app = MSIX `Claude_pzs8sxrjxfjjc`, installs to `C:\Program Files\WindowsApps\Claude_<ver>_x64__pzs8sxrjxfjjc`
- `%LOCALAPPDATA%\AnthropicClaude\app-<ver>` is a **vestigial Squirrel leftover** — deleting it is safe
- MSIX apps do **not** appear in the classic Add/Remove registry keys; absence there is NOT corruption
- Installer = 6.7 MB Go bootstrapper, EV-signed `CN="Anthropic, PBC"`, pulls the real MSIX
- Upgrade path: `https://claude.ai/api/desktop/win32/x64/setup/latest/redirect` (403s to a PowerShell UA — use curl with a browser UA)

### The install failure worth remembering
`AddPackage failed with HRESULT 0x80073CFF` = `ERROR_INSTALL_POLICY_FAILURE`.
**The installer's own precheck reads the WRONG key**: it logs `Sideloading enabled: true` from
`HKLM\...\CurrentVersion\AppModelUnlock`, but `HKLM\SOFTWARE\Policies\Microsoft\Windows\Appx` is
what actually enforces. Policy=0 with AppModelUnlock=1 → it proceeds confidently, then fails.
Fix = set `AllowAllTrustedApps` (signed pkgs) and/or `AllowDevelopmentWithoutDevLicense` (unsigned/dev).

## Refuted hypotheses (all plausible, all wrong)

1. **"Cleanup deleted Update.exe so it can't self-update"** — irrelevant; MSIX doesn't use Squirrel.
2. **"Defender scanning slows extension spawn"** — real-time protection is **OFF**, 0 exclusions.
3. **"RAM pressure"** — trivial `node -e` start is **47-57 ms**. Box was fine.
4. **SURVIVED: cold file cache.** Extension spawn limit is **5000 ms**; cold 7519 / 9775 / 32998 ms
   vs warm **442 / 373 / 990 ms**. The upgrade invalidated the cache over 88,765 extension files.
   **Fix is simply a restart** — no config change.

Also refuted: an account-mismatch theory — `extensions-installations.json` holds **zero UUIDs**
(extensions are not account-scoped) and `cowork-enabled-cli-ops.json` ownerAccountId matched.

## Concrete gotchas

- **`burp` MCP died on JDK path rot**: config hardcoded `jdk-21.0.10.7-hotspot`; a patch update made
  it `jdk-21.0.11.10-hotspot`. Electron's UtilityProcess does NOT PATH-resolve a bare `java` on
  Windows, so the entry must stay absolute — a junction (`jdk-21-current`) is the durable fix.
- `vm_bundles` = a full Linux microVM for Cowork local-agent-mode (`rootfs.vhdx` 10 GB). **13.25 GB
  reclaimable** if local agent mode is unwanted; the app rebuilds on demand.
- Desktop data dir went 16,663 MB → ~2,600 MB after removing the VM, agent-mode sessions, caches.

## Still open — a SECURITY control merged but not deployed

`hooks/per-edit-check/check.py`: the write-path secret gate from **PR #211 is merged but NOT LIVE**.
Live copy is 9,546 bytes with **zero** `_scan_secrets`; repo is 15,378 with the full gate.
Not deployed unasked because it blocks edits with exit 2 and 13 fixture files would need
`PER_EDIT_SECRETS=off`. **The control whose absence was the headline finding is still absent live.**

## Deploys landed (each both-states proven)

- `tool-result-sentinel` — HTTP 200 was read as `exit code 200`. Repo was a strict superset; deployed;
  **6/6** both-states. Side effect: closes the `user_cancelled_or_timedout` field-name FP loop.
- `stubscan` wrapped-comment fix (**PR #230**) — `_WEAK`'s lead-vs-trail test was LINE-scoped, so a
  description that WRAPS put the word at line-offset 16 (≤24) and read as a declaration. Now
  reassembles the comment BLOCK and measures within the SENTENCE. Fail-first proven.
- `sessionstart-replay` — **already deployed**; my "not deployed" call came from comparing BYTES
  (comments differ) instead of CODE. Compare code lines, not file size.

Related: [[project_ci_coverage_and_aws_2026-07-25]] · [[reference_session_learnings_2026-07-18]]
