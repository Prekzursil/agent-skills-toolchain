import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

import { ensureDesktopRunning, requestJson } from '../../../web/promptbridge-talk-lane/src/mcp-lib.mjs';
import { runCodexExec } from './orchestrator/codex.mjs';
import { defaultStateDir } from '../../../web/promptbridge-talk-lane/src/state.mjs';
import { ensureManagerDb, writeRoute, appendHealthEvent } from './manager/store.mjs';

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
      consult: {
        tool: 'codex_consult',
        mode: 'consult',
        peer_count: 1,
        role: 'expert',
        use_curator: false,
        promptbridge_key: 'promptbridge-consult'
      },
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
    promptbridgeKey: String(overrides.promptbridgeKey || profile.promptbridge_key || laneDefaults.promptbridge_default_key || 'promptbridge-curator'),
    sessionReuse: overrides.sessionReuse ?? overrides.session_reuse ?? profile.session_reuse ?? false,
    enableExtendedThinking: overrides.enableExtendedThinking ?? profile.enable_extended_thinking ?? false,
    enableWebSearch: overrides.enableWebSearch ?? profile.enable_web_search ?? false,
    timeoutMs: Number(overrides.timeoutMs ?? profile.timeout_ms ?? laneDefaults.default_timeout_ms ?? 30 * 60_000),
    queryTimeoutMs: Number(overrides.queryTimeoutMs ?? profile.query_timeout_ms ?? laneDefaults.default_query_timeout_ms ?? 8 * 60_000)
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

function consultationScalar(value, preferredKeys = ['summary', 'id', 'title', 'name', 'reason', 'description']) {
  if (typeof value === 'string') return value.trim();
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (value && typeof value === 'object') {
    for (const key of preferredKeys) {
      const candidate = value[key];
      if (typeof candidate === 'string' && candidate.trim()) return candidate.trim();
      if (typeof candidate === 'number' || typeof candidate === 'boolean') return String(candidate);
    }
    try {
      return JSON.stringify(value);
    } catch {}
  }
  return '';
}

function consultationList(value, preferredKeys) {
  if (!Array.isArray(value)) return [];
  return value.map((entry) => consultationScalar(entry, preferredKeys)).filter(Boolean);
}

function normalizeConsultationResult(result, { fallbackMode }) {
  if (!result || typeof result !== 'object') throw new Error(`invalid_consultation_result:${fallbackMode || 'consultation'}`);
  const normalized = {
    problem: consultationScalar(result.problem, ['problem', 'summary', 'title', 'name', 'reason', 'description']),
    assumptions: consultationList(result.assumptions, ['summary', 'title', 'name', 'reason', 'description', 'id']),
    options: consultationList(result.options, ['summary', 'title', 'name', 'id', 'reason', 'description']),
    recommended_option: consultationScalar(result.recommended_option, ['id', 'summary', 'title', 'name', 'reason', 'description']),
    risks: consultationList(result.risks, ['summary', 'title', 'name', 'reason', 'description', 'id']),
    verification_plan: consultationList(result.verification_plan, ['summary', 'title', 'name', 'reason', 'description', 'id']),
    confidence: consultationScalar(result.confidence, ['summary', 'label', 'name', 'id', 'reason', 'description']) || 'unknown'
  };
  const missing = REQUIRED_CONSULTATION_SCHEMA_KEYS.filter((key) => {
    const value = normalized[key];
    return Array.isArray(value) ? value.length === 0 : !value;
  });
  if (missing.length) throw new Error(`${fallbackMode || 'consultation'}_missing_schema:${missing.join(',')}`);
  return normalized;
}

function buildStructuredPrompt({ mode, prompt, role, participantIndex = null, peerCount = 1, candidates = [], reasoningEffort = null }) {
  const roleLine = participantIndex === null
    ? `Role: ${role}.`
    : `Role: ${role}. You are participant ${participantIndex + 1} of ${peerCount}.`;
  const reasoningLine = reasoningEffort ? `Reasoning effort requested: ${reasoningEffort}.` : null;
  const candidatesBlock = candidates.length
    ? `\nCandidates to synthesize:\n${JSON.stringify(candidates, null, 2)}\n`
    : '';
  return [
    `Mode: ${mode}.`,
    roleLine,
    reasoningLine,
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
  ].filter(Boolean).join('\n');
}

function parseConsultationJsonText(text, fallbackMode) {
  const normalized = String(text || '').trim();
  if (!normalized) throw new Error(`invalid_consultation_result:${fallbackMode || 'consultation'}`);

  try {
    return normalizeConsultationResult(JSON.parse(normalized), { fallbackMode });
  } catch {}

  const match = normalized.match(/\{[\s\S]*\}$/);
  if (!match) throw new Error(`invalid_consultation_result:${fallbackMode || 'consultation'}`);

  return normalizeConsultationResult(JSON.parse(match[0]), { fallbackMode });
}

async function configurePromptbridgeSession({ conn, key, requestedModel = null }) {
  if (!requestedModel) return null;
  return await requestJson({
    ...conn,
    method: 'POST',
    path: '/configure-session',
    body: {
      key,
      expectedVendorId: 'chatgpt',
      modelHint: requestedModel,
      confirmModelHintNotAuthoritative: true
    }
  });
}

async function defaultPromptbridgeConsult({
  prompt,
  key = 'promptbridge-consult',
  timeoutMs = 480_000,
  queryTimeoutMs = 480_000,
  stateDir = defaultStateDir(),
  requestedModel = null,
  reasoningEffort = null,
  enableExtendedThinking = false,
  enableWebSearch = false
}) {
  const conn = await ensureDesktopRunning({ stateDir, timeoutMs: 90_000 });
  await requestJson({
    ...conn,
    method: 'POST',
    path: '/ensure-ready',
    body: {
      key,
      timeoutMs: 90_000
    }
  });
  await configurePromptbridgeSession({ conn, key, requestedModel });
  const requestPrompt = buildStructuredPrompt({
    mode: 'promptbridge_consult',
    prompt,
    role: 'expert',
    reasoningEffort
  });
  const data = await requestJson({
    ...conn,
    method: 'POST',
    path: '/query',
    body: {
      key,
      prompt: requestPrompt,
      ...(requestedModel ? { modelHint: requestedModel } : {}),
      ...(enableExtendedThinking ? { enableExtendedThinking: true } : {}),
      ...(enableWebSearch ? { enableWebSearch: true } : {}),
      timeoutMs: queryTimeoutMs
    }
  });
  return parseConsultationJsonText(data?.result?.text || '', 'promptbridge_consult');
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
  return parseConsultationJsonText(data?.result?.text || '', 'promptbridge_curate');
}

function laneAFallbackFrom(baseResult, error) {
  const reason = error?.message || String(error);
  return {
    ...baseResult,
    fallback_to_lane_a: true,
    risks: [...new Set([...(baseResult?.risks || []), `PromptBridge lane unavailable: ${reason}`])],
    verification_plan: [
      ...(baseResult?.verification_plan || []),
      'If PromptBridge consultation is required, start the desktop lane manually and rerun the request.'
    ]
  };
}

function configOverrideArgs(reasoningEffort) {
  const overrides = [];
  if (reasoningEffort) overrides.push(`model_reasoning_effort=${reasoningEffort}`);
  return overrides;
}

function trimForError(value) {
  return String(value || '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 240);
}

function deriveSessionKey(workspaceDir) {
  if (!workspaceDir) return 'promptbridge-consult';
  const base = path.basename(path.resolve(workspaceDir));
  return `pb-${base.replace(/[^a-zA-Z0-9_-]/g, '_')}`;
}

async function lookupExistingSession({ codexHome, workspaceDir }) {
  try {
    const db = await ensureManagerDb({ codexHome });
    try {
      const routeKey = `session:${path.resolve(workspaceDir || '.')}`;
      const row = db.prepare(`SELECT route_key, value_json, updated_at FROM routes WHERE route_key = ?`).get(routeKey);
      if (!row) return null;
      const value = JSON.parse(row.value_json);
      if (!value?.sessionId) return null;
      const ageMs = Date.now() - new Date(row.updated_at).getTime();
      if (ageMs > 24 * 60 * 60 * 1000) return null;
      return value;
    } finally {
      db.close();
    }
  } catch {
    return null;
  }
}

async function persistSession({ codexHome, workspaceDir, sessionId, toolName }) {
  try {
    await writeRoute({
      codexHome,
      routeKey: `session:${path.resolve(workspaceDir || '.')}`,
      value: { sessionId, toolName, timestamp: Date.now() }
    });
  } catch {}
}

async function recordHealthEvent({ codexHome, source, severity, message, details }) {
  try {
    await appendHealthEvent({ codexHome, source, severity, message, details });
  } catch {}
}

export async function runCodexOrchestration({
  toolName,
  prompt,
  config,
  overrides = {},
  workspaceDir,
  runCodexExecImpl = runCodexExec,
  promptbridgeConsultImpl = defaultPromptbridgeConsult,
  promptbridgeCurateImpl = defaultPromptbridgeCurate
} = {}) {
  const resolved = resolveOrchestrationRequest({ toolName, config, overrides });
  const codexHome = config?.codexHome || defaultCodexHome();
  const participants = [];
  const candidateResults = [];
  const peerCount = Math.max(1, Number(resolved.peerCount || 1));

  if (toolName === 'codex_consult') {
    const sessionKey = deriveSessionKey(workspaceDir);
    const sessionReuse = resolved.sessionReuse !== false;

    try {
      const promptbridgeResult = await promptbridgeConsultImpl({
        prompt,
        key: sessionKey,
        timeoutMs: resolved.timeoutMs,
        queryTimeoutMs: resolved.queryTimeoutMs,
        requestedModel: overrides.promptbridgeModel || resolved.model || null,
        reasoningEffort: overrides.promptbridgeReasoningEffort || resolved.reasoningEffort,
        enableExtendedThinking: resolved.enableExtendedThinking,
        enableWebSearch: resolved.enableWebSearch
      });
      participants.push({
        index: 0,
        role: resolved.role,
        lane: 'promptbridge',
        model: overrides.promptbridgeModel || resolved.model || null,
        reasoningEffort: overrides.promptbridgeReasoningEffort || resolved.reasoningEffort,
        sessionKey
      });
      return {
        ...promptbridgeResult,
        metadata: {
          mode: toolName,
          profile: resolved.profileName,
          participants,
          peerCount: 1,
          curatorUsed: false,
          model: resolved.model,
          reasoningEffort: resolved.reasoningEffort,
          sessionKey
        }
      };
    } catch (promptbridgeError) {
      await recordHealthEvent({
        codexHome,
        source: 'codex_consult',
        severity: 'warning',
        message: `PromptBridge fallback to Lane A: ${promptbridgeError.message}`,
        details: { toolName, workspaceDir, sessionKey }
      });

      const existing = sessionReuse ? await lookupExistingSession({ codexHome, workspaceDir }) : null;
      const useEphemeral = !existing?.sessionId;

      const participantPrompt = buildStructuredPrompt({
        mode: resolved.mode,
        prompt,
        role: resolved.role,
        reasoningEffort: resolved.reasoningEffort
      });
      const execResult = await runCodexExecImpl({
        workspaceDir,
        prompt: participantPrompt,
        ephemeral: useEphemeral,
        sessionId: existing?.sessionId || null,
        skipGitRepoCheck: true,
        model: resolved.model,
        configOverrides: configOverrideArgs(resolved.reasoningEffort),
        timeoutMs: resolved.timeoutMs
      });
      if (!execResult?.ok) {
        throw new Error(`codex_exec_failed:${trimForError(execResult?.stderr || execResult?.stdout || execResult?.abortedReason || execResult?.exit?.code || 'unknown')}`);
      }

      if (execResult.sessionId && sessionReuse) {
        await persistSession({ codexHome, workspaceDir, sessionId: execResult.sessionId, toolName });
      }

      const parsed = parseAgentJsonResult(execResult.stdout);
      if (!parsed) {
        throw new Error(`invalid_consultation_result:${trimForError(execResult?.stderr || execResult?.stdout || 'missing_agent_message')}`);
      }
      const normalized = normalizeConsultationResult(parsed, { fallbackMode: toolName });
      participants.push({
        index: 0, role: resolved.role, lane: 'codex', model: resolved.model,
        reasoningEffort: resolved.reasoningEffort,
        sessionId: execResult.sessionId || null,
        resumed: !useEphemeral
      });
      return {
        ...laneAFallbackFrom(normalized, promptbridgeError),
        metadata: {
          mode: toolName,
          profile: resolved.profileName,
          participants,
          peerCount: 1,
          curatorUsed: false,
          model: resolved.model,
          reasoningEffort: resolved.reasoningEffort,
          sessionKey,
          sessionReused: !useEphemeral
        }
      };
    }
  }

  const participantCalls = toolName === 'codex_review' || toolName === 'codex_consult' || toolName === 'codex_curate' ? 1 : peerCount;
  for (let idx = 0; idx < participantCalls; idx += 1) {
    const participantPrompt = buildStructuredPrompt({
      mode: resolved.mode,
      prompt,
      role: resolved.role,
      participantIndex: participantCalls === 1 ? null : idx,
      peerCount: participantCalls,
      reasoningEffort: resolved.reasoningEffort
    });
    const execResult = await runCodexExecImpl({
      workspaceDir,
      prompt: participantPrompt,
      ephemeral: true,
      skipGitRepoCheck: true,
      model: resolved.model,
      configOverrides: configOverrideArgs(resolved.reasoningEffort)
    });
    if (!execResult?.ok) {
      throw new Error(`codex_exec_failed:${trimForError(execResult?.stderr || execResult?.stdout || execResult?.abortedReason || execResult?.exit?.code || 'unknown')}`);
    }
    const parsed = parseAgentJsonResult(execResult.stdout);
    if (!parsed) {
      throw new Error(`invalid_consultation_result:${trimForError(execResult?.stderr || execResult?.stdout || 'missing_agent_message')}`);
    }
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
      candidates: candidateResults,
      reasoningEffort: resolved.reasoningEffort
    });
    const execResult = await runCodexExecImpl({
      workspaceDir,
      prompt: synthesisPrompt,
      ephemeral: true,
      skipGitRepoCheck: true,
      model: resolved.model,
      configOverrides: configOverrideArgs(resolved.reasoningEffort)
    });
    if (!execResult?.ok) {
      throw new Error(`codex_exec_failed:${trimForError(execResult?.stderr || execResult?.stdout || execResult?.abortedReason || execResult?.exit?.code || 'unknown')}`);
    }
    const parsed = parseAgentJsonResult(execResult.stdout);
    if (!parsed) {
      throw new Error(`invalid_consultation_result:${trimForError(execResult?.stderr || execResult?.stdout || 'missing_agent_message')}`);
    }
    synthesis = normalizeConsultationResult(parsed, { fallbackMode: `${toolName}_synthesis` });
  }

  let curatorUsed = false;
  let finalResult = synthesis;
  if (resolved.useCurator) {
    try {
      finalResult = await promptbridgeCurateImpl({
        prompt,
        candidates: candidateResults,
        key: resolved.promptbridgeKey,
        requestedModel: overrides.promptbridgeModel || null,
        reasoningEffort: overrides.promptbridgeReasoningEffort || null
      });
      curatorUsed = true;
    } catch (error) {
      finalResult = laneAFallbackFrom(synthesis, error);
    }
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
