FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
COPY providers ./providers
COPY scripts ./scripts

RUN uv sync --no-dev \
    && chmod +x /app/scripts/migrate.sh /app/scripts/entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/src

EXPOSE 8000

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
