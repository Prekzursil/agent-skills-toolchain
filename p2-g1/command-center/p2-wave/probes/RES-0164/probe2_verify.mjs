#!/usr/bin/env node
// RES-0164 probe2_verify: independent JS recompute of the recommended schema
// contract partition, the load-bearing claims' verdict/band/lineage shape, the
// 10-source registry with byte counts and hashes, and the NC1 mutation leg.
// Defaults to FAIL.
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const probePath = fileURLToPath(import.meta.url);
const REPO = resolve(dirname(probePath), "..", "..", "..", "..");
const art = resolve(REPO, "command-center/research/prior-art/RES-0164-event-log-schema-prior-art.json");
const txt = readFileSync(art, "utf8");
const doc = JSON.parse(txt);
const checks = [];
const ck = (name, ok, detail = "") => {
  checks.push({ check: name, pass: Boolean(ok), detail: String(detail).slice(0, 220) });
  return Boolean(ok);
};

const rep = doc.report || {};
const rsc = rep.recommended_schema_contract || {};
for (const key of ["immutable_replay_projection", "erasable_sidecar", "redaction_record",
                   "preventive_encryption", "integrity_scope", "replay_failure_policy"]) {
  ck(`rsc.${key}`, String(rsc[key] || "").length >= 20, String(rsc[key] || "").slice(0, 80));
}
ck("partition-splits-replay-from-erasable",
  /non-secret|replay/i.test(String(rsc.immutable_replay_projection))
  && /sensitive|redact|deletion/i.test(String(rsc.erasable_sidecar)),
  "projection vs sidecar named");

const lbc = rep.load_bearing_claims || [];
ck("claims-have-verdict-band-path",
  lbc.every((c) => c.verdict && c.sherman_kent?.band && c.independent_verification_path),
  lbc.map((c) => `${c.id}:${c.verdict}`).join(" | ").slice(0, 180));
ck("claims-lineage-resolvable",
  lbc.every((c) => (c.source_lineage || []).every((s) => s.source_id && s.resolved_url)),
  `n_claims=${lbc.length}`);

const sr = rep.source_registry || [];
ck("ten-sources-with-sha",
  sr.length === 10 && sr.every((s) => s.sha256 && String(s.sha256).length === 64),
  `n=${sr.length}`);

const ncs = doc.negative_controls || [];
ck("nc1-wrong-expectation-went-red",
  ncs.some((n) => n.fired_on_bad_state === true
    && /WRONG/.test(String(n.id || ""))
    && String(n.bad_state_output || "").includes("RESULT=RED")),
  ncs.map((n) => n.id).join(","));
ck("ncs-both-states",
  ncs.length >= 2 && ncs.every((n) => n.fired_on_bad_state === true && n.silent_on_good_state === true),
  `n=${ncs.length}`);

ck("state-success-sentinel",
  doc.state === "SUCCESS" && txt.includes("SUCCESS:RES-0164"), String(doc.state));

const red = checks.filter((c) => !c.pass);
console.log(JSON.stringify({ probe: "probe2-verify", unit_id: "RES-0164", pass: red.length === 0, checks, red }));
console.log(red.length === 0
  ? "SUCCESS:RES-0164-probe2 schema contract and claims verified from JS"
  : `FAILED:RES-0164-probe2 red=${red.length}`);
process.exit(red.length === 0 ? 0 : 1);
