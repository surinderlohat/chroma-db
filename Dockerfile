FROM python:3.11-slim

WORKDIR /service

# Install gcc and build tools needed for psutil on linux/arm64
# Cleaned up after install to keep image size small
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Layer 1: torch (cached unless this RUN command changes) ───
# Installed first and separately so it gets its own cache layer.
# This is the heaviest install (~200 MB) — only re-runs if this
# RUN command itself changes.
RUN pip install --no-cache-dir torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# ── Layer 2: pip dependencies (cached unless requirements.txt changes) ─
# Copy requirements first — Docker only invalidates this layer
# when requirements.txt actually changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Layer 3: app source (cached unless app/ changes) ──────
# Copied last so code changes don't invalidate the pip layers above.
COPY app/ ./app/

# Create mount points for Docker volumes
RUN mkdir -p /app/chromadb /app/models

EXPOSE 9000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]