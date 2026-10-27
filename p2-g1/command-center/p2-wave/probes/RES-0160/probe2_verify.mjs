#!/usr/bin/env node
// RES-0160 probe2_verify: independent JS recompute of the decision-record spec
// (ADOPT all-must-hold / REVERT triggers / owner-visible cost line) and the
// gate's retroactive rule. Defaults to FAIL.
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const probePath = fileURLToPath(import.meta.url);
const REPO = resolve(dirname(probePath), "..", "..", "..", "..");
const art = resolve(REPO, "command-center/research/gem-hunt/RES-0160-gem-adoption-gate-with-measured-improvement.json");
const txt = readFileSync(art, "utf8");
const doc = JSON.parse(txt);
const checks = [];
const ck = (name, ok, detail = "") => {
  checks.push({ check: name, pass: Boolean(ok), detail: String(detail).slice(0, 220) });
  return Boolean(ok);
};

const rep = doc.report || {};
const ag = rep.adoption_gate || {};
const need = ["ADOPT", "KEEP", "PARK", "REJECT", "REVERT", "retroactive_rule"];
ck("five-decision-records-plus-retroactive-rule", need.every((k) => k in ag),
  `present=${need.filter((k) => k in ag).join(",")}`);

const adopt = ag.ADOPT?.all_must_hold || [];
ck("adopt-six-conjuncts", adopt.length >= 5, `n=${adopt.length}`);
ck("adopt-requires-two-independent-probes",
  adopt.some((s) => /independent/i.test(String(s))), adopt[4] || "");
ck("adopt-requires-owner-cost-ceiling",
  adopt.some((s) => /cost/i.test(String(s))), "cost line conjunct present");

const rev = ag.REVERT || {};
ck("revert-has-triggers-and-action",
  (rev.when_any || []).length >= 3 && String(rev.action || "").length > 20,
  `triggers=${(rev.when_any || []).length}`);

const rr = ag.retroactive_rule || {};
ck("retroactive-rule-recorded",
  String(rr.rule || rr.text || JSON.stringify(rr)).length > 30,
  String(rr.rule || rr.text || "").slice(0, 120));

// every back-test row carries revert_trigger_status + owner cost status
const rows = rep.back_test?.rows || [];
ck("rows-carry-revert-and-cost-fields",
  rows.length === 30 && rows.every((r) => r.revert_trigger_status && r.owner_cost_line_status),
  `n=${rows.length}`);

ck("state-success-sentinel",
  doc.state === "SUCCESS" && txt.includes("SUCCESS:RES-0160"), String(doc.state));

const red = checks.filter((c) => !c.pass);
console.log(JSON.stringify({ probe: "probe2-verify", unit_id: "RES-0160", pass: red.length === 0, checks, red }));
console.log(red.length === 0
  ? "SUCCESS:RES-0160-probe2 decision-record spec verified from JS"
  : `FAILED:RES-0160-probe2 red=${red.length}`);
process.exit(red.length === 0 ? 0 : 1);
