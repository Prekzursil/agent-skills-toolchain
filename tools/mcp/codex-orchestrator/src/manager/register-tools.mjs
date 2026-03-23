import { z } from 'zod';

import {
  appendHealthEvent,
  bindWorkspace,
  readHealthEvents,
  setThreadMetadata,
  writeRoute,
  readRoute
} from './store.mjs';

function ensureJsonSerializable(value, label) {
  try {
    JSON.stringify(value ?? null);
  } catch (error) {
    throw new Error(`${label}_must_be_json_serializable:${error?.message || String(error)}`);
  }
}

export function registerManagerTools(server, { codexHome }) {
  server.registerTool(
    'manager_workspace_bind',
    {
      description: 'Bind a workspace path to manager-owned metadata such as an alias.',
      inputSchema: {
        workspacePath: z.string().min(1).describe('Absolute workspace path.'),
        alias: z.string().optional().describe('Optional friendly alias for the workspace.')
      }
    },
    async ({ workspacePath, alias }) => {
      const workspace = await bindWorkspace({ codexHome, workspacePath, alias: alias || null });
      return {
        content: [{ type: 'text', text: JSON.stringify(workspace, null, 2) }],
        structuredContent: workspace
      };
    }
  );

  server.registerTool(
    'manager_thread_metadata_set',
    {
      description: 'Store manager-owned thread metadata such as workspace binding, label, tags, and pin state.',
      inputSchema: {
        threadId: z.string().min(1).describe('Codex thread identifier.'),
        workspacePath: z.string().optional().describe('Workspace path associated with the thread.'),
        label: z.string().optional().describe('Optional manager-side label.'),
        tags: z.array(z.string()).optional().describe('Tags to attach to the thread.'),
        pinned: z.boolean().optional().describe('Pinned state.')
      }
    },
    async ({ threadId, workspacePath, label, tags, pinned }) => {
      const metadata = await setThreadMetadata({
        codexHome,
        threadId,
        workspacePath: workspacePath || null,
        label: label || null,
        tags: tags || [],
        pinned
      });
      return {
        content: [{ type: 'text', text: JSON.stringify(metadata, null, 2) }],
        structuredContent: metadata
      };
    }
  );

  server.registerTool(
    'manager_route_read',
    {
      description: 'Read a manager routing policy or session mapping entry.',
      inputSchema: {
        routeKey: z.string().min(1).describe('Route key to read.')
      }
    },
    async ({ routeKey }) => {
      const route = await (async () => {
        const { ensureManagerDb } = await import('./store.mjs');
        const db = await ensureManagerDb({ codexHome });
        try {
          return readRoute({ db, routeKey });
        } finally {
          db.close();
        }
      })();
      return {
        content: [{ type: 'text', text: JSON.stringify(route, null, 2) }],
        structuredContent: route
      };
    }
  );

  server.registerTool(
    'manager_route_write',
    {
      description: 'Write a manager routing policy or session mapping entry.',
      inputSchema: {
        routeKey: z.string().min(1).describe('Route key to write.'),
        value: z.any().describe('Arbitrary structured value to store.')
      }
    },
    async ({ routeKey, value }) => {
      ensureJsonSerializable(value, 'route_value');
      const route = await writeRoute({ codexHome, routeKey, value });
      return {
        content: [{ type: 'text', text: JSON.stringify(route, null, 2) }],
        structuredContent: route
      };
    }
  );

  server.registerTool(
    'manager_health_read',
    {
      description: 'Read recent manager health events and cleanup diagnostics.',
      inputSchema: {
        limit: z.number().int().min(1).max(100).optional().describe('Maximum number of events to return.')
      }
    },
    async ({ limit }) => {
      const events = await readHealthEvents({ codexHome, limit: limit || 25 });
      return {
        content: [{ type: 'text', text: JSON.stringify(events, null, 2) }],
        structuredContent: { events }
      };
    }
  );

  server.registerTool(
    'manager_health_record',
    {
      description: 'Record a manager-owned health event for cleanup, routing, or session issues.',
      inputSchema: {
        source: z.string().min(1).describe('Subsystem that produced the event.'),
        severity: z.enum(['info', 'warning', 'error']).describe('Severity level.'),
        message: z.string().min(1).describe('Short event message.'),
        details: z.any().optional().describe('Optional structured details.')
      }
    },
    async ({ source, severity, message, details }) => {
      ensureJsonSerializable(details, 'health_details');
      await appendHealthEvent({ codexHome, source, severity, message, details: details ?? null });
      return {
        content: [{ type: 'text', text: 'ok' }],
        structuredContent: { ok: true }
      };
    }
  );
}
