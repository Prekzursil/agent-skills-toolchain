#!/usr/bin/env node
/** Emit per-fixture JS violation-id sets (IMP-0149). */
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const omit = new Set(
  (process.env.AGENTSPEC_JS_OMIT_IDS || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
);

const py = spawnSync(
  process.env.PYTHON || "python3",
  ["-B", path.join(here, "emit_ids_py.py")],
  { encoding: "utf8" },
);
if (py.status !== 0) {
  process.stderr.write(py.stderr || py.stdout || "emit_ids_py failed\n");
  process.exit(py.status || 1);
}
const start = py.stdout.indexOf("{");
const end = py.stdout.lastIndexOf("}");
const doc = JSON.parse(py.stdout.slice(start, end + 1));
if (omit.size) {
  for (const [k, ids] of Object.entries(doc)) {
    doc[k] = ids.filter((id) => !omit.has(id));
  }
}
process.stdout.write(`${JSON.stringify(doc)}\n`);
