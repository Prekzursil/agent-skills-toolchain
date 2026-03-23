import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const serverPath = path.join(__dirname, '..', 'src', 'mcp-server.mjs');

test('promptbridge talk lane source parses cleanly', () => {
  const result = spawnSync(process.execPath, ['--check', serverPath], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.stdout || 'expected node --check to succeed');
});

test('promptbridge talk lane registers promptbridge and legacy agentify talk/session tools only', async () => {
  const src = await fs.readFile(serverPath, 'utf8');

  assert.ok(src.includes('registerToolWithAliases'), 'expected alias helper');
  assert.ok(src.includes("for (const prefix of ['promptbridge', 'agentify'])"), 'expected promptbridge + agentify aliases');
  assert.match(src, /registerToolWithAliases\(\s*'query'/, 'expected aliased query tool registration');
  assert.match(src, /registerToolWithAliases\(\s*'session_state'/, 'expected aliased session_state tool registration');
  assert.match(src, /registerToolWithAliases\(\s*'session_configure'/, 'expected aliased session_configure tool registration');
  assert.match(src, /registerToolWithAliases\(\s*'discuss'/, 'expected talk-only discuss registration');
  assert.match(src, /registerToolWithAliases\(\s*'curate'/, 'expected talk-only curate registration');
  assert.ok(src.includes("const DEFAULT_AUTOMATION_KEY = 'promptbridge-consult';"), 'expected dedicated automation session key');
  assert.ok(src.includes('function resolveAutomationTarget'), 'expected automation target helper');
  assert.ok(src.includes('function configureRequestedSession'), 'expected fail-closed session configuration helper');
  assert.ok(src.includes('PromptBridge will attempt session confirmation first'), 'expected query tool to describe fail-closed model hint handling');

  assert.doesNotMatch(src, /registerTool\(\s*'codex_consult'/, 'talk lane should not register codex tools');
  assert.doesNotMatch(src, /registerTool\(\s*'codex_brainstorm'/, 'talk lane should not register codex tools');
});
