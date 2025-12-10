# Stage 1: The Builder (where heavy dependencies and the model are prepared)
# Using python:3.12-slim as a reliable base
FROM python:3.12-slim AS builder

# 1. Copy uv binaries for fast dependency management
# UV is used here for its efficiency in installing packages
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Configure uv to use a virtual environment
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV VIRTUAL_ENV=/app/.venv

ENV PATH="/app/.venv/bin:$PATH"

# Copy dependency files
COPY pyproject.toml ./
COPY uv.lock .

# Use uv to sync dependencies and install them into the .venv
# Note: Since your original lock file is likely tied to the full PyTorch, 
# you might need to manually adjust it or use a separate build for CPU-only.
# We explicitly install the CPU-only torch to minimize size.
RUN uv sync --frozen --no-cache-dir

# **CRITICAL STEP:** Pre-download the Sentence Transformer Model
# This bakes the model into the layer, so it's copied in the next stage.
# Replace 'your-model-name' with the actual model you use (e.g., 'all-MiniLM-L6-v2')
#RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small', device='cpu')"


# --- Stage 2: The Final Runtime (minimal image for execution) ---
# Start from the same minimal base for consistency
FROM python:3.12-slim AS final

WORKDIR /app

# 2. Copy the virtual environment and the pre-downloaded model from the builder stage
# This is the single step that transfers all necessary packages and the model, 
# leaving behind all the build-time history and caches.
COPY --from=builder /app/.venv /app/.venv

# 3. Copy only the application code
COPY email_agent/ email_agent/

# Set the PATH to include the virtual environment binaries
ENV PATH="/app/.venv/bin:$PATH"

# The entry point remains the same
CMD ["uvicorn", "email_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]