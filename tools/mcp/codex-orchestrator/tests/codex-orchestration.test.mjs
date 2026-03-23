import test from 'node:test';
import assert from 'node:assert/strict';

import {
  defaultOrchestrationConfig,
  renderOrchestrationConfig,
  parseOrchestrationConfig,
  resolveOrchestrationRequest,
  runCodexOrchestration,
  REQUIRED_CONSULTATION_SCHEMA_KEYS
} from '../src/codex-orchestration.mjs';

function codexJson(result) {
  return {
    ok: true,
    stdout: JSON.stringify({ item: { type: 'agent_message', text: JSON.stringify(result) } }),
    stderr: '',
    exit: { code: 0, signal: null },
    sessionId: null
  };
}

test('codex orchestration: render and parse preserve default profiles and skill mappings', () => {
  const cfg = defaultOrchestrationConfig({ codexHome: 'C:/Users/Test/.codex' });
  const parsed = parseOrchestrationConfig(renderOrchestrationConfig(cfg));

  assert.equal(parsed.laneDefaults.default_model, 'gpt-5.4');
  assert.equal(parsed.profiles.consult.tool, 'codex_consult');
  assert.equal(parsed.profiles.brainstorm.peer_count, 2);
  assert.equal(parsed.skillMappings['codex-brainstorm'].tool, 'codex_brainstorm');
});

test('codex orchestration: request overrides win over profile defaults', () => {
  const cfg = defaultOrchestrationConfig({ codexHome: 'C:/Users/Test/.codex' });
  const resolved = resolveOrchestrationRequest({
    toolName: 'codex_brainstorm',
    config: cfg,
    overrides: { model: 'gpt-5.4', reasoningEffort: 'xhigh', peerCount: 3, useCurator: true }
  });

  assert.equal(resolved.model, 'gpt-5.4');
  assert.equal(resolved.reasoningEffort, 'xhigh');
  assert.equal(resolved.peerCount, 3);
  assert.equal(resolved.useCurator, true);
});

test('codex orchestration: discuss mode uses two codex participants, synthesis, and optional talk-only curator', async () => {
  const cfg = defaultOrchestrationConfig({ codexHome: 'C:/Users/Test/.codex' });
  const calls = [];
  const result = await runCodexOrchestration({
    toolName: 'codex_discuss',
    prompt: 'Design the best review loop.',
    config: cfg,
    overrides: { useCurator: true },
    workspaceDir: 'C:/work/repo',
    runCodexExecImpl: async ({ prompt, model, configOverrides }) => {
      calls.push({ kind: 'codex', prompt, model, configOverrides });
      return codexJson({
        problem: 'Design the best review loop.',
        assumptions: ['single repo'],
        options: ['A', 'B'],
        recommended_option: 'A',
        risks: ['latency'],
        verification_plan: ['tests'],
        confidence: 'medium'
      });
    },
    promptbridgeCurateImpl: async ({ prompt, candidates }) => {
      calls.push({ kind: 'promptbridge', prompt, candidates });
      return {
        problem: 'Design the best review loop.',
        assumptions: ['single repo'],
        options: ['A', 'B'],
        recommended_option: 'A',
        risks: ['latency'],
        verification_plan: ['tests'],
        confidence: 'high',
        metadata: { curator: 'promptbridge' }
      };
    }
  });

  assert.equal(calls.filter((entry) => entry.kind === 'codex').length, 3);
  assert.equal(calls.filter((entry) => entry.kind === 'promptbridge').length, 1);
  for (const key of REQUIRED_CONSULTATION_SCHEMA_KEYS) assert.ok(Object.hasOwn(result, key));
  assert.equal(result.metadata.mode, 'codex_discuss');
  assert.equal(result.metadata.curatorUsed, true);
  assert.equal(result.metadata.participants.length, 2);
});
