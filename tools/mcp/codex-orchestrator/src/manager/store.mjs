import fs from 'node:fs/promises';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';

import { defaultCodexHome } from '../codex-orchestration.mjs';

function managerRootDir({ codexHome = defaultCodexHome() } = {}) {
  return path.join(codexHome, 'promptbridge');
}

export function managerDbPath({ codexHome = defaultCodexHome() } = {}) {
  return path.join(managerRootDir({ codexHome }), 'manager.sqlite');
}

export async function ensureManagerDb({ codexHome = defaultCodexHome() } = {}) {
  const rootDir = managerRootDir({ codexHome });
  await fs.mkdir(rootDir, { recursive: true });
  const db = new DatabaseSync(managerDbPath({ codexHome }));
  db.exec(`
    PRAGMA journal_mode = WAL;
    CREATE TABLE IF NOT EXISTS workspaces (
      path TEXT PRIMARY KEY,
      alias TEXT,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS thread_metadata (
      thread_id TEXT PRIMARY KEY,
      workspace_path TEXT,
      label TEXT,
      tags_json TEXT NOT NULL DEFAULT '[]',
      pinned INTEGER NOT NULL DEFAULT 0,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS routes (
      route_key TEXT PRIMARY KEY,
      value_json TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS health_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source TEXT NOT NULL,
      severity TEXT NOT NULL,
      message TEXT NOT NULL,
      details_json TEXT,
      created_at TEXT NOT NULL
    );
  `);
  return db;
}

function nowIso() {
  return new Date().toISOString();
}

export async function bindWorkspace({ codexHome, workspacePath, alias = null }) {
  const db = await ensureManagerDb({ codexHome });
  try {
    db.prepare(`
      INSERT INTO workspaces(path, alias, updated_at)
      VALUES (?, ?, ?)
      ON CONFLICT(path) DO UPDATE SET alias=excluded.alias, updated_at=excluded.updated_at
    `).run(workspacePath, alias, nowIso());
    return readWorkspace({ db, workspacePath });
  } finally {
    db.close();
  }
}

export function readWorkspace({ db, workspacePath }) {
  return db.prepare(`SELECT path, alias, updated_at FROM workspaces WHERE path = ?`).get(workspacePath) || null;
}

export async function setThreadMetadata({ codexHome, threadId, workspacePath = null, label = null, tags = [], pinned = null }) {
  const db = await ensureManagerDb({ codexHome });
  try {
    const existing = db.prepare(`SELECT thread_id, workspace_path, label, tags_json, pinned FROM thread_metadata WHERE thread_id = ?`).get(threadId);
    const next = {
      workspacePath: workspacePath ?? existing?.workspace_path ?? null,
      label: label ?? existing?.label ?? null,
      tags: Array.isArray(tags)
        ? [...new Set(tags.map((t) => String(t).trim()).filter(Boolean))]
        : JSON.parse(existing?.tags_json || '[]'),
      pinned: typeof pinned === 'boolean' ? (pinned ? 1 : 0) : (existing?.pinned ?? 0)
    };
    db.prepare(`
      INSERT INTO thread_metadata(thread_id, workspace_path, label, tags_json, pinned, updated_at)
      VALUES (?, ?, ?, ?, ?, ?)
      ON CONFLICT(thread_id) DO UPDATE SET
        workspace_path=excluded.workspace_path,
        label=excluded.label,
        tags_json=excluded.tags_json,
        pinned=excluded.pinned,
        updated_at=excluded.updated_at
    `).run(threadId, next.workspacePath, next.label, JSON.stringify(next.tags), next.pinned, nowIso());
    return db.prepare(`SELECT thread_id, workspace_path, label, tags_json, pinned, updated_at FROM thread_metadata WHERE thread_id = ?`).get(threadId) || null;
  } finally {
    db.close();
  }
}

export async function writeRoute({ codexHome, routeKey, value }) {
  const db = await ensureManagerDb({ codexHome });
  try {
    db.prepare(`
      INSERT INTO routes(route_key, value_json, updated_at)
      VALUES (?, ?, ?)
      ON CONFLICT(route_key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
    `).run(routeKey, JSON.stringify(value ?? null), nowIso());
    return readRoute({ db, routeKey });
  } finally {
    db.close();
  }
}

export function readRoute({ db, routeKey }) {
  const row = db.prepare(`SELECT route_key, value_json, updated_at FROM routes WHERE route_key = ?`).get(routeKey);
  if (!row) return null;
  return { route_key: row.route_key, value: JSON.parse(row.value_json), updated_at: row.updated_at };
}

export async function appendHealthEvent({ codexHome, source, severity, message, details = null }) {
  const db = await ensureManagerDb({ codexHome });
  try {
    db.prepare(`
      INSERT INTO health_events(source, severity, message, details_json, created_at)
      VALUES (?, ?, ?, ?, ?)
    `).run(source, severity, message, details ? JSON.stringify(details) : null, nowIso());
  } finally {
    db.close();
  }
}

export async function readHealthEvents({ codexHome, limit = 25 }) {
  const db = await ensureManagerDb({ codexHome });
  try {
    return db.prepare(`
      SELECT id, source, severity, message, details_json, created_at
      FROM health_events
      ORDER BY id DESC
      LIMIT ?
    `).all(limit).map((row) => ({
      ...row,
      details: row.details_json ? JSON.parse(row.details_json) : null
    }));
  } finally {
    db.close();
  }
}
