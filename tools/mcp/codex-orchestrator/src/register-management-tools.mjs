import { z } from 'zod';

import { withCodexAppServer } from './app-server-client.mjs';
import { defaultCodexHome } from './codex-orchestration.mjs';

async function callMethod({ workspaceDir, codexHome, method, params = undefined, timeoutMs = 30_000 }) {
  const env = { ...process.env, CODEX_HOME: codexHome };
  return await withCodexAppServer({
    workspaceDir,
    env,
    timeoutMs,
    fn: async ({ request }) => await request(100, method, params, timeoutMs)
  });
}

export function registerCodexManagementTools(server, { codexHome = defaultCodexHome() } = {}) {
  server.registerTool(
    'codex_account_read',
    {
      description: 'Read current Codex account/auth state via codex app-server.',
      inputSchema: {
        workspaceDir: z.string().optional().describe('Workspace directory for the app-server process.')
      }
    },
    async ({ workspaceDir }) => {
      const result = await callMethod({ workspaceDir: workspaceDir || process.cwd(), codexHome, method: 'account/read' });
      return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }], structuredContent: result };
    }
  );

  server.registerTool(
    'codex_model_list',
    {
      description: 'List currently available Codex models via codex app-server.',
      inputSchema: {
        workspaceDir: z.string().optional().describe('Workspace directory for the app-server process.')
      }
    },
    async ({ workspaceDir }) => {
      const result = await callMethod({ workspaceDir: workspaceDir || process.cwd(), codexHome, method: 'model/list' });
      return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }], structuredContent: result };
    }
  );

  server.registerTool(
    'codex_config_read',
    {
      description: 'Read resolved Codex config via codex app-server.',
      inputSchema: {
        workspaceDir: z.string().optional().describe('Workspace directory for the app-server process.'),
        includeLayers: z.boolean().optional().describe('Include layered config details.')
      }
    },
    async ({ workspaceDir, includeLayers }) => {
      const result = await callMethod({
        workspaceDir: workspaceDir || process.cwd(),
        codexHome,
        method: 'config/read',
        params: { cwd: workspaceDir || process.cwd(), includeLayers: includeLayers ?? true }
      });
      return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }], structuredContent: result };
    }
  );

  server.registerTool(
    'codex_feature_list',
    {
      description: 'List experimental Codex features via codex app-server.',
      inputSchema: {
        workspaceDir: z.string().optional().describe('Workspace directory for the app-server process.')
      }
    },
    async ({ workspaceDir }) => {
      const result = await callMethod({
        workspaceDir: workspaceDir || process.cwd(),
        codexHome,
        method: 'experimentalFeature/list'
      });
      return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }], structuredContent: result };
    }
  );

  server.registerTool(
    'codex_mcp_status',
    {
      description: 'List MCP server health/status from Codex app-server.',
      inputSchema: {
        workspaceDir: z.string().optional().describe('Workspace directory for the app-server process.'),
        limit: z.number().int().min(1).max(200).optional().describe('Maximum server entries to return.')
      }
    },
    async ({ workspaceDir, limit }) => {
      const result = await callMethod({
        workspaceDir: workspaceDir || process.cwd(),
        codexHome,
        method: 'mcpServerStatus/list',
        params: { limit: limit || 100 }
      });
      return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }], structuredContent: result };
    }
  );

  server.registerTool(
    'codex_thread_name_set',
    {
      description: 'Set the user-facing name/title for a Codex thread via app-server.',
      inputSchema: {
        workspaceDir: z.string().optional().describe('Workspace directory for the app-server process.'),
        threadId: z.string().min(1).describe('Thread identifier.'),
        name: z.string().min(1).describe('New thread title.')
      }
    },
    async ({ workspaceDir, threadId, name }) => {
      const result = await callMethod({
        workspaceDir: workspaceDir || process.cwd(),
        codexHome,
        method: 'thread/name/set',
        params: { threadId, name }
      });
      return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }], structuredContent: result };
    }
  );
}
