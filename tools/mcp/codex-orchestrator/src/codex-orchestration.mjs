import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import { ensureDesktopRunning, requestJson } from '../../../web/promptbridge-talk-lane/src/mcp-lib.mjs';
import { runCodexExec } from './orchestrator/codex.mjs';
import { defaultStateDir } from '../../../web/promptbridge-talk-lane/src/state.mjs';

export const REQUIRED_CONSULTATION_SCHEMA_KEYS = [
  'problem',
  'assumptions',
  'options',
  'recommended_option',
  'risks',
  'verification_plan',
  'confidence'
];

export function defaultCodexHome({ env = process.env, homeDir = os.homedir() } = {}) {
  const fromEnv = String(env.CODEX_HOME || '').trim();
  if (fromEnv) return fromEnv;
  const winHome = String(env.USERPROFILE || '').trim();
  return path.join(winHome || homeDir, '.codex');
}

export function defaultOrchestrationConfig({ codexHome = defaultCodexHome() } = {}) {
  return {
    codexHome,
    laneDefaults: {
      default_model: 'gpt-5.4',
      default_reasoning_effort: 'high',
      default_peer_count: 2,
      use_promptbridge_curator: false,
      promptbridge_default_key: 'promptbridge-curator'
    },
    profiles: {
      consult: { tool: 'codex_consult', mode: 'consult', peer_count: 1, role: 'expert', use_curator: false },
      brainstorm: { tool: 'codex_brainstorm', mode: 'brainstorm', peer_count: 2, role: 'idea_generator', use_curator: false },
      review: { tool: 'codex_review', mode: 'review', peer_count: 1, role: 'critic', use_curator: false },
      discuss: { tool: 'codex_discuss', mode: 'discuss', peer_count: 2, role: 'debater', use_curator: false },
      coordinate: { tool: 'codex_coordinate', mode: 'coordinate', peer_count: 2, role: 'coordinator', use_curator: false },
      curate: { tool: 'codex_curate', mode: 'curate', peer_count: 1, role: 'selector', use_curator: true }
    },
    skillMappings: {
      'codex-brainstorm': { tool: 'codex_brainstorm', profile: 'brainstorm' },
      'codex-review': { tool: 'codex_review', profile: 'review' },
      'codex-discuss': { tool: 'codex_discuss', profile: 'discuss' },
      'codex-coordinate': { tool: 'codex_coordinate', profile: 'coordinate' },
      'codex-curate': { tool: 'codex_curate', profile: 'curate' },
      'codex-audit': { tool: 'codex_review', profile: 'review' },
      'codex-triage': { tool: 'codex_consult', profile: 'consult' },
      'codex-fix': { tool: 'codex_coordinate', profile: 'coordinate' },
      'codex-governance': { tool: 'codex_curate', profile: 'curate' }
    }
  };
}

function encodeTomlValue(value) {
  if (typeof value === 'string') return JSON.stringify(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  return String(value);
}

export function renderOrchestrationConfig(config) {
  const lines = [
    '# PromptBridge orchestration config',
    '# Generated and managed by integrations/codex/bootstrap.mjs',
    '',
    '[lane_defaults]'
  ];

  for (const [key, value] of Object.entries(config.laneDefaults || {})) {
    lines.push(`${key} = ${encodeTomlValue(value)}`);
  }

  for (const [name, profile] of Object.entries(config.profiles || {})) {
    lines.push('', `[profiles.${name}]`);
    for (const [key, value] of Object.entries(profile)) lines.push(`${key} = ${encodeTomlValue(value)}`);
  }

  for (const [name, mapping] of Object.entries(config.skillMappings || {})) {
    lines.push('', `[skill_mappings.${name}]`);
    for (const [key, value] of Object.entries(mapping)) lines.push(`${key} = ${encodeTomlValue(value)}`);
  }

  return `${lines.join('\n')}\n`;
}

function parseTomlValue(raw) {
  const text = String(raw || '').trim();
  if (text === 'true') return true;
  if (text === 'false') return false;
  if (/^-?\d+$/.test(text)) return Number(text);
  if ((text.startsWith('"') && text.endsWith('"')) || (text.startsWith("'") && text.endsWith("'"))) {
    try {
      return JSON.parse(text.replace(/^'/, '"').replace(/'$/, '"'));
    } catch {
      return text.slice(1, -1);
    }
  }
  return text;
}

export function parseOrchestrationConfig(text) {
  const config = { laneDefaults: {}, profiles: {}, skillMappings: {} };
  let section = null;
  let currentName = null;
  for (const rawLine of String(text || '').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const sectionMatch = line.match(/^\[(.+)\]$/);
    if (sectionMatch) {
      const value = sectionMatch[1];
      if (value === 'lane_defaults') {
        section = 'laneDefaults';
        currentName = null;
      } else if (value.startsWith('profiles.')) {
        section = 'profiles';
        currentName = value.slice('profiles.'.length);
        config.profiles[currentName] = config.profiles[currentName] || {};
      } else if (value.startsWith('skill_mappings.')) {
        section = 'skillMappings';
        currentName = value.slice('skill_mappings.'.length);
        config.skillMappings[currentName] = config.skillMappings[currentName] || {};
      }
      continue;
    }
    const idx = line.indexOf('=');
    if (idx === -1 || !section) continue;
    const key = line.slice(0, idx).trim();
    const value = parseTomlValue(line.slice(idx + 1));
    if (section === 'laneDefaults') config.laneDefaults[key] = value;
    else if (currentName) config[section][currentName][key] = value;
  }
  return config;
}

export async function loadOrchestrationConfig({ filePath = null, codexHome = defaultCodexHome() } = {}) {
  const resolved = filePath || path.join(codexHome, 'promptbridge-orchestration.toml');
  try {
    const text = await fs.readFile(resolved, 'utf8');
    const parsed = parseOrchestrationConfig(text);
    return {
      path: resolved,
      config: {
        ...defaultOrchestrationConfig({ codexHome }),
        ...parsed,
        laneDefaults: { ...defaultOrchestrationConfig({ codexHome }).laneDefaults, ...(parsed.laneDefaults || {}) },
        profiles: { ...defaultOrchestrationConfig({ codexHome }).profiles, ...(parsed.profiles || {}) },
        skillMappings: { ...defaultOrchestrationConfig({ codexHome }).skillMappings, ...(parsed.skillMappings || {}) }
      }
    };
  } catch {
    return { path: resolved, config: defaultOrchestrationConfig({ codexHome }) };
  }
}

function findProfileForTool(toolName, config) {
  for (const [profileName, profile] of Object.entries(config.profiles || {})) {
    if (profile.tool === toolName) return { profileName, profile };
  }
  throw new Error(`unknown_orchestration_tool:${toolName}`);
}

export function resolveOrchestrationRequest({ toolName, config, overrides = {} }) {
  const { profileName, profile } = findProfileForTool(toolName, config);
  const laneDefaults = config.laneDefaults || {};
  return {
    profileName,
    toolName,
    mode: profile.mode || toolName,
    role: profile.role || 'expert',
    model: overrides.model || profile.model || laneDefaults.default_model || 'gpt-5.4',
    reasoningEffort:
      overrides.reasoningEffort || overrides.reasoning_effort || profile.reasoning_effort || laneDefaults.default_reasoning_effort || 'high',
    peerCount: Number(overrides.peerCount ?? overrides.peer_count ?? profile.peer_count ?? laneDefaults.default_peer_count ?? 1),
    useCurator: Boolean(overrides.useCurator ?? overrides.use_curator ?? profile.use_curator ?? laneDefaults.use_promptbridge_curator ?? false),
    promptbridgeKey: String(overrides.promptbridgeKey || profile.promptbridge_key || laneDefaults.promptbridge_default_key || 'promptbridge-curator')
  };
}

function parseAgentJsonResult(stdout) {
  const lines = String(stdout || '').split('\n').map((line) => line.trim()).filter(Boolean);
  for (let idx = lines.length - 1; idx >= 0; idx -= 1) {
    try {
      const outer = JSON.parse(lines[idx]);
      const text = outer?.item?.type === 'agent_message' ? outer.item.text : null;
      if (!text) continue;
      return JSON.parse(text);
    } catch {}
  }
  return null;
}

function normalizeConsultationResult(result, { fallbackMode }) {
  if (!result || typeof result !== 'object') throw new Error('invalid_consultation_result');
  const normalized = {
    problem: typeof result.problem === 'string' ? result.problem : '',
    assumptions: Array.isArray(result.assumptions) ? result.assumptions : [],
    options: Array.isArray(result.options) ? result.options : [],
    recommended_option: typeof result.recommended_option === 'string' ? result.recommended_option : '',
    risks: Array.isArray(result.risks) ? result.risks : [],
    verification_plan: Array.isArray(result.verification_plan) ? result.verification_plan : [],
    confidence: typeof result.confidence === 'string' ? result.confidence : 'unknown'
  };
  const missing = REQUIRED_CONSULTATION_SCHEMA_KEYS.filter((key) => {
    const value = normalized[key];
    return Array.isArray(value) ? value.length === 0 : !value;
  });
  if (missing.length) throw new Error(`${fallbackMode || 'consultation'}_missing_schema:${missing.join(',')}`);
  return normalized;
}

function buildStructuredPrompt({ mode, prompt, role, participantIndex = null, peerCount = 1, candidates = [] }) {
  const roleLine = participantIndex === null
    ? `Role: ${role}.`
    : `Role: ${role}. You are participant ${participantIndex + 1} of ${peerCount}.`;
  const candidatesBlock = candidates.length
    ? `\nCandidates to synthesize:\n${JSON.stringify(candidates, null, 2)}\n`
    : '';
  return [
    `Mode: ${mode}.`,
    roleLine,
    'Return exactly one JSON object with these keys and no markdown:',
    REQUIRED_CONSULTATION_SCHEMA_KEYS.join(', '),
    '',
    'Task:',
    prompt,
    candidatesBlock,
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

async function defaultPromptbridgeCurate({ prompt, candidates, key = 'promptbridge-curator', timeoutMs = 8 * 60_000, stateDir = defaultStateDir() }) {
  const conn = await ensureDesktopRunning({ stateDir });
  const requestPrompt = buildStructuredPrompt({ mode: 'promptbridge_curate', prompt, role: 'curator', candidates });
  const data = await requestJson({
    ...conn,
    method: 'POST',
    path: '/query',
    body: { key, prompt: requestPrompt, attachments: [], timeoutMs }
  });
  const text = String(data?.result?.text || '').trim();
  let parsed = null;
  try {
    parsed = JSON.parse(text);
  } catch {
    const match = text.match(/\{[\s\S]*\}$/);
    if (match) parsed = JSON.parse(match[0]);
  }
  return normalizeConsultationResult(parsed, { fallbackMode: 'promptbridge_curate' });
}

function configOverrideArgs(reasoningEffort) {
  const overrides = [];
  if (reasoningEffort) overrides.push(`model_reasoning_effort=${reasoningEffort}`);
  return overrides;
}

export async function runCodexOrchestration({
  toolName,
  prompt,
  config,
  overrides = {},
  workspaceDir,
  runCodexExecImpl = runCodexExec,
  promptbridgeCurateImpl = defaultPromptbridgeCurate
} = {}) {
  const resolved = resolveOrchestrationRequest({ toolName, config, overrides });
  const participants = [];
  const candidateResults = [];
  const peerCount = Math.max(1, Number(resolved.peerCount || 1));

  const participantCalls = toolName === 'codex_review' || toolName === 'codex_consult' || toolName === 'codex_curate' ? 1 : peerCount;
  for (let idx = 0; idx < participantCalls; idx += 1) {
    const participantPrompt = buildStructuredPrompt({
      mode: resolved.mode,
      prompt,
      role: resolved.role,
      participantIndex: participantCalls === 1 ? null : idx,
      peerCount: participantCalls
    });
    const execResult = await runCodexExecImpl({
      workspaceDir,
      prompt: participantPrompt,
      ephemeral: true,
      model: resolved.model,
      configOverrides: configOverrideArgs(resolved.reasoningEffort)
    });
    const parsed = parseAgentJsonResult(execResult.stdout);
    const normalized = normalizeConsultationResult(parsed, { fallbackMode: toolName });
    candidateResults.push(normalized);
    participants.push({ index: idx, role: resolved.role, model: resolved.model, reasoningEffort: resolved.reasoningEffort });
  }

  let synthesis = candidateResults[0];
  if (candidateResults.length > 1 || toolName === 'codex_coordinate' || toolName === 'codex_discuss' || toolName === 'codex_brainstorm') {
    const synthesisPrompt = buildStructuredPrompt({
      mode: `${resolved.mode}_synthesis`,
      prompt,
      role: 'synthesizer',
      candidates: candidateResults
    });
    const execResult = await runCodexExecImpl({
      workspaceDir,
      prompt: synthesisPrompt,
      ephemeral: true,
      model: resolved.model,
      configOverrides: configOverrideArgs(resolved.reasoningEffort)
    });
    const parsed = parseAgentJsonResult(execResult.stdout);
    synthesis = normalizeConsultationResult(parsed, { fallbackMode: `${toolName}_synthesis` });
  }

  let curatorUsed = false;
  let finalResult = synthesis;
  if (resolved.useCurator) {
    finalResult = await promptbridgeCurateImpl({
      prompt,
      candidates: candidateResults,
      key: resolved.promptbridgeKey,
      requestedModel: overrides.promptbridgeModel || null,
      reasoningEffort: overrides.promptbridgeReasoningEffort || null
    });
    curatorUsed = true;
  }

  return {
    ...finalResult,
    metadata: {
      mode: toolName,
      profile: resolved.profileName,
      participants,
      peerCount,
      curatorUsed,
      model: resolved.model,
      reasoningEffort: resolved.reasoningEffort
    }
  };
}
