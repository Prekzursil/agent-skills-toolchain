import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';
import { Buffer } from 'node:buffer';
import { DatabaseSync } from 'node:sqlite';
import { TextDecoder } from 'node:util';

import { uncompress as snappyUncompress } from 'snappyjs';

const TEXT_DECODER = new TextDecoder('utf8', { fatal: true });

const COOKIE_HOST_ALLOWLIST = new Set([
  '.chatgpt.com',
  'chatgpt.com',
  '.auth.openai.com',
  'auth.openai.com',
  '.openai.com',
  'openai.com'
]);

const LOCAL_STORAGE_ORIGINS = {
  'https://chatgpt.com': ['storage', 'default', 'https+++chatgpt.com', 'ls', 'data.sqlite'],
  'https://auth.openai.com': ['storage', 'default', 'https+++auth.openai.com', 'ls', 'data.sqlite']
};

function normalizeBlob(value) {
  if (Buffer.isBuffer(value)) return value;
  if (value instanceof Uint8Array) return Buffer.from(value);
  if (ArrayBuffer.isView(value)) return Buffer.from(value.buffer, value.byteOffset, value.byteLength);
  if (value instanceof ArrayBuffer) return Buffer.from(value);
  if (typeof value === 'string') return Buffer.from(value, 'utf8');
  return Buffer.alloc(0);
}

function isAllowedCookieHost(host) {
  return COOKIE_HOST_ALLOWLIST.has(String(host || '').trim());
}

function stripLeadingDot(host) {
  return String(host || '').trim().replace(/^\./, '');
}

function normalizeCookiePath(cookiePath) {
  const p = String(cookiePath || '/').trim() || '/';
  return p.startsWith('/') ? p : `/${p}`;
}

function sameSiteFromFirefox(raw) {
  const code = Number(raw);
  if (code === 0) return 'no_restriction';
  if (code === 1) return 'lax';
  if (code === 2) return 'strict';
  if (code === 256) return 'unspecified';
  throw new Error(`unsupported_sameSite:${raw}`);
}

function cookieUrlForHost({ host, path: cookiePath, secure = true }) {
  const scheme = secure ? 'https' : 'http';
  return `${scheme}://${stripLeadingDot(host)}${normalizeCookiePath(cookiePath)}`;
}

function summarizeLocalStorage(localStorageByOrigin) {
  const summary = {};
  for (const [origin, entries] of Object.entries(localStorageByOrigin || {})) {
    summary[origin] = Object.keys(entries || {}).length;
  }
  return summary;
}

async function pathExists(file) {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

async function copyFileIfPresent(src, dst) {
  if (!(await pathExists(src))) return false;
  await fs.mkdir(path.dirname(dst), { recursive: true });
  await fs.copyFile(src, dst);
  return true;
}

async function copySqliteWithSidecars(src, dst) {
  const copiedMain = await copyFileIfPresent(src, dst);
  if (!copiedMain) return false;
  for (const ext of ['-wal', '-shm']) {
    await copyFileIfPresent(`${src}${ext}`, `${dst}${ext}`);
  }
  return true;
}

function readTableRows(dbPath, sql) {
  const db = new DatabaseSync(dbPath);
  try {
    const stmt = db.prepare(sql);
    return stmt.all();
  } finally {
    db.close();
  }
}

async function snapshotFirefoxProfile(profilePath) {
  const tmpRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'agentify-firefox-import-'));
  const snapshotRoot = path.join(tmpRoot, 'profile');
  const cookiesDbPath = path.join(snapshotRoot, 'cookies.sqlite');
  const copiedCookies = await copySqliteWithSidecars(path.join(profilePath, 'cookies.sqlite'), cookiesDbPath);
  if (!copiedCookies) throw new Error('missing_firefox_cookies_db');

  const localStorageDbPaths = {};
  for (const [origin, relativeParts] of Object.entries(LOCAL_STORAGE_ORIGINS)) {
    const src = path.join(profilePath, ...relativeParts);
    const dst = path.join(snapshotRoot, ...relativeParts);
    const copied = await copySqliteWithSidecars(src, dst);
    localStorageDbPaths[origin] = copied ? dst : null;
  }

  return {
    cleanup: async () => {
      await fs.rm(tmpRoot, { recursive: true, force: true });
    },
    cookiesDbPath,
    localStorageDbPaths
  };
}

export function defaultFirefoxProfilesRoot({ platform = process.platform, env = process.env, homeDir = os.homedir() } = {}) {
  if (platform === 'win32') {
    const appData = String(env.APPDATA || '').trim();
    if (!appData) throw new Error('missing_APPDATA');
    return path.join(appData, 'Mozilla', 'Firefox', 'Profiles');
  }
  if (platform === 'darwin') return path.join(homeDir, 'Library', 'Application Support', 'Firefox', 'Profiles');
  return path.join(homeDir, '.mozilla', 'firefox');
}

function firefoxProfileSortKey(name) {
  if (name === 'k4cy1nuq.default-release') return [0, name.toLowerCase()];
  if (name.endsWith('.default-release')) return [1, name.toLowerCase()];
  if (name.endsWith('.default')) return [2, name.toLowerCase()];
  return [3, name.toLowerCase()];
}

export async function listFirefoxProfiles({ profilesRoot = defaultFirefoxProfilesRoot() } = {}) {
  if (!(await pathExists(profilesRoot))) return [];
  const entries = await fs.readdir(profilesRoot, { withFileTypes: true });
  const profiles = entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => {
      const id = entry.name;
      return {
        id,
        label: id,
        path: path.join(profilesRoot, id),
        isDefault: id === 'k4cy1nuq.default-release' || id.endsWith('.default-release')
      };
    });
  profiles.sort((a, b) => {
    const [aRank, aName] = firefoxProfileSortKey(a.id);
    const [bRank, bName] = firefoxProfileSortKey(b.id);
    if (aRank !== bRank) return aRank - bRank;
    return aName.localeCompare(bName);
  });
  return profiles;
}

export function decodeFirefoxLocalStorageValue({ value, conversionType, compressionType }) {
  if (Number(conversionType) !== 1) {
    throw new Error(`unsupported_conversion_type:${conversionType}`);
  }
  let bytes = normalizeBlob(value);
  if (Number(compressionType) === 1) {
    bytes = Buffer.from(snappyUncompress(bytes));
  } else if (Number(compressionType) !== 0) {
    throw new Error(`unsupported_compression_type:${compressionType}`);
  }
  return TEXT_DECODER.decode(bytes);
}

export function toElectronCookieDetails(row) {
  const host = String(row?.host || '').trim();
  const secure = !!Number(row?.isSecure);
  const sameSite = sameSiteFromFirefox(row?.sameSite);
  const out = {
    url: cookieUrlForHost({ host, path: row?.path, secure: secure || sameSite === 'no_restriction' }),
    name: String(row?.name || ''),
    value: String(row?.value || ''),
    path: normalizeCookiePath(row?.path),
    secure: secure || sameSite === 'no_restriction',
    httpOnly: !!Number(row?.isHttpOnly),
    sameSite
  };
  if (host.startsWith('.')) out.domain = host;
  const expiry = Number(row?.expiry || 0);
  if (Number.isFinite(expiry) && expiry > 0) out.expirationDate = expiry;
  return out;
}

function readCookiesFromSnapshot(cookiesDbPath) {
  const rows = readTableRows(
    cookiesDbPath,
    `
      SELECT originAttributes, name, value, host, path, expiry, isSecure, isHttpOnly, sameSite, isPartitionedAttributeSet
      FROM moz_cookies
      ORDER BY host, name
    `
  );

  const summary = {
    imported: 0,
    skippedOriginAttributes: 0,
    skippedPartitioned: 0,
    skippedHost: 0
  };
  const cookies = [];

  for (const row of rows) {
    if (!isAllowedCookieHost(row.host)) {
      summary.skippedHost += 1;
      continue;
    }
    if (String(row.originAttributes || '').trim()) {
      summary.skippedOriginAttributes += 1;
      continue;
    }
    if (Number(row.isPartitionedAttributeSet || 0) !== 0) {
      summary.skippedPartitioned += 1;
      continue;
    }
    cookies.push(toElectronCookieDetails(row));
    summary.imported += 1;
  }

  return { cookies, summary };
}

function readLocalStorageFromSnapshot(localStorageDbPaths) {
  const localStorageByOrigin = {};
  for (const [origin, dbPath] of Object.entries(localStorageDbPaths || {})) {
    if (!dbPath) {
      localStorageByOrigin[origin] = {};
      continue;
    }
    const rows = readTableRows(
      dbPath,
      `
        SELECT key, conversion_type AS conversionType, compression_type AS compressionType, value
        FROM data
        ORDER BY key
      `
    );
    const entries = {};
    for (const row of rows) {
      entries[String(row.key)] = decodeFirefoxLocalStorageValue(row);
    }
    localStorageByOrigin[origin] = entries;
  }
  return localStorageByOrigin;
}

export async function readFirefoxBootstrapFromProfile({ profilePath }) {
  if (!profilePath) throw new Error('missing_firefox_profile_path');
  const snapshot = await snapshotFirefoxProfile(profilePath);
  try {
    const { cookies, summary: cookieSummary } = readCookiesFromSnapshot(snapshot.cookiesDbPath);
    const localStorageByOrigin = readLocalStorageFromSnapshot(snapshot.localStorageDbPaths);
    return {
      cookies,
      localStorageByOrigin,
      summary: {
        cookies: cookieSummary,
        localStorage: summarizeLocalStorage(localStorageByOrigin)
      }
    };
  } finally {
    await snapshot.cleanup();
  }
}

function cookieMatchesAllowlist(cookie) {
  return isAllowedCookieHost(cookie?.domain || cookie?.host || '');
}

async function clearAllowlistedCookies(session) {
  const cookies = await session.cookies.get({});
  for (const cookie of cookies) {
    if (!cookieMatchesAllowlist(cookie)) continue;
    await session.cookies.remove(cookieUrlForHost({ host: cookie.domain || cookie.host, path: cookie.path, secure: cookie.secure }), cookie.name);
  }
  await session.flushStorageData();
}

function localStoragePayload(entries) {
  return Buffer.from(JSON.stringify(Object.entries(entries || {})), 'utf8').toString('base64');
}

async function clearOriginLocalStorage(win, origin) {
  await win.loadURL(origin);
  await win.webContents.executeJavaScript(
    `
      (() => {
        localStorage.clear();
        return { ok: true, count: localStorage.length };
      })()
    `,
    true
  );
}

async function setOriginLocalStorage(win, origin, entries) {
  await win.loadURL(origin);
  const payload = localStoragePayload(entries);
  const result = await win.webContents.executeJavaScript(
    `
      (() => {
        const pairs = JSON.parse(atob(${JSON.stringify(payload)}));
        localStorage.clear();
        for (const [key, value] of pairs) {
          localStorage.setItem(key, value);
        }
        return { ok: true, count: localStorage.length };
      })()
    `,
    true
  );
  return Number(result?.count || 0);
}

async function clearAllowlistedLocalStorage({ session, BrowserWindowCtor }) {
  if (typeof BrowserWindowCtor !== 'function') throw new Error('missing_browser_window_ctor');
  const win = new BrowserWindowCtor({
    show: false,
    webPreferences: {
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      session
    }
  });
  try {
    for (const origin of Object.keys(LOCAL_STORAGE_ORIGINS)) {
      await clearOriginLocalStorage(win, origin);
    }
  } finally {
    try {
      if (!win.isDestroyed()) win.destroy();
    } catch {}
  }
}

async function applyAllowlistedLocalStorage({ session, BrowserWindowCtor, localStorageByOrigin }) {
  if (typeof BrowserWindowCtor !== 'function') throw new Error('missing_browser_window_ctor');
  const win = new BrowserWindowCtor({
    show: false,
    webPreferences: {
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      session
    }
  });
  try {
    for (const [origin, entries] of Object.entries(localStorageByOrigin || {})) {
      await setOriginLocalStorage(win, origin, entries);
    }
  } finally {
    try {
      if (!win.isDestroyed()) win.destroy();
    } catch {}
  }
}

function focusWindow(win) {
  if (!win || win.isDestroyed?.()) return;
  try {
    if (win.isMinimized?.()) win.restore();
    win.show?.();
    win.focus?.();
  } catch {}
}

export async function importFirefoxSession({
  profilePath,
  session,
  defaultTabWindow = null,
  BrowserWindowCtor
}) {
  if (!session) throw new Error('missing_target_session');
  if (typeof BrowserWindowCtor !== 'function') throw new Error('missing_browser_window_ctor');
  const state = await readFirefoxBootstrapFromProfile({ profilePath });
  const hasSessionData =
    state.cookies.length > 0 || Object.values(state.localStorageByOrigin).some((entries) => Object.keys(entries || {}).length > 0);
  if (!hasSessionData) throw new Error('no_matching_firefox_session');

  await clearAllowlistedCookies(session);
  let rollbackNeeded = true;
  try {
    await clearAllowlistedLocalStorage({ session, BrowserWindowCtor });
    for (const cookie of state.cookies) {
      await session.cookies.set(cookie);
    }
    await session.flushStorageData();
    await applyAllowlistedLocalStorage({ session, BrowserWindowCtor, localStorageByOrigin: state.localStorageByOrigin });
    await session.flushStorageData();
    rollbackNeeded = false;
  } catch (error) {
    if (rollbackNeeded) {
      try {
        await clearAllowlistedCookies(session);
        await clearAllowlistedLocalStorage({ session, BrowserWindowCtor });
      } catch {}
    }
    throw error;
  }

  if (defaultTabWindow && !defaultTabWindow.isDestroyed?.()) {
    await defaultTabWindow.loadURL('https://chatgpt.com/');
    focusWindow(defaultTabWindow);
  }

  return state;
}
