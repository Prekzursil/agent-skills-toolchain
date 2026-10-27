/**
 * THE ANTI-BLINDNESS GATE. Read this before touching `package.json`'s test script.
 *
 * MEASURED TRAP: `node --test --experimental-test-coverage` does NOT see a source file that no
 * test imports. The file is absent from the coverage table entirely — not listed at 0% — and
 * the run exits 0 reporting "all files 100.00". Reproduced on Node v22.23.1 AND v24.16.0. A
 * "100% coverage" claim from a bare run is therefore MEANINGLESS on its own.
 *
 * `--test-coverage-include='src/**'` does NOT fix it: measured, it FILTERS the already-loaded
 * set and never force-loads, so the orphan stays absent and the run still exits 0. A barrel
 * alone does not fix it either: a new file nobody adds to the barrel stays invisible.
 *
 * What DOES fix it, and is proven RED-then-GREEN in this lane's report:
 *   1. this test walks `src/` on DISK and dynamically imports every module it finds, which
 *      forces each one into the coverage table at its TRUE rate;
 *   2. it cross-checks the disk walk against `MODULES`, an independently written literal, so a
 *      new file also has to be declared;
 *   3. `package.json` passes all THREE thresholds. Lines alone is not enough — a never-executed
 *      file reports `branch 100.00` while `funcs` is 0.00, so a branches-only gate stays blind.
 *   4. `--test-coverage-exclude=test/**` (NOT `--test-coverage-include=src/**`): exclude is
 *      default-IN, so a stray source file outside `src/` is still measured. Include is
 *      default-OUT, i.e. fail-open — the same bug class as the trap itself.
 */

import assert from "node:assert/strict";
import { readdir } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

import { MODULES } from "../src/index.mjs";

const SRC_DIR = fileURLToPath(new URL("../src/", import.meta.url));

async function walkSources(directory) {
  const found = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const full = `${directory}${entry.name}`;
    if (entry.isDirectory()) {
      found.push(...(await walkSources(`${full}/`)));
    } else if (entry.name.endsWith(".mjs")) {
      found.push(full);
    }
  }
  return found.sort();
}

test("the src walk finds files at all", async () => {
  const files = await walkSources(SRC_DIR);
  // A broken glob finding zero files must FAIL. Silence from an empty walk reads as a pass and
  // is how a census gate quietly stops measuring anything.
  assert.ok(files.length > 0, "walked src/ and found no .mjs files");
  assert.ok(files.length >= 15, `expected the full module set, found only ${files.length}`);
});

test("the declared module set equals the module set ON DISK", async () => {
  const files = await walkSources(SRC_DIR);
  const onDisk = files.map((file) => file.slice(SRC_DIR.length).replace(/\.mjs$/u, "")).sort();
  assert.deepEqual(
    onDisk,
    [...MODULES].sort(),
    "src/ and index.mjs MODULES disagree: add the new module to the barrel AND to MODULES",
  );
});

test("every source module is force-loaded, so none can hide from the coverage table", async () => {
  const files = await walkSources(SRC_DIR);
  const loaded = [];
  for (const file of files) {
    const module = await import(pathToFileURL(file).href);
    assert.ok(module !== null, `${file} imported as null`);
    loaded.push(file);
  }
  assert.equal(loaded.length, files.length);
  assert.equal(loaded.length, MODULES.length);
});

test("the barrel exposes every module as a namespace", async () => {
  const barrel = await import("../src/index.mjs");
  for (const name of MODULES) {
    if (name === "index") {
      continue;
    }
    assert.equal(typeof barrel[name], "object", `barrel is missing the ${name} namespace`);
    assert.ok(Object.keys(barrel[name]).length > 0, `barrel namespace ${name} is empty`);
  }
});
