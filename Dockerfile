# Forgetter backend — FastAPI scan service.
# Multi-stage: install heavy deps in builder, copy lean runtime.
# GLiNER + sentence-transformers models download to a writable cache on first
# request. Mount /app/data + /app/models as volumes for persistence.

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching
COPY pyproject.toml uv.lock ./
RUN pip install uv && \
    uv pip install --system --no-deps \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "presidio-analyzer>=2.2.0" \
        "spacy>=3.7.0" \
        "prometheus-fastapi-instrumentator>=7.0.0" \
        "gliner>=0.2.13" \
        "sentence-transformers>=3.0.0" \
        "pydantic>=2.0.0" \
        "httpx>=0.27.0" \
        "python-dotenv>=1.0.0" \
        "orjson>=3.10.0" \
        "reportlab>=4.2.0" \
        "python-docx>=1.1.0" \
        "pypdf>=6.12.2" \
    && uv pip install --system \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "presidio-analyzer>=2.2.0" \
        "spacy>=3.7.0" \
        "prometheus-fastapi-instrumentator>=7.0.0" \
        "gliner>=0.2.13" \
        "sentence-transformers>=3.0.0" \
        "pydantic>=2.0.0" \
        "httpx>=0.27.0" \
        "python-dotenv>=1.0.0" \
        "orjson>=3.10.0" \
        "reportlab>=4.2.0" \
        "python-docx>=1.1.0" \
        "pypdf>=6.12.2"

# spaCy model required by Presidio
RUN python -m spacy download en_core_web_lg

# Pre-download embedder so first request is fast
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

# ===== Runtime image =====
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/app/.hf-cache \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bring over installed Python packages + caches
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /root/.cache /root/.cache

# Copy application code
COPY services ./services
COPY data_gen ./data_gen

# Writable dirs (mount as volumes for persistence)
RUN mkdir -p /app/data /app/models /app/.hf-cache

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=3).raise_for_status()" || exit 1

CMD ["uvicorn", "services.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
