import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const registerManagementPath = path.join(__dirname, '..', 'src', 'register-management-tools.mjs');
const registerManagerPath = path.join(__dirname, '..', 'src', 'manager', 'register-tools.mjs');

test('codex orchestrator server registers codex, talk-lane, and manager tools on one managed MCP surface', async () => {
  const src = await fs.readFile(path.join(__dirname, '..', 'src', 'mcp-server.mjs'), 'utf8');
  const managementSrc = await fs.readFile(registerManagementPath, 'utf8');
  const managerSrc = await fs.readFile(registerManagerPath, 'utf8');

  for (const tool of [
    'codex_consult',
    'codex_brainstorm',
    'codex_review',
    'codex_discuss',
    'codex_coordinate',
    'codex_curate'
  ]) {
    assert.ok(src.includes(`server.registerTool(tool` ) === false, 'sanity');
    assert.ok(src.includes(`['${tool}',`) || src.includes(`\"${tool}\"`) || src.includes(`'${tool}'`), `expected ${tool} to be present in server source`);
  }

  for (const helper of [
    'registerPromptbridgeTalkTools',
    'registerCodexManagementTools',
    'registerManagerTools'
  ]) {
    assert.ok(src.includes(helper), `expected ${helper} to be wired into the managed server`);
  }

  for (const managementTool of [
    'codex_account_read',
    'codex_model_list',
    'codex_config_read',
    'codex_mcp_status',
    'codex_thread_name_set'
  ]) {
    assert.ok(managementSrc.includes(managementTool), `expected ${managementTool} to be represented in management registration source`);
  }

  for (const managerTool of [
    'manager_workspace_bind',
    'manager_thread_metadata_set',
    'manager_route_read',
    'manager_route_write',
    'manager_health_read'
  ]) {
    assert.ok(managerSrc.includes(managerTool), `expected ${managerTool} to be represented in manager registration source`);
  }

  assert.ok(src.includes('runCodexOrchestration'), 'expected shared orchestration backend');
  assert.ok(src.includes('promptbridgeKey'), 'expected PromptBridge curator override support');
});
