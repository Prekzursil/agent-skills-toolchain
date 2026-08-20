export const meta = {
  name: 'bc-stage-compendium-enrichment',
  description: 'Enrich the BC event atlas into a LIVING STAGE COMPENDIUM: close the critic gaps (JP cross-region diff, schedule-band namespace verify, exact activatable sets) AND add new dimensions (cat-linkage, addition-versions, semi-story/progressive). Read-only; no device. Writes BC-STAGE-COMPENDIUM.md.',
  phases: [
    { title: 'Enrich', detail: 'Parallel: close critic P0/P1 gaps + mine cat-linkage, addition-versions, semi-story/progressive from local game-data + wiki' },
    { title: 'Compile', detail: 'Synthesize atlas + gap-closures + new dimensions into the living compendium doc' },
    { title: 'Critique', detail: 'Completeness critic on the compendium' },
  ],
}

// ---------------------------------------------------------------------------
// H6 — per-agent timeout + stall heartbeat. Paste at the top of the workflow.
// Sandbox-safe: uses only injected globals (setTimeout/clearTimeout/log/parallel).
// No Date.now / Math.random / new Date() -> stays workflow_lint clean.
// SCOPE: unblocks the BARRIER. Does NOT kill the agent -- the dropped agent keeps
// running and keeps its concurrency slot until it dies on its own.
// ---------------------------------------------------------------------------
const H6_TIMEOUT_MS = 1800000; // 30 min; blueprint dispatch_timeout_seconds default
const H6_STALL_MS = 90000; // 90 s; B3 falsifier #22

// A typed drop-receipt (design item H3). NEVER return a bare null from a barrier:
// null is produced for at least three different causes -- user skipped the agent,
// the subagent died on a terminal error, and (here) our own timeout -- and
// .filter(Boolean) throws that distinction away, making "12 of 15 returned"
// unauditable.
function h6Receipt(endReason, label, ms, detail) {
  return {
    __h6: true,
    __endReason: endReason, // 'timeout' | 'threw' | 'null'
    label: label,
    ms: ms,
    detail: detail === undefined ? null : detail,
  };
}

function h6IsDrop(r) {
  return !!r && r.__h6 === true;
}
function h6Survivors(results) {
  return results.filter(function (r) {
    return !h6IsDrop(r);
  });
}
function h6Drops(results) {
  return results.filter(h6IsDrop);
}

// Emit one heartbeat line if the unit is still outstanding at H6_STALL_MS.
// Returns a canceller. This is an OBSERVATION ("still waiting"), not a verdict
// that the agent is hung -- the sandbox cannot see orchestrator state.
function h6Heartbeat(label, stallMs) {
  if (typeof setTimeout !== 'function') return function () {};
  const t = setTimeout(function () {
    if (typeof log === 'function') {
      log('H6 heartbeat: still waiting on ' + label + ' after ' + stallMs + 'ms');
    }
  }, stallMs);
  return function () {
    if (typeof clearTimeout === 'function') clearTimeout(t);
  };
}

// Bound ONE thunk. Always resolves -- never rejects, never returns undefined --
// so a barrier over wrapped thunks can no longer be poisoned by one unit.
async function withTimeout(thunk, ms, label, stallMs) {
  const lbl = label === undefined ? 'unit' : label;
  const budgetMs = ms === undefined ? H6_TIMEOUT_MS : ms;
  // Runtime-drift guard: if a future build stops injecting timers, degrade to a
  // plain await instead of dying with a ReferenceError at fan-out time.
  if (typeof setTimeout !== 'function') {
    try {
      return await thunk();
    } catch (err) {
      return h6Receipt('threw', lbl, budgetMs, String((err && err.message) || err));
    }
  }
  const stopBeat = h6Heartbeat(lbl, stallMs === undefined ? H6_STALL_MS : stallMs);
  let timer = null;
  const expiry = new Promise(function (resolve) {
    timer = setTimeout(function () {
      resolve(h6Receipt('timeout', lbl, budgetMs, null));
    }, budgetMs);
  });
  try {
    return await Promise.race([Promise.resolve().then(thunk), expiry]);
  } catch (err) {
    return h6Receipt('threw', lbl, budgetMs, String((err && err.message) || err));
  } finally {
    // ALWAYS clear on the winning path too: an un-cleared timer stays in the
    // runtime's abort set and can hold the workflow open past its last agent.
    if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer);
    stopBeat();
  }
}

// A SETTLED barrier: same shape as parallel(), but one hung unit costs you that
// unit instead of the phase. Output is index-aligned with `thunks` and every
// slot is either a real result or a typed drop-receipt -- no nulls, no holes.
async function settle(thunks, ms, labels) {
  const nameOf = function (i) {
    return labels && labels[i] !== undefined ? labels[i] : 'unit-' + i;
  };
  const raw = await parallel(
    thunks.map(function (t, i) {
      return function () {
        return withTimeout(t, ms, nameOf(i));
      };
    }),
  );
  return raw.map(function (r, i) {
    // The runtime still yields null for a cause we never saw (a user skip).
    // Type it rather than filtering it away.
    return r === null || r === undefined ? h6Receipt('null', nameOf(i), ms, null) : r;
  });
}

const obj = (properties, required = []) => ({
  type: 'object', additionalProperties: false, required, properties,
})
const WORK_RESULT = obj(
  { digest: { type: 'string', description: 'The prompt-specific report or requested final status message.' } },
  ['digest'],
)
const runAgent = (prompt, options) => agent(prompt, { ...options, schema: WORK_RESULT }).then((result) => (result == null ? null : result.digest))

const ROOT = 'D:/ReverseTools/Android/battlecats-toolkit'
const EN = 'C:/Users/Prekzursil/Documents/bcsfe/game_data/en/15.3.0'
const JP = 'C:/Users/Prekzursil/Documents/bcsfe/game_data/jp/15.4.0'

const SHARED = [
  'GOAL (re-anchored): EXTEND the existing Battle Cats special-stage ATLAS into a LIVING STAGE COMPENDIUM that tracks EVERY special/event/tower stage across all dimensions. The atlas (read it first, it is your foundation): ' + ROOT + '/docs/game-knowledge/BC-EVENT-ARCHITECTURE.md (band->category map in §2, master table in §3, activation matrix §4, reset-risk §4.4).',
  'SCOPE: same as the atlas — ALL non-regular specials (Gauntlets, Behemoth Culling, Dojo, Collabs, Advent/Aku/Crazed/Awakens, Cyclones, Enigma, Colosseum, Way-of-Cat, Z-Outbreak, Towers, Catfruit/XP/Material/Ticket, Anniversary, Seasonal). EXCLUDE main story + SoL/UL/ZL ladders.',
  'HARD RULES: (1) READ-ONLY. No device/ADB/frida/save/running game. Parse LOCAL files + the web only. (2) Cite the exact file/line or wiki page for every claim. (3) Return STRUCTURED pipe-delimited tables, concise, no prose essays. (4) When a dimension is unknown for a band, say "unknown" explicitly — do NOT fabricate.',
  'LOCAL DATA (read with Read/Bash/Grep):',
  '  - EN content pack: ' + EN + '/DataLocal/Map_option.csv (stageID authority), ' + EN + '/resLocal/All_day_event.tsv (EN names). Gacha/cat sources in ' + EN + '/DataLocal/: GatyaDataSetN1-3/R1-3/E1-3.csv (gacha pools), DropItem.csv, Adreward_table.csv, EventGatya_Setting.csv, EventGatyaMedamaItem.json, unit files.',
  '  - JP content pack (for cross-region diff): ' + JP + '/DataLocal/Map_option.csv + ' + JP + '/resLocal/ (also jp/15.2.0, 15.3.0, 15.3.1 exist for history).',
  '  - event_0 schedule TSVs: ' + ROOT + '/dat-cache-decode/_stock_ev0.plain.tsv (real), event0_allon_monthly.plain.tsv (all-on). Schema in ' + ROOT + '/dat-cache-decode/STARTUP_FILTER_RE.md.',
  '  - Stage rewards / drop cats: ' + ROOT + '/tools/tbcml-bake/cross-region/MapStageData (per-map reward+drop records).',
  '  - Runtime namespace: ' + ROOT + '/dat-cache-decode/stagedatamgr_dump.json.',
  '  - Activation model + prereq gates: ' + ROOT + '/docs/EVENT-UNLOCK-PLAYBOOK.md, ' + ROOT + '/dat-cache-decode/STARTUP_FILTER_RE.md (sub_819E20 prereq predicate, sub_5F8DF0 id-band gate).',
  '  - WEB: the Battle Cats wiki (battlecats.miraheze.org, battle-cats.fandom.com) for version-history (when stages/cats were added) + cat introductions.',
].join('\n')

phase('Enrich')
const tasks = [
  // ---- Close the completeness-critic gaps ----
  { label: 'gap:jp-crossregion', prompt: 'CRITIC GAP P0-1/P0-2 + the ASSETS dimension. Diff EN ' + EN + '/DataLocal/Map_option.csv vs JP ' + JP + '/DataLocal/Map_option.csv (and the resLocal Map name / All_day_event name files). Produce, PER BAND from the atlas §2: EN-only stageIDs | JP-only stageIDs | shared. Then NAME the ~51 EN-blank All_day_event rows using the JP names. Output a table: band | en_count | jp_count | shared | jp_only_examples(names) | asset_status(EN-present / NEEDS-IMPORT-FROM-JP / shared). This IS the "assets present locally vs needed from other region" compendium dimension. Confirm or correct the atlas §4.3 region-collab list (currently guessed from EN-blank names).' },
  { label: 'gap:sched-band-namespace', prompt: 'CRITIC GAP P1-1. The atlas flags six schedule-only bands (8xxx, 9089-9682, 15xxx, 17xxx, 26xxx, 28xxx) as "needs JP/MapStageData bake". VERIFY: grep ' + ROOT + '/tools/tbcml-bake/cross-region/MapStageData AND ' + ROOT + '/dat-cache-decode/stagedatamgr_dump.json for ANY id in those bands; also check JP ' + JP + '/DataLocal/Map_option.csv. If those ids appear in NEITHER content NOR MapStageData in EN OR JP, reclassify them as "schedule-namespace artifact / MapStageData-remap, NOT a content-bake gap". Output: band | in_EN_content | in_JP_content | in_MapStageData | in_stagedatamgr | reclassification.' },
  { label: 'gap:runtime-namespace', prompt: 'CRITIC GAP P1-2. Load ' + ROOT + '/dat-cache-decode/stagedatamgr_dump.json and print the actual set of mapId/stageId records it contains (the records[] ids). Confirm or refute the atlas "third runtime namespace" claim (ids 50321/50732/50742/51035 + gauntlet 5100/5110). Output: the real id list found + whether the 5xxxx runtime-namespace headline holds.' },
  { label: 'gap:exact-activatable', prompt: 'CRITIC GAP P1-3. Replace the atlas "~100 collabs" estimate with EXACT sets. From the event_0 all-on TSV + EN Map_option + All_day_event: compute per category the EXACT id lists for: (a) named-AND-allon-AND-non-retired(non-旧) => activatable-now; (b) content-present-but-no-allon-row => needs-row; (c) retired-旧 => unsafe. Focus collabs (2xxx) + gauntlets (24014-24080) + collab-gauntlets (27xxx). Output exact pipe-delimited id lists, not estimates.' },
  // ---- New compendium dimensions ----
  { label: 'dim:cat-linkage-gacha', prompt: 'NEW DIMENSION — CAT LINKAGE (gacha/collab). For COLLAB bands (2xxx, 27xxx, 9xxx) and event-gacha, map each collab/event to the UNITS it introduced. Sources: ' + EN + '/DataLocal/GatyaDataSetE1-3.csv + GatyaDataSetR1-3.csv (event/rare gacha pools = unit id lists per banner), EventGatya_Setting.csv, EventGatyaMedamaItem.json, and the wiki for collab->cat mapping + the unit NAMES + the game version each cat/collab was added. Output: collab/event | mapid_band | introduced_units(ids+names) | gacha_set | first_added_version. Be concrete where the data allows; "unknown" where not.' },
  { label: 'dim:cat-linkage-drops', prompt: 'NEW DIMENSION — CAT LINKAGE (stage drops/unlocks). For Advent/Crazed/Awakens/Cyclone/Behemoth/EX stages, map each stage to the UNIT it unlocks or drops. Sources: ' + ROOT + '/tools/tbcml-bake/cross-region/MapStageData (per-map reward/drop unit records), ' + EN + '/DataLocal/DropItem.csv + Adreward_table.csv, and the wiki. E.g. Crazed 1017-1025 -> Crazed cats; Awakens 1045-1138 -> evolved forms; Behemoth Culling -> Behemoth-Stone awakening. Output: mapid | stage_name | unlocks/drops_unit(id+name) | reward_type(drop/firstclear/unlock) | source.' },
  { label: 'dim:addition-versions', prompt: 'NEW DIMENSION — WHEN ADDED (temporal). For each category/band AND each major named stage, find the game VERSION (and date) it was ADDED. Sources: the wiki version-history pages (battlecats.miraheze.org Version_X.Y_Update pages list new stages/events/cats per version) + the event_0 min_ver field (a proxy: 50700=15.7-class, 110500=11.5 guerrilla, 140000=14.0 carrier) + the atlas inline dates. Output: category/band_or_stage | added_version | added_date | source. Cover the spread from old (EoC-era specials) to newest (15.4.x anniversary). Flag the NEWEST additions (15.3-15.4) specifically.' },
  { label: 'dim:semi-story-progressive', prompt: 'NEW DIMENSION — SEMI-STORY / PROGRESSIVE classification. Classify EACH stage/band as one of: FREELY-REPEATABLE | ONE-TIME-UNLOCK | PROGRESSIVE-CHAIN (clear A to unlock B...) | SEMI-STORY (gated, story-like progression). Sources: the prereq predicate sub_819E20 + unlock conditions in Map_option.csv (prereq columns) + STARTUP_FILTER_RE.md + the atlas unlock notes. Canonical examples to map: Gates of Aku 1255->...->1268 Unleashing (progressive chain), Aku Realms unlock, Crazed-cat unlock gating, Behemoth Culling unlock subs 1312-1318/1333-1347, EX parent-gating (4xxx entered from parent), Way-of-Cat 検定 初段->十二段 (progressive ranks), Tower floors (progressive within a tower). Output: band/stage | classification | prerequisite_chain(if any) | unlock_target | evidence.' },
]
const results = h6Survivors(await settle(
  tasks.map(t => () => runAgent(SHARED + '\n\n=== YOUR SUBTASK ===\n' + t.prompt, { label: t.label, phase: 'Enrich' }))
, H6_TIMEOUT_MS))
log('Enrich done: ' + results.length + '/' + tasks.length + ' enrichment streams returned')

phase('Compile')
const corpus = results.map((r, i) => '### STREAM ' + (i + 1) + ' (' + tasks[i].label + ')\n' + r).join('\n\n')
const compendium = await runAgent(
  SHARED + '\n\n=== YOUR SUBTASK: WRITE THE LIVING STAGE COMPENDIUM ===\n' +
  'Synthesize the atlas (BC-EVENT-ARCHITECTURE.md) + all enrichment streams below into ONE comprehensive LIVING compendium and WRITE it (Write tool) to ' + ROOT + '/docs/game-knowledge/BC-STAGE-COMPENDIUM.md. It MUST contain:\n' +
  '1. A short pointer to BC-EVENT-ARCHITECTURE.md for the activation model (do not duplicate it).\n' +
  '2. THE MASTER COMPENDIUM TABLE — one row per band/stage with columns: mapid_band | canonical_name | region(EN/JP/shared) | category | placement | local_assets | asset_status(present/NEEDS-IMPORT-FROM-JP) | schedule_type | repeatable | reset_risk | classification(repeatable/one-time/progressive/semi-story) | introduced_units | unlocks/drops | added_version | sources.\n' +
  '3. A CROSS-REGION ASSET MATRIX (EN-only / JP-only / shared per band; the ~51 newly-named blanks; what needs importing from JP).\n' +
  '4. A CAT-LINKAGE INDEX (collab/event -> introduced units + version; stage -> unlocked/dropped cat).\n' +
  '5. A SEMI-STORY / PROGRESSIVE section (the unlock chains: Gates of Aku, Aku Realms, Crazed, Behemoth unlock, Way-of-Cat ranks, EX parent-gating, tower floors).\n' +
  '6. A TEMPORAL / VERSION-HISTORY section (when each category/major stage was added; the newest 15.3-15.4 additions flagged).\n' +
  '7. A "LIVING — how to update this each version" section: the exact convention to diff a new version (re-decode event_0, diff Map_option vs prior, check the wiki Version page) + a dated CHANGELOG stub (start with "2026-06-16 — initial compendium, EN 15.4.1 / content 15.3.0").\n' +
  'Fold in the critic gap-closures (corrected region list, reclassified schedule-only bands, exact activatable sets, verified runtime namespace). After writing, return a concise summary: total bands, dimensions populated, biggest remaining unknowns.\n\n=== ENRICHMENT STREAMS ===\n' + corpus,
  { label: 'compile:compendium', phase: 'Compile' }
)

phase('Critique')
const critic = await runAgent(
  SHARED + '\n\n=== YOUR SUBTASK: COMPLETENESS CRITIC ===\n' +
  'A living compendium was written to ' + ROOT + '/docs/game-knowledge/BC-STAGE-COMPENDIUM.md. Read it. Adversarially assess: is any compendium dimension (region/asset-status, cat-linkage, added-version, semi-story/progressive) left as a hand-wave or estimate where the LOCAL data could have made it concrete? Did the cross-region diff actually use the JP pack? Are the cat-linkages cited to a gacha-set/MapStageData/wiki line, or guessed? Is the living-update convention actually runnable? Return a prioritized punch-list (P0/P1) of remaining gaps + the cheapest closure for each.\n\n=== COMPENDIUM SUMMARY FROM WRITER ===\n' + compendium,
  { label: 'critique:compendium', phase: 'Critique' }
)
return { compendium_summary: compendium, critic_punchlist: critic, streams_returned: results.length }
