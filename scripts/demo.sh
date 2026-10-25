#!/usr/bin/env bash
# One command for the demo: mock issuer (:8100) + officer API (:8000), then the web app's command.
#
#   bash scripts/demo.sh        (Ctrl-C stops what this script started)
#
# The web app runs from Windows PowerShell (printed below). Pipeline results are read from
# data/out/pipeline; to (re)build them first:
#   DATABASE_URL=sqlite:///data/ledger.db python -m services.worker.pipeline data/synthetic
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-}"
for candidate in .venv-wsl/bin/python .venv/bin/python; do
  if [ -z "$PY" ] && [ -x "$candidate" ]; then PY="$candidate"; fi
done
PY="${PY:-python}"

LOGS=data/demo-logs
mkdir -p "$LOGS"
PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

up() { curl -fs -m 2 "http://localhost:$1/health" >/dev/null 2>&1; }

# serve <name> <port> <uvicorn app>: start it unless something already answers on the port.
serve() {
  local name=$1 port=$2 app=$3
  if up "$port"; then
    echo "  $name: already running on :$port (left alone)"
    return
  fi
  "$PY" -m uvicorn "$app" --host 127.0.0.1 --port "$port" >"$LOGS/$name.log" 2>&1 &
  PIDS+=("$!")
  for _ in $(seq 1 60); do
    up "$port" && { echo "  $name: started on :$port (log: $LOGS/$name.log)"; return; }
    kill -0 "${PIDS[-1]}" 2>/dev/null || break
    sleep 0.5
  done
  echo "  $name: FAILED to start; see $LOGS/$name.log" >&2
  tail -n 5 "$LOGS/$name.log" >&2 || true
  exit 1
}

echo "Starting services (python: $PY)"
serve mock-issuer 8100 services.mock_issuer.main:app
serve api 8000 services.api.main:app

count=$(find data/out/pipeline -maxdepth 1 -name 'app*.json' 2>/dev/null | wc -l)
if [ "$count" -eq 0 ]; then
  echo "WARNING: data/out/pipeline is empty, so the officer queue will be empty." >&2
  echo "  Build it first: DATABASE_URL=sqlite:///data/ledger.db $PY -m services.worker.pipeline data/synthetic" >&2
else
  echo "  pipeline results: $count applications in data/out/pipeline"
fi

web_dir=$(wslpath -w "$PWD/apps/web" 2>/dev/null || echo "$PWD/apps/web")
cat <<EOF

Web app: in a Windows PowerShell window run

    cd '$web_dir'; npm run dev

then open http://localhost:3000/officer   (API: http://localhost:8000/docs)

EOF
if [ "${#PIDS[@]}" -eq 0 ]; then
  echo "Both services were already running; this script started nothing and stops nothing."
  exit 0
fi
echo "Services are running. Press Ctrl-C here to stop them."
wait
