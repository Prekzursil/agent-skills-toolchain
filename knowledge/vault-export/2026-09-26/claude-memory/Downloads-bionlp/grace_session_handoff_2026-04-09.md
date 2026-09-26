---
name: GRACE @ IberLEF 2026 session handoff
description: Phase 1-6 implemented locally. 15 experiment configs ready. 51 tests
  passing. Next = RunPod deploy for full sweep + Track 2 pipeline.
type: project
originSessionId: 7d868df4-f868-4a58-acac-c022173b11b4
permalink: main/claude-memory/downloads-bionlp/grace-session-handoff-2026-04-09
---

**Project:** GRACE @ IberLEF 2026 (Spanish clinical argument mining shared task)
**Workspace:** `C:\Users\Prekzursil\Downloads\bionlp\`
**Current state (2026-04-10 session 5):** Phases 1-6 implemented locally. 51 tests passing.

## Training results — 13 experiments across H100 + A100 (~$10 total GPU)

| # | Config | S1 F1 | Finding |
|---|---|---|---|
| **1** | **BETO 20ep lr=3e-5 custom loop** | **0.4037** | **CHAMPION** |
| 2 | BETO + oversampling 5x/3x/2x | 0.4019 | Oversampling = flat |
| 3 | BETO 30ep | 0.3879 | Overfits after 20 |
| 4 | BETO 10ep baseline | 0.3694 | |
| 5 | XLM-R-large 20ep lr=3e-5 | 0.3353 | Monolingual wins |
| 6 | BETO HF Trainer lr=3e-5 | 0.3067 | Proper batching hurts |
| 7 | Full pipeline (tagger+rel) | S1=0.37, S2=0.07 | Relation clf works |

## What's implemented (session 5)

### Phase 1: Pipeline wiring ✅
- Fixed gold-relation leak (`relations=case.relations` → `relations=()`)
- Batched RelationClassifier (`_encode_pairs_batched`, save/load)
- 3-phase train_track1.py (tagger → rel_clf → predict+score)
- beto_base.yaml updated to 20 epochs

### Phase 2: Backbone configs ✅ (ready for RunPod)
- rigoberta2.yaml, rigoberta2_lowlr.yaml, rigoberta2_midlr.yaml
- mdeberta_ctebmsp.yaml, mdeberta_ctebmsp_lowlr.yaml
- beto_clinical.yaml

### Phase 3: Architecture upgrades ✅
- FocalLoss class (configurable gamma, class weights)
- CRF layer (pytorch-crf, valid BIO transitions)
- BiLSTM between encoder and classifier/CRF
- Dual loss (50% CRF NLL + 50% focal/CE)
- Custom head architecture (AutoModel + BiLSTM + classifier + CRF)
- 5 experiment configs: beto_focal, beto_focal_g2, beto_crf, beto_focal_crf, beto_focal_crf_bilstm

### Phase 4: NLI Relation Classifier ✅
- NLIRelationClassifier with NLI reframing (Support=entailment, Attack=contradiction)
- Partial-Attack threshold logic
- Wired into train_track1.py via `method: nli` config
- 3 configs: beto_nli_small, beto_nli_base, beto_nli_xlmr

### Phase 5: External Data ✅
- convert_abstrct_es.py for HiTZ/AbstRCT-ES download+convert

### Phase 6: LLM Synthetic ✅
- generate_synthetic.py with Claude API, offset validation, 30 medical topics

## Critical findings (preserved from session 4)

1. **BETO > XLM-R-large** — monolingual Spanish pretraining wins at 350 cases
2. **Custom loop > HF Trainer** — gradient summation = effective LR ~5e-4
3. **Oversampling/class weights don't help** — need NEW data not duplicates
4. **Cross-lingual transfer blocked** — English AbstRCT lacks MajorClaim
5. **0.40 ceiling** = MajorClaim bottleneck (64 examples, 3%)
6. **20 epochs optimal**, lr=3e-5 sweet spot

## RunPod infrastructure
- SSH key: `~/.ssh/id_ed25519`
- Pod setup: upload tarball → sed pyproject >=3.10 → pip install -e . → torch==2.6.0+cu124 → pip install pytorch-crf → uninstall torchvision/torchaudio

## 15 experiment configs ready for RunPod sweep

| Phase | Configs | Estimated time (A100) |
|---|---|---|
| P2 Backbone | beto_base, rigoberta2 (×3 LRs), mdeberta_ctebmsp (×2), beto_clinical | ~2h |
| P3 Architecture | beto_focal (×2 gammas), beto_crf, beto_focal_crf, beto_focal_crf_bilstm | ~1.5h |
| P4 NLI | beto_nli_small, beto_nli_base, beto_nli_xlmr | ~1h |
| **Total** | **15 experiments** | **~4.5h on A100 80GB** |

## Next steps (priority)

1. **Deploy to RunPod** — run `bash scripts/run_full_sweep.sh`
2. **Run generate_synthetic.py** — Claude API to generate MajorClaim/Attack examples
3. **Run convert_abstrct_es.py** — download AbstRCT-ES external data
4. **Phase 7** — Track 2 full pipeline (train_track2.py)
5. **Phase 8-10** — Multi-task, ensemble, submission
6. Deadline: submission 2026-05-03, paper 2026-05-24