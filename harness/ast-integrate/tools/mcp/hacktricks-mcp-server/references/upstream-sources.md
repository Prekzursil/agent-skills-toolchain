# Upstream sources and safe review record

## Grounding (immutable receipts)

- Official organization: `https://github.com/HackTricks-wiki`
- Official main source: `https://github.com/HackTricks-wiki/hacktricks`
- Official cloud source: `https://github.com/HackTricks-wiki/hacktricks-cloud`
- Official AI documentation: `https://docs-ai.hacktricks.wiki/`
- Official AI origin: `https://ai.hacktricks.wiki`
- Community stdio source: `https://github.com/Xplo8E/hacktricks-mcp-server`
- Reviewed community commit: `931b474ce6d725ed71cd1a8534758e0dd3f4a110`
- npm release/tag commit: `b184f3d44f946bf6b0cc751ab0817078ee55accd`
- MCP Registry identity: `io.github.Xplo8E/hacktricks-mcp-server`
- npm package + integrity: `hacktricks-mcp-server@1.3.4`,
  `sha512-UupJYXXjWFq7AD+HnY7L3LRjv1gAiVtVrnxm7gGeGE7qFNpSh3NzFr6v7JW4rAj69MbUK7CMDUuLo2BC1ezkQg==`
- Pinned main corpus commit: `346301958c8bf94120ba0aaaaf9cd963997bdac3`
- Pinned cloud snapshot receipt: `5aadfa8fbffc738ddd9db0b8bb42cca2b62db9fc`

## Provenance verdict

As of 2026-07-24, HackTricks does **not** publish an official MCP server or MCP
repository. Official HackTricks AI is an authenticated REST Chat/RAG API. The
practical installable MCP is the community-maintained `Xplo8E/hacktricks-mcp-server`;
adopt it only under that label, never as an official HackTricks server.

## Safe review procedure used

Reviewed read-only from a trusted parent directory. Cloned
`--depth 1 --no-recurse-submodules` to a disposable temp directory, inspected the
pinned commit's tree/manifests/lifecycle scripts, then deleted the checkout. Never
`Set-Location` into the checkout; never ran its `npm`/`npx`/build/tests/postinstall/
setup/hooks/server.

## Independent review evidence (fresh clone, 2026-07-24)

A fresh `git clone --depth 1` resolved `HEAD` to exactly
`931b474ce6d725ed71cd1a8534758e0dd3f4a110` (matches the recorded reviewed commit —
independent second signal). Observed in that tree:

- `package.json` declares `"postinstall": "node scripts/postinstall.js"` (lifecycle
  script) and `"@modelcontextprotocol/sdk": "^1.0.0"` (floating, un-pinned graph);
  license `MIT`; `mcpName` `io.github.Xplo8E/hacktricks-mcp-server`.
- `.gitmodules` binds submodule `hacktricks` to `https://github.com/carlospolop/hacktricks.git`.
- `scripts/postinstall.js` (CONFIRMED behaviors): `rmSync(hacktricksPath, {recursive:true, force:true})`
  on an "incomplete" sibling `hacktricks/`; `git clone --depth 1 --single-branch`
  of the unpinned moving `carlospolop/hacktricks.git`; a `SKIP_POSTINSTALL=true`
  bypass; and deliberate `process.exit(0)` when Git is missing so `npm install` never
  fails. It never refreshes an existing valid clone and cannot consume `HACKTRICKS_CORPUS`.

## Reasons the raw upstream fails this estate's run gate

- `scripts/postinstall.js` can recursively remove an incomplete sibling `hacktricks/`,
  clones an unpinned moving branch, times out after 120 seconds, and deliberately
  exits zero when Git is missing or the clone fails;
- it clones main only from `https://github.com/carlospolop/hacktricks.git` (currently
  redirected to the official repository), never refreshes an existing valid clone, and
  cannot consume `HACKTRICKS_CORPUS`;
- `execFile` avoids shell expansion, but the model-controlled regex appears before the
  path without `-e ... --`, so a leading-dash query is option injection and can invoke
  ripgrep features such as `--pre`;
- category handling lacks complete containment; page checks are lexical rather than
  realpath/symlink-safe;
- raw queries/categories go to stderr;
- native Windows `C:\path:line:text` breaks its colon-delimited result parser;
- full pages, sections, cheatsheets, trees, and quick lookup are not usefully bounded;
  its child buffer may grow to 10 MiB;
- it recognizes ordinary triple-backtick fences only;
- it has manual material but no automated coverage gate;
- package pinning alone does not pin the `^1.0.0` MCP SDK dependency graph or the
  corpus HEAD.

## Rejected unsafe registration (historical evidence only — never place in active config)

```json
"hacktricks": {
  "type": "stdio",
  "command": "cmd.exe",
  "args": ["/d", "/s", "/c", "npx.cmd", "--yes", "hacktricks-mcp-server@1.3.4"],
  "env": {}
}
```

```json
"hacktricks": {
  "type": "stdio",
  "command": "cmd",
  "args": ["/c", "npx", "-y", "hacktricks-mcp-server@1.3.4"]
}
```

Also rejected for active use: `npm install --global hacktricks-mcp-server@1.3.4`,
`npx hacktricks-mcp-server`, floating tags/branches, `@latest`, and
`SKIP_POSTINSTALL=true` as a lifecycle-security substitute. The first dependency
materialization after transplant/review is `npm ci --ignore-scripts`.
