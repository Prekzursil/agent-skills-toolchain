#!/usr/bin/env node
/**
 * Monitor/dispatcher JavaScript reimplementation of the 12-condition
 * completion predicate (TST-0330 subject B). Table-driven, reverse-scan
 * then min-id pick. Independent of python_reducer.py.
 *
 * ESM (repo package.json has "type": "module"). CommonJS require() is
 * not defined here; stdin is node:fs, CLI is the default export path.
 *
 * TST0330_REDUCER_ROLE = "monitor-javascript"
 */

import fs from "node:fs";
import { pathToFileURL } from "node:url";

const TST0330_REDUCER_ROLE = "monitor-javascript";

const TERMINAL = {
  SUCCESS: true,
  FAILED: true,
  BLOCKED: true,
  TIMEOUT: true,
  SEVERED: true,
  PARTIAL: true,
};

const REASONS = {
  PARSE: "torn or non-object JSON",
  C01: "state is not a valid terminal",
  C02: "expected artifact does not exist",
  C03: "artifact empty or below min_bytes_threshold",
  C04: "artifact does not parse",
  C05: "required sentinel missing",
  C06: "required evidence anchors missing",
  C07: "required tests did not pass",
  C08: "negative controls did not fail as expected",
  C09: "independent reviewer status is not PASS",
  C10: "unresolved P0/P1 defect attached",
  C11: "output not registered in artifact manifest",
  C12: "downstream consumers cannot read it",
  COMPLETE: "all twelve conditions passed",
};

function canon(verdict) {
  return JSON.stringify(
    {
      failing_condition_id: Object.prototype.hasOwnProperty.call(
        verdict,
        "failing_condition_id"
      )
        ? verdict.failing_condition_id
        : null,
      reason: verdict.reason,
      verdict: verdict.verdict,
    },
    ["failing_condition_id", "reason", "verdict"]
  );
}

function malformed() {
  return {
    failing_condition_id: "PARSE",
    reason: REASONS.PARSE,
    verdict: "MALFORMED",
  };
}

function artOf(obj) {
  return obj && typeof obj.artifact === "object" && obj.artifact !== null
    ? obj.artifact
    : {};
}

function c01(obj) {
  return typeof obj.state === "string" && TERMINAL[obj.state] === true;
}

function c02(obj) {
  const art = obj.artifact;
  return !!art && typeof art === "object" && art.exists === true;
}

function c03(obj) {
  const art = artOf(obj);
  const n = Number(art.bytes == null ? 0 : art.bytes);
  if (!Number.isFinite(n)) return false;
  let floor = obj.min_bytes_threshold == null ? 128 : obj.min_bytes_threshold;
  floor = Number(floor);
  if (!Number.isFinite(floor)) return false;
  return n > 0 && n >= floor;
}

function c04(obj) {
  const art = artOf(obj);
  if (typeof art.body === "string") {
    try {
      const parsed = JSON.parse(art.body);
      return !!parsed && typeof parsed === "object" && !Array.isArray(parsed);
    } catch (_err) {
      return false;
    }
  }
  return art.parse_ok === true;
}

function c05(obj) {
  const uid = obj.unit_id;
  const sent = obj.sentinel;
  return typeof uid === "string" && uid.length > 0 && typeof sent === "string" && sent.indexOf(uid) !== -1;
}

function c06(obj) {
  const ev = obj.evidence;
  if (!Array.isArray(ev) || ev.length < 2) return false;
  for (let i = 0; i < ev.length; i += 1) {
    const item = ev[i];
    if (!item || typeof item !== "object") return false;
    const anchor = item.anchor;
    if (typeof anchor !== "string" || !anchor.trim()) return false;
  }
  return true;
}

function c07(obj) {
  const tests = obj.tests;
  if (!Array.isArray(tests) || tests.length === 0) return false;
  for (let i = 0; i < tests.length; i += 1) {
    const t = tests[i];
    if (!t || typeof t !== "object" || t.result !== "PASS") return false;
  }
  return true;
}

function c08(obj) {
  const ncs = obj.negative_controls;
  if (!Array.isArray(ncs) || ncs.length === 0) return false;
  for (let i = 0; i < ncs.length; i += 1) {
    const c = ncs[i];
    if (c && typeof c === "object" && c.fired_on_bad_state === true) return true;
  }
  return false;
}

function c09(obj) {
  const rev = obj.reviewer;
  return !!rev && typeof rev === "object" && rev.verdict === "PASS";
}

function c10(obj) {
  let defs = obj.defects;
  if (defs == null) defs = [];
  if (!Array.isArray(defs)) return false;
  for (let i = 0; i < defs.length; i += 1) {
    const d = defs[i];
    if (!d || typeof d !== "object") continue;
    const sev = String(d.severity || "").toUpperCase();
    const st = String(d.status || "").toLowerCase();
    if ((sev === "P0" || sev === "P1") && (st === "open" || st === "unresolved")) {
      return false;
    }
  }
  return true;
}

function c11(obj) {
  if (obj.manifest_registered === true) return true;
  const man = obj.manifest;
  return !!man && typeof man === "object" && man.registered === true;
}

function c12(obj) {
  const ds = obj.downstream;
  if (!Array.isArray(ds) || ds.length === 0) return false;
  for (let i = 0; i < ds.length; i += 1) {
    const x = ds[i];
    if (!x || typeof x !== "object" || x.read_ok !== true || x.executed !== true) {
      return false;
    }
  }
  return true;
}

const TABLE = [
  ["C12", c12],
  ["C11", c11],
  ["C10", c10],
  ["C09", c09],
  ["C08", c08],
  ["C07", c07],
  ["C06", c06],
  ["C05", c05],
  ["C04", c04],
  ["C03", c03],
  ["C02", c02],
  ["C01", c01],
];

function evaluateObject(obj, skip) {
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) return malformed();
  const skipped = skip || {};
  const fails = [];
  for (let i = 0; i < TABLE.length; i += 1) {
    const cid = TABLE[i][0];
    const fn = TABLE[i][1];
    if (skipped[cid]) continue;
    if (!fn(obj)) fails.push(cid);
  }
  fails.sort();
  if (fails.length === 0) {
    return {
      failing_condition_id: null,
      reason: REASONS.COMPLETE,
      verdict: "COMPLETE",
    };
  }
  const first = fails[0];
  return {
    failing_condition_id: first,
    reason: REASONS[first],
    verdict: "INCOMPLETE",
  };
}

function evaluateRow(row, skip) {
  if (!row || typeof row !== "object") return malformed();
  if (row.kind === "raw") {
    if (typeof row.raw !== "string") return malformed();
    try {
      const obj = JSON.parse(row.raw);
      return evaluateObject(obj, skip);
    } catch (_err) {
      return malformed();
    }
  }
  if (row.kind === "object") return evaluateObject(row.state, skip);
  return malformed();
}

function parseSkip(argv) {
  const skip = {};
  for (let i = 2; i < argv.length; i += 1) {
    if (argv[i] === "--skip" && argv[i + 1]) {
      skip[argv[i + 1]] = true;
      i += 1;
    }
  }
  return skip;
}

function readStdin() {
  return fs.readFileSync(0, "utf8");
}

function main() {
  const skip = parseSkip(process.argv);
  const rows = JSON.parse(readStdin());
  const out = [];
  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i];
    const verdict = evaluateRow(row, skip);
    out.push({
      id: row.id,
      canonical: canon(verdict),
      verdict: verdict,
    });
  }
  process.stdout.write(JSON.stringify(out) + "\n");
}

const invokedAsCli =
  Boolean(process.argv[1]) &&
  import.meta.url === pathToFileURL(process.argv[1]).href;
if (invokedAsCli) {
  main();
}

export { TST0330_REDUCER_ROLE, evaluateRow, canon };
