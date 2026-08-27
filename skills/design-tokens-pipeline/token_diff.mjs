#!/usr/bin/env node
// token_diff.mjs — diff two DTCG token files and emit BOTH the forward change
// set AND the inverse patch. The inverse patch IS the lossless revert surface
// the TCR loop relies on (DESIGN-WORKFLOW §G6: "every apply-back is a
// reversible commit; revert anything that regresses a tracked axis"; tokens
// are "the only thing that round-trips cleanly").
//
// Usage: node token_diff.mjs --before old.json --after new.json [--out diff.json] [--revert revert.json]
//   --before / --after   the two DTCG trees to compare.
//   --out                write the full diff report (default: stdout).
//   --revert             ALSO write a DTCG tree that, applied over `after`,
//                        restores `before` exactly (the revert artifact).
//
// Emits SUCCESS:design-tokens-diff <added>+<removed>+<changed> / FAILED:...
import { readFileSync, writeFileSync } from "node:fs";
import { parseArgs, flatten, unflatten, emitMarker } from "./lib.mjs";

const ID = "design-tokens-diff";

function load(path) {
  return flatten(JSON.parse(readFileSync(path, "utf8")));
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.before || !args.after) return process.exit(emitMarker(false, ID, "need --before and --after"));
  let a, b;
  try {
    a = load(String(args.before));
    b = load(String(args.after));
  } catch (e) {
    return process.exit(emitMarker(false, ID, e.message));
  }

  const added = [];   // present in after, not before
  const removed = []; // present in before, not after
  const changed = []; // present in both, value or type differs
  const revertEntries = []; // applied on `after` -> restores `before`

  for (const [path, leaf] of b) {
    if (!a.has(path)) {
      added.push({ path, value: leaf.value, type: leaf.type });
    } else {
      const prev = a.get(path);
      if (prev.value !== leaf.value || prev.type !== leaf.type) {
        changed.push({ path, before: prev, after: leaf });
        revertEntries.push([path, prev]); // restore old value
      }
    }
  }
  for (const [path, leaf] of a) {
    if (!b.has(path)) {
      removed.push({ path, value: leaf.value, type: leaf.type });
      revertEntries.push([path, leaf]); // re-add removed token
    }
  }
  // Note: tokens ADDED in `after` cannot be "un-added" by an overlay patch
  // alone — they are listed under report.revertDeletes for a git-level removal.
  const report = {
    id: ID,
    before: String(args.before),
    after: String(args.after),
    summary: { added: added.length, removed: removed.length, changed: changed.length },
    added, removed, changed,
    revertDeletes: added.map((t) => t.path), // paths a revert must DELETE
  };

  if (args.out) writeFileSync(String(args.out), JSON.stringify(report, null, 2) + "\n");
  else process.stdout.write(JSON.stringify(report, null, 2) + "\n");

  if (args.revert) {
    writeFileSync(String(args.revert), JSON.stringify(unflatten(revertEntries), null, 2) + "\n");
    process.stderr.write(`revert overlay -> ${args.revert} (also delete: ${report.revertDeletes.join(", ") || "none"})\n`);
  }

  process.exit(emitMarker(true, ID, `${added.length}+${removed.length}+${changed.length}`));
}

main();
