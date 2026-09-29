#!/usr/bin/env node
// hide-spawn.mjs — windowsHide stdio wrapper (estate terminal-spam fix, 2026-09-26).
// Usage: node hide-spawn.mjs <command> [args...]
//
// WHY: console-class MCP servers (python/cmd/java) spawned by GUI parents
// (ZCode, Grok Bot) allocate a VISIBLE console window per spawn unless created
// with windowsHide. This wrapper adds exactly that flag while keeping stdio
// transparent for the MCP client, so configs can point at it without any
// change to the wrapped server.
import { spawn } from "node:child_process";

const [command, ...args] = process.argv.slice(2);
if (!command) {
  console.error("hide-spawn: no command given");
  process.exit(2);
}

const child = spawn(command, args, {
  stdio: "inherit",
  windowsHide: true,
  env: process.env,
});

child.on("error", (err) => {
  console.error("hide-spawn: spawn failed:", err.message);
  process.exit(127);
});

child.on("exit", (code, signal) => {
  if (signal) {
    try { process.kill(process.pid, signal); } catch { process.exit(1); }
  } else {
    process.exit(code ?? 0);
  }
});

// Forward teardown signals so session shutdown takes the wrapped server down too.
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"]) {
  process.on(sig, () => {
    try { child.kill(sig); } catch { /* child already gone */ }
  });
}
