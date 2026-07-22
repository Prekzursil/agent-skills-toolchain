# proxy-mcp — HTTP(S) traffic inspection over MCP

Lets an agent observe and analyse HTTP(S) traffic: list captured flows, filter
them, read request/response headers and bodies, replay or modify a request, and
export a HAR — through MCP tools.

**Registered DISABLED by default** (owner preference: expose everything, keep it
off until needed). Enable it for a session when you actually want to capture.

---

## Which rail is real on THIS machine

| Rail | Status here | Evidence |
|---|---|---|
| **mitmproxy** | **REAL — verified working** | `mitmdump 12.2.3` on PATH; live capture of `GET http://httpbin.org/get?lane=proxy-mcp` → `200` read back through `get_traffic_summary` / `inspect_flow`; HAR 1.2 export with 1 entry. |
| **Fiddler** | **NOT INSTALLED** | Confirmed absent by three independent probes: Program Files / AppData paths, the 705-entry uninstall registry (detector sanity-checked — it finds Git and Python), and a recursive user-tree scan for `Fiddler*`. |

No Fiddler rail ships. A rail that cannot run is scaffolding that reports
success, which is worse than an honest gap. If Fiddler Classic or Everywhere is
installed later, the natural bridge is its FiddlerScript/EXE automation surface
behind the same tool names — but that is unwritten and **UNVERIFIED**, and it
should not be built until there is an install to test it against.

mitmproxy is the primary engine regardless: scriptable, cross-platform, and
Python-native, so it matches this repo's stdlib-Python house style.

---

## Architecture — adopt, don't rewrite

The capture engine is **[snapspecter/mitmproxy-mcp](https://github.com/snapspecter/mitmproxy-mcp)**
(MIT, Python, 25 tools, 88★, last pushed 2026-06-05), adopted rather than
reimplemented per the workspace's prefer-a-proven-implementation rule.

Rejected alternatives:

- `lucasoeth/mitmproxy-mcp` — an unmodified project scaffold. Its only tool is
  the template's `add-note`; no license, last pushed 2025-06.
- `usk6666/yorishiro-proxy` — capable but written in Go, which would add a
  toolchain this repo does not otherwise carry, for no capability gain.

The engine is installed **out-of-tree** at `~/.local/opt/mitmproxy-mcp`, the same
convention the repo already uses for `apktool-mcp-server` and
`cheatengine-mcp-bridge`. It is not vendored, so upstream fixes arrive with a
`git pull` + `uv sync`.

`proxy_mcp.py` is a thin stdio JSON-RPC pass-through in front of it — the same
shape as the `social-hub` / `cloud-hub` multiplexers — adding the two things
upstream does not provide. Everything else is forwarded verbatim, so upstream
tools keep their exact names and schemas and an upgrade needs no changes here.

### 1. Credential redaction (`redaction.py`)

A traffic proxy sees **everything**: `Authorization` bearers, session cookies,
`Set-Cookie` grants, API keys in query strings, passwords and OAuth
`access_token`s in bodies. Upstream returns all of it verbatim — measured, not
assumed: a probe with a sentinel bearer token came back in cleartext through
`inspect_flow`.

Every `tools/call` result is scrubbed before it reaches the client. A redacted
value becomes `<redacted:sha256=ab12cd34,len=39>` — the short digest lets you
correlate ("same token as that other flow") and diff across requests without the
value being recoverable; the length helps debug a truncated credential.

Unlike the sibling `_shared/hardening.py` ConfirmGate, this is **ON by default**,
not shadow-by-default. A blocking gate that fires wrongly breaks a workflow, so
shadow-first is right there; a confidentiality control that defaults to
"observe only" provides nothing. Set `PROXY_MCP_REDACT=off` to consciously
disable it.

Building this found three leak paths that header-name matching alone misses —
each caught by an end-to-end probe against real captured traffic, not by
inspection:

| Leak path | Why key-matching missed it |
|---|---|
| Credentials **inside a response body** | A body arrives as an opaque string. An OAuth endpoint returns `access_token` there, and echo endpoints reflect the request `Authorization` straight back. Embedded JSON is now parsed and scrubbed recursively. |
| **HAR name/value pairs** | HAR models headers/cookies as `{"name": "Authorization", "value": "..."}`. The secret sits under a key literally called `value`. The pair shape is now handled explicitly. |
| **Inline `curl_command`** | Upstream renders a reproducible `curl ... -H 'Authorization: Bearer ...'` per flow. A line-anchored header pattern missed a credential quoted mid-line. |

Redaction is deliberately **not** a substitute for care: it is a
name-and-pattern matcher, so a credential in a field it does not recognise
(a bespoke header, a token buried in an opaque binary body) can still surface.
Treat captured traffic as sensitive regardless.

### 2. `export_har` (capability gap)

Upstream can dump mitmproxy `.flow` files but cannot emit HAR. This adds a
native HAR 1.2 export built on mitmproxy's own `savehar` addon, so the output is
what Chrome DevTools, Charles and Fiddler import. HAR entries are scrubbed too.

```
start_proxy(port=8080, dump_file="C:/tmp/session.flow")
  … drive traffic …
stop_proxy()
export_har(dump_file="C:/tmp/session.flow", output_path="C:/tmp/session.har")
```

---

## Install

```bash
git clone https://github.com/snapspecter/mitmproxy-mcp.git ~/.local/opt/mitmproxy-mcp
cd ~/.local/opt/mitmproxy-mcp && uv sync
```

Verified on this box: `uv sync` completes on Windows and the full dependency
tree (mitmproxy 12.2.1, curl-cffi, aioquic, argon2-cffi) installs from wheels —
no compiler needed.

Run `proxy_mcp.py` **with the engine venv's interpreter** so `export_har` can
import mitmproxy. That is what the canonical config entry does.
Override the engine location with `PROXY_MCP_ENGINE_HOME`.

## Verify

```bash
python -m pytest tools/mcp/proxy-mcp/tests -q       # 44 redaction tests
```

Handshake + tool surface:

```bash
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"probe","version":"0.1"}}}' \
 '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
 | ~/.local/opt/mitmproxy-mcp/.venv/Scripts/python.exe tools/mcp/proxy-mcp/proxy_mcp.py
```

Expect `serverInfo {"name": "Mitmproxy Manager", "version": "1.26.0"}` and 26
tools (25 upstream + `export_har`).

---

## HTTPS interception requires an OWNER decision

Out of the box this captures **HTTP** fully. HTTPS shows only `CONNECT` tunnels —
host and port, no headers or bodies — because TLS is doing its job.

To read HTTPS content, mitmproxy must terminate TLS and re-sign each connection
with its own CA. That requires **installing the mitmproxy root CA certificate
into the OS/browser trust store**, which is a real security decision and is
deliberately left to the owner. **No CA certificate was installed by this work.**

What you are accepting if you install it:

- Any process holding that CA's private key (`~/.mitmproxy/mitmproxy-ca-key.pem`)
  can mint a trusted certificate for **any** domain — your bank, your email —
  and your machine will accept it silently.
- The key is an ordinary file on disk. Anything that can read it inherits that
  power for as long as the CA stays trusted.
- Certificate pinning still refuses to be intercepted, so some apps break
  outright while the proxy is in use.

Practical guidance: install it only while you need it, prefer a scoped trust
store (a single browser profile) over the system store, keep
`set_scope(allowed_domains=[...])` narrow so unrelated traffic is not decrypted,
and **remove the CA when the investigation is done**. If it is ever
exposed, regenerate it — `~/.mitmproxy/` — rather than assuming brief exposure
was harmless.

Setup instructions: <https://docs.mitmproxy.org/stable/concepts-certificates/>
(with the proxy running, `http://mitm.it` serves the certificate).

## Operating notes

- **Scope the capture.** `set_scope(allowed_domains=[...])` before driving
  traffic — narrower capture means fewer credentials at rest.
- **Clear when done.** `clear_traffic()` drops the in-memory flow store;
  `stop_proxy()` ends the listener.
- **Dump files and HAR exports are plaintext artifacts on disk.** They outlive
  the session. Write them somewhere you will actually clean up, and do not commit
  them — `*.flow` and `*.har` are gitignored here.
- **This box freezes on MCP process duplication.** Keep proxy-mcp disabled unless
  a session is actively capturing; do not leave it enabled across many sessions.
