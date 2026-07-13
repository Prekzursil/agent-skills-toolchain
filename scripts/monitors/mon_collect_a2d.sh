#!/usr/bin/env bash
# Verbose a2d monitor collector v3 (accurate): BPMD ladder (per-trial via out.tgz) +
# QM interaction-energy jobs (state via _qm_results.log exit codes + live .out/.log, so
# relaunched jobs read correctly). Emits key=value lines for scw_a2d_dashboard.ps1.
export PATH=/usr/bin:/bin:/usr/sbin:$PATH
NOW=$(date +%s)
QMD=/root/n1_qm
RES=$QMD/_qm_results.log

# ---------- GPUs ----------
nvidia-smi --query-gpu=index,utilization.gpu,memory.used,power.draw --format=csv,noheader,nounits 2>/dev/null | \
while IFS=',' read -r i u m p; do
  i=${i// /}; u=${u// /}; m=${m// /}; p=${p// /}; p=${p%.*}
  [ -n "$i" ] && echo "GPU=$i,$u,$m,$p"
done

# ---------- BPMD ladder (completed trials = trial_NN dirs holding a *-out.tgz) ----------
declare -A GPUOF=( [gabapentin]=0 [baclofen]=1 [pregabalin]=2 [R_phenibut]=3 )
bdone=0
for L in gabapentin baclofen pregabalin R_phenibut; do
  d=/root/jobs/bpmd_$L; g=${GPUOF[$L]}
  pid=$(pgrep -f "jobname bpmd_$L" | head -1)
  ok=$(grep -c "DONE_BPMD_${L}_exit_0" "$d/run.log" 2>/dev/null); ok=${ok:-0}
  fail=$(grep -oE "DONE_BPMD_${L}_exit_[1-9][0-9]*" "$d/run.log" 2>/dev/null | head -1)
  out=0; [ -f "$d/bpmd_${L}-out.maegz" ] && out=1
  el=0; [ -n "$pid" ] && el=$(ps -o etimes= -p "$pid" 2>/dev/null | tr -d ' ')
  trials=0
  pose=$(ls -dt /scratch/root/jobs/*/bpmd_${L}_metadynamics/pose_01 2>/dev/null | head -1)
  if [ -n "$pose" ]; then
    for t in "$pose"/trial_*; do
      [ -d "$t" ] || continue
      if ls "$t"/*-out.tgz >/dev/null 2>&1; then trials=$((trials+1)); fi
    done
  fi
  if [ "$ok" -ge 1 ] || [ "$out" = 1 ]; then st=done; bdone=$((bdone+1))
  elif [ -n "$fail" ]; then st=failed
  elif [ -n "$pid" ]; then st=running
  else st=pending; fi
  echo "BPMD=$L,$g,$st,${el:-0},$trials,8"
done
echo "BPMDDONE=$bdone,4"

# ---------- QM (accurate state; running(pgrep) > live .out/.log > historical marker) ----------
qmstate(){
  local job=$1
  if pgrep -f "${job}.in" >/dev/null 2>&1; then echo running; return; fi
  grep -q 'completed on' "$QMD/${job}.out" 2>/dev/null && { echo done; return; }
  grep -qiE 'ERROR 2256|died in program scf|SCF convergence failure' "$QMD/${job}.log" 2>/dev/null && { echo failscf; return; }
  local m; m=$(grep -oE "DONE_${job}_exit_[0-9]+" "$RES" 2>/dev/null | tail -1)
  if [ -n "$m" ]; then local ec=${m##*_}; [ "$ec" = 0 ] && echo done || echo "fail$ec"; return; fi
  echo pending
}
for job in pocket F_phenibut_cluster S_phenibut_cluster baclofen_cluster R_phenibut_cluster gabapentin_cluster pregabalin_cluster; do
  st=$(qmstate "$job")
  last=$(grep -E '^ *etot' "$QMD/${job}.log" 2>/dev/null | tail -1)
  step=$(echo "$last" | awk '{print $2}')
  energy=$(echo "$last" | awk '{print $7}')
  jp=$(pgrep -f "${job}.in" | head -1); el=0; [ -n "$jp" ] && el=$(ps -o etimes= -p "$jp" 2>/dev/null | tr -d ' ')
  echo "QM=$job,$st,${step:-0},${energy:-NA},${el:-0}"
done
# interaction-energy readiness (cluster + ligand + shared pocket all done)
pk=$(qmstate pocket); ie=0
for L in F_phenibut S_phenibut baclofen R_phenibut gabapentin pregabalin; do
  c=$(qmstate "${L}_cluster"); lg=$(qmstate "${L}_ligand")
  [ "$c" = done ] && [ "$lg" = done ] && [ "$pk" = done ] && ie=$((ie+1))
done
echo "QMIE=$ie,6,$pk"
echo "TS=$NOW"
