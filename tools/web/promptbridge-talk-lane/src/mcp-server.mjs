#!/usr/bin/env node
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';

import { defaultStateDir } from './state.mjs';
import { registerPromptbridgeTalkTools } from './register-tools.mjs';

const server = new McpServer({ name: 'promptbridge-desktop', version: '0.1.0-alpha.1' });
registerPromptbridgeTalkTools(server, { stateDir: defaultStateDir(), showTabs: process.argv.includes('--show-tabs') });

function installShutdownHandlers() {
  let shuttingDown = false;
  const handle = (signal) => {
    if (shuttingDown) return;
    shuttingDown = true;
    console.error(`promptbridge-desktop MCP shutting down on ${signal}`);
    process.exit(0);
  };
  process.on('SIGINT', () => handle('SIGINT'));
  process.on('SIGTERM', () => handle('SIGTERM'));
}

async function main() {
  installShutdownHandlers();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('promptbridge-desktop MCP server running on stdio');
}

main().catch((e) => {
  console.error('promptbridge-desktop MCP fatal:', e);
  process.exit(1);
});
