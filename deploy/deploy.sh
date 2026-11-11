#!/bin/sh
# AgriPrix Observatory - production helper, run on the server from the repository root.
#   ./deploy/deploy.sh up        build images and (re)start the stack
#   ./deploy/deploy.sh refresh   load / refresh the data now (ETL + training)
#   ./deploy/deploy.sh status    container health and the public endpoints
#   ./deploy/deploy.sh logs      follow the logs
#   ./deploy/deploy.sh update    git pull, rebuild and restart
set -eu

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
[ -f .env ] || { echo "Missing .env: cp .env.prod.example .env, then set every value." >&2; exit 1; }
if grep -q "change-me" .env; then
    echo "Some passwords in .env are still 'change-me': generate them with openssl rand -base64 24" >&2
    exit 1
fi
GIT_SHA="$(git rev-parse --short HEAD)"
export GIT_SHA
DOMAIN="$(grep '^DOMAIN=' .env | cut -d= -f2 | cut -d' ' -f1)"

case "${1:-}" in
    up) $COMPOSE up -d --build --wait ;;
    refresh) $COMPOSE run --rm scheduler python -m src.ops.refresh --force-train ;;
    status)
        $COMPOSE ps
        curl -fsS "https://${DOMAIN}/api/v1/health" && echo
        curl -fsS -o /dev/null -w "dashboard HTTP %{http_code}\n" "https://${DOMAIN}/"
        ;;
    logs) $COMPOSE logs -f --tail=100 ;;
    update) git pull --ff-only && $COMPOSE up -d --build --wait ;;
    *) sed -n '2,8p' "$0"; exit 1 ;;
esac
