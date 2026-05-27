---
name: faiss
description: "Use when you need Facebook's FAISS library for efficient similarity search and clustering of dense vectors — supports billions of vectors, GPU acceleration, and various index types (Flat, IVF, HNSW). Fast k-NN search, large-scale vector retrieval, or pure similarity search without metadata. Best for high-performance applications. NOT for: production managed vector databases (use Pinecone), metadata filtering (use Chroma/Qdrant), or cloud-based solutions."
category: optional-skills
---

# FAISS - Efficient Similarity Search

Facebook AI's library for billion-scale vector similarity search.

## When to use FAISS

**Use FAISS when:**
- Need fast similarity search on large vector datasets (millions/billions)
- GPU acceleration required
- Pure vector similarity (no metadata filtering needed)
- High throughput, low latency critical
- Offline/batch processing of embeddings

**Metrics**:
- **31,700+ GitHub stars**
- Meta/Facebook AI Research
- **Handles billions of vectors**
- **C++** with Python bindings

## Index Types

### 1. Flat (exact search)

python
# L2 (Euclidean) distance
index = faiss.IndexFlatL2(d)

# Inner product (cosine similarity if normalized)
index = faiss.IndexFlatIP(d)

# Slowest, most accurate


### 2. IVF (inverted file) - Fast approximate

python
# Create quantizer
quantizer = faiss.IndexFlatL2(d)

# IVF index with 100 clusters
nlist = 100
index = faiss.IndexIVFFlat(quantizer, d, nlist)

# Train on data
index.train(vectors)

# Add vectors
index.add(vectors)

# Search (nprobe = clusters to search)
index.nprobe = 10
distances, indices = index.search(query, k)


### 3. HNSW (Hierarchical NSW) - Best quality/speed

python
# HNSW index
M = 32  # Number of connections per layer
index = faiss.IndexHNSWFlat(d, M)

# No training needed
index.add(vectors)

# Search
distances, indices = index.search(query, k)


### 4. Product Quantization - Memory efficient

python
# PQ reduces memory by 16-32×
m = 8   # Number of subquantizers
nbits = 8
index = faiss.IndexPQ(d, m, nbits)

# Train and add
index.train(vectors)
index.add(vectors)


### 5. LSH - Hashing-based search

python
# Locality-Sensitive Hashing for certain distance metrics
index = faiss.IndexLSH(d, nbits)
index.add(vectors)


## Core Operations

python
import faiss
import numpy as np

# Create index
d = 128  # dimension
index = faiss.IndexFlatIP(d)  # Inner Product for normalized vectors

# Add vectors
vectors = np.random.rand(10000, d).astype('float32')
faiss.normalize_L2(vectors)  # Normalize for cosine similarity
index.add(vectors)

# Search
k = 5
query = np.random.rand(1, d).astype('float32')
faiss.normalize_L2(query)
distances, indices = index.search(query, k)


## GPU Acceleration

python
# Single GPU
res = faiss.StandardGpuResources()
index_cpu = faiss.IndexFlatL2(d)
index_gpu = faiss.index_cpu_to_gpu(res, 0, index_cpu)  # GPU 0

# Multi-GPU
index_gpu = faiss.index_cpu_to_all_gpus(index_cpu)

# 10-100× faster than CPU


## Save and Load

python
# Save index
faiss.write_index(index, "large.index")

# Load index
index = faiss.read_index("large.index")

# Continue using
distances, indices = index.search(query, k)


## LangChain Integration

python
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

# Create FAISS vector store
vectorstore = FAISS.from_documents(docs, OpenAIEmbeddings())

# Save
vectorstore.save_local("faiss_index")

# Load
vectorstore = FAISS.load_local(
    "faiss_index",
    OpenAIEmbeddings(),
    allow_dangerous_deserialization=True
)

# Search
results = vectorstore.similarity_search("query", k=5)


## LlamaIndex Integration

python
from llama_index.vector_stores.faiss import FaissVectorStore
import faiss

# Create FAISS index
d = 1536
faiss_index = faiss.IndexFlatL2(d)

vector_store = FaissVectorStore(faiss_index=faiss_index)


## Performance

| Index Type | Build Time | Search Time | Memory | Accuracy |
|------------|------------|-------------|--------|----------|
| Flat | Fast | Slow | High | 100% |
| IVF | Medium | Fast | Medium | 95-99% |
| HNSW | Slow | Fastest | High | 99% |
| PQ | Medium | Fast | Low | 90-95% |
| LSH | Medium | Medium | Medium | ~85% |

## Best Practices

1. **Choose right index type** - Flat for <10K, IVF for 10K-1M, HNSW for quality
2. **Normalize for cosine** - Use IndexFlatIP with normalized vectors
3. **Use GPU for large datasets** - 10-100× faster
4. **Save trained indices** - Training is expensive
5. **Tune nprobe/ef_search** - Balance speed/accuracy
6. **Monitor memory** - PQ for large datasets
7. **Batch queries** - Better GPU utilization
8. **IVF indexes reduce memory at cost of recall**
9. **HNSW provides best speed/recall tradeoff for ANN**

## When to Use FAISS vs Alternatives

| Use Case | Recommended |
|----------|-------------|
| Billion-scale search | FAISS |
| Pure similarity search without metadata | FAISS |
| Production managed service | Pinecone |
| Metadata filtering + vectors | Chroma/Qdrant |
| Local development | Chroma |

## Resources

- **GitHub**: https://github.com/facebookresearch/faiss ⭐ 31,700+
- **Wiki**: https://github.com/facebookresearch/faiss/wiki
- **License**: MIT
