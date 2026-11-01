# MARG Classroom Coach (RAG over ChromaDB + local LLM served by Ollama).
# The knowledge base (data/chroma_db, data/pdfs) is mounted as a volume, not baked in.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/opt/hf
WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu \
 && grep -v '^torch' requirements.txt > /tmp/req.txt && pip install -r /tmp/req.txt

# Pre-download the embedding model so the container starts offline.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY app ./app

RUN useradd --create-home --uid 10002 coach && chown -R coach /opt/hf
USER coach

EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=4).status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
