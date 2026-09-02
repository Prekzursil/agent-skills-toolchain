# Estate native browser automation

Contract: `PROFILE-CHOICE.md` (mandatory a/b/c every run). Audit: `AUDIT.md`. Skill: `SKILL.md`.

```powershell
pwsh -File ~\.agents\browser-bridge\Start-Hub.ps1 -Mode agent
pwsh -File ~\.agents\browser-bridge\Start-AgentBrowser.ps1 -Browser chrome -Profile agent-persistent
pwsh -File ~\.agents\browser-bridge\Start-FirefoxAgent.ps1 -Profile agent-persistent
python ~\.agents\browser-bridge\proof\prove-firefox.py --profile agent-persistent --user-data-dir $env:USERPROFILE\.agents\browser-profiles\firefox-agent --results ~\.agents\browser-bridge\proof\results
pwsh -File ~\.agents\browser-bridge\Start-TorLane.ps1 -Profile agent-persistent   # dry-run unless -Launch
```

Persistent profiles (never wiped): `~\.agents\browser-profiles\{chrome,edge,firefox,tor}-agent`.
Hub: `ws://127.0.0.1:8770` (agent) / `8790` (live). Token required from `~\.agents\local.json` `chromeBridge` (gitignored). Do not use 8787.
LIVE uses `extension-live` (8790 baked in). Agent uses `extension-agent` (8770, id `bdccimcedobipcmhcikcnakjdemiechj`). Never load the agent extension into the human profile.
