#!/usr/bin/env bash
# Start MARG for testing on a physical phone over the local Wi-Fi (Expo Go).
#
#   bash scripts/start-mobile-stack.sh              # backend + Expo (login, all mentor screens)
#   bash scripts/start-mobile-stack.sh --mentor-ai  # + Mentor Intelligence (NVIDIA-hosted API)
#   bash scripts/start-mobile-stack.sh --coach      # + Classroom Coach (NVIDIA-hosted API)
#   bash scripts/start-mobile-stack.sh --all        # everything
#   bash scripts/start-mobile-stack.sh --stop       # stop what this script started
#
# Network exposure (LAN only, never the internet):
#   * backend  : 0.0.0.0:8000  -> reachable from devices on the same Wi-Fi (the phone calls it)
#   * Expo     : LAN mode :8082 -> Expo Go loads the app bundle from here
#   * Coach / Mentor Intelligence: 127.0.0.1 only (called by the backend, never by the phone)
# Secrets are loaded from each service's .env and .scratch/local-integration.env; nothing is printed.
set -euo pipefail

ROOT="/d/AI-MARG"
LOGS="$ROOT/.scratch/mobile-logs"
PIDS="$LOGS/pids"
mkdir -p "$LOGS"

stop_all() {
  [ -f "$PIDS" ] || { echo "Nothing recorded to stop."; return; }
  while read -r name pid; do
    if taskkill //PID "$pid" //T //F >/dev/null 2>&1; then echo "stopped $name (pid $pid)"; fi
  done < "$PIDS"
  rm -f "$PIDS"
}

port_busy() { netstat -ano | grep -qE ":$1 .*LISTEN"; }

start() {  # name port logfile command...
  local name=$1 port=$2 log=$3; shift 3
  if port_busy "$port"; then echo "port $port already in use - not starting $name (check what is running there)"; return; fi
  ( "$@" > "$LOGS/$log" 2>&1 ) &
  echo "$name $!" >> "$PIDS"
  echo "started $name on port $port (log: .scratch/mobile-logs/$log)"
}

WITH_AI=0; WITH_COACH=0
for arg in "$@"; do
  case $arg in
    --stop) stop_all; exit 0 ;;
    --mentor-ai) WITH_AI=1 ;;
    --coach) WITH_COACH=1 ;;
    --all) WITH_AI=1; WITH_COACH=1 ;;
    *) echo "unknown option: $arg"; exit 2 ;;
  esac
done

# Laptop LAN IPv4 (the Wi-Fi adapter with a default gateway).
LAN_IP=$(powershell -NoProfile -Command "(Get-NetIPConfiguration | Where-Object { \$_.IPv4DefaultGateway -ne \$null -and \$_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1).IPv4Address.IPAddress" | tr -d '\r')
[ -n "$LAN_IP" ] || { echo "Could not detect the LAN IP address"; exit 1; }
echo "Laptop LAN IP: $LAN_IP"

# shellcheck disable=SC1091
source "$ROOT/scripts/env-local.sh"   # service keys + demo database URL (not printed)
export CORS_ORIGINS="http://localhost:8082,http://localhost:8081,http://$LAN_IP:8082"

if [ "$WITH_COACH" = 1 ]; then
  start "classroom-coach" 8001 coach.log bash -c "cd '$ROOT/Marg-LLM' && COACH_API_KEY='$COACH_API_KEY' .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001"
fi

start "backend" 8000 backend.log bash -c "cd '$ROOT/Marg-AppBackend' && DATABASE_URL='$BACKEND_DATABASE_URL' .venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

if [ "$WITH_AI" = 1 ]; then
  start "mentor-intelligence" 8002 mentor-intelligence.log bash -c "cd '$ROOT/MARG-Mentor-Intelligence' && BACKEND_MODE=marg MARG_BACKEND_URL=http://127.0.0.1:8000 MARG_BACKEND_SERVICE_KEY='$MI_SERVICE_KEY' TRUSTED_GATEWAY_IDENTITY=true .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002"
fi

start "expo" 8082 expo.log bash -c "cd '$ROOT/Marg-AppFrontend' && EXPO_PUBLIC_API_URL='http://$LAN_IP:8000/api/v1' npx expo start --lan --port 8082 --clear"

echo
echo "Phone:  Expo Go -> Scan QR code (or Enter URL manually): exp://$LAN_IP:8082"
echo "        The QR code is also printed in .scratch/mobile-logs/expo.log once Metro is ready."
echo "Check:  on the phone's browser open http://$LAN_IP:8000/health  (should show {\"status\":\"ok\",...})"
echo "Stop:   bash scripts/start-mobile-stack.sh --stop"
