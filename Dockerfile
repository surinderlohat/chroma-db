FROM python:3.11-slim

WORKDIR /service

COPY requirements.txt .

# Install CPU-only torch first via PyTorch's own CPU index
# This must happen before sentence-transformers otherwise pip pulls CUDA torch
RUN pip install --no-cache-dir torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies — torch is already installed above so pip reuses it
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY app/ ./app/

# Create mount points for Docker volumes
RUN mkdir -p /app/chromadb /app/models

EXPOSE 9000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]