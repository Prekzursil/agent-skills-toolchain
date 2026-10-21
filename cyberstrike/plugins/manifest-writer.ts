/**
 * CyberStrike session-manifest shard writer (G-8=B, Phase-3) — v2 2026-09-22.
 *
 * VERDICT (experiments lane, 2026-09-22): v1 loaded (TUI log 2026-09-22T143008.log:31)
 * but wrote ZERO shards. Two confirmed defects, both fixed here:
 *
 *   DEFECT-1 (registration): v1 registered top-level hook keys "session.created" /
 *   "session.idle" / "session.compacted". Those keys DO NOT EXIST in the host dispatch
 *   surface — @cyberstrike-io/plugin dist/index.d.ts:108-230 (Hooks) exposes session
 *   events ONLY through the generic `event` hook as { event: { type, properties } }
 *   (sdk gen/types.gen.d.ts:406-503). Dead keys => handlers never invoked.
 *
 *   DEFECT-2 (payload shape): v1's sessionFrom() read `input.session ?? input` then
 *   `.sessionID ?? .id ?? .session_id`. Real payloads:
 *     session.created   -> properties.info: Session { id, title, directory, parentID?, ... }
 *     session.idle      -> properties.sessionID: string
 *     session.compacted -> properties.sessionID: string
 *   (sdk gen/types.gen.d.ts:413-424, :493-497, :465-486 Session). The old extractor
 *   would have returned undefined => silent no-write even if a key HAD fired.
 *
 * OPEN (UNVERIFIED until next TUI restart with this fixed plugin mounted): whether the
 * generic `event` hook is dispatched to config-loaded plugins at all in v1.1.16 —
 * hook-experiment.log shows zero `event` lines from the same session (the declared
 * `permission.ask` hook is already proven never-dispatched: binary exact-string count 0).
 * The defensive debug log below settles it in ONE restart: it records Object.keys(input)
 * and the payload keys for every event that reaches us.
 *
 * Remount note (config boundary, owner-applied): HEAD removed the plugin array because
 * the BARE-PATH string form boot-crashes (bun add <path>@latest -> BunInstallFailedError,
 * log 2026-09-20T230623.log; commit 04aff13). The file:// array form is the PROVEN-LOADING
 * shape (live TUI 2026-09-22T143008.log:31-32 loaded both plugins via file:/// URLs):
 *   "plugin": ["file:///C:/Users/Prekzursil/.config/cyberstrike/plugins/manifest-writer.ts"]
 *
 * Design unchanged (grill G-8=B): append-only per-session NDJSON shards under
 *   <dataDir>/manifest/sessions/<sessionID>.ndjson
 * one JSON line per event {ts, event, sessionID, title, directory, parentID, pid}.
 * Merge-on-sweep + two-signal death check live in scripts/manifest_merge.py.
 * Shards are NEVER truncated or rewritten. Fail-open everywhere (a manifest error must
 * never break a session); no network; no credential-shaped data is ever written.
 */
import { appendFile, mkdir } from "node:fs/promises";
import { join } from "node:path";

const DATA_DIR =
  process.env.CYBERSTRIKE_DATA ??
  join(process.env["USERPROFILE"] ?? process.env["HOME"] ?? ".", ".local", "share", "cyberstrike");
const MANIFEST_DIR = join(DATA_DIR, "manifest", "sessions");
// Defensive event-shape debug log (task 2026-09-22): "console.error to a file" — a
// dedicated NDJSON side-file survives TUI log rotation and never touches the console.
const DEBUG_LOG = join(DATA_DIR, "manifest", "_debug-events.ndjson");
const DEBUG_NON_SESSION_CAP = 200; // bounded: non-session events sampled, session events always

interface SessionRef {
  sessionID?: string;
  title?: string;
  directory?: string;
  parentID?: string;
}

// Real shapes (VERIFIED typings, see header):
//   { type: "session.created",   properties: { info: Session } }
//   { type: "session.idle",      properties: { sessionID } }
//   { type: "session.compacted", properties: { sessionID } }
function sessionFromEvent(ev: any): SessionRef {
  const p = ev?.properties ?? {};
  const info = p.info && typeof p.info === "object" ? p.info : {};
  return {
    sessionID: p.sessionID ?? info.id,
    title: info.title ?? undefined,
    directory: info.directory ?? undefined,
    parentID: info.parentID ?? undefined,
  };
}

// Legacy defensive extractor: kept for the (unproven) case a future build dispatches
// session.* as top-level hooks. Understands BOTH the old guessed shape and the real
// {properties} / {event:{properties}} envelope.
function sessionFromAny(input: any): SessionRef {
  const candidates = [
    input?.properties,
    input?.event?.properties,
    input?.session,
    input,
  ];
  for (const c of candidates) {
    if (!c || typeof c !== "object") continue;
    const info = c.info && typeof c.info === "object" ? c.info : {};
    const sid = c.sessionID ?? c.id ?? c.session_id ?? info.id;
    if (sid) {
      return {
        sessionID: sid,
        title: c.title ?? info.title,
        directory: c.directory ?? info.directory,
        parentID: c.parentID ?? c.parent_id ?? info.parentID,
      };
    }
  }
  return {};
}

let debugCount = 0;

async function debugEvent(via: string, input: any, ev?: any): Promise<void> {
  try {
    const type = ev?.type ?? "(no-type)";
    const isSession = String(type).startsWith("session.");
    if (!isSession && debugCount >= DEBUG_NON_SESSION_CAP) return;
    debugCount++;
    const line = JSON.stringify({
      ts: new Date().toISOString(),
      pid: process.pid,
      via, // "event-hook" | "legacy-session-key" | "compacting-hook"
      type,
      inputKeys: Object.keys(input ?? {}),
      payloadKeys: Object.keys(ev ?? {}),
      propertiesKeys: Object.keys(ev?.properties ?? {}),
      sampled: JSON.stringify(ev ?? input ?? {}).slice(0, 400), // shape only; sessions carry no secrets
    }) + "\n";
    await mkdir(join(DATA_DIR, "manifest"), { recursive: true });
    await appendFile(DEBUG_LOG, line, "utf8");
  } catch {
    // fail open: debug loss is never a session failure
  }
}

async function appendEvent(event: string, s: SessionRef): Promise<void> {
  try {
    if (!s.sessionID) return; // nothing addressable — fail open, write nothing
    const line = JSON.stringify({
      ts: new Date().toISOString(),
      event,
      sessionID: s.sessionID,
      title: s.title,
      directory: s.directory,
      parentID: s.parentID,
      pid: process.pid,
    }) + "\n";
    await mkdir(MANIFEST_DIR, { recursive: true });
    await appendFile(join(MANIFEST_DIR, `${s.sessionID}.ndjson`), line, "utf8");
  } catch {
    // fail open: manifest loss is a monitoring gap, never a session failure
  }
}

const MANIFEST_EVENTS = new Set(["session.created", "session.idle", "session.compacted"]);

export const ManifestWriter = async () => ({
  // PRIMARY channel (per Hooks typings): every session.* bus event arrives here.
  event: async (input: { event?: any }) => {
    const ev = input?.event;
    await debugEvent("event-hook", input, ev);
    if (!ev || !MANIFEST_EVENTS.has(ev.type)) return;
    const event = ev.type === "session.created" ? "created"
      : ev.type === "session.idle" ? "idle"
      : "compacted";
    await appendEvent(event, sessionFromEvent(ev));
  },
  // TYPED compaction-lifecycle hook (index.d.ts:208-213): carries sessionID directly.
  // Backstop in case the generic event hook proves never-dispatched on v1.1.16.
  "experimental.session.compacting": async (input: { sessionID: string }) => {
    await debugEvent("compacting-hook", input, { type: "experimental.session.compacting" });
    await appendEvent("compacting", { sessionID: input?.sessionID });
  },
  // LEGACY keys (v1 shape): dead on v1.1.16 typings, kept defensively for forks that
  // dispatch them; each hit also feeds the debug log so the shape question closes fast.
  "session.created": async (input: any) => {
    await debugEvent("legacy-session-key", input, input?.event ?? input);
    await appendEvent("created", sessionFromAny(input));
  },
  "session.idle": async (input: any) => {
    await debugEvent("legacy-session-key", input, input?.event ?? input);
    await appendEvent("idle", sessionFromAny(input));
  },
  "session.compacted": async (input: any) => {
    await debugEvent("legacy-session-key", input, input?.event ?? input);
    await appendEvent("compacted", sessionFromAny(input));
  },
});

export default ManifestWriter;
