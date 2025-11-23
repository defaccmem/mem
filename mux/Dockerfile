FROM ghcr.io/astral-sh/uv:trixie-slim
RUN apt-get update && apt-get install -y curl jq
WORKDIR /app
COPY uv.lock /app/
COPY pyproject.toml /app/
COPY .python-version /app/
RUN uv sync
COPY . /app/
CMD uv run --no-sync /app/app.py
