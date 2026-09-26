---
title: BC unit.csv column map + derived orb-pick table
type: reference
permalink: main/battlecats/bc-unit.csv-column-map-derived-orb-pick-table
tags:
- battlecats
- orbs
- unit-csv
- 15.3.0
- reverse-engineering
---

# BC unit.csv column map + derived best-orb table (15.3.0 EN)

Ground-truth column map for `DataLocal/unitNNN.csv` (cat_id N -> unit{N+1:03d}.csv; each LINE = one form, last line = highest/true/ultra form). Source = fieryhenry/tbcml `src/tbcml/game_data/cat_base/cats.py` CatStats `col_index` fields, INDEPENDENTLY validated against battlecatsstats.com unit pages.

## Trait-target boolean columns (0-indexed)
Red=10, Floating=16, Black=17, Metal=18, traitless=19, Angel=20, Alien=21, Zombie=22, Witch=54, Eva=76, Relic=78, Aku=96. (Note: trait block is NOT contiguous — Float/Black/Metal/traitless/Angel/Alien/Zombie are 16-22 because cols 11-15 are unused/area_attack/foreswing/z-layers; Witch/Eva/Relic/Aku live in late extension columns.)

## Ability flag columns
strong=23, resistant=29, massive=30, crit_prob=31, is_metal=43, zombie_killer=52, witch_killer=53, eva_killer=77, curse_immunity=79, insanely_tough=80, insane_damage=81, savage_blow_prob=82, surge_prob=86, surge_level=89, toxic_immunity=90, surge_immunity=91, wave_prob=35, wave_is_mini=94, knockback_prob=24, colossus_slayer=97, behemoth_slayer=105, counter_surge=109, sage_slayer=111. Immunities: wave=46,kb=48,freeze=49,slow=50,weaken=51.

## KEY GOTCHA — prompt anchor labels were WRONG vs live 15.3.0 data
The task's 6 "known-true" anchors were mostly imprecise; the CSV+wiki are ground truth:
- cat24 Holy Valkyrie = targets ALL traits (area attacker), NO innate massive (talents=Atk/Def buff). NOT "Massive Angel".
- cat71 Sanada/Immortal Yukimura = Massive **Black** (NOT Red).
- cat38 Wheel/Chill = Massive **Alien** (NOT Black).
- cat41 Salon/Cyborg = area attacker, Survive, NO zombie-killer/strong-zombie.
- cat46 Jurassic/Catasaurus = Critical 12% + KB-resist, NO anti-metal.
- cat259 Radiant/Almighty Aphrodite = Massive Alien (correct).
Lesson: trust the CSV + battlecatsstats.com, not a remembered ability label.

## Orb catalog facts (orb_catalog_15.3.0.json)
Stat orbs exist for traits: Red, Floating, **Dark**(=Black in unit data), Metal, Angel, Alien, Zombie, Relic, Aku. Metal = **Defense/Attack only, NO Massive/Strong/Tough**. Effects: Attack Up, Defense Up, Strong Effect Up, Massive Damage Up, Tough Effect Up + traitless (Resist Waves/KB/Slow/Freeze/Surges/Curse/Toxic/Weaken/Explosions, Berserker, Shortened Cooldown, Cashback...). attribute_id: Red0 Float1 Dark2 Metal3 Angel4 Alien5 Zombie6 Relic7 Aku11.

## Deliverable
Decoder script: `D:\ReverseTools\Android\battlecats-toolkit\tools\save-tools\_workspace\derive_orb_picks.py` (run w/ `D:/ReverseTools/Android/BCSFE-Python/.venv/Scripts/python.exe`). Output JSON: `...\_workspace\derived_orb_picks.json` — 193 eligible cats, per-cat slot0/slot1 grade-S pick + confidence + undecidable flag. 99 high / 61 medium / 33 low; 21 undecidable (multi-trait massive/strong); 13 slot0=null (talent-only cats NOT in 180-orb roster: 80,93,97,130,187,362,452,469,613,649,658,662,691 — confirmed orb_slots=0 in orb_capable_roster_15.3.0.csv).
