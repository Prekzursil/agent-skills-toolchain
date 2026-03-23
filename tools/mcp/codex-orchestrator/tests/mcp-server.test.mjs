import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('codex orchestrator server registers the six codex multi-agent tools', async () => {
  const src = await fs.readFile(path.join(__dirname, '..', 'src', 'mcp-server.mjs'), 'utf8');

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

  assert.ok(src.includes('runCodexOrchestration'), 'expected shared orchestration backend');
  assert.ok(src.includes('promptbridgeKey'), 'expected PromptBridge curator override support');
});
