#!/usr/bin/env node
// Stdio bootstrap. Excluded from the unit coverage denominator (real transport +
// process exit); all behavior lives in the tested policy modules.

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { checkCorpusHealth } from "./corpus.js";
import { defaultToolDeps, realFs, realGit, resolveCorpusRoot } from "./defaults.js";
import { createServer } from "./server.js";

async function main(): Promise<void> {
  const root = resolveCorpusRoot(process.env, import.meta.url);
  const corpus = await checkCorpusHealth(root, realGit, realFs);
  const server = createServer({ corpus, ...defaultToolDeps() });
  await server.connect(new StdioServerTransport());
  const state = corpus.ok ? "ok" : `unavailable (${corpus.subcode})`;
  process.stderr.write(`hacktricks-mcp-hardened ready; corpus ${state}\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`fatal: ${String(error)}\n`);
  process.exitCode = 1;
});
