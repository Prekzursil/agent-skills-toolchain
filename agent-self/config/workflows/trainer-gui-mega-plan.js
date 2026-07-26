export const meta = {
  name: 'trainer-gui-mega-plan',
  description: 'Deep multi-phase research+design+adversarial-critique workflow producing the master implementation plan for the Battle Cats trainer-GUI mega-upgrade: visual deck/slot editor, full cat editor, advanced filter, and a stage->team SOLVER (ideal + save-constrained teams, win-confidence, full game mechanics).',
  phases: [
    { title: 'Research', detail: 'parallel deep research: mechanics x stage-types x data-sources x algorithm x GUI' },
    { title: 'SolverDeepDive', detail: 'extra-depth research on the stage->team solver engine (the crux)' },
    { title: 'Design', detail: 'synthesize research into concrete design sections' },
    { title: 'Critique', detail: 'adversarial reviewers: feasibility/completeness/scope/algorithm + 5-perspective design gate + data-accuracy/perf/testability' },
    { title: 'Refine', detail: 'revise each design section to resolve critique concerns' },
    { title: 'Finalize', detail: 'compile + integrate-critique + append phased build plan -> the master plan' },
  ],
}

const ROOT = 'C:/Users/Prekzursil/source/reports/plan-trainer-gui-mega'

const CTX = `PROJECT: Battle Cats EN 15.3.0 trainer-GUI mega-upgrade — a planning effort (NO implementation; produce a plan). KEY LOCATIONS (use Read/Grep/Glob/Bash on these):
- Trainer GUI (PySide6): D:/ReverseTools/Android/bc-toolkit-unified-wt/tools/trainer-gui/trainer_gui/ — shell/ (main_window, activity_bar, section_panel, status_*), controllers/ (base.py = BaseController/Worker/QThread KEYSTONE: _work never touches self, shutdown joins; plus data, orbs, aku, monthly, heartbeat, readonly), services/ (bc_save_reader, content_loader, bc_event_index, orb_catalog, save_routing, adb, frida_probe, event0), panels: stages/panel.py, orbs/panel.py, logbook/panel.py, audit/panel.py, settings/panel.py, theme/ (manager, tokens). Tests under tools/trainer-gui/tests/ (100% line+branch coverage gate, pytest, QT_QPA_PLATFORM=offscreen).
- BC game data (8738 files CSV/TSV/JSON): C:/Users/Prekzursil/Documents/bcsfe/game_data/en/15.3.0/DataLocal/ (units, enemies, stages: MapData_*.csv, stage*.csv, unitbuy.csv, unitlevel.csv, unitlimit.csv, SkillAcquisition*, NyancomboData*, t_unit*) and resLocal/ (localized names, All_day_event.tsv).
- BCSFE save lib: D:/ReverseTools/Android/BCSFE-Python/src/bcsfe (core.SaveFile; lineups [slots[i].slots[j].cat_id, names], equipped_talent_orbs, owned cats/levels/forms/talents/treasures/combos).
- Prior BC knowledge docs: D:/ReverseTools/Android/bc-toolkit-unified-wt/docs/knowledge/ (decks, orbs) + docs/research/ (stage-system, sources) + C:/Users/Prekzursil/source/reports/research/.
EXTERNAL: use WebSearch/WebFetch + Context7 (mcp) for battle-cats.fandom wiki (unit/enemy/stage data + RECOMMENDED LINEUPS = prior art/validation), community team-builders, BC battle simulators, and optimization-algorithm references.
DISCIPLINE: be exhaustive + specific; cite sources; grade each key claim HIGH/MED/LOW confidence; flag unknowns; always tie findings back to IMPLICATIONS for building the stage->team solver + GUI.`

function rprompt(id, title, body, subs) {
  return `${CTX}

ROLE: Deep-research analyst. TOPIC: ${title}.
${body}
COVER THOROUGHLY: ${subs}

DELIVERABLE: Use the Write tool to write a thorough, structured markdown findings doc to the ABSOLUTE PATH ${ROOT}/research/${id}.md. Include: concrete schemas/formulas/IDs/data-file names with examples, what's known (+source+confidence), open questions, and explicit IMPLICATIONS for the team-solver and the GUI. This feeds an implementation plan — depth and correctness matter more than brevity.
FINAL MESSAGE (one line only): "${id}: <one-sentence summary + the single biggest risk/unknown>".`
}

function sprompt(id, title, body, subs) { // solver deep-dive (writes to research/ too)
  return rprompt(id, title, body, subs)
}

function dprompt(id, title, reads, subs) {
  return `${CTX}

ROLE: Senior designer/architect. DESIGN SECTION: ${title}.
First READ the relevant research already written in ${ROOT}/research/ (use Glob "${ROOT}/research/*.md" then Read the files matching: ${reads}). Synthesize them.
PRODUCE a concrete, buildable DESIGN for "${title}". COVER: ${subs}
Be specific: dataclasses/types, module + file layout (relative to tools/trainer-gui/trainer_gui/), function/class interfaces, algorithms with pseudo-code, data flow, and how it integrates with the existing GUI keystone (BaseController/Worker). Note dependencies + risks.

DELIVERABLE: Write the design to ${ROOT}/design/${id}.md (Write tool).
FINAL MESSAGE (one line): "${id}: <one-sentence design summary + the key dependency/risk>".`
}

function cprompt(id, role, focus) {
  return `${CTX}

ROLE: ADVERSARIAL REVIEWER — ${role}. You are skeptical; your job is to find real, blocking problems, not to praise.
READ the design docs in ${ROOT}/design/ (Glob "${ROOT}/design/*.md" then Read all) and the supporting research in ${ROOT}/research/ as needed.
CRITIQUE strictly through this lens: ${focus}
List concrete issues ranked by severity (BLOCKER / MAJOR / MINOR), each with a specific fix or a simpler alternative. Call out anything under-specified, factually wrong, infeasible, over-engineered, or missing.

DELIVERABLE: Write your critique to ${ROOT}/critique/${id}.md (Write tool).
FINAL MESSAGE: end with exactly one of "VERDICT: PASS" (design is sound, complete, and feasible for your lens — only MINOR issues) or "VERDICT: CONCERNS" followed by your top 3 BLOCKER/MAJOR issues in one line each.`
}

// ---------------- RESEARCH TABLES ----------------
const MECH = [
  ['mech-traits','Enemy traits & cat anti-trait targeting','Map the full trait system end to end.','all enemy traits (Red, Floating, Black, Angel, Alien/Starred-Alien, Zombie, Relic, Aku, White/Traitless, Metal, Witch, Eva-Angel, Colossus, Behemoth, Sage); what "targets"/"Strong against"/"Massive Damage vs" means; the bitfield encoding of traits in the unit & enemy CSV columns; how multi-trait enemies work'],
  ['mech-offense','Offensive ability damage multipliers','Quantify the damage abilities.','Strong (x1.5/x1.8?), Massive Damage (x3/x4?), Insane Damage, Savage Blow (% proc + multiplier), Critical (vs Metal), Metal Critical; exact multipliers + proc chances + the CSV encoding'],
  ['mech-slayers','Slayer/anti-special abilities','Map the special-target abilities.','Zombie Killer, Soulstrike, Colossus Slayer, Behemoth Slayer, Sage Slayer, Metal (1-damage rule), Witch Killer, Eva-Angel Killer, Barrier Breaker, Shield Piercing; thresholds + encoding'],
  ['mech-control','Control abilities','Quantify crowd control.','Knockback (count), Freeze (prob+duration), Slow (prob+duration), Weaken (prob+duration+%), Curse; the proc/duration encoding; how they shift a fight'],
  ['mech-defense','Defensive abilities','Map survivability abilities.','Resistant / Insane Resistant (vs trait), Dodge (Tricky/prob), Warding, Strong (defensive half), Survives-lethal, Zombie-revive; immunity flags'],
  ['mech-waves-surge','Wave / Surge mechanics','Map the AoE-projectile mechanics.','Wave + Mini-wave (level, count, range), Surge + Mini-surge (range band, level), Counter-surge, wave-blocker, wave/surge immunity; how they hit the backline'],
  ['mech-combos','The Combo (Nyancombo) system','Map the team-buff combo system fully.','all combo categories (Cooldown/Attack/Health/Worker/Wallet/Strengthen/Move Speed/Knockback/Research/Accounting/Study/Energy/Defense/Critical/Savage/Resist/Special/Eva etc.), S/M/L magnitudes, the cat-set that forms each, that combos require the forming cats in the deck slots'],
  ['mech-talents','NP Talents','Map the talent system.','the talent tree per unit, what talents add (stat % up, new abilities, immunities, cost/recharge down), the SkillAcquisition data file, max talent levels, Ultra Talents'],
  ['mech-forms','Forms & evolution','Map forms.','1st/2nd(evolved)/True/Ultra forms, evolution requirements (XP/catfruit/behemoth stones), the per-form stat+ability differences, why True form matters'],
  ['mech-levels-catseyes','Levels, +levels, catseyes','Map leveling + stat scaling.','base level cap, plus-levels, catseye/catfruit caps, the exact per-level HP/ATK growth formula (the level multiplier curve)'],
  ['mech-treasures','Treasures & stat boosts','Map the treasure power system.','each treasure set + its % HP/ATK boost to cats (the cumulative treasure bonus), the EoC/ITF/CotC treasure tables, how treasures gate effective player power'],
  ['mech-stats-formula','Effective-stat computation formula','Derive the FULL effective stat formula.','effective HP/ATK = base x level-multiplier x treasure-multiplier x talent x orb; the exact order + rounding; range/speed/KB/cost/recharge (which scale, which dont); cite the formula source'],
  ['mech-cannon-base','Cat Cannon & Ototo base','Map the cannon/base.','cannon types (normal/slow/iron-wall/thunder/holy-blast/curse/breaker) + effects, the Ototo base upgrades (foundation/style/cannon levels), how the cannon factors into clears'],
  ['mech-economy','Money/worker economy & timing','Map the in-battle economy.','money generation, worker-level cost curve + cap, cat cost & recharge, wallet cap, the meatshield-spam economy, the early/mid/late money curve'],
  ['mech-roles-meta','Cat roles & metagame','Classify cats by combat role.','roles: meatshield/wall, generalist attacker, sniper/backliner, anti-trait specialist, control (KB/freeze/slow), support/buffer, tank, crowd-pusher; how a balanced team composes these'],
  ['mech-rarity','Rarities & cost/recharge tradeoffs','Map rarities.','Normal/EX/Rare/Super Rare/Uber Super Rare/Legend Rare; cost vs recharge vs power; availability (gacha vs farmable); the role each rarity tends to fill'],
  ['mech-range-attack','Range, area, positioning','Map the spatial game.','range value, single vs area attack, long-distance (min..max range), omni-strike, attack animation/foreswing/backswing timing, the spacing/positioning that decides fights'],
  ['mech-special-enemy','Special enemy mechanics','Map the gimmick mechanics.','barriers (break threshold), shields (Aku), zombie corpse-revive + burrow, surge fields, metal (1-damage + crit), relic (curse interaction), colossus/behemoth/sage damage rules, the wave/surge bosses'],
  ['mech-immunity-matrix','The full immunity matrix','Tabulate immunities.','which abilities can be immune (KB/freeze/slow/weaken/wave/surge/curse/toxic/warp/explosion), how enemies AND cats encode immunities, the implication for which control abilities work on a given stage'],
  ['mech-orbs','Talent Orbs','Map the equippable orb system.','attack/defense/effect orbs per trait + grade (D..S), their % effects, the per-cat 1-3 orb slots, how orbs change effective stats vs a trait (ties to docs/knowledge/orbs)'],
  ['mech-anti-trait-matrix','Cat->trait effectiveness matrix','Define the effectiveness matrix.','how to compute, for any cat vs any enemy trait, an effectiveness score combining anti-trait targeting + Strong/Massive/Resistant + slayers; the data needed to build this 700xN matrix'],
  ['mech-uber-tierlist','Strongest units by role (meta)','Survey the current EN meta.','the strongest/most-used ubers + key rares/specials by role (anti-Red, anti-Alien, anti-Floating, generalist, control, behemoth) — to seed the ideal-team pool; cite community tier lists with confidence'],
]
const STAGE = [
  ['stage-eoc','Empire of Cats','EoC chapters mechanics.','ch1-3 enemy progression, the moon magnification, base HP, the cannon role, the canonical early-game lineup'],
  ['stage-itf','Into the Future','ITF mechanics.','ch1-3, the ITF treasure STAT-DOWN on enemies, starred aliens, the alien-specialist need'],
  ['stage-cotc','Cats of the Cosmos','CotC mechanics.','ch1-3, relic enemies, star enemies, the harder magnification, the no-easy-clear gating'],
  ['stage-sol','Stories of Legend','SoL mechanics.','the SoL sub-chapters, the enemy roster, crowns (1-4) and their enemy stat magnification per crown'],
  ['stage-ul','Uncanny Legends','UL mechanics.','UL difficulty + crowns + the stronger magnification + the anti-meta enemies'],
  ['stage-z','Zero Legends','Z Legends mechanics.','the newest sub-chapters + mechanics + the enemies introduced'],
  ['stage-events','Limited event stages','Event-stage mechanics.','collab/seasonal limited stages, their special enemies, the time-limited availability (ties to the event_0/guerrilla system already RE-d)'],
  ['stage-gauntlet','Gauntlets / Baron stages','Gauntlet mechanics.','the no-continue, the back-to-back stages, the time-limited clears, the strict lineup demands'],
  ['stage-aku','Aku Realm / Uncanny','Aku mechanics.','the Aku trait, the Aku floors/labyrinth, the Aku-shield, the Aku-slayer need (ties to the guerrilla/+4536 RE)'],
  ['stage-behemoth','Behemoth Culling','Behemoth mechanics.','the Behemoth trait + Behemoth Slayer + Savage Blow, the Behemoth Stones, the gauntlet structure'],
  ['stage-dojo','Catclaw / Ranking Dojo','Dojo mechanics.','SCORE-based not clear-based (down-the-hole damage), the ranking, why team-building differs (max damage before death) — flag as a special solver mode'],
  ['stage-collab','Collab event stages','Collab mechanics.','the collab-specific enemies + gimmicks (EVA, Bikkuriman, etc.), the collab cat tie-ins'],
  ['stage-cyclone-advent','Cyclones & Advent','Cyclone/Advent mechanics.','the Cyclone bosses (Crimson/Cyberhorn/etc.), the Advent stages + their unique bosses + counters'],
  ['stage-material-xp','Material/Catfruit/XP/Ticket farming','Farming-stage mechanics.','the material/catfruit/XP/ticket stages, the farming-efficiency optimization (a different objective: speed/yield not just clear)'],
  ['stage-tower-legendquest','Towers / Citadels / Legend Quest','Multi-floor mechanics.','the multi-floor towers, cumulative difficulty, Legend Quest gating'],
  ['stage-restrictions','Line-up restriction taxonomy','Catalog ALL restriction types.','rarity-only (e.g. Specials only), cost-limit, slot-count-limit, no-continue, specific-cat-only, no-gacha, max-deploy, level-cap, no-cannon; HOW restrictions are encoded in stage data (MapConditions.json, FilterStage_Setting.csv) — CRITICAL for the solver'],
  ['stage-magnification','Enemy stat magnification','Decode the magnification system.','how a stage scales each enemy HP/ATK (the per-enemy magnification %), the crown multipliers, where it lives in the stage CSV — the solver MUST apply this to get effective enemy stats'],
  ['stage-schema-mapdata','Stage/Map CSV schema','Decode the stage data schema with examples.','MapData_*.csv + stage*.csv columns: enemy id, spawn (start-delay, respawn, count, base-distance), magnification HP/ATK, the boss flag, base HP, length, money, the wave structure; parse a concrete example stage end-to-end'],
  ['stage-treasures-rewards','Stage treasures & rewards','Map rewards.','the % treasures + their grind, the rewards/drops, how clearing builds player power over time (relevant to the available-team progression)'],
  ['stage-crown-difficulty','Crown / star difficulty','Map the difficulty multipliers.','the 1-4 crown (star) system, the enemy stat multiplier per crown, the Zombie Outbreaks, how difficulty maps to required team power'],
]
const DATA = [
  ['data-unit-csv','Unit stat CSV schema','Decode the unit data files.','unitbuy.csv (cost/recharge/rarity/unlock), unitlevel.csv (level curve), unitlimit.csv, the per-form stat CSVs (HP/ATK/range/speed/KB/foreswing), the ABILITY bitfield columns + how to decode each ability + its params; show real rows'],
  ['data-enemy-csv','Enemy stat data schema','Decode enemy data.','the enemy stat files (HP/ATK/range/speed/abilities/traits), how to resolve an enemy id -> stats + abilities + traits; show real rows'],
  ['data-stage-csv','Stage data parsing','Deep-parse the stage files.','given a map/stage id, how to get the ordered enemy list with per-enemy magnification + spawn params + base HP + restrictions; the file naming convention (Map vs stage); reuse what BCSFE/tbcml already parse'],
  ['data-skill-talent','Skill/Talent data','Decode talents.','SkillAcquisition + the talent data: map unit -> available talents -> stat/ability effects + the NP costs + max levels'],
  ['data-combo','Combo data (NyancomboData)','Decode combos.','the combo definition file: each combo -> forming cat-ids + the buff type + magnitude; how to detect which combos a given deck activates'],
  ['data-bcsfe-tbcml','BCSFE & tbcml abstractions','Survey reusable parsers.','what BCSFE (D:/ReverseTools/Android/BCSFE-Python) and tbcml already parse (units, enemies, stages, gatya); the python APIs to REUSE instead of re-parsing raw CSVs; gaps we must fill ourselves'],
  ['data-wiki-prior-art','Wiki data + recommended lineups','Mine the wiki as data + validation.','battle-cats.fandom: unit/enemy/stage stat pages, and crucially the per-stage RECOMMENDED LINEUPS / strategy sections (prior art for the solver + a validation corpus); how reliably it can be fetched'],
  ['data-community-tools','Community tools, sims, APIs','Survey existing tooling.','existing BC team-builders / "what beats X" tools, open-source BATTLE SIMULATORS (for win-prob), data viewers (godfat, bcdb), any API; what to reuse vs build'],
  ['data-save-model','Save -> player capability model','Map the user-availability inputs.','from a BCSFE SaveFile: owned cats (+forms unlocked), per-cat level/plus-level, per-cat talents, treasures (per chapter), user rank, the combos the user can form, equipped orbs; the exact BCSFE accessors'],
]
const ALGO = [
  ['algo-formulation','Team-building as constrained optimization','Formalize the optimization problem.','decision variables (the <=10 cats chosen + the deploy/loadout + cannon), constraints (slot/restriction/economy-feasibility), objective (maximize calibrated win-probability); the math statement + why it is NP-hard-ish'],
  ['algo-counter-heuristic','Counter/effectiveness heuristic','Design the per-cat-vs-stage score.','given the stage enemy composition (traits+abilities+effective stats+timing), rank candidate cats by anti-trait targeting, damage output vs the composition, control value, survivability, range fit'],
  ['algo-search-methods','Optimization/search method survey','Compare methods for this size.','greedy+local-search, beam search, MILP, genetic algorithm, simulated annealing, MCTS — feasibility/quality/latency tradeoffs for ~700 cats choose <=10 with team-level combo coupling; recommend'],
  ['algo-win-probability','Win-probability / confidence model','Design the confidence output.','how to produce a calibrated 0-100% confidence: heuristic scoring (team-DPS vs enemy effective-HP race, range advantage, control uptime, economy curve, base-HP race) and/or simulation; how to calibrate'],
  ['algo-battle-sim','Lightweight battle simulator feasibility','Assess a sim for accurate confidence.','the BC battle is a 1D lane fight (spawn, march, attack with foreswing, KB, the base-HP race); minimal deterministic+stochastic model; cost vs accuracy; existing sims to port; whether a sim or a heuristic is the right MVP'],
  ['algo-economy-model','In-battle economy feasibility model','Model affordability of a strategy.','can the team afford its plan over time? the worker-level curve, income vs cat-cost, the meatshield cadence; a tractable economy model the optimizer/sim can use'],
  ['algo-ideal-vs-available','Ideal vs save-constrained modes','Specify the two solver modes.','(A) IDEAL = best with ALL cats at max forms/levels/talents (theoretical counter, may include unowned cats); (B) AVAILABLE = best with the users OWNED cats at ACTUAL level/form/talent/combos/orbs; how each is computed + presented + the "you are missing X" diffing'],
  ['algo-talent-combo-opt','Talents + combos in optimization','Handle team-level coupling.','talents change a cats effective stats/abilities; COMBOS are team-level buffs that couple the selection (choosing combo-forming cats changes everyone) — how to optimize with this coupling (joint search / combo-aware scoring)'],
  ['algo-positioning-range','Positioning/range sub-problem','Model the spatial composition.','frontline meatshields vs backline attackers, range coverage, anti-rush vs anti-tank balance, how to encode "the team has the range profile to handle this stages threats"'],
  ['algo-explainability','Explainable recommendations','Design the rationale generator.','generate a human rationale ("Cat A counters the Red boss via Massive Damage; B provides Knockback to stop the rush; C is the meatshield; the combo gives +Attack; economy supports two attackers") from the solver internals'],
  ['algo-validation','Solver validation strategy','Design how to prove the solver works.','the validation corpus (wiki recommended lineups + known-good community teams + simulatable stages), the metrics (does our team clear in sim? does it overlap the wiki team?), regression tests'],
  ['algo-performance','Solver performance/precompute','Design for interactive latency.','~700 cats x thousands of stages; precomputation (cat effectiveness matrices, stage models), caching, incremental recompute on save edits, the latency budget for an interactive GUI'],
]
const GUI = [
  ['gui-existing-arch','Existing trainer-GUI architecture','Deep-read the current GUI.','the shell (main_window/activity_bar/section_panel), the BaseController/Worker/QThread keystone (async save ops, _work isolation, shutdown join), the save wiring (bc_save_reader/save_routing/content_loader), the theme system, the existing stages/orbs/logbook panels; the EXACT seams to add new panels+controllers'],
  ['gui-deck-editor','Visual deck/slot editor','Design the deck editor UX+data.','the BCSFE lineups model (21 decks x 10 slots + loadout + names + cannon/base per deck), drag-drop reordering, cat picker, the live save read/write, multi-deck management'],
  ['gui-cat-editor','Cat editor (level/form/talent/orb)','Design the cat editor.','per-cat edit: level/+level, form (unlock/select), talents (per-talent level), equipped orbs; the effective-stat PREVIEW after edits; the BCSFE write-back + save-routing + undo'],
  ['gui-advanced-filter','Advanced filter','Design the roster filter.','filter the ~700 cats by: trait-targeted, ability present, rarity, owned/unowned, level range, form, role, cost/recharge, stat thresholds; the filter query model + the responsive UI'],
  ['gui-stage-team-viewer','Stage -> ideal-team viewer','Design the stage browser + team view.','the stage browser (chapter/map/stage tree using the stage data), per-stage the ideal team + each cats role + effective stats + the enemy breakdown (what threats + magnification)'],
  ['gui-team-suggester','Team suggester panel','Design the recommender UX.','input a stage -> output ranked team(s) with CONFIDENCE %, BOTH ideal + save-constrained, the explanation/rationale, the "missing cat" hints, the alternative-teams list'],
  ['gui-data-pipeline','Data/service pipeline','Design loading game_data+save into the solver.','loading the 8738-file game_data + the save into an in-memory model the solver consumes; caching/precompute; extending content_loader; keeping the UI responsive via the keystone (off-thread compute)'],
  ['gui-pyside-patterns','PySide6 patterns for new panels','Pin the framework patterns.','virtualized lists for 700 cats (QAbstractItemModel/QListView), drag-drop (QDrag/QMimeData), async compute off the UI thread, the existing theme tokens, dialog/preview patterns, testability with offscreen Qt'],
  ['gui-asset-rendering','Cat/enemy icon rendering','Design asset display.','where the game cat/enemy ICON+sprite assets live (APK/local), how to extract/cache/display them in the deck editor + team viewer; fallback when an asset is missing'],
  ['gui-onboarding-export','Onboarding, export/share, compare','Design the supporting UX.','first-run/help, exporting/sharing a team (text/image/code), comparing two teams side-by-side, the settings for solver depth/mode'],
]
const SOLVER_DEEP = [
  ['solver-arch','Solver engine architecture','Specify the end-to-end engine.','the pipeline stage-model -> candidate-pool -> per-cat scoring -> constrained optimization -> team -> confidence -> explanation; pure-python testable modules; the public API the GUI calls'],
  ['solver-stage-model','Canonical stage model','Define the stage data structure.','the StageModel the solver consumes: ordered enemy encounters with EFFECTIVE stats (post-magnification+crown), spawn timing, base HP, length, restrictions, economy params; built from the parsed stage CSVs'],
  ['solver-cat-model','Canonical cat model','Define the cat data structure.','the CatModel: effective stats per chosen form/level/talent/orb/treasure, the decoded ability set + params, the role classification, cost/recharge; built for both ideal (max) and available (save) modes'],
  ['solver-scoring','Per-cat-vs-stage scoring function','Draft the concrete scoring formula.','a concrete numeric score combining: anti-trait/slayer effectiveness vs each enemy, effective DPS vs effective-HP, range fit, control value (KB/freeze/slow uptime), survivability vs enemy DPS, cost-efficiency; weights + rationale'],
  ['solver-optimizer','Optimizer algorithm (concrete)','Draft the chosen optimizer.','pick + draft the algorithm (e.g. greedy role-coverage seed + combo-aware local search, or beam search) that selects <=10 cats maximizing team score under constraints + combo coupling; pseudo-code + complexity'],
  ['solver-confidence','Confidence calculation (concrete)','Draft the confidence formula.','the concrete win-confidence computation + calibration (vs the sim / vs known clears); how to bucket into HIGH/MED/LOW + a % ; honesty about uncertainty'],
  ['solver-constraints','Constraint handling','Specify constraint enforcement.','restriction filtering (rarity/cost/slot/specific-cat), economy feasibility check, the loadout/deploy ordering; how the optimizer respects them (filter pool vs penalty)'],
  ['solver-combo-integration','Combo-aware selection','Solve the combo coupling.','since combos require specific forming cats in slots and buff the whole team, draft how the optimizer evaluates combo value vs the slot opportunity cost (joint/iterative selection)'],
  ['solver-data-binding','Solver <-> game_data binding','Specify the parse/bind layer.','exactly which CSVs feed the stage + cat models, the parse functions (reuse BCSFE/tbcml where possible), the in-memory caches, the precomputed effectiveness matrices'],
  ['solver-edge-cases','Solver edge cases & special modes','Enumerate the hard cases.','restriction-only stages, no-cannon stages, timed/no-continue gauntlets, multi-wave, dojo SCORE-mode (max damage not clear), "needs a specific uber" stages, farming-efficiency mode; how the solver detects + handles each'],
]

const DESIGN = [
  ['design-overview','Feature & architecture overview','mech-*, gui-existing-arch, solver-arch, algo-ideal-vs-available','the 5 features + the solver as a cohesive product; the new module map under trainer_gui/; how it layers on the existing shell/keystone; the MVP vs full vision'],
  ['design-data-model','Canonical data model','solver-stage-model, solver-cat-model, data-*, mech-stats-formula','the dataclasses for Cat, Enemy, Stage, Team, SaveState, Ability; the effective-stat computation; the parse/bind layer types'],
  ['design-solver-engine','Solver engine design','solver-*, algo-*','the concrete engine spec: modules, the public API, the scoring + optimizer + confidence + explanation, the two modes, performance/precompute, the edge-case handling'],
  ['design-deck-editor','Deck/slot editor design','gui-deck-editor, gui-pyside-patterns, data-save-model','the panel + controller, the lineups read/write, drag-drop, the multi-deck/cannon model, save-routing safety'],
  ['design-cat-editor','Cat editor design','gui-cat-editor, mech-*, data-save-model','the per-cat edit panel, level/form/talent/orb editing, the effective-stat preview, the BCSFE write path + undo'],
  ['design-advanced-filter','Advanced filter design','gui-advanced-filter, mech-anti-trait-matrix','the filter model + UI, the queryable attributes, integration with the roster + the suggester'],
  ['design-stage-team-feature','Stage->team viewer + suggester design','gui-stage-team-viewer, gui-team-suggester, solver-arch, algo-explainability','the stage browser, the ideal+available team views, the confidence display, the rationale + missing-cat hints, the alternatives'],
  ['design-data-pipeline','Data/service pipeline design','gui-data-pipeline, solver-data-binding, data-bcsfe-tbcml','loading game_data+save, caching/precompute, content_loader extension, off-thread compute via the keystone'],
  ['design-gui-integration','GUI integration design','gui-existing-arch, gui-pyside-patterns','wiring the new panels/controllers into the shell + activity bar, the BaseController/Worker usage, threading, theming'],
  ['design-tech-stack','Tech stack & dependencies','data-community-tools, algo-search-methods, algo-battle-sim','the libraries (optimization? sim? caching? image), build/deps, secure-by-default for parsing untrusted data + save writes, the dependency risk'],
  ['design-testing','Testing & validation strategy','algo-validation, gui-pyside-patterns','how to hit 100% line+branch coverage; testing a solver (golden teams, the validation corpus, property tests, deterministic seeds); testing the GUI panels offscreen'],
  ['design-build-plan','Phased build plan (WU decomposition)','design-overview, design-solver-engine','the metaswarm-style work-unit decomposition, ordering + dependencies, milestones, the MVP-first path, effort sizing, risk register'],
]

const CRITIQUE = [
  ['critique-feasibility','Feasibility engineer','Is the solver buildable to USEFUL accuracy with realistic effort? The hardest risks (battle-sim accuracy, data completeness, combo coupling, the 700xstage scale). Is the confidence honest or fake-precise?'],
  ['critique-completeness','Completeness reviewer','What is MISSING? mechanics not modeled, stage types/restrictions not handled, GUI features under-specified, edge cases dropped, data not sourced.'],
  ['critique-scope','Scope & alignment reviewer','Does the plan match the user ask EXACTLY (visual deck editor + cat editor + advanced filter + stage ideal-team + detail stats + suggested teams with confidence + ideal AND save-constrained + ALL mechanics/talents/combos)? scope creep or under-scope?'],
  ['critique-algorithm','Algorithm-soundness reviewer','Is the optimization + confidence model mathematically sound? the failure modes (local optima, miscalibrated confidence, ignoring timing)? a simpler/more-robust alternative?'],
  ['critique-pm','Product manager','User value + prioritization: what is the true MVP that delivers value fastest? what is gold-plating? is the phasing right? will users trust the confidence?'],
  ['critique-architect','Software architect','module boundaries, data-model soundness, coupling, the fit with the existing BaseController/Worker keystone + save-routing, maintainability, testability, the pure-core/UI-shell separation.'],
  ['critique-designer','UX designer','the flows (deck drag-drop, cat editing, the stage->team view, confidence + rationale display, missing-cat hints); information density; discoverability; the 700-cat performance feel.'],
  ['critique-security','Security reviewer','save-write SAFETY (corruption risk on the BCSFE write path; backups/undo), parsing untrusted CSV/wiki data safely, web-fetch SSRF, no secrets, the secure-by-default libs.'],
  ['critique-cto','CTO / go-no-go','overall viability + effort/value; the top 3 existential risks; the recommended scope CUT; go/no-go on the solver vs ship-editors-first.'],
  ['critique-data-accuracy','Data-accuracy reviewer','Are the game-data SCHEMAS/FORMULAS in the research actually CORRECT (the stat formula, magnification, ability encoding, the level/treasure multipliers)? these break the solver if wrong — spot the likely errors + how to verify against the live game/BCSFE.'],
  ['critique-performance','Performance reviewer','will it be responsive? the precompute cost, the optimizer latency per stage, the 700-cat lists, the data load of 8738 files, memory; the worst-case interactions.'],
  ['critique-testability','Testability reviewer','can this hit the 100% line+branch gate AND be meaningfully validated? the hard-to-test parts (the GUI drag-drop, the stochastic sim, the web data); the determinism needs.'],
]
const DESIGN_IDS = DESIGN.map(d => d[0])

// ===================== ORCHESTRATION =====================
const ALL_RESEARCH = [...MECH, ...STAGE, ...DATA, ...ALGO, ...GUI]

phase('Research')
log(`Research: launching ${ALL_RESEARCH.length} parallel deep-research agents (mechanics/stages/data/algorithm/GUI)`)
const research = await parallel(ALL_RESEARCH.map(t => () =>
  agent(rprompt(t[0], t[1], t[2], t[3]), { label: t[0], phase: 'Research' })))
log(`Research complete: ${research.filter(Boolean).length}/${ALL_RESEARCH.length} agents returned`)

phase('SolverDeepDive')
log(`Solver deep-dive: ${SOLVER_DEEP.length} agents on the team-solver engine (the crux)`)
const solver = await parallel(SOLVER_DEEP.map(t => () =>
  agent(sprompt(t[0], t[1], t[2], t[3]), { label: t[0], phase: 'SolverDeepDive' })))
log(`Solver deep-dive complete: ${solver.filter(Boolean).length}/${SOLVER_DEEP.length}`)

phase('Design')
log(`Design: ${DESIGN.length} synthesis agents`)
const design = await parallel(DESIGN.map(d => () =>
  agent(dprompt(d[0], d[1], d[2], d[3]), { label: d[0], phase: 'Design' })))
log(`Design complete: ${design.filter(Boolean).length}/${DESIGN.length}`)

phase('Critique')
log(`Critique: ${CRITIQUE.length} adversarial reviewers`)
const critique = await parallel(CRITIQUE.map(c => () =>
  agent(cprompt(c[0], c[1], c[2]), { label: c[0], phase: 'Critique' })))
const verdicts = critique.map((r, i) => ({
  id: CRITIQUE[i][0],
  pass: /VERDICT:\s*PASS/i.test(r || ''),
  note: ((r || '').match(/VERDICT:[\s\S]*/i) || [''])[0].slice(0, 260),
}))
const concerns = verdicts.filter(v => !v.pass)
log(`Critique complete: ${verdicts.filter(v => v.pass).length}/${verdicts.length} PASS; ${concerns.length} raised CONCERNS`)

phase('Refine')
log(`Refine: revising ${DESIGN_IDS.length} design sections to resolve critique concerns`)
const refine = await parallel(DESIGN_IDS.map(id => () =>
  agent(`${CTX}

ROLE: Senior designer doing a REVISION pass on design section "${id}".
READ: your section ${ROOT}/design/${id}.md AND all critiques in ${ROOT}/critique/ (Glob+Read). Identify every BLOCKER/MAJOR issue that touches "${id}".
REVISE ${ROOT}/design/${id}.md in place (Write tool) to resolve those issues: fix inaccuracies, fill gaps, cut over-engineering, add the missing specifics. Keep it concrete + buildable. Do NOT regress unaffected parts.
FINAL MESSAGE (one line): "${id}: <what you changed to resolve critique>".`,
    { label: `refine:${id}`, phase: 'Refine' })))
log(`Refine complete: ${refine.filter(Boolean).length}/${DESIGN_IDS.length}`)

phase('Finalize')
const FINAL = `${ROOT}/PLAN-trainer-gui-mega-features.md`
log('Finalize: drafting the master plan')
await agent(`${CTX}

ROLE: Lead author. Compile the MASTER IMPLEMENTATION PLAN.
READ: all of ${ROOT}/design/ (the REFINED designs) and skim ${ROOT}/research/ for specifics you need (Glob+Read).
WRITE the plan to ${FINAL} (Write tool). Structure:
1. Executive summary (what we are building + the headline: the stage->team SOLVER with ideal + save-constrained teams + win-confidence).
2. Feature specs: (a) visual deck/slot editor, (b) cat editor, (c) advanced filter, (d) stage->ideal-team viewer + detail stats, (e) team suggester (confidence, ideal+available, rationale, missing-cat hints).
3. The SOLVER engine: stage/cat models, scoring, optimizer, combo+talent handling, confidence, explainability, edge cases, performance.
4. Data model + the game_data/save binding (reuse BCSFE/tbcml where possible).
5. GUI architecture + integration with the existing shell/keystone; tech stack + dependencies (secure-by-default); testing/validation (100% coverage gate).
6. Open questions + the biggest risks.
Be concrete and complete; this is the canonical plan.
FINAL MESSAGE (one line): "draft written + the single biggest open risk".`,
  { label: 'finalize-draft', phase: 'Finalize' })

log('Finalize: integrating critique into the plan')
await agent(`${CTX}

ROLE: Editor. Harden the plan against the critique.
READ ${FINAL} and ALL critiques in ${ROOT}/critique/ (Glob+Read) + the verdict notes: ${JSON.stringify(concerns).slice(0, 1500)}.
REVISE ${FINAL} in place (Write tool): resolve every remaining BLOCKER/MAJOR, add a short "How the plan addresses each critique" subsection, adjust scope per the PM/CTO cut (call out the true MVP vs full vision), and ensure the confidence model is honestly caveated.
FINAL MESSAGE (one line): "integration done + residual risk".`,
  { label: 'finalize-integrate-critique', phase: 'Finalize' })

log('Finalize: appending the phased build plan')
await agent(`${CTX}

ROLE: Delivery lead. Append the BUILD PLAN.
READ ${FINAL} and ${ROOT}/design/design-build-plan.md.
APPEND to ${FINAL} (read it, then Write the full file with the new section) a "## Phased Build Plan" section: an ordered work-unit decomposition (each WU: goal, files/modules touched, deps, test/coverage target, done-criteria), grouped into milestones (MVP -> v1 -> full), with effort sizing (S/M/L), the critical path, and a risk register with mitigations. Make it executable by the metaswarm orchestration later.
FINAL MESSAGE (one line): "build plan appended; N work units across M milestones".`,
  { label: 'finalize-build-plan', phase: 'Finalize' })

return {
  research_files: research.filter(Boolean).length,
  solver_files: solver.filter(Boolean).length,
  design_files: design.filter(Boolean).length,
  critique_verdicts: verdicts,
  concerns_count: concerns.length,
  plan: FINAL,
  total_agents_approx: ALL_RESEARCH.length + SOLVER_DEEP.length + DESIGN.length + CRITIQUE.length + DESIGN_IDS.length + 3,
}
