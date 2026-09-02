/**
 * THE PARITY ORACLE — run both runtimes over the shared corpora and compare BYTES.
 *
 * A single differing byte fails the run. This is the C9 acceptance criterion made executable:
 * a JS runtime that cannot reproduce the Python runtime's normalised bytes exactly is not a
 * second runtime, it is a second dialect.
 *
 * TWO corpora, because "the same bytes" turned out to be two claims:
 *
 *   1. `canonical` — the SERIALISER. Both sides encode the same values and the manifests must
 *      match byte for byte.
 *   2. `behaviour` — the DECISION FUNCTIONS. Added after a measured failure of the first gate
 *      to say anything at all about them: `emit_py.py` imports only `dumpb`, so `judge`,
 *      `missingFields`, `buildArgv`, `checkDispatch` and `planRetry` were never cross-checked.
 *      An independent 483-case differential harness then found **78 outcome divergences** while
 *      both unit suites were green at 100% line+branch — including `judge` reporting SUCCESS on
 *      one runtime and `severed-stream` on the other for identical receipt bytes.
 *
 * Per corpus, three gates in order, because each fails for a different reason:
 *   a. the PYTHON emitter runs clean (else the Python side crashed, not merely disagreed);
 *   b. the JS emitter runs clean;
 *   c. the two manifests are byte-identical.
 *
 * The canonical emitters ALSO check each case against a declared expectation, so gate (c) is not
 * redundant: it is the one that still fires when a case is missing an expectation, i.e. when the
 * fixture itself has stopped constraining a runtime.
 *
 * Zero dependencies. Usage: `node parity/oracle.mjs` (from tools/agentspec-js).
 */

import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const workDir = mkdtempSync(join(tmpdir(), "agentspec-parity-"));

const CORPORA = [
  { name: "canonical", py: "emit_py.py", js: "emit_js.mjs" },
  { name: "behaviour", py: "emit_behaviour_py.py", js: "emit_behaviour_js.mjs" },
];

/** Windows ships `python`; the ubuntu CI runner ships `python3`. Try both, in that order. */
function pythonCommand() {
  for (const candidate of [process.env.AGENTSPEC_PYTHON, "python3", "python"]) {
    if (candidate === undefined) {
      continue;
    }
    const probe = spawnSync(candidate, ["--version"], { encoding: "utf8" });
    if (probe.status === 0) {
      return candidate;
    }
  }
  fail("no working python interpreter found (tried $AGENTSPEC_PYTHON, python3, python)");
  return "";
}

function fail(message) {
  process.stderr.write(`FAILED:parity ${message}\n`);
  rmSync(workDir, { recursive: true, force: true });
  process.exit(1);
}

function run(label, command, args) {
  const result = spawnSync(command, args, { encoding: "utf8", cwd: HERE });
  process.stdout.write(result.stdout ?? "");
  if (result.status !== 0) {
    process.stderr.write(result.stderr ?? "");
    fail(`${label} exited ${result.status}`);
  }
}

function compare(name, pyBytes, jsBytes) {
  if (pyBytes.equals(jsBytes)) {
    return;
  }
  const pyLines = pyBytes.toString("utf8").split("\n");
  const jsLines = jsBytes.toString("utf8").split("\n");
  const differing = [];
  for (let index = 0; index < Math.max(pyLines.length, jsLines.length); index += 1) {
    if (pyLines[index] !== jsLines[index]) {
      differing.push(`  line ${index + 1}:\n    py: ${pyLines[index]}\n    js: ${jsLines[index]}`);
    }
  }
  process.stderr.write(`${differing.slice(0, 10).join("\n")}\n`);
  fail(
    `${name} manifests differ in ${differing.length} line(s); ` +
      `py=${pyBytes.length} bytes, js=${jsBytes.length} bytes`,
  );
}

const python = pythonCommand();
const summary = [];

for (const corpus of CORPORA) {
  const pyOut = join(workDir, `${corpus.name}_py.txt`);
  const jsOut = join(workDir, `${corpus.name}_js.txt`);
  run(`${corpus.name} python emitter`, python, [join(HERE, corpus.py), pyOut]);
  run(`${corpus.name} js emitter`, process.execPath, [join(HERE, corpus.js), jsOut]);
  const pyBytes = readFileSync(pyOut);
  const jsBytes = readFileSync(jsOut);
  compare(corpus.name, pyBytes, jsBytes);
  const caseCount = pyBytes.toString("utf8").trimEnd().split("\n").length;
  if (pyBytes.length === 0) {
    fail(`the ${corpus.name} manifests are empty; an empty parity run passes vacuously`);
  }
  summary.push(`${corpus.name}=${caseCount} cases/${pyBytes.length} bytes`);
}

rmSync(workDir, { recursive: true, force: true });
process.stdout.write(
  `SUCCESS:parity byte-identical across the Python and JS runtimes (${summary.join(", ")})\n`,
);
