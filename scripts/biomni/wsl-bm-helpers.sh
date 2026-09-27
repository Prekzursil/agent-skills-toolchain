#!/bin/bash
# bm helpers (WSL side) - daemon control for the Biomini stack.
# v2 entrypoints (2026-09-22 reconciliation): biomni_tools_web.py (:7860 UI,
# GRADIO_MCP_SERVER=True) + biomni_mcp_server.py (:7870 FastMCP companion).
# Patterns match BOTH the v1 stub (biomni_web.py) and v2 names, so a mixed
# running state never double-starts or port-clashes. Kill patterns require the
# actual python invocation (an editor session on these files is never matched).

BM_ENV=/home/prekzursil/miniforge3/envs/biomni_e1
BM_LOG=/home/prekzursil/biomni-web.log
BM_PAT="[p]ython.*biomni_.*web"          # UI daemon (v1 stub or v2 tools-web)
BM_MCP_PAT="[p]ython.*biomni_mcp_server" # :7870 companion

bm_start() {
  if pgrep -f "$BM_PAT" > /dev/null; then
    echo "SUCCESS:bm-start already-running"
  else
    setsid nohup bash -c "export GRADIO_MCP_SERVER=True PATH=$BM_ENV/bin:/home/prekzursil/miniforge3/bin:/usr/bin:/bin; cd /home/prekzursil/Biomni; python biomni_tools_web.py > $BM_LOG 2>&1" > /dev/null 2>&1 < /dev/null &
    sleep 4
    if pgrep -f "$BM_PAT" > /dev/null; then
      echo "SUCCESS:bm-start launched"
    else
      echo "FAILED:bm-start no-process (see $BM_LOG)"
      return 1
    fi
  fi
  # MCP companion (idempotent; absent in v1 deploys is not an error)
  if ! pgrep -f "$BM_MCP_PAT" > /dev/null; then
    setsid nohup bash -c "export PATH=$BM_ENV/bin:/home/prekzursil/miniforge3/bin:/usr/bin:/bin; cd /home/prekzursil/Biomni; python biomni_mcp_server.py > /home/prekzursil/biomni-mcp.log 2>&1" > /dev/null 2>&1 < /dev/null &
  fi
  return 0
}

bm_stop() {
  pkill -f "$BM_PAT" 2>/dev/null
  pkill -f "$BM_MCP_PAT" 2>/dev/null
  sleep 2
  if pgrep -f "$BM_PAT" > /dev/null; then
    pkill -9 -f "$BM_PAT" 2>/dev/null; sleep 1
  fi
  echo "SUCCESS:bm-stopped"
}

bm_recover() {
  bm_stop
  rm -f /home/prekzursil/Biomni/.gradio/daemon.sock 2>/dev/null
  bm_start
}

bm_health() {
  code=$(curl -sk -o /dev/null -w "%{http_code}" --max-time 8 http://127.0.0.1:7860/ 2>/dev/null)
  ms=$({ time -p curl -sk -o /dev/null --max-time 8 http://127.0.0.1:7860/ > /dev/null 2>&1; } 2>&1 | awk '/^real/{print int($2*1000)}')
  procs=$(ps aux | grep -ac "[p]ython.*biomni_")
  echo "{\"http\":${code:-0},\"ms\":${ms:-0},\"procs\":${procs:-0}}"
}

case "$(basename "$0")" in
  bm-start)   bm_start ;;
  bm-stop)    bm_stop ;;
  bm-recover) bm_recover ;;
  bm-health)  bm_health ;;
  *) case "$1" in
      start)   bm_start ;;
      stop)    bm_stop ;;
      recover) bm_recover ;;
      health)  bm_health ;;
      *) echo "usage: bm-start|bm-stop|bm-recover|bm-health"; exit 2 ;;
     esac ;;
esac
