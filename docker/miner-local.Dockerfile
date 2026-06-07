# Engram Miner — local-embedder image (Windows / Docker Desktop friendly)
#
# Why a separate image?
#   • The root Dockerfile installs the slim `.[miner]` extra, which uses OpenAI
#     embeddings (text-embedding-3-small, 1536-dim). The testnet validator scores
#     against the LOCAL embedder (all-MiniLM-L6-v2, 384-dim) — a slim miner would
#     score 0. This image ships sentence-transformers so the miner matches the
#     validator out of the box, with no OpenAI API key required.
#   • engram-core (Rust) is skipped — every proof path has a pure-Python fallback,
#     so we trade a few ms of proof latency for a fast, toolchain-free build.
#
# Build context is the repo root:
#   docker build -f docker/miner-local.Dockerfile -t engram-miner:local .
FROM python:3.11-slim

WORKDIR /app

# Runtime libs: libgomp1 for faiss-cpu, libgmp-dev for bittensor crypto.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config libssl-dev git curl \
    libgomp1 libgmp-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Be patient with big/slow wheel downloads (torch) on home connections.
ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=5

# Install CPU-only PyTorch first, from PyTorch's CPU index. The default torch
# wheel bundles CUDA (~800 MB+) which a CPU miner never uses and which often
# times out on home networks — the CPU build is a fraction of the size.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install Python deps first so this layer caches until pyproject changes.
# `.[node]` pulls bittensor, faiss-cpu, sentence-transformers, aiohttp.
# torch is already satisfied above, so it won't re-download the CUDA build.
COPY pyproject.toml README.md ./
COPY engram/ engram/
RUN pip install --no-cache-dir ".[node]"

# Pre-download the embedding model into the image so the first miner start is
# instant and works on locked-down networks (no runtime model fetch).
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('all-MiniLM-L6-v2')"

COPY neurons/miner.py neurons/miner.py
RUN mkdir -p data

# Defaults match the testnet validator (subnet 450, 384-dim local embedder).
# Anything here is overridden by .env.miner via docker-compose env_file.
ENV USE_LOCAL_EMBEDDER=true \
    LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2 \
    EMBEDDING_DIM=384 \
    VECTOR_STORE_BACKEND=faiss \
    FAISS_INDEX_PATH=/app/data/miner.index \
    MINER_PORT=8091 \
    NETUID=450 \
    SUBTENSOR_NETWORK=test \
    LOG_LEVEL=INFO

EXPOSE 8091

HEALTHCHECK --interval=30s --timeout=10s --retries=5 --start-period=40s \
    CMD curl -fsS http://localhost:8091/health || exit 1

CMD ["python", "neurons/miner.py"]
