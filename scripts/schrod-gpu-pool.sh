#!/usr/bin/env bash
# One Schrodinger jobserverd PER GPU (CVD-pinned) + launch-time routing via 'jsc
# local-server-dir --set'. Makes Desmond/BPMD subjobs spread across GPUs (the shared
# jobserverd hands subjobs its own empty CUDA_VISIBLE_DEVICES -> all pile on GPU0).
set -uo pipefail
: "${SCHRODINGER:?SCHRODINGER not set}"
POOL_ROOT="${SCHROD_POOL_ROOT:-/root/schrod_pool}"
MARK="$POOL_ROOT/.default_dir"
ngpus(){ nvidia-smi -L 2>/dev/null | wc -l; }
_orig_default(){ local dir; for dir in /tmp/jobserverd-*; do [ -d "$dir" ] && { printf '%s\n' "$dir"; return; }; done; }
start(){
  local N="${1:-$(ngpus)}"; mkdir -p "$POOL_ROOT"
  local DEF; DEF="$(_orig_default)"; echo "$DEF" > "$MARK"
  for i in $(seq 0 $((N-1))); do
    local D="$POOL_ROOT/js_gpu$i"
    if pgrep -f "jobserverd -dir $D " >/dev/null 2>&1; then echo "GPU$i already up"; continue; fi
    rm -rf "$D"
    "$SCHRODINGER/jsc" local-server-dir --set "$D" >/dev/null 2>&1
    CUDA_VISIBLE_DEVICES=$i "$SCHRODINGER/jsc" local-server-start >/dev/null 2>&1
    local port; port=$(grep -o '"job_server_port":[0-9]*' "$D/runstate" 2>/dev/null)
    echo "GPU$i -> $D ($port)"
  done
  "$SCHRODINGER/jsc" local-server-dir --set "$DEF" >/dev/null 2>&1
}
submit(){  # submit <gpu> <cmd...>  — routes at launch, restores default
  local g="$1"; shift
  local D="$POOL_ROOT/js_gpu$g"; local DEF; DEF="$(cat "$MARK" 2>/dev/null || _orig_default)"
  [ -d "$D" ] || { echo "no pool server for GPU$g (run 'start')"; return 1; }
  "$SCHRODINGER/jsc" local-server-dir --set "$D" >/dev/null 2>&1
  CUDA_VISIBLE_DEVICES=$g nohup "$@" >/dev/null 2>&1 &
  local pid=$!; sleep 14
  "$SCHRODINGER/jsc" local-server-dir --set "$DEF" >/dev/null 2>&1
  echo "GPU$g submitted (pid $pid)"
}
status(){ echo "=== pool servers ==="; pgrep -af "jobserverd -dir $POOL_ROOT" || echo "  (none)"; echo "=== GPUs ==="; nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader; }
stop(){ pkill -9 -f "jobserverd -dir $POOL_ROOT" 2>/dev/null; echo "pool stopped"; }
case "${1:-}" in start) shift; start "${1:-}";; submit) shift; submit "$@";; status) status;; stop) stop;; *) echo "usage: $0 {start [N]|submit <gpu> <cmd...>|status|stop}"; exit 2;; esac
