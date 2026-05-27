---
name: hindsight-external-pg-deploy
description: "Deploy Hindsight with an external PostgreSQL database (not the bundled SQLite). Handles Docker networking, environment variable configuration, embedding and reranker model setup via Silicon Flow, and optional MiniMax LLM integration. Use when setting up Hindsight in a self-hosted or containerized environment, connecting to an existing Postgres instance, configuring non-default embedding providers, migrating from SQLite, or connecting Hindsight to Hermes Agent. NOT for single-node installs using the default SQLite backend."
category: deployment
---

## Deploy Hindsight with External PostgreSQL

Deploy [Hindsight](https://github.com/miurla/hindsight) with an external PostgreSQL database instead of the default SQLite. This configuration is required when Hindsight is deployed in a distributed or containerized environment, or when persisting data across container restarts.

### Image Source

**Official release image:**

bash
ghcr.io/miurla/hindsight:v0.5.6


> **Note:** Always use the explicit version tag (e.g., `v0.5.6`) rather than `latest`, to avoid pulling breaking changes. There may be alternative GHCR images (e.g., `ghcr.io/robotmind/hindsight:v0.5.6`). If you encounter SSL verification errors (`SSL: CERTIFICATE_VERIFY_FAILED`) when Hindsight calls external APIs, ensure you are using the official release image before attempting SSL patching or environment variable workarounds.

### Prerequisites

- Docker installed and running on the host
- PostgreSQL instance accessible from the Docker host (can be on the same machine or a remote host)
- Network connectivity between the Docker host and the PostgreSQL server on port `5432`
- PostgreSQL 15+ with the `pgvector` extension enabled on the target database
- Silicon Flow API key (for embedding/reranker models)
- (Optional) MiniMax API key for LLM integration

### Step 1: Create the Docker Network

Create a Docker network so the Hindsight container can reach the PostgreSQL server:

bash
docker network create hindsight-net


If PostgreSQL is running in a container on the same Docker host, add it to this network:

bash
docker network connect hindsight-net <postgres-container-name>


### Step 2: Set Up the Database

Connect to the PostgreSQL server and create the database:

sql
CREATE DATABASE hindsight;
GRANT ALL PRIVILEGES ON DATABASE hindsight TO <username>;


#### Enable pgvector Extension

sql
\c hindsight
CREATE EXTENSION IF NOT EXISTS vector;
\dx vector


#### Recommended: HNSW Index for Production

sql
-- Create table with pgvector (HNSW index)
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    metadata JSONB,
    embedding vector(1024),  -- dimension for BAAI/bge-m3
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX ON memories USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);


> **Note:** HNSW (`m = 16, ef_construction = 64`) provides excellent recall and query speed for typical embedding dimensions (768, 1024). Adjust `m` and `ef_construction` based on your recall/speed requirements.

### Step 3: Environment Variables

Hindsight supports two naming conventions. Use whichever is convenient:

#### Convention A: Individual PG_* Variables

| Variable | Purpose | Example |
|---|---|---|
| `MEMORY_BACKEND=pg` | Use PostgreSQL backend | `pg` |
| `PG_HOST` | PostgreSQL hostname/service | `external-pg` or `pg.example.com` |
| `PG_PORT` | PostgreSQL port | `5432` |
| `PG_DB` | Database name | `hindsight` |
| `PG_USER` | Database user | `hindsight` |
| `PG_PASSWORD` | Database password | `${HINDSIGHT_DB_PASSWORD}` |
| `PG_SSL=true` | Enable SSL for connection | `true` |

Alternative naming convention (`POSTGRES_HOST`, `POSTGRES_PORT`, etc.) is also supported.

#### Convention B: DATABASE_URL + Silicon Flow Variables

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:password@host:5432/hindsight` |
| `NEXT_PUBLIC_SILICONFLOW_API_KEY` | Silicon Flow API key for embeddings | `sk-...` |
| `NEXT_PUBLIC_SILICONFLOW_API_URL` | Silicon Flow base URL | `https://api.siliconflow.cn/v1` |
| `SILICONFLOW_EMBEDDING_MODEL` | Embedding model name | `BAAI/bge-m3` |
| `SILICONFLOW_RERANK_MODEL` | Reranker model name | `BAAI/bge-reranker-v2-m3` |
| `MINIMAX_API_KEY` | (Optional) MiniMax key for LLM | `ek-...` |
| `MINIMAX_BASE_URL` | (Optional) MiniMax endpoint | `https://api.minimax.chat/v1` |

#### Embedding Variables (Convention A)

| Variable | Purpose |
|---|---|
| `EMBEDDING_PROVIDER=openai` (or `siliconflow`) | Use OpenAI/SiliconFlow-compatible embedding API |
| `EMBEDDING_MODEL` | Embedding model name |
| `EMBEDDING_BASE_URL` | Embedding API base URL |
| `EMBEDDING_API_KEY` | Embedding API key |
| `HINDSIGHT_EMBEDDING_DIM` | Vector dimensions (must match model) |

**Model recommendations:**
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions) — faster initialization, recommended for most cases
- `BAAI/bge-m3` (1024 dimensions) — slower initialization (~10 minutes), higher accuracy

#### LLM Variables

**OpenAI-compatible endpoint** (SiliconFlow, OpenRouter, Groq):

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | API key |
| `OPENAI_BASE_URL` | API base URL |
| `OPENAI_LLM_MODEL` | Model name |

**Anthropic-compatible endpoint** (for MiniMax Token Plan keys):

bash
HINDSIGHT_LLM_PROVIDER=anthropic
HINDSIGHT_LLM_BASE_URL=https://api.minimaxi.com/anthropic
HINDSIGHT_LLM_MODEL=claude-3-haiku-20240307


**Alternative naming convention:**

bash
LLM_PROVIDER=minimax
LLM_API_KEY=<your-minimax-api-key>
LLM_BASE_URL=https://api.minimaxi.com/v1
LLM_MODEL=abab6.5s-chat


#### Optional: Reranker Variables

bash
HINDSIGHT_RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
# Or with SiliconFlow provider:
RERANKER_PROVIDER=siliconflow
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
RERANKER_API_KEY=<your-silicon-flow-api-key>
RERANKER_API_BASE=https://api.siliconflow.cn/v1
RERANKER_TOP_N=5


> **Note**: If PostgreSQL is running on the Docker host itself (not in a container), use the host's actual IP address (e.g., `192.168.1.x`) rather than `localhost` or `127.0.0.1`, because `localhost` inside the container refers to the container itself.

### Step 4: Start the Container

#### Docker Run (Convention B)

bash
docker run -d \
  --name hindsight \
  --network hindsight-net \
  -p 3000:3000 \
  -e DATABASE_URL="postgresql://user:password@<postgres-host>:5432/hindsight" \
  -e NEXT_PUBLIC_SILICONFLOW_API_KEY="sk-..." \
  -e NEXT_PUBLIC_SILICONFLOW_API_URL="https://api.siliconflow.cn/v1" \
  -e SILICONFLOW_EMBEDDING_MODEL="BAAI/bge-m3" \
  -e SILICONFLOW_RERANK_MODEL="BAAI/bge-reranker-v2-m3" \
  -e MINIMAX_API_KEY="ek-..." \
  -e MINIMAX_BASE_URL="https://api.minimax.chat/v1" \
  ghcr.io/miurla/hindsight:v0.5.6


#### Docker Run (Convention A - PG_* variables)

bash
docker run -d \
  --name hindsight \
  --network hindsight-net \
  -p 3100:3000 \
  -e MEMORY_BACKEND=pg \
  -e PG_HOST=external-pg \
  -e PG_PORT=5432 \
  -e PG_DB=hindsight \
  -e PG_USER=hindsight \
  -e PG_PASSWORD=${HINDSIGHT_DB_PASSWORD} \
  -e PG_SSL=true \
  -e EMBEDDING_PROVIDER=openai \
  -e EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 \
  -e HINDSIGHT_EMBEDDING_DIM=384 \
  -e EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1 \
  -e EMBEDDING_API_KEY=${SILICON_FLOW_API_KEY} \
  -e OPENAI_API_KEY=${OPENAI_API_KEY} \
  -e OPENAI_BASE_URL=https://api.minimaxi.com/v1 \
  -e OPENAI_LLM_MODEL=gpt-4o-mini \
  ghcr.io/miurla/hindsight:v0.5.6


### Docker Compose Configuration

yaml
services:
  hindsight:
    image: ghcr.io/miurla/hindsight:v0.5.6
    container_name: hindsight
    ports:
      - "3100:3000"
    environment:
      # LLM provider (openai-compatible)
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_BASE_URL=https://api.minimaxi.com/v1
      - OPENAI_LLM_MODEL=gpt-4o-mini
      # Embedding provider
      - EMBEDDING_PROVIDER=openai
      - EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
      - HINDSIGHT_EMBEDDING_DIM=384
      - EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
      - EMBEDDING_API_KEY=${SILICON_FLOW_API_KEY}
      # Memory / database
      - MEMORY_BACKEND=pg
      - PG_HOST=external-pg
      - PG_PORT=5432
      - PG_DB=hindsight
      - PG_USER=hindsight
      - PG_PASSWORD=${HINDSIGHT_DB_PASSWORD}
      - PG_SSL=true
    depends_on:
      - external-pg
    restart: unless-stopped

  external-pg:
    image: ankane/pgvector:latest
    container_name: external-pg
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=hindsight
      - POSTGRES_USER=hindsight
      - POSTGRES_PASSWORD=${HINDSIGHT_DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  pgdata:


#### Using env_file (Alternative)

yaml
services:
  hindsight:
    image: ghcr.io/miurla/hindsight:v0.5.6
    container_name: hindsight
    ports:
      - "127.0.0.1:8432:8432"
    env_file:
      - ./hindsight.env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8432/health"]
      interval: 30s
      timeout: 10s
      retries: 3


bash
# Create env file
cat > hindsight.env << 'EOF'
PG_HOST=<your-postgres-host>
PG_PORT=5432
PG_DB=hindsight
PG_USER=<your-db-user>
PG_PASSWORD=<your-db-password>
MEMORY_BACKEND=pg
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
HINDSIGHT_EMBEDDING_DIM=384
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=<your-silicon-flow-api-key>
OPENAI_API_KEY=<your-api-key>
OPENAI_BASE_URL=https://api.minimaxi.com/v1
OPENAI_LLM_MODEL=gpt-4o-mini
EOF

# Start (must use down+up to apply env changes)
docker compose -f hindsight-compose.yaml down
docker compose -f hindsight-compose.yaml up -d


> **Important:** Paths in `env_file` are relative to the directory where `docker compose` is run, not the working directory. Use absolute paths or verify the correct relative path.

### Step 5: Verify Startup

Check the container logs:

bash
docker logs hindsight


Expected successful indicators:
- Embedding model initialization (e.g., `BAAI/bge-m3` or `MiniLM`)
- Reranker model initialization (if enabled)
- Server started on port 3000

#### Verify pgvector Integration

bash
# Test embedding endpoint
curl -X POST http://localhost:3100/api/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "test document", "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"}'

# Test memory recall
curl -X POST http://localhost:3100/api/memory/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 1}'

# Health check
curl http://localhost:3100/health


### Verification Checklist

- [ ] `docker ps` shows hindsight container running
- [ ] PostgreSQL is reachable from the hindsight container on port 5432
- [ ] `pgvector` extension is present in the hindsight database
- [ ] Embedding model initializes without SSL errors (check container logs)
- [ ] Hindsight health API responds
- [ ] Memory recall API responds
- [ ] LLM integration works (no 401 on chat completions)

### Common Failures and Resolutions

#### SSL/TLS errors during embedding initialization

**Symptom:** Embedding model fails to initialize with SSL certificate errors.

**Cause:** This typically comes from a broken self-hosted pgvector container, NOT from Hindsight itself. The official image handles SiliconFlow HTTPS connections correctly.

**Resolution:** Switch to the `external-pg` service using official `ankane/pgvector` image. No certificate manipulation is required. Verify `NEXT_PUBLIC_SILICONFLOW_API_KEY` and `SILICONFLOW_EMBEDDING_MODEL` values are correct first. If errors persist, verify you are using the official GHCR image, not a Docker Hub variant.

#### LLM returns 401 Unauthorized

**Symptom:** LLM calls return HTTP 401 even with a valid-looking API key.

**Cause:** Key format mismatch. MiniMax issues keys in different formats for different endpoint types:
- Keys with the `sk-cp-...` prefix are **Token Plan keys** — they only work with the Anthropic-compatible endpoint (`https://api.minimaxi.com/anthropic`), **not** the OpenAI-compatible endpoint (`https://api.minimax.chat/v1` or `https://api.minimaxi.com/v1`).
- Keys with the `ek-...` prefix are **general API keys** that work with the OpenAI-compatible endpoint.

**Resolution:** Use a key that matches the `OPENAI_BASE_URL` endpoint format, OR switch to `HINDSIGHT_LLM_PROVIDER=anthropic` with `HINDSIGHT_LLM_BASE_URL=https://api.minimaxi.com/anthropic`.

**Test directly:**
bash
curl -X POST https://api.minimax.chat/v1/chat/completions \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"MiniMax-Text-01","messages":[{"role":"user","content":"ping"}]}'

A 401 here confirms a key/endpoint mismatch.

#### PostgreSQL connection refused

**Symptom:** `could not connect to server: Connection refused`.

**Resolution:**
1. Verify `external-pg` container is running: `docker ps | grep external-pg`
2. Check pgvector extension is installed: `psql -h localhost -U hindsight -d hindsight -c "SELECT * FROM pg_extension WHERE extname = 'vector';"`
3. Verify `PG_HOST` matches the service name in Docker Compose
4. If using `localhost` for a host-based PostgreSQL, change to the host's actual IP address
5. Check connectivity: `docker exec hindsight nc -zv external-pg 5432`

#### Embedding model not found

**Symptom:** `Model not found` error for embedding model.

**Resolution:** Silicon Flow model names may differ from HuggingFace model IDs. Use Silicon Flow catalog names (e.g., `BAAI/bge-m3`) not raw HuggingFace paths.

#### Embedding initialization appears stuck

**Symptom:** Container logs show prolonged download/compile activity during startup.

**Cause:** Loading `BAAI/bge-m3` as the embedding model causes a long initialization (~10 minutes).

**Resolution:** Use `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` instead for faster startup.

#### Dimension mismatch on insert

**Symptom:** `RuntimeError: could not broadcast input array with shape (1024,) from (384,)`.

**Cause:** `HINDSIGHT_EMBEDDING_DIM` does not match the model's actual output dimensions.

**Resolution:** Set `HINDSIGHT_EMBEDDING_DIM=384` for MiniLM or `1024` for BAAI/bge-m3.

#### Container exits immediately after start

**Resolution:** Check `docker logs hindsight` for error messages. Common cause: `DATABASE_URL` or `PG_HOST` points to a host that is unreachable from within the container (e.g., `localhost` when PostgreSQL is on the host machine). Use the Docker host's actual IP address.

### Container Logs

bash
# View hindsight logs
docker logs -f hindsight

# View external-pg logs
docker logs -f external-pg

# Grep for errors
docker logs hindsight 2>&1 | grep -iE "error|fail|ssl|401"


### Restart After Config Changes

bash
docker compose down && docker compose up -d
docker logs -f hindsight  # watch startup


### Connecting to Hermes Agent

For integration with Hermes Agent, add the Hindsight service to the same Docker network and configure the `simplemem-mcp` or `simplemem-integration` skill with the Hindsight endpoint:

bash
# Find Hindsight container IP
docker inspect hindsight | grep IPAddress


Hindsight API base for internal Docker networking:


http://<hindsight-container-ip>:3100


### Silicon Flow Configuration

Silicon Flow provides OpenAI-compatible embedding and reranker endpoints. The default configuration:

- **Embedding endpoint**: `POST https://api.siliconflow.cn/v1/embeddings`
- **Embedding model**: `BAAI/bge-m3` (1024 dimensions) or `paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions)
- **Reranker endpoint**: `POST https://api.siliconflow.cn/v1/rerank`
- **Reranker model**: `BAAI/bge-reranker-v2-m3`

The `NEXT_PUBLIC_SILICONFLOW_API_URL` should always be set to `https://api.siliconflow.cn/v1`.

### Network Connectivity Between Containers

If Hindsight cannot reach PostgreSQL when both are in Docker:

bash
# Both containers must be on the same network
docker network connect hindsight-net hindsight
docker network connect hindsight-net <postgres-container>

# Test connectivity from within the hindsight container
docker exec -it hindsight sh -c "nc -zv <postgres-host> 5432"

