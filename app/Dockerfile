FROM python:3.11-slim

WORKDIR /service

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the embedding model so it's baked into the image
# This avoids cold download on first request
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

# Copy app source
COPY app/ ./app/

# ChromaDB data will be mounted here via Docker volume
RUN mkdir -p /app/chromadb

EXPOSE 9000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9000"]
