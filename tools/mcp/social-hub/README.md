# social-hub — lazy, name-preserving MCP multiplexer for the social stack

Fronts the user's social MCP servers behind **one** MCP registration while keeping
every tool under its **original name**. `initialize` and `tools/list` are answered
from committed per-backend caches **without spawning anything**; a `tools/call`
lazily spawns **only** the owning backend (once, kept alive for the session) and
forwards the request. This is the multi-backend generalization of
`../../../../.local/opt/mcp-shims/lazy_proxy.py` (which fronts a single server).

Why not a normal aggregator (mcp-funnel / 1mcp)? Those rename tools to
`serverName__tool`, which breaks skills that hardcode `mcp__insta-mcp__*` etc. This
hub preserves names and only renames on a genuine cross-backend collision.

## Backends & tool surface (60 tools)

| id | backend | tools | notes |
|----|---------|-------|-------|
| `insta` | insta-mcp (Instagram) | 36 | needs `data/session.json` + `IG_APP_VERSION`; auths at startup |
| `tiktok` | tiktok-mcp (public scraper) | 9 | keyless; some tools need `TIKTOK_PROXY` off a home IP |
| `fb` | fb-messenger-mcp | 5 | needs `data/cookies.json`; enumerates offline |
| `wa` | whatsapp-mcp (Baileys) | 7 | parked POC; QR at startup; degrades to a clear error |
| `fbreels` | fb-reels-uploader | 3 | wraps the Reels upload CLI; one-time FB login (below) |

### Collision policy

Unique names are kept **exactly**. Cross-backend collisions get a minimal
`<prefix>_` and are advertised in the tool description. The only collision today:

| original | fb-messenger exposes | whatsapp exposes |
|----------|---------------------|------------------|
| `search_messages` | `fb_search_messages` | `wa_search_messages` |

`python hub.py --print-plan` prints the live merged plan (counts, collisions, renames, degraded backends).

## Runtime / commands

```
python hub.py                      # runtime stdio MCP (what ~/.mcp.json runs)
python hub.py --refresh [ids...]   # (re)generate tool caches by enumerating backends
python hub.py --print-plan         # print the merged plan summary
```

Caches live in `caches/*.json` (lazy_proxy shape: `{initialize, tools}`) and are
committed so the merged `tools/list` is complete even when a backend can't log in.
`--refresh` never overwrites a good cache with a failed enumeration. `whatsapp` is a
hand-authored static cache (it cannot enumerate offline — QR pairing at startup).

Stdlib only (Python 3.9+). Fail-safe: a backend that can't spawn/enumerate returns a
clear error for **its** tools only; the hub never crashes and other backends are
unaffected. Each child inherits `os.environ`, so session files, cookies,
`IG_APP_VERSION`, `TIKTOK_MS_TOKEN` and proxies pass through automatically.

## Registration (for the orchestrator — not wired here)

Add one entry, remove the three direct social entries it replaces:

```jsonc
"social-hub": {
  "type": "stdio",
  "command": "C:\\Python314\\python.exe",
  "args": ["C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\social-hub\\hub.py"],
  "env": {}
}
```

Remove from `~/.mcp.json`: `insta-mcp`, `tiktok`, `fb-messenger` (now fronted lazily;
`whatsapp` and `fb-reels` were never registered and come along for free).

## fb-reels one-time pre-auth

Facebook has no personal-profile post API, so uploads drive a real browser against a
persistent profile. Authenticate the profile **once** by a human:

```
cd ../fb-reels-uploader
node fb-reels-upload.mjs <anyFolderWithMp4s>   # a window opens — log into Facebook
```

After that the MCP tools (`fb_upload_reel`, `fb_upload_reels_from_folder`) run
headless and are non-blocking: they return a `jobId`; poll `fb_reels_status(jobId)`.

## Tests

```
python -m pytest tests -q     # 10 tests: collision/merge/routing + lazy-spawn integration
python e2e_live.py            # live: routes tiktok_trending through the hub (Windows)
```
