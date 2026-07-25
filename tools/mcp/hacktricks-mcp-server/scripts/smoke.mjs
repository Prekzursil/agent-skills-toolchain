#!/usr/bin/env node
// Harmless read-only MCP smoke test: spawn the built server over stdio, complete
// the SDK initialize handshake, and assert exactly the seven expected tools are
// advertised. Exits 0 on success, 1 otherwise. Never calls a tool (no queries).

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const EXPECTED = [
  "get_hacktricks_cheatsheet",
  "get_hacktricks_outline",
  "get_hacktricks_page",
  "get_hacktricks_section",
  "hacktricks_quick_lookup",
  "list_hacktricks_categories",
  "search_hacktricks",
];

async function main() {
  const entry = process.argv[2] ?? "dist/index.js";
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [entry],
    env: { ...process.env },
    stderr: "inherit",
  });
  const client = new Client({ name: "hacktricks-smoke", version: "0.0.0" });
  await client.connect(transport);
  const list = await client.listTools();
  await client.close();
  const names = list.tools.map((t) => t.name).sort();
  const ok = names.length === 7 && EXPECTED.every((n) => names.includes(n));
  process.stdout.write(`${JSON.stringify({ ok, tools: names })}\n`);
  process.exit(ok ? 0 : 1);
}

main().catch((error) => {
  process.stderr.write(`smoke failed: ${String(error)}\n`);
  process.exit(1);
});
