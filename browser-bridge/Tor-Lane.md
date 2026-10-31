---
title: Tor-Lane
type: note
permalink: dqverify-repo-20261013/browser-bridge/tor-lane
---

# Tor Browser lane — on-demand (locked Tor 2A)

**Status this run:** definition + dry-run only. Tor Browser is installed at
`C:\Users\Prekzursil\Desktop\Tor Browser` (firefox.exe 140.14.0). SOCKS **9150** and
control **9151** were **free** at stand-up (no `tor.exe` running). This lane is **not**
launched automatically so the owner's desktop is not disturbed.

## Contract

- Profile choice still applies. Tor LIVE (the human's TB UI) is **refused**.
- Dedicated persistent profile: `~\.agents\browser-profiles\tor-agent`
- Drive with `tbselenium` / `tbselenium-windows` + geckodriver/Marionette.
- `tor_cfg=USE_RUNNING_TOR`, `socks_port=9150`. **Do not launch a second `tor.exe`.**
- If TB is already running for the owner: do not attach to that UI; wait or abort.
- If TB is not running: starting it would also start Tor — only with explicit `-Launch` after the owner opts in.
- Anonymity hygiene: keep stock window size (letterboxing); do not install extra extensions into TBB; do not mix this lane with Chrome/Edge cookies.

## On-demand start (owner-invoked)

```powershell
pwsh -File ~\.agents\browser-bridge\Start-TorLane.ps1 -Profile agent-persistent -Launch
```

Without `-Launch`, the script only prints the definition and exits 0 (`on-demand / dry-run`).

## Python sketch (not executed this run)

```python
from tbselenium.tbdriver import TorBrowserDriver
from tbselenium.utils import start_xvfb, stop_xvfb  # not used on Windows
from tbselenium.tbdriver import TBDriver

# Windows: tbselenium-windows port; TBB_PATH = r"C:\Users\Prekzursil\Desktop\Tor Browser"
# socks 9150, dedicated profile_dir = r"C:\Users\Prekzursil\.agents\browser-profiles\tor-agent"
```