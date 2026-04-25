#!/usr/bin/env bash
# Simcluster daemon loop — mubz.24
set -u
BASE="$(cd "$(dirname "$0")" && pwd)"
export SIMCLUSTER_DIR="$BASE"
LOG="$BASE/loop.log"
ts() { date '+%Y-%m-%d %H:%M:%S'; }

if [ -z "${SIMCLUSTER_BEARER:-}" ]; then
  echo "[$(ts)] FATAL: SIMCLUSTER_BEARER not set. Add it as a Replit Secret." | tee -a "$LOG"
  exit 1
fi

echo "[$(ts)] ============ Loop runner started ============" | tee -a "$LOG"
cycle=0
while true; do
  echo "[$(ts)] -- cycle #$cycle: cloutbomb --" | tee -a "$LOG"
  python3 "$BASE/cloutbomb.py" 2>&1 | tee -a "$LOG"
  if (( cycle % 4 == 0 )); then
    echo "[$(ts)] -- cycle #$cycle: bounty_hunt (~6h) --" | tee -a "$LOG"
    python3 "$BASE/bounty_hunt.py" 2>&1 | tee -a "$LOG"
  fi
  cycle=$((cycle + 1))
  echo "[$(ts)] sleeping 5400s before cycle #$cycle" | tee -a "$LOG"
  sleep 5400
done
