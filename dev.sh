#!/usr/bin/env bash
# Start the Mangus beta: analysis API (:8000) + Expo/Metro, in one command.
#
#   ./dev.sh
#
# Leave this running. Ctrl+C stops Expo; the API keeps running in the background
# (stop it with:  pkill -f chess_coach.server ).
set -e
cd "$(dirname "$0")"

lan_ip=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 127.0.0.1)

# 1) analysis API — start only if not already up
if curl -s -m 2 http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "✓ analysis server already running on :8000"
else
  echo "→ starting analysis server on :8000 ..."
  nohup .venv/bin/python -m chess_coach.server > /tmp/mangus-server.log 2>&1 &
  for i in $(seq 1 15); do
    curl -s -m 2 http://127.0.0.1:8000/health >/dev/null 2>&1 && break
    sleep 1
  done
  if curl -s -m 2 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "✓ analysis server up"
  else
    echo "✗ analysis server failed to start — see /tmp/mangus-server.log"; exit 1
  fi
fi

echo
echo "  In the app's server box, use:  http://${lan_ip}:8000"
echo "  (phone must be on the same WiFi)"
echo
echo "→ starting Expo (Metro). Scan the QR with Expo Go. Ctrl+C to stop."
echo

# 2) Expo/Metro in the foreground
cd app && exec npx expo start
