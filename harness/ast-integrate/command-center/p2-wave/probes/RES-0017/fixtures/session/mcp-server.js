#!/usr/bin/env node
// MCP server source. Unique marker: RES0017-MCP-SERVER-SOURCE-NOT-TURN0
// This file is inventory. Turn-0 occupancy injects tool schemas, not this
// implementation. A file-size census of the MCP tree would count these
// lines and overstate context occupancy.

const PADDING = `
server source padding 01. Do not inject.
server source padding 02. Do not inject.
server source padding 03. Do not inject.
server source padding 04. Do not inject.
server source padding 05. Do not inject.
server source padding 06. Do not inject.
server source padding 07. Do not inject.
server source padding 08. Do not inject.
server source padding 09. Do not inject.
server source padding 10. Do not inject.
server source padding 11. API_KEY must never be printed or injected.
server source padding 12. Occupancy is schemas, not process source.
server source padding 13. lazy-not-injected sibling of tool JSON.
server source padding 14. wc -c of this file is the rejected inference.
server source padding 15. tokens_cumulative is also the wrong numerator.
`;

function main() {
  // Intentionally unused in the measurement. If RES0017-MCP-SERVER-SOURCE-NOT-TURN0
  // appears in the concatenated turn-0 prompt, the injector is broken.
  process.stderr.write("fixture mcp server is not launched by RES-0017\n");
}

main();
