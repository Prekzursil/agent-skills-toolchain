/**
 * JS side of the BEHAVIOURAL parity oracle: drive the shared corpus, emit a manifest.
 *
 * Thin I/O shell by design. All the driver logic lives in `src/behaviour.mjs`, which the
 * coverage gate holds at 100% line+branch; `test/parity-shell.test.mjs` enforces that thinness
 * with a line budget so logic cannot migrate out of `src/` to dodge the gate.
 *
 * The manifest is written in BINARY with explicit LF — a text-mode write on Windows appends CR
 * and every byte comparison downstream becomes a false mismatch.
 */

import { Buffer } from "node:buffer";
import { readFileSync, writeFileSync } from "node:fs";
import process from "node:process";
import { fileURLToPath } from "node:url";

import { runCorpus } from "../src/behaviour.mjs";

const CORPUS = fileURLToPath(new URL("../fixtures/behaviour-corpus.json", import.meta.url));

const results = runCorpus(JSON.parse(readFileSync(CORPUS, "utf8")));
const lines = results.map(
  (result) => `${result.id}\t${Buffer.from(result.output, "utf8").toString("hex")}`,
);

writeFileSync(process.argv[2], Buffer.from(`${lines.join("\n")}\n`, "utf8"));
process.stdout.write(`SUCCESS:js-behaviour ${results.length} cases executed\n`);
