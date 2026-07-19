# ── Stage 1: builder ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-install-project --no-dev

# Copy source code
COPY . .

# Install project
RUN uv sync --frozen --no-dev


# ── Stage 2: runtime ──────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install uv in runtime too
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install required system packages
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    nodejs \
    npm && \
    rm -rf /var/lib/apt/lists/*

# Copy project files
COPY --from=builder /app /app

# Update yt-dlp to latest version and install node-gyp for better support
RUN uv pip install --system --upgrade yt-dlp && \
    npm install -g node-gyp

# Set PATH
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]