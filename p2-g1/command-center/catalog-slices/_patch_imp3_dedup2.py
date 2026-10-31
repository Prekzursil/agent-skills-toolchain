"""Second de-dup pass: cede the workflow FUSION / CERTIFICATION / META surface to bucket
B04 (WFA-2.json, phase 2B) and refill with 9 distinct units.

WHY: a direct title read of WFA-2's 24 phase-2B units shows it already owns fusion
lineage + decomposition round-trip (WFA-0138), the pairwise tournament runner (WFA-0132),
decertification and supersession (WFA-0137, WFA-0142), the >=96 semantic non-duplication
proof (WFA-0136), workflow-scout (WFA-0143) and workflow-forge (WFA-0144), the
find/repair/merge/build recommendation (WFA-0146), the capability-loss and
control-plane-singularity gates on fusion (WFA-0140, WFA-0141) and workflow pack
packaging (WFA-0152). Token-Jaccard scored my nearest pair at 0.237, well under any
threshold - lexical similarity is a BROKEN detector for this, twice now.

The spec itself double-lists this surface (Phase 2B builds the foundry pipeline at
10729-10744; Phase 7 ships scout/forge at 10913), so the overlap is spec-inherited, not
invented. Program-wide only one owner may hold it. B04 already does.

MY RETAINED PHASE-7 SCOPE after this pass: the typed workflow RUNTIME only - schema, SDK,
builder, parameters, subworkflows, fan-out, barriers, loops, checkpoints, retry, repair,
resume, replay, cache, dry-run, estimation, policy, routing, failure policy, blackboard,
heartbeat, idempotency, harvest, in-flight migration, isolation, docs, observability,
manifest. No fusion, no certification, no meta-workflows.

Replacement is IN PLACE by id so every other unit's dependencies stay valid; dependencies
pointing at a ceded id are repointed at the WFA unit that now owns it, and an unmapped
reference is a hard failure rather than a silent dangle.
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "IMP-3.json")
data = json.loads(io.open(SRC, encoding="utf-8").read())
assert len(data) == 128

CORP = "C:/Users/Prekzursil/.claude/harness-restore-20260806"
SPEC = CORP + "/_USER-PROMPTS.md"
A_PRED = SPEC + ":10627-10648"
A_SCALE = SPEC + ":10570-10584"
A_P7 = SPEC + ":10873-10913"
A_P7A = SPEC + ":10915-10946"
A_P2C = SPEC + ":10746-10767"
A_CPROD = SPEC + ":11172-11244"
A_FAIL = SPEC + ":11298-11347"
C_SPEC = CORP + "/11-COUNCIL-SPECIFICATION.md"
C_SCHEMA = CORP + "/11-COUNCIL-SPECIFICATION.schema.json"
P7 = [A_P7, A_PRED]
P7A = [A_P7A, A_P2C, A_CPROD, C_SPEC, C_SCHEMA]

R_PIVOT = ("two strikes then pivot (AGENTS.md 4b): after two failures sharing an error "
           "fingerprint, enumerate >=2 alternative designs before a third attempt")
REV_SOLO = ("one independent adversarial reviewer in a fresh context who did not author the "
            "module and starts from the tests, not the author's summary")
REV_OWNER = ("one independent adversarial reviewer plus an explicit owner sign-off block in the "
             "receipt; the reviewer may not grant the owner half")
T_W = ["Read", "Write", "Edit", "Grep", "Glob", "Bash"]
T_WP = ["Read", "Write", "Edit", "Grep", "Glob", "Bash", "PowerShell"]
M_OPUS = {"vendor": "anthropic", "model": "opus", "role": "implementer"}

# ceded id -> the B04/WFA unit that now owns the mechanism
CEDE = {
    "IMP-0276": "WFA-0152",   # portable workflow pack packaging / versioning / publication
    "IMP-0277": "WFA-0136",   # semantic non-duplication proof for the >=96 catalog
    "IMP-0278": "WFA-0140",   # fusion engine + capability-loss / control-plane gates
    "IMP-0279": "WFA-0138",   # fusion lineage record and decomposition round trip
    "IMP-0280": "WFA-0132",   # pairwise workflow tournament runner
    "IMP-0281": "WFA-0137",   # decertification / supersession lifecycle
    "IMP-0282": "WFA-0143",   # workflow-scout
    "IMP-0283": "WFA-0144",   # workflow-forge
    "IMP-0353": "WFA-0136",   # blueprint distinctness gate
}
ORDER = ["IMP-0276", "IMP-0277", "IMP-0278", "IMP-0279", "IMP-0280", "IMP-0281",
         "IMP-0282", "IMP-0283", "IMP-0353"]

NEW = {}


def put(slot, phase, title, q, inputs, deps, ev, tests, **kw):
    NEW[slot] = dict(phase=phase, title=title, q=q, inputs=inputs, deps=deps, ev=ev,
                     tests=tests, kw=kw)


put("IMP-0276", "7", "Downstream-consumer readability contract at every stage boundary",
    "Implement tools/foundry/consume.py enforcing predicate condition 12 - that a produced "
    "artifact can actually be READ by its declared downstream consumers - by executing each "
    "consumer's parser against the artifact at production time. Falsifiable question: does a "
    "stage ever complete with an artifact that its own declared consumer cannot parse, and is "
    "readability checked by RUNNING the consumer parser rather than by matching a file extension?",
    P7 + [A_PRED],
    ["IMP-0257", "IMP-0263"],
    "1) each declared consumer's parser executed against the produced artifact, with failures "
    "listed by consumer id; 2) an extension-only check run alongside, and the cases where the two "
    "disagree published.",
    ["unit: consumer-parser execution across 6 artifact types",
     "negative control: hand a consumer a well-named but malformed artifact and assert the "
     "extension-only check passes while the execution check FAILS"],
    to=2700)

put("IMP-0277", "7", "Concurrency fairness across sibling workflow runs",
    "Implement tools/foundry/fairness.py so one large run cannot starve concurrent sibling runs of "
    "the shared worker pool, using per-run shares rather than global FIFO. Falsifiable question: "
    "with one 200-child run and one 3-child run submitted together, what is the small run's "
    "completion latency under FIFO versus fair-share, measured rather than argued?",
    P7 + [A_SCALE],
    ["IMP-0262"],
    "1) measured completion latency for the small run under both policies on identical inputs; 2) "
    "a per-run share accounting trace summing to the configured pool size.",
    ["load: 200-child vs 3-child co-submission under both policies",
     "negative control: set all shares equal to the pool size and assert starvation reappears, "
     "proving the measurement is sensitive to the policy"],
    to=5400, sub="cloud-batch")

put("IMP-0278", "7", "Owner-facing run audit-trail export",
    "Implement tools/foundry/audit_export.py producing a single portable record of who ran what, "
    "when, under which tool policy, with which model routing and at what cost. Falsifiable "
    "question: can the exported trail be reconstructed offline with no live service call, and does "
    "it ever contain a credential or raw prompt body the retention policy forbids?",
    P7 + [A_FAIL, SPEC + ":11345"],
    ["IMP-0269", "IMP-0273"],
    "1) an offline export with egress blocked, validated against the trail schema; 2) a "
    "credential and prompt-body scan over the exported file across four encodings.",
    ["integration: offline export completeness against a recorded run",
     "security: 4-encoding secret scan on the export",
     "negative control: disable redaction and assert the scan FIRES on all four encodings"],
    to=2700, sub="local-serialized", tools=T_WP)

put("IMP-0279", "7", "Graceful degradation when an optional tool or MCP is unavailable",
    "Implement tools/foundry/degrade.py so a stage whose optional capability is missing degrades "
    "LOUDLY - completing with a recorded reduced-capability marker - rather than silently "
    "producing a thinner result that reads as complete. Falsifiable question: is a degraded result "
    "distinguishable from a full one by a downstream consumer that never read the logs?",
    P7 + [SPEC + ":10983", A_PRED],
    ["IMP-0275", "IMP-0263"],
    "1) a degraded artifact carrying a machine-readable reduced-capability marker, asserted by the "
    "consumer; 2) a capability-availability probe recorded at run time rather than assumed from "
    "config.",
    ["integration: run with an optional MCP disabled",
     "negative control: strip the marker and assert the degraded and full artifacts become "
     "indistinguishable, proving the marker is load-bearing"],
    to=2700, sub="local-serialized", tools=T_WP,
    fc=["uncontrolled-silence", "overclaim", "detector-failure", "green-not-live"])

put("IMP-0280", "7A", "Evidence freshness and revalidation gate",
    "Implement tools/council/evidence/freshness.py stamping every evidence anchor with an "
    "as-of date and refusing to let a stale anchor carry a binding decision without revalidation. "
    "Falsifiable question: how many anchors in a recorded council are older than the configured "
    "freshness window, and does revalidation actually re-read the source rather than re-reading a "
    "cached copy of it?",
    P7A + [SPEC + ":10714"],
    ["IMP-0333", "IMP-0328"],
    "1) an age histogram of anchors at decision time; 2) a cache-bypass proof that revalidation "
    "issued a real read, verified from the transport layer rather than the cache's own report.",
    ["unit: freshness window enforcement per evidence class",
     "negative control: point revalidation at the cache and assert the transport-layer check FIRES"],
    to=2700)

put("IMP-0281", "7A", "Precedent retrieval from prior councils",
    "Implement tools/council/precedent.py surfacing prior councils that already settled the same or "
    "an overlapping question, so a settled question is not silently re-deliberated. Falsifiable "
    "question: on a corpus of recorded councils, what is the retrieval recall for a known-repeated "
    "question, and does the retriever surface a superseded decision without its supersession "
    "marker?",
    P7A + [A_CPROD],
    ["IMP-0335", "IMP-0323"],
    "1) recall measured against a planted repeated-question control; 2) a supersession-marker check "
    "on every returned precedent.",
    ["control: planted repeated question must be retrieved",
     "negative control: a superseded decision returned without its marker must FAIL the check",
     "control: a genuinely novel question must return no precedent (false-positive rate reported)"],
    to=2700)

put("IMP-0282", "7A", "Council-claim registration into the program claim registry",
    "Implement tools/council/artifacts/claims.py emitting every load-bearing council claim into "
    "CLAIM-REGISTRY.json with a stable claim id, canonical mechanism, verification status and the "
    "exact settling probe. Falsifiable question: does every claim that influenced the decision "
    "reach the registry, and can a registered claim carry status VERIFIED without a resolvable "
    "evidence anchor?",
    P7A + [SPEC + ":10662-10679", "command-center/CLAIM-REGISTRY.json"],
    ["IMP-0333", "IMP-0331"],
    "1) a decision-to-registry coverage count with unregistered influential claims listed; 2) an "
    "anchor-resolution pass over every VERIFIED claim.",
    ["unit: claim record schema and status transitions",
     "invariant: VERIFIED requires a resolvable anchor",
     "negative control: mark an unanchored claim VERIFIED and assert the resolution pass FIRES"],
    to=2700)

put("IMP-0283", "7A", "Live-run determinism: per-seat sampling parameters pinned and recorded",
    "Implement tools/council/determinism.py pinning and RECORDING each participant's sampling "
    "parameters and seed where the vendor exposes them, and explicitly recording NOT-PINNABLE "
    "where it does not. Falsifiable question: which vendors on this estate actually honour a seed - "
    "measured by repeated identical calls - and what fraction of a council is therefore genuinely "
    "reproducible rather than merely replayable from a recording?",
    P7A + [A_P7A],
    ["IMP-0287", "IMP-0335"],
    "1) a repeat-call determinism probe per vendor with the observed identical-output rate; 2) the "
    "per-seat parameter record present in the artifact, including NOT-PINNABLE entries.",
    ["measurement: per-vendor determinism rate published, not assumed",
     "negative control: a vendor that ignores the seed must be recorded as NOT-PINNABLE rather "
     "than claimed deterministic"],
    to=2700, sub="local-serialized", tools=T_WP,
    fc=["overclaim", "detector-failure", "stale-premise", "dependency-blocked"])

put("IMP-0353", "7A", "Seat-failure isolation",
    "Implement tools/council/resilience.py so one participant's crash, timeout or malformed output "
    "cannot abort the council: the seat is isolated, its partial contribution retained, and quorum "
    "recomputed. Falsifiable question: at what fraction of failed seats does the council correctly "
    "refuse to conclude, and is that threshold enforced or merely documented?",
    P7A + [A_PRED, A_FAIL],
    ["IMP-0299", "IMP-0324"],
    "1) a fault-injection sweep failing 1..N seats with the conclude/refuse boundary recorded; 2) "
    "an artifact census proving each failed seat's partial contribution was retained.",
    ["chaos: seat crash, seat timeout and malformed-output injection",
     "invariant: quorum recomputed, partial contributions retained",
     "negative control: remove the quorum recomputation and assert a sub-quorum council wrongly "
     "concludes"],
    to=3600)

assert set(NEW) == set(ORDER), (sorted(NEW), sorted(ORDER))

FAM = {
    "7": dict(sub="worktree-isolated", to=3600, tools=T_W, rev=REV_SOLO, model=M_OPUS,
              retry=R_PIVOT, prof="workflow-foundry-module",
              fc=["schema-invalid", "overclaim", "green-not-live", "dependency-blocked"]),
    "7A": dict(sub="worktree-isolated", to=3600, tools=T_W, rev=REV_SOLO, model=M_OPUS,
               retry=R_PIVOT, prof="council-runtime-module",
               fc=["schema-invalid", "overclaim", "detector-failure", "dependency-blocked"]),
}

by_id = {u["id"]: u for u in data}
for slot in ORDER:
    n = NEW[slot]
    base = FAM[n["phase"]]
    kw = n["kw"]
    u = by_id[slot]
    u["title"] = n["title"]
    u["phase"] = n["phase"]
    u["question_or_target"] = n["q"]
    u["inputs"] = n["inputs"]
    u["dependencies"] = n["deps"]
    u["assigned_model_vendor_role"] = kw.get("model", base["model"])
    u["tool_permissions"] = kw.get("tools", base["tools"])
    u["execution_substrate"] = kw.get("sub", base["sub"])
    u["timeout_seconds"] = kw.get("to", base["to"])
    u["evidence_requirement"] = n["ev"]
    u["tests_required"] = n["tests"]
    u["reviewer_requirement"] = kw.get("rev", base["rev"])
    u["retry_policy"] = kw.get("retry", base["retry"])
    u["failure_classification"] = kw.get("fc", base["fc"])
    u["owner_approval_required"] = kw.get("oa", False)
    u["output_schema"] = ("command-center/schema/receipt.schema.json profile=%s "
                          "(required: unit_id, artifact_paths[], spec_anchor, evidence[], "
                          "test_ids[], negative_control_ids[], reviewer_verdict, "
                          "residual_unknowns[])"
                          % kw.get("prof", base["prof"]))

# repoint every dependency that referenced a ceded id at its new B04 owner
repointed = 0
for u in data:
    if u["id"] in CEDE and u["id"] in ORDER:
        pass  # the slot itself has fresh deps already
    new_deps = []
    for d in u["dependencies"]:
        if d in CEDE and u["id"] not in ORDER:
            new_deps.append(CEDE[d])
            repointed += 1
        elif d in CEDE and u["id"] in ORDER:
            raise SystemExit("new unit %s must not depend on a ceded id %s" % (u["id"], d))
        else:
            new_deps.append(d)
    seen = set()
    u["dependencies"] = [x for x in new_deps if not (x in seen or seen.add(x))]

# hard check: no surviving reference to a ceded mechanism as an intra-slice dependency
for u in data:
    for d in u["dependencies"]:
        if d in CEDE:
            raise SystemExit("dangling ceded dep %s in %s" % (d, u["id"]))

with io.open(SRC, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(data, fh, indent=2, ensure_ascii=True)
    fh.write("\n")

ph = {}
for u in data:
    ph[u["phase"]] = ph.get(u["phase"], 0) + 1
print("ceded=%d repointed_deps=%d n=%d phases=%s"
      % (len(ORDER), repointed, len(data), sorted(ph.items())))
