#!/usr/bin/env node
/**
 * Live catalog-input driver for TST-0169.
 *
 * Production persist/resume uses tools/lib/handled-ledger.mjs against a
 * caller-supplied durable --state-dir. Mutant persist/resume plants and
 * requires a sidecar under os.tmpdir() so the detector control can prove
 * a temp-dir dependency fails after a wiped TMPDIR.
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

function arg(name, fallback = "") {
  const i = process.argv.indexOf(name);
  return i >= 0 ? String(process.argv[i + 1] || "") : fallback;
}

const action = process.argv[2] || "";
const ledgerPath = arg("--ledger");
const stateDir = arg("--state-dir");
const key = arg("--key", "tst-0169");
const id = arg("--id", "run-mjs");

if (!action || !ledgerPath || !stateDir) {
  console.error(
    "FAILED:usage ledger_cli.mjs <persist|resume|mutant-persist|mutant-resume> --ledger PATH --state-dir PATH",
  );
  process.exit(2);
}

const mod = await import(pathToFileURL(path.resolve(ledgerPath)).href);
const { markHandled, isHandled } = mod;

if (action === "persist") {
  await markHandled(stateDir, {
    key,
    id,
    status: "done",
    meta: { engine: "handled-ledger.mjs" },
  });
  const ok = await isHandled(stateDir, { key, id });
  if (!ok) {
    console.error("FAILED:mjs persist did not round-trip");
    process.exit(1);
  }
  console.log(JSON.stringify({ action, stateDir, key, id, handled: true }));
  console.log("SUCCESS:mjs-cold-resume action=persist");
} else if (action === "resume") {
  const ok = await isHandled(stateDir, { key, id });
  if (!ok) {
    console.error("FAILED:mjs resume missed durable key after cold start");
    process.exit(1);
  }
  console.log(JSON.stringify({ action, stateDir, key, id, handled: true }));
  console.log("SUCCESS:mjs-cold-resume action=resume");
} else if (action === "mutant-persist") {
  await markHandled(stateDir, { key, id, status: "done" });
  const sidecar = path.join(os.tmpdir(), `${id}-volatile-sidecar.json`);
  fs.writeFileSync(sidecar, JSON.stringify({ key, id }));
  console.log(JSON.stringify({ action, sidecar }));
  console.log("SUCCESS:mjs-cold-resume action=mutant-persist");
} else if (action === "mutant-resume") {
  const sidecar = path.join(os.tmpdir(), `${id}-volatile-sidecar.json`);
  if (!fs.existsSync(sidecar)) {
    console.error("FAILED:TEMP-DEPENDENCY: volatile sidecar missing after cold start");
    process.exit(1);
  }
  console.log(JSON.stringify({ action, sidecar }));
  console.log("SUCCESS:mjs-cold-resume action=mutant-resume");
} else {
  console.error(`FAILED:unknown action ${action}`);
  process.exit(2);
}
