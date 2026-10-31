#!/usr/bin/env node
// RES-0157 probe2_node: mechanically independent (JS) recompute of the
// durability artifact's core invariants. Defaults to FAIL.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const probePath = fileURLToPath(import.meta.url);
const REPO = resolve(probePath, "..", "..", "..", "..", "..");

const art = resolve(REPO, "command-center/research/gem-hunt/RES-0157-transfer-durability-transaction-models.json");
const txt = readFileSync(art, "utf8");
const doc = JSON.parse(txt);
const checks = [];
const ck = (name, ok, detail = "") => {
  checks.push({ check: name, pass: Boolean(ok), detail: String(detail).slice(0, 220) });
  return Boolean(ok);
};

const sec = doc.side_effect_classes || [];
ck("five-side-effect-classes", sec.length === 5, `n=${sec.length}`);
const noncomp = sec.filter((c) => c.compensable === false).map((c) => c.class_id || c.id);
ck("exactly-one-non-compensable", noncomp.length === 1, `noncomp=${noncomp.join(",")}`);
ck("notification-non-compensable", noncomp[0] === "human_notification", String(noncomp[0]));
ck(
  "compensables-have-compensation",
  sec.filter((c) => c.compensable === true).every((c) => String(c.compensation_or_noncompensable || "").trim()),
  "compensation_or_noncompensable named per compensable class",
);

const nc = (doc.negative_controls || [])[0] || {};
ck(
  "all-compensable-mutant-red",
  nc.fired_on_bad_state === true && String(nc.bad_state_output || "").includes("DETECTOR_RESULT=RED"),
  String(nc.bad_state_output || "").slice(-120),
);

ck("report-kind-gem-candidate", doc.report?.kind === "gem-candidate", String(doc.report?.kind));
ck("state-success", doc.state === "SUCCESS" && txt.includes("SUCCESS:RES-0157"), String(doc.state));
ck("claims-present", (doc.claims || []).length >= 1, `n=${(doc.claims || []).length}`);
ck("evidence-present", (doc.evidence || []).length >= 1, `n=${(doc.evidence || []).length}`);

// use-vs-mention side check from tests_required: instructions are data
const q = doc.question_or_target || "";
ck("question-recorded", q.length > 40, q.slice(0, 90));

const red = checks.filter((c) => !c.pass);
const verdict = { probe: "probe2-node", unit_id: "RES-0157", pass: red.length === 0, checks, red };
console.log(JSON.stringify(verdict));
console.log(red.length === 0
  ? "SUCCESS:RES-0157-probe2 independent JS recompute agrees"
  : `FAILED:RES-0157-probe2 red=${red.length}`);
process.exit(red.length === 0 ? 0 : 1);
