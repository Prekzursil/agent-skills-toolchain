/**
 * CyberStrike plugin-API hook experiment (G-11 prerequisite - dispatcher stage)
 * Repo: ~/.config/cyberstrike | Receipt: D:/bolt/admin-crack-2026-09-19/raw/cs-audit/phase2-5/dispatcher_verdict.json
 *
 * STATIC FINDINGS this experiment CONFIRMS at runtime (from cyberstrike.exe v1.1.16, 2026-09-20):
 *   - Plugin.trigger (binary L756266) is a sequential for-of with a bare `await fn3(input, output)`
 *     and NO timeout/race  ->  (a) sleep mode: the tool call is delayed by the full sleep; host never truncates.
 *   - Tool processors wrap execute in try/catch (binary L571711) -> (b) throw mode (exit-2-equivalent):
 *     error becomes a status:"error" tool part + {success:false}; process survives; turn continues.
 *   - "permission.ask" hook declared in @cyberstrike-io/plugin typings is NEVER dispatched by the host
 *     (exact-string count 0) -> denial must go through throw, not permission.ask.
 *
 * SAFETY
 *   - Default mode "log" is a passive observer (no sleep, no throw) - safe if left registered.
 *   - Mode: env CS_HOOK_EXP_MODE in {log,sleep,throw}; sleep ms: CS_HOOK_EXP_SLEEP_MS (default 8000).
 *   - This file is INERT until registered in cyberstrike.json:
 *       "plugin": ["file:///C:/Users/Prekzursil/.config/cyberstrike/plugin/hook-experiment.ts"]
 *     (v1.1.16 loader = config "plugin" array ONLY, npm pkg or file:// URL; NO directory auto-load, L756217)
 *
 * RUNTIME PROTOCOL (next CyberStrike start; deferred 2026-09-20: free RAM 0.8 GB < 8 GB gate)
 *   0. Preconditions: free RAM > 8 GB; no other critical work on the box.
 *   1. cp cyberstrike.json cyberstrike.json.bak-hookexp-<date>; add the plugin entry above.
 *   2. CS_HOOK_EXP_MODE=log   -> start TUI (or: cyberstrike run "run: echo ping" with a free model)
 *      EXPECT: "plugin-loaded" line in plugin/hook-experiment.log  (loader proof)
 *   3. CS_HOOK_EXP_MODE=sleep -> trigger any tool call
 *      EXPECT: before:start -> before:end delta ~= CS_HOOK_EXP_SLEEP_MS; tool completes AFTER the sleep
 *      (a shorter delta or a host-side cancel would indicate a dispatcher timeout - static analysis says none)
 *   4. CS_HOOK_EXP_MODE=throw -> trigger any tool call
 *      EXPECT: errored tool part ("CS hook-experiment intentional deny"), TUI stays alive, turn continues
 *      (a frozen TUI or dead process would indicate denial is NOT fail-open)
 *   5. Cleanup: remove the plugin entry from cyberstrike.json; keep this file + the log as evidence.
 */
import type { Plugin } from "@cyberstrike-io/plugin"
import { appendFileSync } from "node:fs"
import { homedir } from "node:os"
import { join } from "node:path"

const LOG = join(homedir(), ".config", "cyberstrike", "plugin", "hook-experiment.log")
const MODE = (process.env.CS_HOOK_EXP_MODE ?? "log").toLowerCase() // log | sleep | throw
const SLEEP_MS = Number(process.env.CS_HOOK_EXP_SLEEP_MS ?? 8000)

function log(event: string, data: Record<string, unknown> = {}) {
  try {
    appendFileSync(LOG, JSON.stringify({ t: new Date().toISOString(), mode: MODE, event, ...data }) + "\n")
  } catch {
    /* the logger must never break the host */
  }
}

let eventCount = 0

export const HookExperimentPlugin: Plugin = async (input) => {
  log("plugin-loaded", { directory: input.directory, serverUrl: input.serverUrl?.toString() })
  return {
    // Observer channel. Plugin.init dispatches event hooks UNAWAITED and UNCAUGHT (binary L756291),
    // so an exception here would be an unhandled rejection - this handler must never throw.
    async event({ event }) {
      try {
        if (eventCount++ < 200) log("event", { type: event.type })
      } catch {}
    },
    "tool.execute.before": async (input, output) => {
      const started = Date.now()
      log("tool.execute.before:start", { tool: input.tool, callID: input.callID })
      if (MODE === "sleep") {
        await new Promise((resolve) => setTimeout(resolve, SLEEP_MS))
      } else if (MODE === "throw") {
        // exit-2-equivalent denial: failure-by-exception. Host converts to an errored tool part.
        throw new Error(`CS hook-experiment intentional deny (mode=throw, callID=${input.callID})`)
      }
      log("tool.execute.before:end", { tool: input.tool, elapsedMs: Date.now() - started })
      // output.args is mutable in place; deliberately left unmodified.
    },
    "tool.execute.after": async (input) => {
      log("tool.execute.after", { tool: input.tool, callID: input.callID })
    },
  }
}
