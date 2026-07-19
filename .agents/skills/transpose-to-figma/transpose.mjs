#!/usr/bin/env node
// transpose-to-figma — G2 TRANSPOSE altitude selector + node resolver + record writer.
// Pure Node, zero deps. The actual canvas work happens via the Figma MCP tools
// (generate_figma_design / use_figma) and the story.to.design / html.to.design
// plugins — this harness is plumbing: it PICKS the path, RESOLVES a node URL, and
// WRITES a typed transpose record. It never calls a model and never edits Figma.
//
// Subcommands:
//   select   --target live|localhost|audit  [--has-storybook] [--auth]
//            -> recommends the path + drift class + caveats + the exact next tool call
//   resolve  --url <figma-url>
//            -> parses fileKey + node-id (mirrors figma-implement-design)
//   record   --path <path> --out <dir> [--drift low|medium|high]
//            [--code-connect] [--token-refs] [--screens a,b]
//            -> writes transpose-record.json (the lossy-revert surface manifest)
//
// Every subcommand prints a terminal-state marker on its last line:
//   SUCCESS:transpose-<sub>-<id>  /  FAILED:transpose-<sub>-<id> <reason>

import { writeFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) out[key] = true;
      else { out[key] = next; i++; }
    } else out._.push(a);
  }
  return out;
}

const shortId = () => Math.random().toString(36).slice(2, 8);

// The altitude table — the load-bearing decision of G2 (FIGMA-SETUP.md §1 transpose
// table; DESIGN-WORKFLOW.md G2; DESIGN-SKILLS-AND-EVAL.md §1.2).
const ALTITUDES = {
  'system-loop': {
    tool: 'story.to.design',
    drift: 'low',
    granularity: 'component',
    surviving: 'real Figma components + variants (your component graph IS what lands)',
    caveat: 'Requires a Storybook / published component kit. Greenfield apps with no kit have nothing to bind — extract tokens manually first (audit loop).',
    nextCall: 'Run the story.to.design plugin against the Storybook URL; the import carries Code Connect IDs + token refs.',
  },
  'live': {
    tool: 'generate_figma_design (Figma MCP)',
    drift: 'medium',
    granularity: 'screen',
    surviving: 'semantic editable frames (render-mediated: dev server -> rendered DOM serialized)',
    caveat: 'Render-mediated beta — captures VISUAL state, not logic/state/routing. Single-use capture IDs. Free during beta, slated to become usage-based paid. If it flakes, degrade to screenshot -> critique -> MCP-fed edit.',
    nextCall: 'Call generate_figma_design with the live/staging URL (works behind auth via the capture path).',
  },
  'localhost': {
    tool: 'generate_figma_design (Figma MCP)',
    drift: 'medium',
    granularity: 'screen',
    surviving: 'semantic editable frames from your local dev server',
    caveat: 'Same render-mediated beta caveats as live. Point it at the Vite/dev port (e.g. an Electron renderer like Reframe on :5173).',
    nextCall: 'Start the dev server, then call generate_figma_design with the localhost URL.',
  },
  'audit': {
    tool: 'html.to.design',
    drift: 'high',
    granularity: 'flat',
    surviving: 'DOM-accurate FLAT layers only — a record to LOOK AT, never the system loop',
    caveat: 'WRONG for the system loop: screenshot/DOM importers cause design-system drift the moment Figma naming diverges from code. Handles auth/private/localhost. Use only as an audit/benchmark record.',
    nextCall: 'Use the html.to.design browser extension to capture the DOM into flat editable layers.',
  },
};

function cmdSelect(args) {
  const id = shortId();
  const target = args.target;
  if (!['live', 'localhost', 'audit'].includes(target)) {
    console.log(`FAILED:transpose-select-${id} --target must be one of live|localhost|audit`);
    process.exit(1);
  }
  // System loop wins whenever a component kit exists AND we are not explicitly doing an audit-only record.
  let key;
  if (args['has-storybook'] && target !== 'audit') key = 'system-loop';
  else if (target === 'audit') key = 'audit';
  else key = target; // live | localhost
  const a = ALTITUDES[key];
  const rec = {
    id: `transpose-select-${id}`,
    chosenAltitude: key,
    tool: a.tool,
    driftClass: a.drift,
    granularity: a.granularity,
    surviving: a.surviving,
    caveat: a.caveat,
    nextCall: a.nextCall,
    hasStorybook: !!args['has-storybook'],
    auth: !!args.auth,
  };
  console.log(JSON.stringify(rec, null, 2));
  console.log(`SUCCESS:transpose-select-${id}`);
}

function cmdResolve(args) {
  const id = shortId();
  const url = args.url;
  if (!url || url === true) {
    console.log(`FAILED:transpose-resolve-${id} --url is required`);
    process.exit(1);
  }
  // Figma URL shape: /design/:fileKey/:fileName?node-id=1-2  (also legacy /file/)
  const fileKey = (url.match(/\/(?:design|file)\/([a-zA-Z0-9]+)/) || [])[1] || null;
  let nodeId = (url.match(/[?&]node-id=([0-9]+-[0-9]+|[0-9]+%3A[0-9]+|[0-9]+:[0-9]+)/) || [])[1] || null;
  if (nodeId) nodeId = decodeURIComponent(nodeId).replace('-', ':');
  if (!fileKey) {
    console.log(`FAILED:transpose-resolve-${id} could not parse fileKey from URL`);
    process.exit(1);
  }
  console.log(JSON.stringify({ id: `transpose-resolve-${id}`, fileKey, nodeId }, null, 2));
  console.log(`SUCCESS:transpose-resolve-${id}`);
}

function cmdRecord(args) {
  const id = shortId();
  const outDir = args.out;
  if (!outDir || outDir === true) {
    console.log(`FAILED:transpose-record-${id} --out <dir> is required`);
    process.exit(1);
  }
  const path = args.path || 'unknown';
  const codeConnect = !!args['code-connect'];
  const tokenRefs = !!args['token-refs'];
  // The only things that round-trip CLEANLY (DESIGN-WORKFLOW.md §1).
  const losslessChannels = [];
  if (tokenRefs) losslessChannels.push('DTCG design tokens (Tokens Studio <-> Git <-> Style Dictionary)');
  if (codeConnect) losslessChannels.push('Code-Connected components (emits your real <Button>, not a re-derived div)');
  const record = {
    id: `transpose-${id}`,
    path,
    driftClass: args.drift || (ALTITUDES[path] ? ALTITUDES[path].drift : 'unknown'),
    screens: typeof args.screens === 'string' ? args.screens.split(',').map(s => s.trim()) : [],
    survives: losslessChannels,
    doesNotSurvive: ['React state', 'routing', 'API calls / data fetch', 'business logic'],
    systemLoopReady: codeConnect && tokenRefs,
    revertSurface: tokenRefs
      ? 'token diff (tiny + reviewable) — the clean revert channel'
      : 'NONE bound — this is an audit-only record; do not treat as the system source of truth',
    capturedAt: new Date().toISOString(),
  };
  mkdirSync(outDir, { recursive: true });
  const file = join(outDir, 'transpose-record.json');
  writeFileSync(file, JSON.stringify(record, null, 2));
  console.log(`wrote ${file}`);
  if (!record.systemLoopReady) {
    console.log('NOTE: nodes are NOT both Code-Connected and token-bound -> AUDIT loop only, not the system loop.');
  }
  console.log(`SUCCESS:transpose-${id}`);
}

const args = parseArgs(process.argv.slice(2));
const sub = args._[0];
try {
  if (sub === 'select') cmdSelect(args);
  else if (sub === 'resolve') cmdResolve(args);
  else if (sub === 'record') cmdRecord(args);
  else {
    console.log('Usage: transpose.mjs <select|resolve|record> [flags]');
    console.log(`FAILED:transpose-usage-${shortId()} unknown subcommand: ${sub ?? '(none)'}`);
    process.exit(1);
  }
} catch (e) {
  console.log(`FAILED:transpose-${shortId()} ${e.message}`);
  process.exit(1);
}
