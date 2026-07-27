/**
 * THE PARITY ORACLE — run both runtimes over the shared corpus and compare BYTES.
 *
 * A single differing byte fails the run. This is the C9 acceptance criterion made executable:
 * a JS runtime that cannot reproduce the Python runtime's normalised receipt bytes exactly is
 * not a second runtime, it is a second dialect.
 *
 * Three independent gates, in order, because each can fail for a different reason:
 *   1. the PYTHON emitter agrees with the corpus expectations (else the Python encoder drifted);
 *   2. the JS emitter agrees with the corpus expectations (else the JS encoder drifted);
 *   3. the two manifests are byte-identical (else the two agree with the fixture but not with
 *      each other — which can only happen if the fixture itself under-specifies a case).
 *
 * Gate 3 is not redundant with 1 and 2: it is the one that still fires when a case is missing
 * an expectation, so the corpus cannot silently stop constraining a runtime.
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
const pyOut = join(workDir, "out_py.txt");
const jsOut = join(workDir, "out_js.txt");

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

run("python emitter", pythonCommand(), [join(HERE, "emit_py.py"), pyOut]);
run("js emitter", process.execPath, [join(HERE, "emit_js.mjs"), jsOut]);

const pyBytes = readFileSync(pyOut);
const jsBytes = readFileSync(jsOut);

if (!pyBytes.equals(jsBytes)) {
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
    `manifests differ in ${differing.length} line(s); ` +
      `py=${pyBytes.length} bytes, js=${jsBytes.length} bytes`,
  );
}

const caseCount = pyBytes.toString("utf8").trimEnd().split("\n").length;
if (caseCount === 0) {
  fail("the manifests are empty; an empty parity run passes vacuously");
}

rmSync(workDir, { recursive: true, force: true });
process.stdout.write(
  `SUCCESS:parity ${caseCount} cases, ${pyBytes.length} manifest bytes byte-identical ` +
    `across the Python and JS runtimes\n`,
);
