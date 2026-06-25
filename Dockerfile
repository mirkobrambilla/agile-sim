# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl: fetches the Tailwind standalone CLI in scripts/build_css.sh
# tini: PID 1 init so SIGTERM reaches uvicorn directly for graceful shutdown
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tini ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY harness ./harness
COPY scripts ./scripts
COPY tailwind.config.js ./
COPY scenarios ./scenarios
COPY assets ./assets
COPY docs ./docs
COPY README.md ./

RUN pip install --no-cache-dir -e ".[dev]" \
    && ./scripts/build_css.sh

# Non-root runtime user; /app and the future mount points must be writable.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && mkdir -p /data/runs /data/scenarios \
    && chown -R appuser:appuser /app /data

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER appuser

ENV AGILE_SIM_RUNS_DIR=/data/runs \
    AGILE_SIM_SCENARIOS_DIR=/data/scenarios \
    AGILE_SIM_HOST=0.0.0.0 \
    AGILE_SIM_PORT=8765

EXPOSE 8765

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
