---
name: pinecone
description: "Managed vector database for production AI applications. Use when building production RAG, recommendation systems, or semantic search at scale with a managed vector database. Serverless, auto-scaling, with hybrid search (dense + sparse), metadata filtering, and namespaces. Low latency (<100ms p95). Best for serverless, managed infrastructure. NOT for: local development (use Chroma), research experiments, or when self-hosted solutions (use Qdrant/FAISS) are preferred."
category: optional-skills
---

# Pinecone - Managed Vector Database

Pinecone is a managed vector database designed for production AI workloads. It provides serverless and pod-based deployment options, auto-scaling, hybrid search (dense + sparse), metadata filtering, and namespaces for multi-tenancy.

## Key Features

- **Serverless & Pod-based**: Choose between serverless (auto-scales) or pod-based (dedicated resources) deployment
- **Hybrid Search**: Combines dense vector search with sparse BM25-style keyword matching
- **Metadata Filtering**: Filter results by metadata attributes before vector search
- **Namespaces**: Multi-tenancy support by isolating data within namespaces
- **Low Latency**: <100ms p95 query latency at scale
- **Managed Infrastructure**: No servers to manage, automatic scaling

## Quick Start

### Installation

bash
pip install pinecone-client


### Initialize Client

python
from pinecone import Pinecone

pc = Pinecone(api_key="your-api-key")
index = pc.Index("my-index")


## Core Operations

### Create Index

python
from pinecone import ServerlessSpec, PodSpec

# Serverless (recommended)
pc.create_index(
    name="my-index",
    dimension=1536,
    metric="cosine",  # or "euclidean", "dotproduct"
    spec=ServerlessSpec(cloud="aws", region="us-east-1")
)

# Pod-based (for consistent performance)
pc.create_index(
    name="my-index",
    dimension=1536,
    metric="cosine",
    spec=PodSpec(environment="us-east1-gcp", pod_type="p1.x1")
)


### Upsert Vectors

python
# Single upsert
index.upsert(vectors=[
    {
        "id": "vec1",
        "values": [0.1, 0.2, ...],  # 1536 dimensions
        "metadata": {
            "text": "Document content",
            "category": "tutorial",
            "timestamp": "2025-01-01"
        }
    }
])

# Batch upsert (recommended - 100-200 per batch)
vectors = [
    {"id": f"vec{i}", "values": embedding, "metadata": metadata}
    for i, (embedding, metadata) in enumerate(zip(embeddings, metadatas))
]
index.upsert(vectors=vectors, batch_size=100)


### Query Vectors

python
# Basic query
results = index.query(
    vector=[0.1, 0.2, ...],
    top_k=10,
    include_metadata=True,
    include_values=False
)

# With metadata filtering
results = index.query(
    vector=[0.1, 0.2, ...],
    top_k=5,
    filter={"category": {"$eq": "tutorial"}}
)

# Namespace query
results = index.query(
    vector=[0.1, 0.2, ...],
    namespace="production",
    top_k=5
)

# Access results
for match in results["matches"]:
    print(f"ID: {match['id']}, Score: {match['score']}")


### Fetch

python
results = index.fetch(ids=["vec1", "vec2"], namespace="")


### Delete

python
# Delete by ID
index.delete(ids=["vec1", "vec2"])

# Delete by filter
index.delete(filter={"category": "old"})

# Delete all in namespace
index.delete(delete_all=True, namespace="test")

# Delete entire index
index.delete(delete_all=True)


## Metadata Filtering

python
# Exact match
filter = {"category": "tutorial"}

# Comparison operators: $gt, $gte, $lt, $lte, $ne
filter = {"price": {"$gte": 100}}

# Logical operators
filter = {
    "$and": [
        {"category": "tutorial"},
        {"difficulty": {"$lte": 3}}
    ]
}  # Also: $or

# In operator
filter = {"tags": {"$in": ["python", "ml"]}}

# Exists check
filter = {"text": {"$exists": True}}


## Namespaces

python
# Partition data by namespace
index.upsert(
    vectors=[{"id": "vec1", "values": [...]}],
    namespace="user-123"
)

# Query specific namespace
results = index.query(vector=[...], namespace="user-123", top_k=5)

# List namespaces
stats = index.describe_index_stats()
print(stats['namespaces'])


## Hybrid Search (Dense + Sparse)

python
# Upsert with sparse vectors
index.upsert(vectors=[
    {
        "id": "doc1",
        "values": [0.1, 0.2, ...],  # Dense vector
        "sparse_values": {
            "indices": [10, 45, 123],  # Token IDs
            "values": [0.5, 0.3, 0.8]   # TF-IDF scores
        },
        "metadata": {"text": "..."}
    }
])

# Hybrid query
results = index.query(
    vector=[0.1, 0.2, ...],  # Dense
    sparse_vector={
        "indices": [10, 45],
        "values": [0.5, 0.3]
    },
    top_k=5,
    alpha=0.5  # 0=sparse only, 1=dense only, 0.5=hybrid
)


## Index Management

python
# List indexes
pc.list_indexes()

# Describe index
index_info = pc.describe_index("my-index")

# Get stats
stats = index.describe_index_stats()
print(f"Total vectors: {stats['total_vector_count']}")
print(f"Namespaces: {stats['namespaces']}")

# Delete index
pc.delete_index("my-index")


## RAG Example with OpenAI

python
from openai import OpenAI
from pinecone import Pinecone

openai_client = OpenAI()
pc = Pinecone()
index = pc.Index("rag-index")

def retrieve_context(query: str, top_k: int = 3) -> str:
    # Generate query embedding
    query_embedding = openai_client.embeddings.create(
        input=query,
        model="text-embedding-ada-002"
    ).data[0].embedding
    
    # Retrieve similar documents
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )
    
    # Build context string
    context = "\n".join([
        match["metadata"]["text"] 
        for match in results["matches"]
    ])
    return context

def rag_answer(question: str) -> str:
    context = retrieve_context(question)
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"Use this context to answer: {context}"},
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content


## LangChain Integration

python
from langchain_pinecone import PineconeVectorStore
from langchain_openai import OpenAIEmbeddings

# Create vector store
vectorstore = PineconeVectorStore.from_documents(
    documents=docs,
    embedding=OpenAIEmbeddings(),
    index_name="my-index"
)

# Query
results = vectorstore.similarity_search("query", k=5)

# As retriever
retriever = vectorstore.as_retriever(search_kwargs={"k": 10})


## LlamaIndex Integration

python
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Pinecone

pc = Pinecone(api_key="your-key")
vector_store = PineconeVectorStore(pinecone_index=pc.Index("my-index"))

from llama_index.core import StorageContext, VectorStoreIndex
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)


## Best Practices

1. **Use serverless** - Auto-scaling, cost-effective for most workloads
2. **Batch upserts** - More efficient (100-200 per batch)
3. **Add metadata** - Enable filtering capabilities
4. **Use namespaces** - Isolate data by user/tenant
5. **Use hybrid search** - Better search quality with dense + sparse
6. **Set appropriate dimensions** - Match your embedding model
7. **Optimize filters** - Index frequently filtered fields
8. **Monitor usage** - Check Pinecone dashboard
9. **Test with free tier** - 1 index, 100K vectors free
10. **Regular backups** - Export important data

## Performance

| Operation | Latency | Notes |
|-----------|---------|-------|
| Upsert | ~50-100ms | Per batch |
| Query (p50) | ~50ms | Depends on index size |
| Query (p95) | <100ms | SLA target |
| Metadata filter | ~+10-20ms | Additional overhead |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PINECONE_API_KEY` | Yes | Your Pinecone API key |

## Common Issues

- **403 Forbidden**: Invalid or expired API key
- **404 Not Found**: Index does not exist (create it first)
- **Quota Exceeded**: Upgrade your Pinecone plan
- **Dimension Mismatch**: Ensure query vectors match index dimension

## Pricing (as of 2025)

**Serverless**:
- $0.096 per million read units
- $0.06 per million write units
- $0.06 per GB storage/month

**Free tier**:
- 1 serverless index
- 100K vectors (1536 dimensions)
- Great for prototyping

## Resources

- **Website**: https://www.pinecone.io
- **Docs**: https://docs.pinecone.io
- **Console**: https://app.pinecone.io
- **Pricing**: https://www.pinecone.io/pricing

## Alternatives

- **Chroma**: Self-hosted, open-source - for local development
- **FAISS**: Offline, pure similarity search
- **Weaviate/Qdrant**: Self-hosted with more features when you need control

