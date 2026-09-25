# Session transcript locate + bundle + Taildrop transfer (VM -> host)

Reusable knowledge from session `498c0655` on `offload-w2025` (the disposable VM).
Goal: capture a *complete* Claude Code session — main transcript plus every
subagent / ultracode-workflow transcript — and move it to the durable host.

## 1. Where a full session actually lives

A session is **not** one file, and its pieces are **not** all under one project slug.

| Piece | Path |
|---|---|
| Main transcript | `~/.claude/projects/<slug>/<session-id>.jsonl` |
| Subagent / workflow transcripts | `~/.claude/projects/<slug>/<session-id>/subagents/workflows/wf_*/` |
| — per workflow | `journal.jsonl` (one result line per agent) + `agent-<id>.jsonl` per subagent |
| Workflow scripts | `~/.claude/projects/<slug>/<session-id>/workflows/scripts/*.js` |
| Background task outputs (workflow results) | `%TEMP%\claude\<slug>\<session-id>\tasks\*.output` |

**Gotcha — the cwd-slug split.** The project *slug* is derived from the cwd, so
when the working directory changes mid-session the same `<session-id>` gets a
**second (and third) slug directory**, and the workflow *scripts* often land under
a different slug than the *transcripts*. In `498c0655` the scripts were under
`...Example-folder--1-...` and `...-artifacts` slugs while the transcripts were
under `C--Users-prekzursil`. **Always enumerate every slug for the session id**
(`find ~/.claude/projects -maxdepth 2 -name "<id>.jsonl"` and
`-type d -name "<id>"`), never assume one.

## 2. Bundle it (verifiable)

`scripts`-style one-shot: zip every slug's `<id>.jsonl` + `<id>/` tree + the
`tasks/*.output`, add a `MANIFEST.txt` (file list + counts by kind + raw bytes),
then **record sha256 and run `zipfile.testzip()`** so the archive is proven intact
before it leaves the box. Session `498c0655`: 277 files, 167.9 MiB raw -> 66.4 MiB
zip (39.5%). Subagent transcripts dominate (127 files / 156 MB) — the main
transcript was only 14 MB.

## 3. Transfer via Taildrop

`& 'C:\Program Files\Tailscale\tailscale.exe' file cp <bundle> <host>:`

**Gotcha — no store-and-forward.** If the target peer is offline the send does
**not** queue. It prints `# warning: <host> is reportedly offline; trying anyway`
then `502 Bad Gateway` — **and exits 0**, so a naive `$?` check reads it as
success. Always check `tailscale status --json` `.Peer[].Online` first, and grep
the cp output for `Bad Gateway|offline|error|refused`, not just the exit code.

**Pattern — retry-until-online (survives session end).** Register a Scheduled
Task that every ~2 min reads `tailscale status --json`, sends only when the peer
is `Online`, logs the result, and **self-unregisters on success**. This is the
right move on a disposable VM: don't leave the only copy on `offload-w2025`.

**Gotcha — schtasks under Git Bash.** MSYS path-conversion rewrites `/Create`,
`/TN`, `/SC` … into `<git-root>/Create` etc., so `schtasks /Create` fails with
`Invalid argument/option - 'F:/'`. Use PowerShell `Register-ScheduledTask`
(`-Trigger -Once -RepetitionInterval`, `-Settings -StartWhenAvailable`), not
`schtasks` from bash.

**Verify on arrival** with the recorded sha256; do not delete the VM copy until it
matches on the host.

## 4. Host roles (do not confuse)

- `offload-w2025` — the **disposable VM**. Nothing on it is safe until transferred
  or pushed. This is why the transfer is retried rather than left pending.
- `desktop-a60s9gp` — **durable home**, the fuller side. Taildrop lands in its
  Downloads; on Windows the receive side may prompt depending on Tailscale
  settings, so if it doesn't appear, check for a notification.
- Taildrop is peer-to-peer over the tailnet; `s24` (phone, usually online) works as
  a relay when the host is down.
