/**
 * JS side of the parity oracle: drive the shared corpus, emit a byte manifest.
 *
 * Thin I/O shell by design. All the corpus logic lives in `src/corpus.mjs`, which the coverage
 * gate holds at 100% line+branch; keeping this file trivial is what stops logic migrating into
 * an uncovered script. `test/parity-shell.test.mjs` enforces that thinness with a line budget.
 *
 * The manifest is written in BINARY with explicit LF — see the note in `emit_py.py`; a text-mode
 * write on Windows appends CR and every byte comparison downstream becomes a false mismatch.
 *
 * Exit 0 = every case matched its expectation. Exit 1 = at least one disagreed.
 */

import { Buffer } from "node:buffer";
import { readFileSync, writeFileSync } from "node:fs";
import process from "node:process";
import { fileURLToPath } from "node:url";

import { disagreements, runCorpus } from "../src/corpus.mjs";

const CORPUS = fileURLToPath(new URL("../fixtures/canonical-corpus.json", import.meta.url));

const corpus = JSON.parse(readFileSync(CORPUS, "utf8"));
const results = runCorpus(corpus);

const lines = results.map((result) => {
  const status = result.status === "ok" ? "OK" : "RJ";
  const payload =
    result.status === "ok" ? Buffer.from(result.output, "utf8").toString("hex") : result.output;
  return `${result.id}\t${status}\t${payload}`;
});

writeFileSync(process.argv[2], Buffer.from(`${lines.join("\n")}\n`, "utf8"));

const failed = disagreements(results);
for (const result of failed) {
  process.stderr.write(
    `FAILED:js-corpus ${result.id}: expected ${result.expected.status}/` +
      `${JSON.stringify(result.expected.output)}, got ${result.status}/${JSON.stringify(result.output)}\n`,
  );
}
if (failed.length > 0) {
  process.exit(1);
}
process.stdout.write(`SUCCESS:js-corpus ${results.length} cases matched the corpus expectation\n`);
