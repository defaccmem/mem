FROM ghcr.io/astral-sh/uv:trixie-slim
WORKDIR /app
COPY uv.lock /app/
COPY pyproject.toml /app/
COPY .python-version /app/
RUN uv sync
COPY . /app/
CMD uv run --no-sync /app/app.py
