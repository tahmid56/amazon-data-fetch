FROM python:3.11-slim

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    TF_CPP_MIN_LOG_LEVEL=2

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


# Copy dependency files first for Docker layer caching
COPY pyproject.toml uv.lock ./
RUN uv python install 3.12
# Install dependencies into the project's .venv
RUN uv sync --frozen --no-dev

# Copy application
COPY . .

EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s \
    --timeout=10s \
    --start-period=60s \
    --retries=3 \
    CMD curl -f http://127.0.0.1:8501/_stcore/health || exit 1

# Run Streamlit through uv
CMD ["uv", "run", "streamlit", "run", "src/main.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]