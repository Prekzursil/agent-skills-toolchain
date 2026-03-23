#!/usr/bin/env node
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

import { defaultStateDir } from './state.mjs';
import { ensureDesktopRunning, requestJson } from './mcp-lib.mjs';

const server = new McpServer({ name: 'promptbridge-desktop', version: '0.1.0-alpha.1' });
const stateDir = defaultStateDir();
const showTabs = process.argv.includes('--show-tabs');
const DEFAULT_AUTOMATION_KEY = 'promptbridge-consult';

function registerTool(name, def, handler) {
  server.registerTool(name, def, handler);
}

function registerToolWithAliases(nameBase, def, handler) {
  for (const prefix of ['promptbridge', 'agentify']) {
    registerTool(`${prefix}_${nameBase}`, def, handler);
  }
}

async function getConn() {
  return await ensureDesktopRunning({ stateDir, showTabs });
}

function isExpectedSessionError(error) {
  const code = error?.data?.body?.error || null;
  return code === 'model_hint_confirmation_required' || code === 'unsupported_session_vendor';
}

function resolveAutomationTarget({ tabId, key }) {
  if (tabId && key) return { tabId, key };
  if (tabId) return { tabId };
  if (key) return { key };
  return { key: DEFAULT_AUTOMATION_KEY };
}

function toSessionErrorBody(error) {
  return error?.data?.body || { error: 'internal_error' };
}

function sessionErrorResult(body) {
  return {
    content: [{ type: 'text', text: JSON.stringify(body, null, 2) }],
    structuredContent: body
  };
}

function targetSearchPath(basePath, target) {
  const search = new URLSearchParams();
  if (target.tabId) search.set('tabId', target.tabId);
  if (target.key) search.set('key', target.key);
  return search.size ? `${basePath}?${search.toString()}` : basePath;
}

async function configureRequestedSession({ conn, tabId, key, requestedModel }) {
  const target = resolveAutomationTarget({ tabId, key });
  if (!requestedModel) return { target, configured: null, errorBody: null };
  try {
    const configured = await requestJson({
      ...conn,
      method: 'POST',
      path: '/configure-session',
      body: {
        ...target,
        expectedVendorId: 'chatgpt',
        modelHint: requestedModel,
        confirmModelHintNotAuthoritative: true
      }
    });
    return { target, configured, errorBody: null };
  } catch (error) {
    if (!isExpectedSessionError(error)) throw error;
    return { target, configured: null, errorBody: toSessionErrorBody(error) };
  }
}

async function requestQuery({ conn, tabId, key, prompt, requestedModel = null, attachments = [], timeoutMs }) {
  const { target, configured, errorBody } = await configureRequestedSession({ conn, tabId, key, requestedModel });
  if (errorBody) return { target, configured, errorBody, data: null };
  try {
    const data = await requestJson({
      ...conn,
      method: 'POST',
      path: '/query',
      body: {
        ...target,
        prompt,
        modelHint: requestedModel,
        attachments,
        timeoutMs: timeoutMs || 10 * 60_000
      }
    });
    return { target, configured, errorBody: null, data };
  } catch (error) {
    if (!isExpectedSessionError(error)) throw error;
    return { target, configured, errorBody: toSessionErrorBody(error), data: null };
  }
}

registerToolWithAliases(
  'query',
  {
    description:
      'Send a prompt to the local Agentify Desktop session (ChatGPT web) and return the latest assistant response. If no tabId/key is supplied, PromptBridge uses the dedicated automation session key "promptbridge-consult" instead of the protected default tab. If a CAPTCHA/login challenge appears, the desktop window will ask for user intervention and resume automatically.',
    inputSchema: {
      model: z
        .string()
        .optional()
        .describe('Non-authoritative model hint. PromptBridge will attempt session confirmation first and return a structured error if the request cannot be confirmed.'),
      tabId: z.string().optional().describe('Tab/session id to use (for parallel jobs).'),
      key: z.string().optional().describe('Stable tab key (e.g., project name); creates a dedicated automation tab if missing.'),
      prompt: z.string().describe('Prompt to send to ChatGPT.'),
      attachments: z.array(z.string()).optional().describe('Local file paths to upload before sending the prompt.'),
      timeoutMs: z.number().optional().describe('Maximum time to wait for completion.')
    }
  },
  async ({ model, tabId, key, prompt, attachments, timeoutMs }) => {
    const conn = await getConn();
    const { target, configured, errorBody, data } = await requestQuery({
      conn,
      tabId,
      key,
      prompt,
      requestedModel: model || null,
      attachments: attachments || [],
      timeoutMs
    });
    if (errorBody) return sessionErrorResult(errorBody);
    const structuredContent = {
      tabId: data.tabId || target.tabId || null,
      key: target.key || key || null,
      text: data.result?.text || '',
      codeBlocks: data.result?.codeBlocks || [],
      meta: data.result?.meta || null,
      session: configured
    };
    return {
      content: [{ type: 'text', text: structuredContent.text }],
      structuredContent
    };
  }
);

registerToolWithAliases(
  'read_page',
  {
    description: 'Read text content from the active PromptBridge automation session or a targeted tab in the local desktop window.',
    inputSchema: {
      tabId: z.string().optional().describe('Tab/session id to use.'),
      key: z.string().optional().describe('Stable tab key; uses the dedicated automation session if omitted.'),
      maxChars: z.number().optional().describe('Maximum characters to return.')
    }
  },
  async ({ tabId, key, maxChars }) => {
    const conn = await getConn();
    const target = resolveAutomationTarget({ tabId, key });
    const data = await requestJson({
      ...conn,
      method: 'POST',
      path: '/read-page',
      body: { ...target, maxChars: maxChars || 200_000 }
    });
    return { content: [{ type: 'text', text: data.text || '' }], structuredContent: { ...data, ...target } };
  }
);

registerToolWithAliases(
  'navigate',
  {
    description: 'Navigate the PromptBridge desktop browser window to a URL for a targeted automation session.',
    inputSchema: {
      tabId: z.string().optional().describe('Tab/session id to use.'),
      key: z.string().optional().describe('Stable tab key; uses the dedicated automation session if omitted.'),
      url: z.string().describe('URL to navigate to.')
    }
  },
  async ({ tabId, key, url }) => {
    const conn = await getConn();
    const target = resolveAutomationTarget({ tabId, key });
    const data = await requestJson({ ...conn, method: 'POST', path: '/navigate', body: { ...target, url } });
    return { content: [{ type: 'text', text: data.url || 'ok' }], structuredContent: { ...data, ...target } };
  }
);

registerToolWithAliases(
  'ensure_ready',
  {
    description:
      'Wait until ChatGPT is ready for input (e.g., after login/CAPTCHA). If no tabId/key is supplied, PromptBridge uses the dedicated automation session key "promptbridge-consult". Triggers local user handoff if needed and resumes when the prompt textarea is visible.',
    inputSchema: {
      tabId: z.string().optional().describe('Tab/session id to use.'),
      key: z.string().optional().describe('Stable tab key; uses the dedicated automation session if omitted.'),
      timeoutMs: z.number().optional().describe('Maximum time to wait for readiness.')
    }
  },
  async ({ tabId, key, timeoutMs }) => {
    const conn = await getConn();
    const target = resolveAutomationTarget({ tabId, key });
    const data = await requestJson({
      ...conn,
      method: 'POST',
      path: '/ensure-ready',
      body: { ...target, timeoutMs: timeoutMs || 10 * 60_000 }
    });
    return { content: [{ type: 'text', text: JSON.stringify(data.state || {}, null, 2) }], structuredContent: { ...data, ...target } };
  }
);

registerToolWithAliases(
  'show',
  {
    description: 'Bring the PromptBridge desktop window to the front for a targeted session.',
    inputSchema: { tabId: z.string().optional(), key: z.string().optional() }
  },
  async ({ tabId, key }) => {
    const conn = await getConn();
    const target = resolveAutomationTarget({ tabId, key });
    await requestJson({ ...conn, method: 'POST', path: '/show', body: target });
    return { content: [{ type: 'text', text: 'ok' }], structuredContent: target };
  }
);

registerToolWithAliases(
  'hide',
  {
    description: 'Minimize the PromptBridge desktop window for a targeted session.',
    inputSchema: { tabId: z.string().optional(), key: z.string().optional() }
  },
  async ({ tabId, key }) => {
    const conn = await getConn();
    const target = resolveAutomationTarget({ tabId, key });
    await requestJson({ ...conn, method: 'POST', path: '/hide', body: target });
    return { content: [{ type: 'text', text: 'ok' }], structuredContent: target };
  }
);

registerToolWithAliases(
  'status',
  {
    description: 'Get current URL and blocked/ready status for the PromptBridge desktop window.',
    inputSchema: { tabId: z.string().optional(), key: z.string().optional().describe('Stable tab key for dedicated session targeting.') }
  },
  async ({ tabId, key }) => {
    const conn = await getConn();
    const target = resolveAutomationTarget({ tabId, key });
    const data = await requestJson({ ...conn, method: 'GET', path: targetSearchPath('/status', target) });
    return { content: [{ type: 'text', text: JSON.stringify(data, null, 2) }], structuredContent: { ...data, ...target } };
  }
);

registerToolWithAliases(
  'session_state',
  {
    description:
      'Inspect the machine-readable ChatGPT session state, capabilities, and non-authoritative model-hint configuration for a targeted session. If no tabId/key is supplied, PromptBridge inspects the dedicated automation session key "promptbridge-consult".',
    inputSchema: {
      tabId: z.string().optional().describe('Tab/session id to inspect.'),
      key: z.string().optional().describe('Stable tab key to inspect.')
    }
  },
  async ({ tabId, key }) => {
    const conn = await getConn();
    const target = resolveAutomationTarget({ tabId, key });
    const data = await requestJson({ ...conn, method: 'GET', path: targetSearchPath('/session-state', target) });
    return { content: [{ type: 'text', text: JSON.stringify(data, null, 2) }], structuredContent: { ...data, ...target } };
  }
);

registerToolWithAliases(
  'session_configure',
  {
    description:
      'Configure ChatGPT-only session expectations for a targeted session. If no tabId/key is supplied, PromptBridge configures the dedicated automation session key "promptbridge-consult". Model hints remain non-authoritative and require explicit confirmation.',
    inputSchema: {
      tabId: z.string().optional().describe('Tab/session id to configure.'),
      key: z.string().optional().describe('Stable tab key to configure.'),
      expectedVendorId: z.string().optional().describe('Expected vendor id. Only "chatgpt" is supported.'),
      modelHint: z.string().optional().describe('Non-authoritative model hint to associate with the session.'),
      confirmModelHintNotAuthoritative: z
        .boolean()
        .optional()
        .describe('Required to acknowledge that model hints do not switch the backend model.')
    }
  },
  async ({ tabId, key, expectedVendorId, modelHint, confirmModelHintNotAuthoritative }) => {
    const conn = await getConn();
    const target = resolveAutomationTarget({ tabId, key });
    try {
      const data = await requestJson({
        ...conn,
        method: 'POST',
        path: '/configure-session',
        body: {
          ...target,
          expectedVendorId,
          modelHint,
          confirmModelHintNotAuthoritative: !!confirmModelHintNotAuthoritative
        }
      });
      return { content: [{ type: 'text', text: JSON.stringify(data, null, 2) }], structuredContent: { ...data, ...target } };
    } catch (error) {
      if (!isExpectedSessionError(error)) throw error;
      return sessionErrorResult(toSessionErrorBody(error));
    }
  }
);

registerToolWithAliases(
  'image_gen',
  {
    description:
      'Generate images via ChatGPT web UI (best-effort): sends the prompt through the dedicated automation session unless a tabId/key is supplied, then downloads any images from the latest assistant message to a local folder and returns file paths.',
    inputSchema: {
      tabId: z.string().optional().describe('Tab/session id to use.'),
      key: z.string().optional().describe('Stable tab key; uses the dedicated automation session if omitted.'),
      prompt: z.string().describe('Prompt to send to ChatGPT for image generation.'),
      timeoutMs: z.number().optional().describe('Maximum time to wait for completion.'),
      maxImages: z.number().optional().describe('Maximum images to download.')
    }
  },
  async ({ tabId, key, prompt, timeoutMs, maxImages }) => {
    const conn = await getConn();
    const { target, errorBody, data: q } = await requestQuery({ conn, tabId, key, prompt, timeoutMs });
    if (errorBody) return sessionErrorResult(errorBody);
    const downloadTarget = q.tabId ? { tabId: q.tabId } : target;
    const d = await requestJson({
      ...conn,
      method: 'POST',
      path: '/download-images',
      body: { ...downloadTarget, maxImages: maxImages || 6 }
    });
    const structuredContent = { tabId: q.tabId || downloadTarget.tabId || null, key: downloadTarget.key || target.key || null, text: q.result?.text || '', files: d.files || [] };
    return {
      content: [{ type: 'text', text: JSON.stringify(structuredContent, null, 2) }],
      structuredContent
    };
  }
);

registerToolWithAliases(
  'download_images',
  {
    description:
      'Download images from the latest assistant message (best-effort). If no tabId/key is supplied, PromptBridge reads from the dedicated automation session key "promptbridge-consult". Useful if you generated images manually in the UI or via promptbridge_query.',
    inputSchema: {
      tabId: z.string().optional().describe('Tab/session id to use.'),
      key: z.string().optional().describe('Stable tab key; uses the dedicated automation session if omitted.'),
      maxImages: z.number().optional().describe('Maximum images to download.')
    }
  },
  async ({ tabId, key, maxImages }) => {
    const conn = await getConn();
    const target = resolveAutomationTarget({ tabId, key });
    const d = await requestJson({ ...conn, method: 'POST', path: '/download-images', body: { ...target, maxImages: maxImages || 6 } });
    const structuredContent = { tabId: d.tabId || target.tabId || null, key: target.key || null, files: d.files || [] };
    return {
      content: [{ type: 'text', text: JSON.stringify(structuredContent, null, 2) }],
      structuredContent
    };
  }
);

registerToolWithAliases(
  'tabs',
  { description: 'List current tabs/sessions (for parallel jobs).', inputSchema: {} },
  async () => {
    const conn = await getConn();
    const data = await requestJson({ ...conn, method: 'GET', path: '/tabs' });
    return { content: [{ type: 'text', text: JSON.stringify(data, null, 2) }], structuredContent: data };
  }
);

registerToolWithAliases(
  'tab_create',
  {
    description: 'Create (or ensure) a tab/session for a given key.',
    inputSchema: { key: z.string().optional(), name: z.string().optional(), show: z.boolean().optional().describe('Show the tab window immediately.') }
  },
  async ({ key, name, show }) => {
    const conn = await getConn();
    const data = await requestJson({
      ...conn,
      method: 'POST',
      path: '/tabs/create',
      body: { key, name, show: typeof show === 'boolean' ? show : undefined }
    });
    return { content: [{ type: 'text', text: data.tabId || '' }], structuredContent: data };
  }
);

registerToolWithAliases(
  'tab_close',
  { description: 'Close a tab/session by tabId.', inputSchema: { tabId: z.string().describe('Tab id to close.') } },
  async ({ tabId }) => {
    const conn = await getConn();
    const data = await requestJson({ ...conn, method: 'POST', path: '/tabs/close', body: { tabId } });
    return { content: [{ type: 'text', text: 'ok' }], structuredContent: data };
  }
);

registerToolWithAliases('shutdown', { description: 'Gracefully shut down the PromptBridge Desktop app.', inputSchema: {} }, async () => {
  const conn = await getConn();
  await requestJson({ ...conn, method: 'POST', path: '/shutdown', body: { scope: 'app' } });
  return { content: [{ type: 'text', text: 'ok' }] };
});

registerToolWithAliases(
  'rotate_token',
  { description: 'Rotate the local HTTP API bearer token (requires reconnect on subsequent calls).', inputSchema: {} },
  async () => {
    const conn = await getConn();
    await requestJson({ ...conn, method: 'POST', path: '/rotate-token' });
    return { content: [{ type: 'text', text: 'ok' }] };
  }
);

function buildStructuredTalkPrompt({ mode, prompt, candidates = [] }) {
  const candidateBlock = candidates.length
    ? `Candidates to synthesize:
${JSON.stringify(candidates, null, 2)}
`
    : '';
  return [
    `Mode: ${mode}.`,
    'Return exactly one JSON object with these keys and no markdown:',
    'problem, assumptions, options, recommended_option, risks, verification_plan, confidence',
    '',
    'Task:',
    prompt,
    candidateBlock,
    'Schema requirements:',
    '- problem: string',
    '- assumptions: array of strings',
    '- options: array of strings',
    '- recommended_option: string',
    '- risks: array of strings',
    '- verification_plan: array of strings',
    '- confidence: string'
  ].join('\n');
}

registerToolWithAliases(
  'discuss',
  {
    description:
      'Use the PromptBridge talk-only lane as a discussion partner. This sends a structured planning prompt through the dedicated automation session unless a tabId/key is supplied.',
    inputSchema: {
      tabId: z.string().optional().describe('Tab/session id to use.'),
      key: z.string().optional().describe('Stable tab key; uses the dedicated automation session if omitted.'),
      prompt: z.string().describe('Discussion prompt to send to ChatGPT.'),
      timeoutMs: z.number().optional().describe('Maximum time to wait for completion.'),
      requestedModel: z.string().optional().describe('Optional non-authoritative PromptBridge model hint.')
    }
  },
  async ({ tabId, key, prompt, timeoutMs, requestedModel }) => {
    const conn = await getConn();
    const { target, configured, errorBody, data } = await requestQuery({
      conn,
      tabId,
      key,
      prompt: buildStructuredTalkPrompt({ mode: 'promptbridge_discuss', prompt }),
      requestedModel: requestedModel || null,
      timeoutMs
    });
    if (errorBody) return sessionErrorResult(errorBody);
    return {
      content: [{ type: 'text', text: data.result?.text || '' }],
      structuredContent: {
        tabId: data.tabId || target.tabId || null,
        key: target.key || key || null,
        text: data.result?.text || '',
        meta: data.result?.meta || null,
        session: configured
      }
    };
  }
);

registerToolWithAliases(
  'curate',
  {
    description:
      'Use the PromptBridge talk-only lane as a final curator that compares supplied candidates and returns a structured recommendation.',
    inputSchema: {
      tabId: z.string().optional().describe('Tab/session id to use.'),
      key: z.string().optional().describe('Stable tab key; uses the dedicated automation session if omitted.'),
      prompt: z.string().describe('Decision prompt for the final curator pass.'),
      candidates: z.array(z.any()).optional().describe('Candidate structured outputs to compare.'),
      timeoutMs: z.number().optional().describe('Maximum time to wait for completion.'),
      requestedModel: z.string().optional().describe('Optional non-authoritative PromptBridge model hint.')
    }
  },
  async ({ tabId, key, prompt, candidates, timeoutMs, requestedModel }) => {
    const conn = await getConn();
    const { target, configured, errorBody, data } = await requestQuery({
      conn,
      tabId,
      key,
      prompt: buildStructuredTalkPrompt({ mode: 'promptbridge_curate', prompt, candidates: candidates || [] }),
      requestedModel: requestedModel || null,
      timeoutMs
    });
    if (errorBody) return sessionErrorResult(errorBody);
    return {
      content: [{ type: 'text', text: data.result?.text || '' }],
      structuredContent: {
        tabId: data.tabId || target.tabId || null,
        key: target.key || key || null,
        text: data.result?.text || '',
        meta: data.result?.meta || null,
        session: configured
      }
    };
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('promptbridge-desktop MCP server running on stdio');
}

main().catch((e) => {
  console.error('promptbridge-desktop MCP fatal:', e);
  process.exit(1);
});
