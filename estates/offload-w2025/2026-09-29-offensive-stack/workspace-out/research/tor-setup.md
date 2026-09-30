# Tor setup — VM provisioning notes

Date: 2026-09-29. All commands below were run on this VM during this ask.

## Status: WORKING

## Install layout

- Install dir: `D:\opt\tor` (tor.exe, tor-gencert.exe, pluggable_transports/ with
  lyrebird.exe + conjure-client.exe, `torrc`, `data/` DataDirectory, `tor.log`).
- Tor version (from `D:\opt\tor\tor.exe --version`, run this session):
  **0.4.9.13 (git-3c575400909efe65)**, Libevent 2.1.13-stable, OpenSSL 3.5.8,
  compiled with clang 19.1.7.
- Provenance caveat: the expert bundle was already present and running when this
  ask started (file timestamps today 17:53–18:46). The download itself happened
  before this session, so I did not witness which source served the zip. Both
  candidate sources are reachable from this VM (checked this session):
  - `https://dist.torproject.org/torbrowser/` → HTTP 200 (primary)
  - `https://github.com/torproject/tor` → HTTP 200 (mirror)
  If a re-download is ever needed, fetch
  `dist.torproject.org/torbrowser/<ver>/tor-expert-bundle-windows-x86_64-<ver>.tar.gz`
  and extract into `D:\opt\tor`.

## Config (`D:\opt\tor\torrc`)

```
SocksPort 127.0.0.1:9050
SocksPort 127.0.0.1:9150
DataDirectory D:\opt\tor\data
Log notice file D:\opt\tor\tor.log
```

## Proxy strings (the answer to "exact proxy string")

- **Primary: `socks5h://127.0.0.1:9050`** — in curl:
  `curl --socks5-hostname 127.0.0.1:9050 <url>` (DNS resolved through Tor, which
  is what you want for .onion / no-leak use).
- Fallback: `--socks5-hostname 127.0.0.1:9150` (second listener in the same
  process; handy when another tool squats on 9050).
- `--socks5` (not `-hostname`) would resolve DNS locally — avoid.
- SOCKS5, no auth. Not an HTTP proxy.

## Autostart

Scheduled task **`TorProxy`** (status Ready, verified this session via
`schtasks /Query /TN TorProxy`): runs `D:\opt\tor\tor.exe -f D:\opt\tor\torrc`
at logon for `prekzursil`, no execution-time limit. Defined in
`D:\opt\tor\tor-autostart-install.ps1`. Single process, no watchdog — same
lifecycle pattern as CyberStrikeGateway.

## Verification (run this session)

1. Port listening: `netstat -ano | grep :9050` →
   `TCP 127.0.0.1:9050 ... LISTENING` (PID 28740, tor.exe confirmed via tasklist).
2. **Primary check, exactly as specified:**
   ```
   curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip
   → {"IsTor":true,"IP":"45.84.107.200"}   (exit 0)
   ```
   `IsTor` is `true` — Tor confirmed. (The API's JSON key is `IsTor`, capital I —
   not `is_this_tor` as the ask's shorthand put it.)
3. Fallback port: `curl --socks5-hostname 127.0.0.1:9150
   https://check.torproject.org/api/ip` → `{"IsTor":true,"IP":"109.70.100.6"}`
   (exit 0). Different exit IP = different circuit, both live.

## Log / health

`D:\opt\tor\tor.log` shows normal notice-level traffic plus benign
`[scrubbed].onion resolve failed / No more HSDir available` entries from earlier
use of the proxy — not a health problem for the proxy itself. Bootstrap state
files in `D:\opt\tor\data\` (cached-microdesc-consensus, cached-microdescs) are
populated and fresh.

## Usage recipes

- curl: `curl --socks5-hostname 127.0.0.1:9050 https://example.onion/`
- Python requests: `requests.get(url, proxies={"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"})`
  (needs `pip install requests[socks]`).
- Restart if needed: `schtasks /End /TN TorProxy; schtasks /Run /TN TorProxy`
  (or `taskkill /PID <pid>` then `/Run`).
