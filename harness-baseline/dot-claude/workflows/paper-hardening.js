export const meta = {
  name: 'paper-hardening',
  description: 'Audit, ground, fix and adversarially verify the two phenibut manuscripts until no blocking findings remain',
  phases: [
    { title: 'Ground', detail: 'Establish verified current state of both manuscripts and their receipts' },
    { title: 'Audit', detail: 'Read-only lenses over correctness, claims, stats, figures, prose, safety' },
    { title: 'Research', detail: 'Literature grounding, corpus mining, anchor verification, paywall triage' },
    { title: 'Triage', detail: 'Consolidate and de-duplicate findings, assign to disjoint file scopes' },
    { title: 'Fix', detail: 'Apply fixes, one agent per disjoint file scope' },
    { title: 'Verify', detail: 'Adversarial critics re-read the fixed files' },
    { title: 'Synthesize', detail: 'Final report, residual gaps, truthful not-obtained list' },
  ],
}

// ---------------------------------------------------------------- H6 timeout helper (paste-in)
// The sandbox has no module loader, so this cannot be imported. Bounds the BARRIER, not the agent:
// a timed-out agent keeps running and keeps spending budget until it dies on its own.
function withTimeout(thunk, ms, label) {
  return new Promise((resolve) => {
    let done = false
    const t = setTimeout(() => {
      if (!done) { done = true; resolve({ __h6: true, __endReason: 'timeout', label, ms }) }
    }, ms)
    Promise.resolve()
      .then(thunk)
      .then((v) => { if (!done) { done = true; clearTimeout(t); resolve(v ?? { __h6: true, __endReason: 'null', label, ms }) } })
      .catch((e) => { if (!done) { done = true; clearTimeout(t); resolve({ __h6: true, __endReason: 'threw', label, ms, error: String(e).slice(0, 400) }) } })
  })
}
const isDrop = (x) => !!(x && x.__h6)
const kept = (arr) => arr.filter((x) => x && !isDrop(x))
const drops = (arr) => arr.filter(isDrop)

// ---------------------------------------------------------------- schemas
const obj = (properties, required = []) => ({ type: 'object', additionalProperties: false, required, properties })

const FINDING = {
  type: 'object',
  additionalProperties: false,
  required: ['id', 'severity', 'file', 'claim', 'why'],
  properties: {
    id: { type: 'string' },
    severity: { type: 'string', enum: ['blocking', 'major', 'minor', 'nit'] },
    file: { type: 'string' },
    locator: { type: 'string' },
    claim: { type: 'string' },
    why: { type: 'string' },
    fix: { type: 'string' },
    evidence: { type: 'array', items: { type: 'string' } },
    confidence: { type: 'string' },
  },
}

const AUDIT = obj({
  digest: { type: 'string' },
  findings: { type: 'array', items: FINDING },
  evidence: { type: 'array', items: { type: 'string' } },
  artifact: { type: 'string' },
}, ['digest', 'evidence'])

const RESEARCH = obj({
  digest: { type: 'string' },
  found: { type: 'array', items: { type: 'string' } },
  not_obtained: { type: 'array', items: { type: 'string' } },
  corrections: { type: 'array', items: FINDING },
  evidence: { type: 'array', items: { type: 'string' } },
  artifact: { type: 'string' },
}, ['digest', 'evidence'])

const TRIAGE = obj({
  digest: { type: 'string' },
  blocking_count: { type: 'integer' },
  total_count: { type: 'integer' },
  by_scope: { type: 'array', items: obj({
    scope: { type: 'string' },
    finding_ids: { type: 'array', items: { type: 'string' } },
  }, ['scope', 'finding_ids']) },
  dropped_duplicates: { type: 'integer' },
  evidence: { type: 'array', items: { type: 'string' } },
}, ['digest', 'blocking_count', 'total_count', 'evidence'])

const FIX = obj({
  digest: { type: 'string' },
  applied: { type: 'array', items: { type: 'string' } },
  refused: { type: 'array', items: { type: 'string' } },
  files_touched: { type: 'array', items: { type: 'string' } },
  verification_run: { type: 'string' },
  evidence: { type: 'array', items: { type: 'string' } },
}, ['digest', 'evidence'])

const VERIFY = obj({
  digest: { type: 'string' },
  verdict: { type: 'string', enum: ['clean', 'residual', 'regressed'] },
  blocking: { type: 'array', items: FINDING },
  evidence: { type: 'array', items: { type: 'string' } },
}, ['digest', 'evidence'])

const SYNTH = obj({
  digest: { type: 'string' },
  worth_assessment: { type: 'string' },
  residual_gaps: { type: 'array', items: { type: 'string' } },
  not_obtained_truthful: { type: 'array', items: { type: 'string' } },
  evidence: { type: 'array', items: { type: 'string' } },
}, ['digest', 'evidence'])

// ---------------------------------------------------------------- shared, byte-stable prefix
// Rule 8: identical across every agent so the prompt cache is hit N-1 times. Nothing volatile in it.
const P = String.raw`D:\Research\projects\phenibut`
const OUT = String.raw`D:\Research\projects\phenibut\docs\_hardening`

const CONTEXT = `
=== PROJECT ===
Single-author computational-pharmacology program on phenibut (beta-phenyl-GABA). Author: Andrei
Mihai VISALON, University of Bucharest, ORCID 0009-0001-8776-8498. Two manuscripts are being
finalised for preprint:
  Paper 1 -> ChemRxiv : ${P}\\docs\\PAPER_1_FINAL_2026-09-15.md
  Paper B -> medRxiv  : ${P}\\docs\\PAPER_B_FINAL_2026-09-15.md

=== VERIFIED GROUND TRUTH (established by direct inspection immediately before this run) ===
 1. ATM/RBFE validation edge R-phenibut -> arbaclofen: ddG = -1.890 +/- 0.368 kcal/mol,
    acceptance gate PASS.  [probe: compute/atm-data/work/valid_rerun_2026-09-15/DONE.json]
 2. R->S enantioselectivity now has THREE seeds, reported separately and never averaged:
    seed 1 = +1.673 +/- 0.321 (Scaleway 4x H100), seed 2 = +0.633 +/- 0.302 (Modal 8x H100),
    seed 3 = +0.783 +/- 0.304 (Modal 8x H100, completed 2026-09-16, gate PASS).
    [probe: compute/atm-data/work/rs_seed3_2026-09-16/results/results/analyze_*.log]
 3. Seeds 2 and 3 agree (0.150 apart); seed 1 is the OUTLIER (0.890-1.040 above them). The
    between-seed SD is 0.562, LARGER than every individual corrected bar (0.321/0.302/0.304).
    Two of three seeds, and the mean (+1.03), fall BELOW the experimental lower bound +1.42.
    The protocol UNDER-PREDICTS the magnitude. Only the SIGN is claimed.
 4. Seed 1 is the only 4x H100 run and the only outlier, so "sampling tail" and "worker-count
    artifact" are both live explanations; this is unresolved and must stay unresolved in text.
 5. compute/RESULTS.md is the single source of truth for every computed number.
 6. scripts/verify_numbers.py currently reports 190/190 canonical tokens present.
    [probe: python scripts/verify_numbers.py, run immediately before this workflow]

=== NON-NEGOTIABLE PROJECT RULES ===
 A. Single author. Remove first-person plural ("we", "our"). "I" is allowed for authorial
    judgement. No third-person self-reference.
 B. NEVER invent or fabricate a citation, DOI, PMID or quotation. A visible placeholder is
    strictly better than a plausible-looking fake. If you cannot verify an identifier, say so.
 C. Phenibut content is MECHANISM / HYPOTHESIS framing only. No dosing, titration, tapering,
    substitution, sourcing, or any human-use guidance anywhere, including in figure captions.
 D. Limitations must be scientific or scope-based. NO logistical, resource, cost, availability,
    tooling, compute-budget or process-log language anywhere in either manuscript.
 E. Never delete a computed result. Supersede it in place with its provenance.
 F. Documents were never published, so reserve "withdrawn" for CLAIMS falsified by evidence and
    use "superseded" for DATA replaced by a better run. Never "RETRACTION" as a notice header.

=== PROSE RULES (the author has explicitly asked for these) ===
 G. Strip overused AI-tell phrasing. Specifically BANNED as crutch words in the manuscripts:
    "load-bearing", "smoking gun", "honest"/"honestly" used as intensifiers, "it is worth noting",
    "delve", "tapestry", "crucially", "importantly", "testament to", "navigate the landscape",
    "in the realm of", "seamless", "robust" as filler. Also strip: negative parallelism
    ("not X, but Y") used as a tic, rule-of-three padding, em-dash overuse, and vague
    attribution ("studies show", "experts agree"). Replace with the specific claim.
 H. Do NOT flatten precision to achieve (G). A technical term that is the correct word stays.
    The target is prose a careful specialist reader would find direct and unpadded.

=== SKILLS YOU MUST LOAD BEFORE STARTING ===
This machine carries a curated skill vault. Load the ones named in YOUR task with the Skill tool
before you begin; they encode this author's standards and save you from reinventing them.
Available and relevant:
  research-paper-craft            manuscript construction, section craft, venue conventions
  writing-skills                  general writing discipline
  anthropic-skills:humanizer      removes AI-writing tells; the canonical list of banned patterns
  research-integrity-forensics    citation verification, fabricated-reference detection
  scholarly-literature-review     systematic search and synthesis method
  deep-research                   multi-source research protocol
  institutional-literature-access credentials and cookie jar for paywalled retrieval ALREADY set
                                  up on this machine; REUSE it, never re-derive it
  biomedical-paper-triage         rapid appraisal of biomedical primary literature
  consensus-tooluniverse-research GtoPdb / DGIdb / FAERS structured lookups
  drug-discovery-literature-bridge  chemistry-to-literature linking
  gem-hunt                        discovery sweeps for overlooked high-value material
If a named skill fails to load, say so in your digest and continue with your own method.

=== HONESTY CONTRACT (does not carry in from any global config; applies here or not at all) ===
 - Attach UNVERIFIED inline to the sentence it qualifies. A limitations paragraph does not count.
 - Every UNVERIFIED names the experiment that would settle it.
 - "Absent / not found / broken" is a CLAIM, not an observation. Before reporting an absence,
   prove your detector can find a KNOWN-PRESENT item. This project has repeatedly been burned by
   false negatives from a broken probe (a DOI regex that kept markdown bold markers reported
   0 of 18 references present when most were on disk).
 - Do not report CONFIRMED from the same mechanism that produced the original claim. Corroborate
   a load-bearing absence with a mechanically DIFFERENT probe.
 - If a tool is denied you are in a subagent and no human will answer. Do not stop. Record the
   gap, use an alternative, and report it in your digest.
`

const OUTPUT_CONTRACT = `
=== OUTPUT CONTRACT ===
 1. Write your FULL deliverable with the Write tool to the artifact path given in your task.
    If one call is too large, append with Add-Content. Never build a multi-KB literal inside a
    shell command string (Windows 32767-char limit -> os error 206).
 2. Return a <= 400 word structured digest as your final text, NOT the whole document.
    Lead the digest with any correction to the ground truth above.
 3. Append an EVIDENCE block of 3-5 file:line or URL anchors. Exempt from the word cap.
 4. Every finding you report must carry a stable id of the form <lens-slug>-NN.
`

// ---------------------------------------------------------------- work definitions
const AUDIT_LENSES = [
  { key: 'numerics', skills: 'research-paper-craft', title: 'Numerical traceability',
    task: `Every number in BOTH manuscripts must trace to compute/RESULTS.md or a named receipt file. Find numbers that appear in a manuscript but in no receipt, numbers that disagree between manuscript and receipt, stale numbers left over from a superseded run, and arithmetic that does not follow (intervals that do not match their central value +/- error, percentages that do not match their counts). Recompute every interval you check.` },
  { key: 'seed3', skills: 'research-paper-craft', title: 'Three-seed propagation',
    task: `The third R->S seed was added hours ago. Verify the propagation is COMPLETE and internally consistent across Paper 1: abstract, Figure 1 caption, hardware list, results table, section 3.2, section 3.3, Figure 6 and 8 captions, discussion 4.1/4.2, limitations 5.2, conclusion, and the SI list. Report any place that still reads as if there were two seeds, any place where seed 1 is still described as canonical or primary, and any arithmetic about the spread (1.04, 0.890, 0.150, SD 0.562, mean +1.03) that does not check out.` },
  { key: 'claims', skills: 'research-paper-craft, biomedical-paper-triage', title: 'Claim-evidence mapping',
    task: `Build a claim ledger for BOTH manuscripts: every assertion that a reader could cite, with the evidence actually offered and a grade. Flag every claim whose strength exceeds its evidence, every causal verb resting on associational evidence, and every place a hedge is missing. Pay attention to Paper B, whose contribution is explicitly a tiered synthesis; check that each claim sits in the correct tier.` },
  { key: 'stats', skills: 'biomedical-paper-triage', title: 'Statistical correctness',
    task: `Check every statistical statement in both manuscripts: error propagation, the distinction between a confidence interval and a bound, disproportionality metrics (PRR/ROR/Evans criteria), Mendelian-randomization assumptions and instrument strength, colocalization posterior interpretation, autocorrelation correction, and any implicit multiple-comparison exposure. Flag anything where an interval is presented as if it were a probability statement about the truth, or a bound as if it were a CI.` },
  { key: 'citations', skills: 'research-integrity-forensics, institutional-literature-access', title: 'Citation integrity',
    task: `For every citation in both manuscripts, verify the identifier resolves to the work described and that the claim attributed to it is actually what that work reports. Flag any identifier that cannot be resolved, any mismatch between citation and claim, and any reference cited for something it does not say. Do NOT invent replacements. Distinguish clearly between "identifier is wrong", "identifier is right but does not support the claim", and "could not check".` },
  { key: 'figures', skills: 'research-paper-craft', title: 'Figure correctness and completeness',
    task: `Inventory every figure referenced by both manuscripts. For each: does the file exist, does a generator script exist, does the caption match what the figure shows, are the numbers in the figure current, is the encoding accessible (never colour alone), and is the figure actually necessary. Then propose specific NEW figures or panels that would materially strengthen the papers, and specific corrections to existing ones. Be concrete about what each proposed figure would show and from which data file.` },
  { key: 'prose', skills: 'anthropic-skills:humanizer, writing-skills, research-paper-craft', title: 'Prose, voice and AI-tells',
    task: `Apply prose rules G and H above to BOTH manuscripts. Find every banned crutch phrase, every first-person plural, every third-person self-reference, and every instance of the AI-writing patterns listed. Quote the offending sentence and give a specific replacement that preserves the technical precision. Also flag sentences that are simply too long or that bury their claim.` },
  { key: 'structure', skills: 'research-paper-craft', title: 'Internal consistency and cross-references',
    task: `Check section numbering, cross-references (every "see section X" resolves and points at the right thing), figure numbering versus order of first mention, table numbering, the SI list versus what is actually described, terminology used consistently, and abbreviations defined at first use. Also check that the abstract accurately reflects the body and does not claim anything the body does not support.` },
  { key: 'safety', skills: 'research-paper-craft', title: 'Scope and safety boundary',
    task: `Verify rules C and D above hold across BOTH manuscripts including every figure caption, table cell, SI section and footnote. Flag any sentence that could be read as human-use guidance, any dosing-adjacent phrasing, and any logistical/resource/tooling/cost language that has leaked into a limitations or methods section where only scientific scope belongs.` },
  { key: 'repro', skills: 'research-paper-craft', title: 'Reproducibility and data availability',
    task: `Assess whether an independent reader could reproduce each result from what is stated plus what is in the repository. Check that every figure has a generator, every computed number has a named receipt, software versions and commits are pinned where they matter, and the data-availability statement is accurate rather than aspirational. Flag anything the statement promises that is not actually present.` },
  { key: 'paperb_testable', skills: 'consensus-tooluniverse-research, biomedical-paper-triage', title: 'Paper B: untested claims that COULD be tested',
    task: `Paper B is a mechanism and hypothesis synthesis. Identify every claim in it that is currently asserted or cited but that COULD be tested with data already reachable: FAERS/openFDA, GTEx, eQTLGen, FinnGen, MetaBrain, PsychENCODE, ChEMBL, GtoPdb, or the project's own corpus and compute outputs. For each, specify the exact test, the data source, the statistic, and what result would support versus refute. Rank by how much the paper would gain. This list is the input to a later execution pass, so be concrete and feasible, not aspirational.` },
  { key: 'paperb_weak', skills: 'biomedical-paper-triage, research-integrity-forensics', title: 'Paper B: weakest links',
    task: `Find the parts of Paper B most likely to be attacked by a referee: the colocalization provenance, the single cis-instrument MR, the small-N phenibut FAERS cells, the literature-absent gap, the fasoracetam material, and anything resting on a source that could not be retrieved. For each, state the strongest version of the objection and the minimum change that would blunt it. Say explicitly which cannot be fixed by writing alone and need either data or removal.` },
  { key: 'venue', skills: 'research-paper-craft', title: 'Venue readiness and worth',
    task: `Assess both manuscripts against what a reviewer at the realistic target venue would demand (Paper 1: ChemRxiv then a journal such as JCIM or JCTC; Paper B: medRxiv then a clinical/epi venue). Identify what currently caps the papers at modest worth and what specific, achievable changes would raise them. Be concrete and skeptical: name the changes that actually move a reviewer, not cosmetic ones. Also check reporting-guideline conformance where applicable (READUS-PV for Paper B's pharmacovigilance section, LiveCoMS-style best practice for Paper 1's free-energy methods).` },
  { key: 'crossref', skills: 'research-paper-craft', title: 'Cross-paper consistency',
    task: `Paper B cites Paper 1's result. Verify that everything Paper B says about Paper 1 is still true after the three-seed update, in particular anything about the eutomer claim and its strength. Flag any place where the two manuscripts state the same fact differently, or where Paper B leans on a Paper 1 claim that Paper 1 itself now hedges more heavily.` },
]

const RESEARCH_LANES = [
  { key: 'anchors', skills: 'institutional-literature-access, research-integrity-forensics, biomedical-paper-triage', title: 'Experimental anchor verification',
    task: `The whole of Paper 1 rests on a small number of experimental anchors: R-phenibut GABA-B Ki ~92 uM and racemic ~177 uM (attributed to Dambrova 2008, PMID 18275958), baclofen Ki ~6.0 uM in the same assay, S-phenibut inactive above 1 mM, R-phenibut alpha2delta Ki 23 uM (PMID 26234470), and the -1.6 to -2.0 kcal/mol validation range derived from them. Verify each against its primary record. Confirm the assay, species, radioligand and units match how the manuscript uses the number, and confirm the derived free-energy conversions. Report any anchor that cannot be verified at its primary source, and say exactly what IS available (abstract only, full text, gated).` },
  { key: 'litsearch', skills: 'deep-research, scholarly-literature-review, institutional-literature-access', title: 'New literature sweep',
    task: `Search for work published or indexed that is relevant to either manuscript and is NOT currently cited: phenibut pharmacology and enantioselectivity, beta-aryl-GABA SAR, GABA-B orthosteric structure and agonist binding, alchemical transfer method / RBFE benchmarks and their reported accuracy on stereocentres, KCTD subunit biology in mood, baclofen withdrawal pharmacovigilance, and fasoracetam. For each hit, state why it matters to a specific section, and whether it strengthens, complicates or contradicts an existing claim. Prioritise anything that CONTRADICTS the manuscripts, since that is what a referee will find.` },
  { key: 'corpus', skills: 'scholarly-literature-review, gem-hunt', title: 'Local corpus and Russian-language mining',
    task: `The project holds a large local corpus including Soviet/Volgograd-school Russian-language material, some of it already translated. Mine it for material that supports or complicates claims in either manuscript, especially phenibut pharmacology, enantiomer data, tolerance and withdrawal. Report what the corpus actually contains on each point, and flag any manuscript claim attributed to this literature that the corpus does not in fact support. Note that the Lapin 1990 monograph is deliberately cited as named-but-not-retrieved; verify that framing is still accurate rather than changing it.` },
  { key: 'rbfe_context', skills: 'deep-research, scholarly-literature-review, drug-discovery-literature-bridge', title: 'Method-performance context',
    task: `Paper 1's central negative finding is that the protocol under-predicts enantioselectivity magnitude while getting the sign right, and that between-seed scatter exceeds within-run error. Find published context for this: reported RBFE accuracy on stereochemical perturbations, known failure modes of alchemical transfer on chiral centres, published seed-to-seed reproducibility studies, and any prior report that within-run convergence diagnostics fail to predict between-run reproducibility. This is the literature that turns an isolated negative result into a contribution.` },
  { key: 'paperb_data', skills: 'deep-research, consensus-tooluniverse-research', title: 'Paper B data-source reachability',
    task: `For each external data source Paper B depends on (FinnGen R12, GTEx v8, eQTLGen, MetaBrain, PsychENCODE, openFDA/FAERS), establish what is actually reachable right now without credentials, what needs a request, and what is hard-gated. The KCTD16 colocalization PP.H4 = 0.948 is currently transcribed rather than reproduced because MetaBrain is access-gated; determine precisely what would be needed to reproduce it and whether any open mirror or summary-statistics release would serve. Do not guess at access status; probe it.` },
  { key: 'notfound', skills: 'research-integrity-forensics, institutional-literature-access, scholarly-literature-review', title: 'Not-obtained triage',
    task: `The project has accumulated wishlists of references it could not obtain. Triage every not-obtained item into exactly one of: (a) REAL and open-access somewhere, with the location; (b) REAL but paywalled or gated, with what access would be needed; (c) REAL but genuinely not digitised or only in print; (d) CITATION IS WRONG, the identifier does not match the described work, with the correct identifier if findable; (e) NO SUCH WORK APPEARS TO EXIST, i.e. the reference is likely fabricated or garbled, with the evidence for that conclusion. Category (e) is the one the author specifically wants surfaced, so apply it only on positive evidence of non-existence after searching multiple indexes, never as a default for "I could not find it".` },
]

const VERIFY_LENSES = [
  { key: 'v_numerics', title: 'Numbers still trace and still agree' },
  { key: 'v_claims', title: 'No claim now exceeds its evidence' },
  { key: 'v_prose', title: 'Banned phrasing gone, precision intact' },
  { key: 'v_safety', title: 'Scope and safety boundary intact' },
  { key: 'v_structure', title: 'Cross-references and numbering still resolve' },
  { key: 'v_figures', title: 'Figures regenerate and match their captions' },
  { key: 'v_citations', title: 'No fabricated or unresolvable identifier was introduced' },
  { key: 'v_regress', title: 'Nothing previously correct was broken' },
]

const FIX_SCOPES = [
  { key: 'paper1', title: 'Paper 1 manuscript',
    scope: `${P}\\docs\\PAPER_1_FINAL_2026-09-15.md`,
    note: 'ONLY this file. Do not touch Paper B, scripts, or RESULTS.md.' },
  { key: 'paperb', title: 'Paper B manuscript',
    scope: `${P}\\docs\\PAPER_B_FINAL_2026-09-15.md`,
    note: 'ONLY this file. Do not touch Paper 1, scripts, or RESULTS.md.' },
  { key: 'figures', title: 'Figure generators and figures',
    scope: `${P}\\scripts\\*.py and ${P}\\docs\\figures\\**`,
    note: 'ONLY generator scripts and the figures they emit. Never edit a manuscript. Every figure you touch or add MUST have a generator that reads real data and MUST be regenerated and visually checked before you report it done.' },
  { key: 'receipts', title: 'RESULTS.md and supporting docs',
    scope: `${P}\\compute\\RESULTS.md, ${P}\\compute\\README.md, ${P}\\README.md, ${P}\\compute\\EXPERIMENTAL_ANCHORS.md, ${P}\\docs\\OPEN_LOOPS_2026-09-15.md`,
    note: 'ONLY these receipt and index documents. Never edit a manuscript or a script.' },
]

// ---------------------------------------------------------------- run
const MAX_ROUNDS = 3
const T_AUDIT = 1500000
const T_FIX = 2100000
const T_VERIFY = 1500000

log(`paper-hardening: ${AUDIT_LENSES.length} audit lenses, ${RESEARCH_LANES.length} research lanes, ${FIX_SCOPES.length} fix scopes, ${VERIFY_LENSES.length} verify lenses, max ${MAX_ROUNDS} rounds`)

phase('Ground')
const ground = await withTimeout(() => agent(
  `${CONTEXT}

=== YOUR TASK (ground) ===
You are establishing the baseline state for a multi-agent hardening run over two manuscripts.
Read both manuscripts in full, compute/RESULTS.md, scripts/verify_numbers.py and its current
output, and list the contents of docs/figures/. Produce: (1) an accurate section-by-section
outline of each manuscript with line ranges, (2) the full inventory of figures with which
generator produces each, (3) the list of every distinct numeric claim with its receipt, and
(4) any place where the ground truth stated above is WRONG. Item (4) is the most valuable
output; the agents downstream will trust the ground truth unless you correct it here.
Create the directory ${OUT} if it does not exist.
${OUTPUT_CONTRACT}
Artifact path: ${OUT}\\00-ground.md`,
  { label: 'ground', phase: 'Ground', schema: AUDIT, effort: 'high', model: 'opus' }
), T_AUDIT, 'ground')

if (isDrop(ground)) log(`ground agent dropped: ${ground.__endReason}`)
else log(`ground: ${String(ground.digest).slice(0, 220)}`)

const GROUND_NOTE = isDrop(ground)
  ? '\n=== GROUND ADDENDUM ===\nThe grounding pass did not complete. Verify every fact yourself before relying on it.\n'
  : `\n=== GROUND ADDENDUM (from the grounding pass; treat as high-confidence but re-checkable) ===\n${String(ground.digest).slice(0, 2500)}\nFull baseline: ${OUT}\\00-ground.md\n`

phase('Research')
const research = kept(await parallel(RESEARCH_LANES.map((r) => () => withTimeout(
  () => agent(
    `${CONTEXT}${GROUND_NOTE}
=== YOUR TASK (research:${r.key}) — ${r.title} ===
LOAD THESE SKILLS FIRST: ${r.skills}

${r.task}

You are READ-ONLY with respect to the manuscripts: do not edit them. Write your findings to your
artifact and return corrections as structured findings. Use the institutional access already
configured on this machine rather than re-deriving it. Be concrete about the specific axis named
in your task, not generic research advice.
${OUTPUT_CONTRACT}
Artifact path: ${OUT}\\10-research-${r.key}.md`,
    { label: `research:${r.key}`, phase: 'Research', schema: RESEARCH, effort: 'high', model: 'fable' }
  ), T_AUDIT, `research:${r.key}`))))

log(`research: ${research.length}/${RESEARCH_LANES.length} lanes returned`)

const RESEARCH_NOTE = research.length
  ? `\n=== RESEARCH ADDENDUM (grounding lanes; corroborate before acting on any of it) ===\n${research.map((r) => `- ${String(r.digest).slice(0, 400)}`).join('\n')}\n`
  : '\n=== RESEARCH ADDENDUM ===\nNo research lane returned. Do not assume literature coverage.\n'

let round = 0
let blocking = 1
let lastTriage = null
const history = []

while (round < MAX_ROUNDS && blocking > 0) {
  round += 1
  if (budget.total && budget.remaining() < 200000) { log(`stopping before round ${round}: budget remaining ${budget.remaining()}`); break }
  log(`=== round ${round} ===`)

  phase('Audit')
  const audits = kept(await parallel(AUDIT_LENSES.map((l) => () => withTimeout(
    () => agent(
      `${CONTEXT}${GROUND_NOTE}${RESEARCH_NOTE}
=== YOUR TASK (audit:${l.key}) — ${l.title} ===
LOAD THESE SKILLS FIRST: ${l.skills}

${l.task}

You are READ-ONLY. Do not edit any file. Report every problem as a structured finding with a
severity. Reserve "blocking" for something that would embarrass the author in review or make a
statement false; use "major" for a real weakness that is not an error. Be concrete about the
specific axis named in your task, not generic manuscript advice.
This is round ${round} of at most ${MAX_ROUNDS}; earlier rounds' fixes are already applied, so
audit the CURRENT text on disk rather than anything you remember.
${OUTPUT_CONTRACT}
Artifact path: ${OUT}\\20-audit-r${round}-${l.key}.md`,
      { label: `audit:${l.key}:r${round}`, phase: 'Audit', schema: AUDIT, effort: 'high', model: 'fable' }
    ), T_AUDIT, `audit:${l.key}:r${round}`))))

  log(`round ${round} audit: ${audits.length}/${AUDIT_LENSES.length} lenses returned`)

  phase('Triage')
  const triage = await withTimeout(() => agent(
    `${CONTEXT}${GROUND_NOTE}
=== YOUR TASK (triage, round ${round}) ===
Every audit lens and research lane has written an artifact under ${OUT}. Read them ALL
(20-audit-r${round}-*.md and 10-research-*.md), then produce a single consolidated, de-duplicated,
ranked finding list.

Rules:
 - Two lenses reporting the same underlying problem is ONE finding. Merge them and keep the
   strongest evidence from each.
 - Drop any finding whose premise you can show is false against the files on disk. Say which.
 - Assign every surviving finding to exactly ONE fix scope, so that no two fixers touch the same
   file: "paper1", "paperb", "figures", "receipts".
 - A finding that requires new computation or new data, rather than editing, goes to scope
   "deferred" and is NOT assigned to a fixer.
 - Rank within scope by severity then by how much it changes what a reader concludes.
Write the consolidated list to your artifact as a numbered table including, for each finding:
id, severity, scope, file, locator, the problem, and the specific edit that resolves it.
${OUTPUT_CONTRACT}
Artifact path: ${OUT}\\30-triage-r${round}.md`,
    { label: `triage:r${round}`, phase: 'Triage', schema: TRIAGE, effort: 'high', model: 'opus' }
  ), T_AUDIT, `triage:r${round}`)

  if (isDrop(triage)) { log(`round ${round}: triage dropped (${triage.__endReason}); stopping`); break }
  lastTriage = triage
  log(`round ${round} triage: ${triage.total_count} findings, ${triage.blocking_count} blocking`)

  if (triage.total_count === 0) { blocking = 0; history.push({ round, triage, fixes: [], verifies: [] }); break }

  phase('Fix')
  const fixes = kept(await parallel(FIX_SCOPES.map((s) => () => withTimeout(
    () => agent(
      `${CONTEXT}${GROUND_NOTE}
=== YOUR TASK (fix:${s.key}, round ${round}) — ${s.title} ===
Read the consolidated triage at ${OUT}\\30-triage-r${round}.md and apply EVERY finding assigned
to scope "${s.key}".

YOUR FILE SCOPE IS STRICTLY: ${s.scope}
${s.note}
Editing outside this scope corrupts a sibling agent's work. If a finding assigned to you actually
requires a change outside your scope, do not make it: record it in "refused" with the reason.

How to apply:
 - Make the smallest edit that fully resolves the finding. Do not rewrite passages that are fine.
 - Preserve every number unless the finding is that the number is wrong; if you change a number,
   state the receipt it now comes from.
 - Never delete a computed result; supersede it in place with its provenance.
 - Obey prose rules G and H, and rules A-F, in everything you write.
 - If you believe a finding is WRONG, do not apply it. Put it in "refused" with your evidence.
   A refusal with evidence is a good outcome; a silent non-application is not.
After editing, RUN the project's own checks that apply to your scope and report what they said:
   python ${P}\\scripts\\verify_numbers.py
and, if you touched a figure generator, re-run that generator and confirm the PNG was rewritten.
${OUTPUT_CONTRACT}
Artifact path: ${OUT}\\40-fix-r${round}-${s.key}.md`,
      { label: `fix:${s.key}:r${round}`, phase: 'Fix', schema: FIX, effort: 'high', model: 'opus', isolation: 'worktree' }
    ), T_FIX, `fix:${s.key}:r${round}`))))

  log(`round ${round} fix: ${fixes.length}/${FIX_SCOPES.length} scopes returned`)

  phase('Verify')
  const verifies = kept(await parallel(VERIFY_LENSES.map((v) => () => withTimeout(
    () => agent(
      `${CONTEXT}${GROUND_NOTE}
=== YOUR TASK (verify:${v.key}, round ${round}) — ${v.title} ===
Fixes have just been applied to the manuscripts, figure generators and receipt documents.
You are an ADVERSARIAL critic. Read the CURRENT files on disk, plus ${OUT}\\30-triage-r${round}.md
and the fix reports ${OUT}\\40-fix-r${round}-*.md.

Answer three questions and let the evidence decide:
 1. Were the findings in your dimension actually fixed, or only claimed fixed? Check the file, not
    the report. A fixer asserting "applied" is not evidence.
 2. Did the fixes introduce anything NEW that is wrong: a broken cross-reference, a number that no
    longer matches its receipt, a hedge removed, a claim strengthened past its evidence, a
    fabricated citation, or prose flattened into imprecision?
 3. Is anything still outstanding in your dimension that no fixer addressed?
Return verdict "clean" only if you can point to the evidence that it is clean. Return "regressed"
if something previously correct is now wrong; that outranks everything else.
You are READ-ONLY. Do not edit.
${OUTPUT_CONTRACT}
Artifact path: ${OUT}\\50-verify-r${round}-${v.key}.md`,
      { label: `verify:${v.key}:r${round}`, phase: 'Verify', schema: VERIFY, effort: 'high', model: 'opus' }
    ), T_VERIFY, `verify:${v.key}:r${round}`))))

  const stillBlocking = verifies.reduce((n, v) => n + ((v.blocking && v.blocking.length) || 0), 0)
  const regressed = verifies.filter((v) => v.verdict === 'regressed').length
  blocking = stillBlocking
  history.push({ round, triage_total: triage.total_count, triage_blocking: triage.blocking_count,
    fixes: fixes.length, verifies: verifies.length, still_blocking: stillBlocking, regressed })
  log(`round ${round} verify: ${verifies.length}/${VERIFY_LENSES.length} critics, ${stillBlocking} blocking remain, ${regressed} regressed`)
}

phase('Synthesize')
const synth = await withTimeout(() => agent(
  `${CONTEXT}${GROUND_NOTE}
=== YOUR TASK (synthesis) ===
The hardening run is finished after ${round} round(s). Read everything under ${OUT} and the
CURRENT state of both manuscripts, then write the final report to your artifact.

It must contain, in this order:
 1. What changed, by manuscript, with the material scientific changes separated from the
    editorial ones. A reader of this section should know whether any CONCLUSION moved.
 2. The state of each manuscript against its target venue, and a direct answer to the author's
    question: has the work moved from modest worth toward high worth, and what specifically is
    still capping it. Do not flatter. If the honest answer is that the cap is structural rather
    than editorial, say so and say what would lift it.
 3. Residual gaps: everything still open, each with the specific action that would close it and
    whether that action is writing, computation, or data access.
 4. The NOT-OBTAINED list, triaged truthfully into the five categories defined for the
    research:notfound lane. Category (e) — "no such work appears to exist" — must be applied only
    on positive evidence after searching multiple indexes, and each entry must state what was
    searched. An honest "real but gated" is far more useful to the author than a speculative
    "probably fabricated", and the reverse error is worse still.
 5. Anything a reviewer would still reject on, ranked.
${OUTPUT_CONTRACT}
Artifact path: ${OUT}\\90-final-report.md`,
  { label: 'synthesis', phase: 'Synthesize', schema: SYNTH, effort: 'max', model: 'opus' }
), T_FIX, 'synthesis')

return {
  envelope: true,
  rounds: round,
  blocking_remaining: blocking,
  history,
  triage: lastTriage ? { total: lastTriage.total_count, blocking: lastTriage.blocking_count } : null,
  synthesis: isDrop(synth) ? { dropped: synth.__endReason } : synth,
  artifacts: OUT,
}
