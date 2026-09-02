#!/usr/bin/env node
/**
 * Live SUT driver for TST-0187: call tools/lib/codex-invocation.mjs
 * createCodexExecPlan and print the spawn plan. Python measures argv length
 * and feeds the prompt file to child_echo.py --stdin.
 */
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createCodexExecPlan } from "../../../../tools/lib/codex-invocation.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "../../../..");

function argValue(flag) {
  const i = process.argv.indexOf(flag);
  if (i < 0 || i + 1 >= process.argv.length) return null;
  return process.argv[i + 1];
}

const promptFileIn = argValue("--prompt-file");
const dir = argValue("--dir");
if (!promptFileIn || !dir) {
  process.stderr.write("usage: js_plan.mjs --prompt-file PATH --dir DIR\n");
  process.exit(2);
}

const prompt = await fs.readFile(promptFileIn, "utf8");
await fs.mkdir(dir, { recursive: true });
const plan = await createCodexExecPlan({
  prompt,
  workspaceDir: repo,
  promptDir: dir,
  platform: "linux",
  env: {},
});

process.stdout.write(
  JSON.stringify({
    command: plan.command,
    args: plan.args,
    shell: plan.shell,
    cwd: plan.cwd,
    promptFile: plan.promptFile,
    stdin: plan.stdin,
    repo,
  }) + "\n"
);
