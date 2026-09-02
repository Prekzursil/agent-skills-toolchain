#!/usr/bin/env node
// Optional offline-invoked, online citation verifier CLI (NOT an eighth MCP
// tool). Reads a locally constructed provenance JSON receipt from a file path
// argument or stdin and prints a verification verdict. Excluded from the unit
// coverage denominator (process/argv/network boundary); the verdict logic lives
// in the tested verify.ts module.

import { readFileSync } from "node:fs";
import { realVerifyDeps } from "./defaults.js";
import { type CitationInput, verifyCitation } from "./verify.js";

async function main(): Promise<void> {
  const arg = process.argv[2];
  const raw = arg === undefined ? readFileSync(0, "utf8") : readFileSync(arg, "utf8");
  const parsed = JSON.parse(raw) as Record<string, unknown>;
  const canonical = parsed["canonical_url"];
  const title = parsed["title"];
  const heading = parsed["heading"];
  const input: CitationInput = {
    canonical_url: typeof canonical === "string" ? canonical : "",
    title: typeof title === "string" ? title : null,
    heading: typeof heading === "string" ? heading : null,
  };
  const result = await verifyCitation(input, realVerifyDeps());
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`fatal: ${String(error)}\n`);
  process.exitCode = 1;
});
