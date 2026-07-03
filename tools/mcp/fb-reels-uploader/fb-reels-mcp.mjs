#!/usr/bin/env node
/**
 * fb-reels-mcp — a thin stdio MCP wrapper around the fb-reels upload CLI.
 *
 * Exposes three tools, reusing the CLI's own browser orchestration
 * (`runBatch` -> `waitForLogin`/`setAudience`/`uploadOneReel`):
 *   - fb_upload_reel(file, audience?)                      : one file
 *   - fb_upload_reels_from_folder(folder, start?, limit?, delaySec?, audience?, headless?)
 *   - fb_reels_status(jobId?)                              : progress reader
 *
 * Uploads are LONG-RUNNING (a real headless browser drives facebook.com), so the
 * upload tools DO NOT block: they register a background job and return a jobId
 * immediately. Poll fb_reels_status(jobId) — it reflects the in-memory job plus
 * the on-disk `<folder>/.fb-posted.json` resume ledger.
 *
 * ONE-TIME SETUP: Facebook has no personal-profile post API, so the persistent
 * browser profile must be authenticated ONCE by a human via the CLI:
 *     node fb-reels-upload.mjs <someFolder>     # a window opens; log in once
 * After that the saved session lets this MCP run headless.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

import { runBatch, DEFAULT_PROFILE } from './fb-reels-upload.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const JOBS_FILE = path.join(__dirname, '.fb-reels-jobs.json');

/** @type {Map<string, any>} */
const jobs = new Map();

function loadJobs() {
  try {
    const data = JSON.parse(fs.readFileSync(JOBS_FILE, 'utf8'));
    for (const j of data.jobs || []) jobs.set(j.id, j);
  } catch { /* fresh start */ }
}

function saveJobs() {
  try {
    const recent = [...jobs.values()].slice(-50);
    fs.writeFileSync(JOBS_FILE, JSON.stringify({ jobs: recent }, null, 2));
  } catch { /* best-effort persistence */ }
}

function newJob(kind, target) {
  const id = `${kind}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const job = {
    id, kind, target, status: 'running',
    startedAt: new Date().toISOString(), finishedAt: null,
    posted: [], failed: [], log: [], error: null,
  };
  jobs.set(id, job);
  saveJobs();
  return job;
}

function emitter(job) {
  return (msg) => {
    job.log.push(`${new Date().toISOString().slice(11, 19)} ${msg}`);
    if (job.log.length > 200) job.log.shift();
    saveJobs();
  };
}

function startJob(job, opts) {
  runBatch(opts, emitter(job))
    .then((r) => {
      job.status = r.failed.length ? 'partial' : 'done';
      job.posted = r.posted;
      job.failed = r.failed;
      job.finishedAt = new Date().toISOString();
      saveJobs();
    })
    .catch((e) => {
      job.status = 'error';
      job.error = e.message;
      job.finishedAt = new Date().toISOString();
      saveJobs();
    });
}

const asText = (obj) => ({ content: [{ type: 'text', text: JSON.stringify(obj, null, 2) }] });
const asError = (msg) => ({ content: [{ type: 'text', text: msg }], isError: true });

function readPostedLedger(folder) {
  try {
    return JSON.parse(fs.readFileSync(path.join(folder, '.fb-posted.json'), 'utf8')).posted || [];
  } catch {
    return [];
  }
}

function buildServer() {
  const server = new McpServer({ name: 'fb-reels', version: '0.1.0' });

  server.tool(
    'fb_upload_reel',
    'Upload ONE local vertical video to Facebook as a Reel. Long-running: returns a jobId immediately; poll fb_reels_status(jobId). Requires the browser profile to be logged into Facebook once (see the tool docs).',
    {
      file: z.string().describe('Absolute path to the .mp4 to upload as a Reel'),
      audience: z.enum(['public', 'friends', 'onlyme']).optional()
        .describe('Reel audience (default public)'),
    },
    async ({ file, audience }) => {
      if (!fs.existsSync(file)) return asError(`File not found: ${file}`);
      const job = newJob('reel', file);
      startJob(job, { files: [file], audience: audience || 'public', headless: true });
      return asText({
        jobId: job.id, status: 'started', file,
        note: 'Runs in the background. Poll fb_reels_status with this jobId.',
      });
    },
  );

  server.tool(
    'fb_upload_reels_from_folder',
    'Upload every *.mp4 in a folder to Facebook as Reels, in filename order, one per post, resuming from .fb-posted.json. Long-running: returns a jobId immediately; poll fb_reels_status(jobId).',
    {
      folder: z.string().describe('Folder containing the .mp4 clips to upload'),
      start: z.number().int().positive().optional().describe('1-based index of the first clip (default 1)'),
      limit: z.number().int().positive().optional().describe('Max clips to upload this run (default all)'),
      delaySec: z.number().int().nonnegative().optional().describe('Pause between posts, anti-spam (default 20)'),
      audience: z.enum(['public', 'friends', 'onlyme']).optional().describe('Reel audience (default public)'),
      headless: z.boolean().optional().describe('Run without a window (default true; needs a prior login)'),
    },
    async ({ folder, start, limit, delaySec, audience, headless }) => {
      if (!fs.existsSync(folder)) return asError(`Folder not found: ${folder}`);
      const job = newJob('folder', folder);
      startJob(job, {
        folder, start, limit, delaySec,
        audience: audience || 'public',
        headless: headless !== undefined ? headless : true,
        profile: DEFAULT_PROFILE,
      });
      return asText({
        jobId: job.id, status: 'started', folder,
        alreadyPosted: readPostedLedger(folder),
        note: 'Runs in the background. Poll fb_reels_status with this jobId.',
      });
    },
  );

  server.tool(
    'fb_reels_status',
    'Read the status of a Reels upload job (or list recent jobs if jobId is omitted). Reflects the in-memory job plus the on-disk .fb-posted.json resume ledger.',
    {
      jobId: z.string().optional().describe('The jobId returned by an upload tool; omit to list recent jobs'),
    },
    async ({ jobId }) => {
      if (!jobId) {
        const recent = [...jobs.values()].slice(-10).map((j) => ({
          id: j.id, kind: j.kind, status: j.status, target: j.target,
          posted: j.posted.length, failed: j.failed.length, startedAt: j.startedAt,
        }));
        return asText({ jobs: recent });
      }
      const job = jobs.get(jobId);
      if (!job) return asError(`Unknown jobId: ${jobId}`);
      const view = { ...job };
      if (job.kind === 'folder') view.ledgerPosted = readPostedLedger(job.target);
      return asText(view);
    },
  );

  return server;
}

async function main() {
  loadJobs();
  const server = buildServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('fb-reels MCP server started (tools: fb_upload_reel, fb_upload_reels_from_folder, fb_reels_status)');
}

main().catch((e) => { console.error('fb-reels MCP fatal:', e); process.exit(1); });
