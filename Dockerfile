FROM python:3.14.7-slim

# Recommended UV Docker environment variables
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    # This adds the /app/.venv/bin (The folder where uv places installed Python executables like
    # python, pip, uvicorn, pytest, etc.)
    # placing /app/.venv/bin first and than :$PATH tells linux to search for the executables commands
    # first. : = path separator
    PATH="/app/.venv/bin:$PATH"


# Install UV into the image by copying its binary from UV's own official image
# faster and lighter than pip-installing uv itself.
COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/

# Create user "appuser" with UID 1000 as 0 is reserved for root "chown" is "change owner" | "owneruser":"ownergroup"
RUN useradd -m -u 1000 appuser && \
    mkdir /app && \
    chown appuser:appuser /app

WORKDIR /app



# Copy only the dependency-defining files first and set ownership.
COPY --chown=appuser:appuser pyproject.toml uv.lock ./

# Switch to non-root user for all remaining operations
USER appuser

# Install dependencies from the .lock file, without installing the project itself yet.
# --frozen prevents uv from updating or regenerating uv.lock.
# This makes the Docker build reproducible.
RUN uv sync --frozen --no-install-project --no-dev

# Copy the actual aplication code
# Copy all from the host's working dir into the container's working dir = /app
# . and ./ are the same thing.
COPY --chown=appuser:appuser . .

# Final sync to install app itself
RUN uv sync --frozen --no-dev

# Document container port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1


# Default commands
CMD ["fastapi", "run", "src/webhook_relay/main.py", "--host", "0.0.0.0", "--port", "8000"]
