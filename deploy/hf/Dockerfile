# syntax=docker/dockerfile:1
# AgriPrix public demo on a Hugging Face Docker Space (ADR-013).
# One container: Caddy (port 7860, the only one HF exposes) routes /api, /docs to the
# FastAPI app and everything else to Streamlit. The warehouse lives on Neon (managed
# PostgreSQL); this image holds no database and no secret (HF injects them as env vars).
#
# On Hugging Face the code is cloned from GitHub at build time (REF = branch or tag).
# Locally, the "source" stage is replaced by the working tree:
#   docker build -f deploy/hf/Dockerfile --build-context source=. -t agriprix-hf .
ARG REPO=https://github.com/Oahmad228/AgriPrix.git
ARG REF=main

FROM alpine:3.20 AS fetch
ARG REPO
ARG REF
RUN apk add --no-cache git && git clone --depth 1 --branch "$REF" "$REPO" /out && rm -rf /out/.git

FROM scratch AS source
COPY --from=fetch /out/ /

FROM caddy:2.10.2-alpine AS caddy

FROM python:3.11.18-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    XDG_DATA_HOME=/tmp/caddy-data \
    XDG_CONFIG_HOME=/tmp/caddy-config \
    API_BASE_URL=http://127.0.0.1:8000 \
    APP_ENV=production
WORKDIR /app

# Same pinned versions as every other image: union of the API and dashboard lock subsets.
COPY --from=source requirements/api.lock requirements/dashboard.lock /tmp/
RUN cat /tmp/api.lock /tmp/dashboard.lock | sort -u > /tmp/space.lock && \
    pip install --no-cache-dir --prefer-binary --no-deps -r /tmp/space.lock && pip check

COPY --from=caddy /usr/bin/caddy /usr/local/bin/caddy
COPY --from=source pyproject.toml README.md ./
COPY --from=source src ./src
COPY --from=source deploy/hf/Caddyfile deploy/hf/start.sh ./deploy/hf/
RUN pip install --no-cache-dir --no-deps -e . && chmod +x deploy/hf/start.sh && \
    useradd --uid 1000 --create-home agriprix && chown -R agriprix /app
# Hugging Face runs Spaces as UID 1000.
USER agriprix
EXPOSE 7860
CMD ["/app/deploy/hf/start.sh"]
