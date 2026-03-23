#!/usr/bin/env node
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

import { defaultCodexHome, loadOrchestrationConfig, runCodexOrchestration } from './codex-orchestration.mjs';
import { registerPromptbridgeTalkTools } from '../../../web/promptbridge-talk-lane/src/register-tools.mjs';
import { registerCodexManagementTools } from './register-management-tools.mjs';
import { registerManagerTools } from './manager/register-tools.mjs';

const server = new McpServer({ name: 'codex-orchestrator', version: '0.1.0' });
const codexHome = defaultCodexHome();

const consultationInputSchema = {
  prompt: z.string().min(1).describe('Task or decision to analyze.'),
  workspaceDir: z.string().optional().describe('Workspace directory passed to codex exec. Defaults to the current working directory.'),
  model: z.string().optional().describe('Optional Codex model override for this orchestration call.'),
  reasoningEffort: z.string().optional().describe('Optional reasoning effort override for this orchestration call.'),
  peerCount: z.number().int().min(1).max(4).optional().describe('Override the number of Codex peers used for multi-agent modes.'),
  useCurator: z.boolean().optional().describe('If true, allow the PromptBridge talk-only curator lane to synthesize the final answer.'),
  promptbridgeKey: z.string().optional().describe('Dedicated PromptBridge session key for talk-only curation.'),
  promptbridgeModel: z.string().optional().describe('Requested PromptBridge model hint for curator mode.'),
  promptbridgeReasoningEffort: z.string().optional().describe('Requested PromptBridge reasoning hint for curator mode.'),
  profile: z.string().optional().describe('Optional orchestration profile name for metadata only.')
};

function buildHandler(toolName) {
  return async ({ prompt, workspaceDir, profile, ...overrides }) => {
    const loaded = await loadOrchestrationConfig();
    const result = await runCodexOrchestration({
      toolName,
      prompt,
      config: loaded.config,
      overrides,
      workspaceDir: workspaceDir || process.cwd()
    });

    return {
      content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
      structuredContent: {
        ...result,
        metadata: {
          ...(result.metadata || {}),
          requestedProfile: profile || null,
          configPath: loaded.path,
          toolName
        }
      }
    };
  };
}

const toolDefs = [
  ['codex_consult', 'Run one expert Codex consultation pass.'],
  ['codex_brainstorm', 'Run two Codex idea generators and synthesize their options.'],
  ['codex_review', 'Run one Codex critic or reviewer pass.'],
  ['codex_discuss', 'Run two Codex peers that debate before a synthesis pass.'],
  ['codex_coordinate', 'Split roles across Codex peers and consolidate the result.'],
  ['codex_curate', 'Pick the best final option, optionally consulting the PromptBridge talk-only curator lane.']
];

for (const [name, description] of toolDefs) {
  server.registerTool(name, { description, inputSchema: consultationInputSchema }, buildHandler(name));
}

registerCodexManagementTools(server, { codexHome });
registerManagerTools(server, { codexHome });
registerPromptbridgeTalkTools(server);

function installShutdownHandlers() {
  let shuttingDown = false;
  const handle = (signal) => {
    if (shuttingDown) return;
    shuttingDown = true;
    console.error(`codex-orchestrator MCP shutting down on ${signal}`);
    process.exit(0);
  };
  process.on('SIGINT', () => handle('SIGINT'));
  process.on('SIGTERM', () => handle('SIGTERM'));
}

async function main() {
  installShutdownHandlers();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('codex-orchestrator MCP server running on stdio');
}

main().catch((error) => {
  console.error('codex-orchestrator MCP fatal:', error);
  process.exit(1);
});
