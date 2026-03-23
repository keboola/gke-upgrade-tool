FROM cgr.dev/chainguard/python:latest-dev AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ARG SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${SETUPTOOLS_SCM_PRETEND_VERSION}
COPY pyproject.toml uv.lock README.md ./
COPY gke_upgrade_tool/ gke_upgrade_tool/
RUN uv sync --frozen --no-dev --no-editable

FROM cgr.dev/chainguard/python:latest
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["gke-upgrade-tool"]
