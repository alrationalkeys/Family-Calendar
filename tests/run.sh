#!/usr/bin/env bash
# FamilyHub checks. Run before pushing an update:   bash tests/run.sh
#   1. server tests (pytest) on a throw-away database with Home Assistant's demo devices
#   2. browser tests of the wall and phone pages (needs Node + Playwright; skipped with a note if missing)
# Nothing here touches familyhub.db, the real Home Assistant, or any paid API.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
fail=0

echo "== 1/2 server tests =="
"$PY" -m pytest tests -q || fail=1

echo; echo "== 2/2 browser tests =="
if ! node -e "require('playwright')" 2>/dev/null; then
  echo "skipped: Node with Playwright isn't installed here"
else
  PORT=8766; TMP=$(mktemp -d)
  for k in ANTHROPIC_API_KEY ELEVENLABS_API_KEY FAMILYHUB_PIN FAMILYHUB_LOCK_READS HA_URL HA_TOKEN; do unset $k; done
  FAMILYHUB_DB="$TMP/pages.db" HA_DEMO=1 "$PY" -m uvicorn app.main:app --port $PORT >"$TMP/server.log" 2>&1 &
  SRV=$!
  for i in $(seq 1 40); do curl -s -o /dev/null "http://localhost:$PORT/api/settings" && break; sleep 0.5; done
  curl -s -XPOST "http://localhost:$PORT/api/todos/" -H 'Content-Type: application/json' -d '{"title":"Browser test to-do"}' >/dev/null
  node tests/pages.js "http://localhost:$PORT" || { fail=1; echo "(server log: $TMP/server.log)"; }
  kill $SRV 2>/dev/null; wait $SRV 2>/dev/null
fi

echo; [ $fail -eq 0 ] && echo "ALL CHECKS PASSED" || echo "SOME CHECKS FAILED"
exit $fail
