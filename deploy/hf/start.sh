#!/bin/bash
# Starts the API, the dashboard and Caddy in one container; if any of them stops, the
# container exits so that Hugging Face restarts it (no silent half-working demo).
set -euo pipefail
cd /app

uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --no-server-header &
(cd src/dashboard && exec streamlit run app.py \
    --server.address 127.0.0.1 --server.port 8501 --server.headless true) &
caddy run --config deploy/hf/Caddyfile --adapter caddyfile &

wait -n
echo "A process exited; stopping the container so that it is restarted." >&2
exit 1
