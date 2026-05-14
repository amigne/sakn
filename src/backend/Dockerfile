# Stage 1: Build
FROM python:3.14-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Stage 2: Runtime
FROM python:3.14-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping traceroute dnsutils openssl ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN setcap cap_net_raw+ep /usr/bin/ping \
    && setcap cap_net_raw+ep /usr/sbin/traceroute
COPY --from=builder /app/.venv /app/.venv
COPY app/ ./app/
COPY tests/ ./tests/
COPY alembic/ ./alembic/
COPY alembic.ini ./
RUN useradd --create-home --uid 1000 sakn
USER sakn
ENV PATH="/app/.venv/bin:$PATH"
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8000/health || exit 1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
