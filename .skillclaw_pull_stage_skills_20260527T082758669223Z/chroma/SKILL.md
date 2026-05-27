---
name: chroma
description: "Use when building semantic search, RAG applications, or document retrieval with an open-source embedding database. Store embeddings and metadata, perform vector and full-text search, filter by metadata. Simple 4-function API. Scales from notebooks to production clusters. Best for local development and open-source projects. NOT for: production managed vector databases (use Pinecone), graph databases, or when you need enterprise support and managed infrastructure."
category: general
version: 1.0.0
...
license: Apache-2.0
...
prerequisites: {commands: [], env_vars: []}
---

# Chroma — Open-source Embedding Database

Chroma is an AI-native, open-source database designed for building LLM applications with memory. It provides a simple API for storing embeddings and metadata, performing similarity search, and filtering results.

## When to use Chroma

**Use Chroma when:**
- Building RAG (retrieval-augmented generation) applications
- Need local/self-hosted vector database
- Want open-source solution (Apache 2.0)
- Prototyping in notebooks
- Semantic search over documents
- Storing embeddings with metadata

**Metrics:**
- **24,300+ GitHub stars**
- **v1.3.3+** (stable, weekly releases)
- **Apache 2.0 license**

## Installation

bash
# Python
pip install chromadb

# JavaScript/TypeScript
npm install chromadb @chroma-core/default-embed


## Core Operations

### 1. Create collection

python
import chromadb

# Simple collection
client = chromadb.Client()
collection = client.create_collection("my_collection")

# With custom embedding function
from chromadb.utils import embedding_functions

openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key="your-key",
    model_name="text-embedding-3-small"
)

collection = client.create_collection(
    name="my_docs",
    embedding_function=openai_ef
)

# Get or delete collection
collection = client.get_collection("my_docs")
client.delete_collection("my_docs")


### 2. Add documents

python
# Add with auto-generated IDs
collection.add(
    documents=["Doc 1", "Doc 2", "Doc 3"],
    metadatas=[
        {"source": "web", "category": "tutorial"},
        {"source": "pdf", "page": 5},
        {"source": "api", "timestamp": "2025-01-01"}
    ],
    ids=["id1", "id2", "id3"]
)

# Add with custom embeddings
collection.add(
    embeddings=[[0.1, 0.2, ...], [0.3, 0.4, ...]],
    documents=["Doc 1", "Doc 2"],
    ids=["id1", "id2"]
)


### 3. Query (similarity search)

python
# Basic query
results = collection.query(
    query_texts=["machine learning tutorial"],
    n_results=5
)

# Query with filters
results = collection.query(
    query_texts=["Python programming"],
    n_results=3,
    where={"source": "web"}
)

# Complex metadata filters
results = collection.query(
    query_texts=["advanced topics"],
    where={
        "$and": [
            {"category": "tutorial"},
            {"difficulty": {"$gte": 3}}
        ]
    }
)

# Access results
print(results["documents"])   # List of matching documents
print(results["metadatas"])   # Metadata for each doc
print(results["distances"])   # Similarity scores
print(results["ids"])         # Document IDs


### 4. Get documents

python
# Get by IDs
docs = collection.get(ids=["id1", "id2"])

# Get with filters
docs = collection.get(
    where={"category": "tutorial"},
    limit=10
)

# Get all documents
docs = collection.get()


### 5. Update documents

python
collection.update(
    ids=["id1"],
    documents=["Updated content"],
    metadatas=[{"source": "updated"}]
)


### 6. Delete documents

python
# Delete by IDs
collection.delete(ids=["id1", "id2"])

# Delete with filter
collection.delete(where={"source": "outdated"})


## Persistent Storage

python
# Persist to disk
client = chromadb.PersistentClient(path="./chroma_db")

collection = client.create_collection("my_docs")
collection.add(documents=["Doc 1"], ids=["id1"])

# Reload later with same path
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("my_docs")


## Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `persist_directory` | Directory for persisted data | `./chroma` |
| `collection_name` | Name of the collection | Required |
| `distance_function` | Similarity metric (cosine, euclidean, manhattan) | cosine |

## Deployment Modes

- **In-memory**: Default, data not persisted
- **Persistent**: Set `persist_directory` to store data locally
- **Client-server**: Run Chroma server for multi-client access

bash
# Run Chroma server
# Terminal: chroma run --path ./chroma_db --port 8000


python
from chromadb.config import Settings

client = chromadb.HttpClient(
    host="localhost",
    port=8000,
    settings=Settings(anonymized_telemetry=False)
)


## Embedding Functions

### Default (Sentence Transformers)

python
# Uses sentence-transformers by default (all-MiniLM-L6-v2)
collection = client.create_collection("my_docs")


### OpenAI

python
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key="your-key",
    model_name="text-embedding-3-small"
)

collection = client.create_collection(
    name="openai_docs",
    embedding_function=openai_ef
)


### HuggingFace

python
huggingface_ef = embedding_functions.HuggingFaceEmbeddingFunction(
    api_key="your-key",
    model_name="sentence-transformers/all-mpnet-base-v2"
)

collection = client.create_collection(
    name="hf_docs",
    embedding_function=huggingface_ef
)


### Custom embedding function

python
from chromadb import Documents, EmbeddingFunction, Embeddings

class MyEmbeddingFunction(EmbeddingFunction):
    def __call__(self, input: Documents) -> Embeddings:
        # Your embedding logic
        return embeddings

my_ef = MyEmbeddingFunction()
collection = client.create_collection(
    name="custom_docs",
    embedding_function=my_ef
)


## Metadata Filtering

python
# Exact match
results = collection.query(
    query_texts=["query"],
    where={"category": "tutorial"}
)

# Comparison operators ($gt, $gte, $lt, $lte, $ne)
results = collection.query(
    query_texts=["query"],
    where={"page": {"$gt": 10}}
)

# Logical operators
results = collection.query(
    query_texts=["query"],
    where={"$and": [{"category": "tutorial"}, {"difficulty": {"$lte": 3}}]}
)

# Contains
results = collection.query(
    query_texts=["query"],
    where={"tags": {"$in": ["python", "ml"]}}
)


## Query Types

| Type | Description |
|------|-------------|
| `query_embeddings` | Find similar embeddings |
| `query_documents` | Find similar text |
| `where` | Metadata filtering |
| `include` | Specify returned fields |

## Use Cases

- Semantic search over documents
- RAG (Retrieval Augmented Generation) pipelines
- Recommendation systems
- Image/video similarity search
- Anomaly detection

## LangChain Integration

python
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Split documents
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000)
docs = text_splitter.split_documents(documents)

# Create Chroma vector store
vectorstore = Chroma.from_documents(
    documents=docs,
    embedding=OpenAIEmbeddings(),
    persist_directory="./chroma_db"
)

# Query
results = vectorstore.similarity_search("machine learning", k=3)

# As retriever
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})


## LlamaIndex Integration

python
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import VectorStoreIndex, StorageContext
import chromadb

# Initialize Chroma
db = chromadb.PersistentClient(path="./chroma_db")
collection = db.get_or_create_collection("my_collection")

# Create vector store
vector_store = ChromaVectorStore(chroma_collection=collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# Create index
index = VectorStoreIndex.from_documents(
    documents,
    storage_context=storage_context
)

# Query
query_engine = index.as_query_engine()
response = query_engine.query("What is machine learning?")


## Best Practices

1. **Use persistent client** — Don't lose data on restart
2. **Add metadata** — Enables filtering and tracking
3. **Batch operations** — Add multiple docs at once for efficiency
4. **Choose right embedding model** — Balance speed/quality
5. **Use filters** — Narrow search space before computing similarity
6. **Unique IDs** — Avoid collisions
7. **Regular backups** — Copy chroma_db directory
8. **Monitor collection size** — Scale up if needed
9. **Test embedding functions** — Ensure quality
10. **Use server mode for production** — Better for multi-user
11. **Embedding dimension** — Ensure consistent dimensions across your data

## Performance

| Operation | Latency | Notes |
|-----------|---------|-------|
| Add 100 docs | ~1-3s | With embedding |
| Query (top 10) | ~50-200ms | Depends on collection size |
| Metadata filter | ~10-50ms | Fast with proper indexing |

## Resources

- **GitHub**: https://github.com/chroma-core/chroma ⭐ 24,300+
- **Docs**: https://docs.trychroma.com
- **Discord**: https://discord.gg/MMeYNTmh3x
- **License**: Apache 2.0
