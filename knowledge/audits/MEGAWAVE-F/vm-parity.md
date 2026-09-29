# MEGAWAVE-F — VM (offload-w2025) parity + restore
Lane: F · Agent: workflow-subagent (Claude, Opus 4.8) · Date: 2026-09-28 · Status: COMPLETE

## Verdicts at a glance
| Item | Verdict |
|---|---|
| 1. VM .agents git parity | PASS — VM branch tip == live origin tip, 0 unpushed (VERIFIED) |
| 2. sshd restoration (port 22) | BLOCKED — guest sshd down; gcloud ssh refused in-guest; SFTP channel exec-restricted; no key reset performed (per directive) |
| 3. WinRM/RDP planning | PLANNED, execution needsMainLoop — 3389/5985/5986 measured OPEN; creds required for auth |
| 4. agents.json keep-set parity gap | NONE within agents.json — no VM-only path pointers; 5/10 keep-set present, 5/10 absent from this registry |
| Restore gap found (bonus) | HOME .agents is the stale side: branch behind origin by 3 FF-able commits — runbook below |

## 0. Method + rail damage (VERIFIED, exact)
- All commands run via the native Bash builtin (probe: echo PROBE_BASH_OK -> PROBE_BASH_OK).
- McpHub codex execute: FAILED "Server closed connection (after 3 attempts)".
- cursor-bridge bridge_status: FAILED — backend D:\opt\cursor-bridge\cursorctl.py status timed out after 120s (wedged).
- McpHub claude_code execute: FAILED "server did not respond within 30s (after 3 attempts)" — hub client timeout kills long jobs.
- Read-only VM access: rclone SFTP remotes vmC: (port 2022) / vmD: (port 2023), user "link", key_file C:\Users\Prekzursil\.ssh\home_to_vm, host 100.117.115.55 (from rclone config show; secret fields filtered — never printed).
- Credential discipline: no key/token read or printed; reset-windows-password / reset-ssh-keys NOT executed (directive honored). Note: the authorized gcloud compute ssh attempt registered/refreshed gclouds own managed SSH key in project metadata (standard behavior of that command; transcript in §2).

## 1. VM .agents git parity — PASS (VERIFIED)
VM repo path (via rclone): vmC:suite/payload/Users/Prekzursil/.agents/.git/ — full .git present (HEAD, packed-refs, refs/, FETCH_HEAD, ORIG_HEAD).

| Ref | VM value | Live origin (ls-remote from home) | Match |
|---|---|---|---|
| HEAD | ref: refs/heads/live-capture/2026-09-02 | (n/a) | - |
| refs/heads/live-capture/2026-09-02 | ee21a2fb0cd531b3c4fcfcac58a2be6d73791441 | ee21a2fb0cd531b3c4fcfcac58a2be6d73791441 | YES |
| refs/remotes/origin/main (loose on VM) | c56f06be554c3c97032ed5814f6063279486cd96 | c56f06be554c3c97032ed5814f6063279486cd96 | YES |
| VM FETCH_HEAD line 1 | 5894ce61... branch live-capture/2026-09-02 | (n/a) | older fetch |

Evidence commands: rclone cat vmC:suite/payload/Users/Prekzursil/.agents/.git/HEAD ; rclone cat .../refs/heads/live-capture/2026-09-02 ; rclone cat .../refs/remotes/origin/main ; git -C C:/Users/Prekzursil/.agents ls-remote origin refs/heads/live-capture/2026-09-02 refs/heads/main.
Note: VM packed-refs carries stale packed copies (heads/live-capture/2026-09-02 = 5af4bbe9..., origin/live-capture/2026-09-02 = 7050d4b8..., origin/main = 9c98df1a...). Loose refs override packed-refs in git; the loose values are authoritative and hash-match live origin.
VERDICT: VM HEAD tip == origin tip exactly; 0 unpushed commits on the VM. (VERIFIED — hash equality on two refs against live origin.)

## 1b. BONUS — home is the stale side (VERIFIED)
- Home C:\Users\Prekzursil\.agents IS a git repo (rev-parse --is-inside-work-tree = true), origin = https://github.com/Prekzursil/agent-skills-toolchain.git.
- Home branch live-capture/2026-09-02 @ 5894ce61558b28522004c0d6e2ef0b92f0c0e287; home origin/main @ c56f06be (== live); but live origin branch tip is ee21a2f.
- GitHub compare API 5894ce61...ee21a2fb -> {"status":"ahead","ahead_by":3,"behind_by":0} — origin is 3 commits ahead of home, clean fast-forward (VERIFIED).
- Restore runbook (main loop / owner; NOT executed here to avoid mutating .agents under concurrent lanes):
  git -C C:/Users/Prekzursil/.agents fetch origin live-capture/2026-09-02 && git -C C:/Users/Prekzursil/.agents merge --ff-only origin/live-capture/2026-09-02

## 2. sshd restoration — BLOCKED (VERIFIED evidence; directive honored)
Attempted exactly: gcloud compute ssh offload-w2025 --zone=europe-central2-a --project=webcoder-462916 --account=prekzursil1993@gmail.com --command="hostname" (timeout 140s).
Result: metadata key stage OK — "Updating project ssh metadata... Updated [projects/webcoder-462916]... Waiting for SSH key to propagate." then 7x "FATAL ERROR: Network error: Connection refused", gcloud error "Could not SSH into the instance... verify that the firewall and instance are set to accept ssh traffic."
- Interpretation: gcloud key propagated to project metadata, but the GUEST sshd on port 22 is down (matches known state). Port 22 measured CLOSED_OR_TIMEOUT from home (independent signal).
- Escalation probe: SSH to the VM own SFTP channel (user link, ports 2022 and 2023, key home_to_vm) -> "hostname" not implemented on BOTH ports — the channel is SFTP-only, no shell; cannot Start-Service sshd from here.
- Per directive: reset-windows-password / reset-ssh-keys NOT run. Reported blocked.
- Remaining paths (all needsMainLoop): (a) WinRM 5985/5986 with creds -> Get-Service sshd; Start-Service sshd; Set-Service sshd -StartupType Automatic; (b) RDP 3389 interactive; (c) GCE serial console enable + connect; (d) gcloud compute reset-windows-password (owner decision — credential action, lane did not run it).

## 3. WinRM/RDP planning — measured ports (VERIFIED)
TcpClient probes to 100.117.115.55 (3s timeout): 22 CLOSED_OR_TIMEOUT; 3389 OPEN; 5985 OPEN; 5986 OPEN.
Answer to "is 3389/5985 enough to plan WinRM?": YES for planning — WinRM listeners are reachable on 5985 (HTTP) and 5986 (HTTPS, preferred: transport-independent of domain), with RDP 3389 as interactive fallback. Execution is auth-gated: needsMainLoop for local-admin credentials. Plan once creds exist:
New-PSSession -ComputerName 100.117.115.55 -Port 5986 -UseSSL -Credential (Get-Credential) -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck) ; then Invoke-Command: Get-Service sshd ; Start-Service sshd ; Set-Service sshd -StartupType Automatic ; then re-probe port 22 from home.

## 4. Parity gap — agents.json keep-set (VERIFIED from C:\Users\Prekzursil\.agents\agents.json, 87,938 bytes, mtime 2026-09-28T01:55)
Keep-set coverage in agents.json ($/mcp/servers/*):

| Keep-set server | In agents.json | Command/transport | VM-only path pointer? |
|---|---|---|---|
| codex | NO — 13 bare codex strings, all inside other entries descriptions/x_codex blocks; no mcp/servers/codex key | - | - |
| github_cli | YES, enabled | gh-cli-mcp (stdio) | no paths |
| ocr-suite | NO (0 grep hits) | - | - |
| openmm-md | NO (0 grep hits) | - | - |
| paper-search | YES, enabled=false (parked: use McpHub SSE) | D:/ReverseTools/mcp/paper-search-mcp/venv/Scripts/paper-search-mcp.exe | NO — path EXISTS on home (VERIFIED on disk: exe present, 108,366 bytes) |
| perplexity | NO (0 grep hits) | - | - |
| postgres | YES, enabled=false (parked) | docker run ghcr.io/pgedge/postgres-mcp | no paths |
| rdkit | NO (0 grep hits) | - | - |
| sonarqube | YES, enabled=false (parked) | docker run docker.io/mcp/sonarqube | no paths |
| codacy | YES, enabled=false (parked) | npx @codacy/codacy-mcp@0.6.24 | no paths |

VERDICT: within agents.json, NONE of the keep-set entries point at a VM-only path. The premise "D:/ReverseTools = VM-only" is FALSE for this registry: the paper-search D:/ReverseTools path resolves on home. The five absent servers (codex, ocr-suite, openmm-md, perplexity, rdkit) are not registered in agents.json at all — they live on other surfaces (McpHub fleet lists ocr-suite/openmm-md/perplexity/rdkit; codex rides its own mcp-server rail). Lane B overlap left to that lane.

## 5. Terminal marker
SUCCESS:MEGAWAVE-F
