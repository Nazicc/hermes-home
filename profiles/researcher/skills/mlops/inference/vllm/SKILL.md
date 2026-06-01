---

name: vllm
description: Serves LLMs with high throughput using vLLM's PagedAttention and continuous batching. Use when deploying production LLM APIs, optimizing inference latency/throughput, or serving models with limited GPU memory. Supports OpenAI-compatible endpoints, quantization (GPTQ/AWQ/FP8), and tensor parallelism.
version: 1.0.0
author: Orchestra Research
license: MIT
dependencies: [vllm, torch, transformers]
metadata:
  hermes:
    tags: [vLLM, Inference Serving, PagedAttention, Continuous Batching, High Throughput, Production, OpenAI API, Quantization, Tensor Parallelism]

---

# vLLM - High-Performance LLM Serving

## Quick start

vLLM achieves 24x higher throughput than standard transformers through PagedAttention (block-based KV cache) and continuous batching (mixing prefill/decode requests).

**Installation**:
```bash
pip install vllm
```

**Basic offline inference**:
```python
from vllm import LLM, SamplingParams

llm = LLM(model="meta-llama/Llama-3-8B-Instruct")
sampling = SamplingParams(temperature=0.7, max_tokens=256)

outputs = llm.generate(["Explain quantum computing"], sampling)
print(outputs[0].outputs[0].text)
```

**OpenAI-compatible server**:
```bash
vllm serve meta-llama/Llama-3-8B-Instruct

# Query with OpenAI SDK
python -c "
from openai import OpenAI
client = OpenAI(base_url='http://localhost:8000/v1', api_key='EMPTY')
print(client.chat.completions.create(
    model='meta-llama/Llama-3-8B-Instruct',
    messages=[{'role': 'user', 'content': 'Hello!'}]
).choices[0].message.content)
"
```

## Common workflows

### Workflow 1: Production API deployment

Copy this checklist and track progress:

```
Deployment Progress:
- [ ] Step 1: Configure server settings
- [ ] Step 2: Test with limited traffic
- [ ] Step 3: Enable monitoring
- [ ] Step 4: Deploy to production
- [ ] Step 5: Verify performance metrics
```

**Step 1: Configure server settings**

Choose configuration based on your model size:

```bash
# For 7B-13B models on single GPU
vllm serve meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --max-model-len 8192 \
  --port 8000

# For 30B-70B models with tensor parallelism
vllm serve meta-llama/Llama-2-70b-hf \
  --tensor-parallel-size 4 \
  --gpu-memory-utilization 0.9 \
  --quantization awq \
  --port 8000

# For production with caching and metrics
vllm serve meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --enable-prefix-caching \
  --enable-metrics \
  --metrics-port 9090 \
  --port 8000 \
  --host 0.0.0.0
```

**Step 2: Test with limited traffic**

Run load test before production:

```bash
# Install load testing tool
pip install locust

# Create test_load.py with sample requests
# Run: locust -f test_load.py --host http://localhost:8000
```

Verify TTFT (time to first token) < 500ms and throughput > 100 req/sec.

**Step 3: Enable monitoring**

vLLM exposes Prometheus metrics on port 9090:

```bash
curl http://localhost:9090/metrics | grep vllm
```

Key metrics to monitor:
- `vllm:time_to_first_token_seconds` - Latency
- `vllm:num_requests_running` - Active requests
- `vllm:gpu_cache_usage_perc` - KV cache utilization

**Step 4: Deploy to production**

Use Docker for consistent deployment:

```bash
# Run vLLM in Docker
docker run --gpus all -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --enable-prefix-caching
```

**Step 5: Verify performance metrics**

Check that deployment meets targets:
- TTFT < 500ms (for short prompts)
- Throughput > target req/sec
- GPU utilization > 80%
- No OOM errors in logs

### Workflow 2: Offline batch inference

For processing large datasets without server overhead.

Copy this checklist:

```
Batch Processing:
- [ ] Step 1: Prepare input data
- [ ] Step 2: Configure LLM engine
- [ ] Step 3: Run batch inference
- [ ] Step 4: Process results
```

**Step 1: Prepare input data**

```python
# Load prompts from file
prompts = []
with open("prompts.txt") as f:
    prompts = [line.strip() for line in f]

print(f"Loaded {len(prompts)} prompts")
```

**Step 2: Configure LLM engine**

```python
from vllm import LLM, SamplingParams

llm = LLM(
    model="meta-llama/Llama-3-8B-Instruct",
    tensor_parallel_size=2,  # Use 2 GPUs
    gpu_memory_utilization=0.9,
    max_model_len=4096
)

sampling = SamplingParams(
    temperature=0.7,
    top_p=0.95,
    max_tokens=512,
    stop=["</s>", "\n\n"]
)
```

**Step 3: Run batch inference**

vLLM automatically batches requests for efficiency:

```python
# Process all prompts in one call
outputs = llm.generate(prompts, sampling)

# vLLM handles batching internally
# No need to manually chunk prompts
```

**Step 4: Process results**

```python
# Extract generated text
results = []
for output in outputs:
    prompt = output.prompt
    generated = output.outputs[0].text
    results.append({
        "prompt": prompt,
        "generated": generated,
        "tokens": len(output.outputs[0].token_ids)
    })

# Save to file
import json
with open("results.jsonl", "w") as f:
    for result in results:
        f.write(json.dumps(result) + "\n")

print(f"Processed {len(results)} prompts")
```

### Workflow 3: Quantized model serving

Fit large models in limited GPU memory.

```
Quantization Setup:
- [ ] Step 1: Choose quantization method
- [ ] Step 2: Find or create quantized model
- [ ] Step 3: Launch with quantization flag
- [ ] Step 4: Verify accuracy
```

**Step 1: Choose quantization method**

- **AWQ**: Best for 70B models, minimal accuracy loss
- **GPTQ**: Wide model support, good compression
- **FP8**: Fastest on H100 GPUs

**Step 2: Find or create quantized model**

Use pre-quantized models from HuggingFace:

```bash
# Search for AWQ models
# Example: TheBloke/Llama-2-70B-AWQ
```

**Step 3: Launch with quantization flag**

```bash
# Using pre-quantized model
vllm serve TheBloke/Llama-2-70B-AWQ \
  --quantization awq \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.95

# Results: 70B model in ~40GB VRAM
```

**Step 4: Verify accuracy**

Test outputs match expected quality:

```python
# Compare quantized vs non-quantized responses
# Verify task-specific performance unchanged
```

## When to use vs alternatives

**Use vLLM when:**
- Deploying production LLM APIs (100+ req/sec)
- Serving OpenAI-compatible endpoints
- Limited GPU memory but need large models
- Multi-user applications (chatbots, assistants)
- Need low latency with high throughput

**Use alternatives instead:**
- **llama.cpp**: CPU/edge inference, single-user
- **HuggingFace transformers**: Research, prototyping, one-off generation
- **TensorRT-LLM**: NVIDIA-only, need absolute maximum performance
- **Text-Generation-Inference**: Already in HuggingFace ecosystem

## Common issues

**Issue: Out of memory during model loading**

Reduce memory usage:
```bash
vllm serve MODEL \
  --gpu-memory-utilization 0.7 \
  --max-model-len 4096
```

Or use quantization:
```bash
vllm serve MODEL --quantization awq
```

**Issue: Slow first token (TTFT > 1 second)**

Enable prefix caching for repeated prompts:
```bash
vllm serve MODEL --enable-prefix-caching
```

For long prompts, enable chunked prefill:
```bash
vllm serve MODEL --enable-chunked-prefill
```

**Issue: Model not found error**

Use `--trust-remote-code` for custom models:
```bash
vllm serve MODEL --trust-remote-code
```

**Issue: Low throughput (<50 req/sec)**

Increase concurrent sequences:
```bash
vllm serve MODEL --max-num-seqs 512
```

Check GPU utilization with `nvidia-smi` - should be >80%.

**Issue: Inference slower than expected**

Verify tensor parallelism uses power of 2 GPUs:
```bash
vllm serve MODEL --tensor-parallel-size 4  # Not 3
```

Enable speculative decoding for faster generation:
```bash
vllm serve MODEL --speculative-model DRAFT_MODEL
```

## Advanced topics

**Server deployment patterns**: See [references/server-deployment.md](references/server-deployment.md) for Docker, Kubernetes, and load balancing configurations.

**Performance optimization**: See [references/optimization.md](references/optimization.md) for PagedAttention tuning, continuous batching details, and benchmark results.

**Quantization guide**: See [references/quantization.md](references/quantization.md) for AWQ/GPTQ/FP8 setup, model preparation, and accuracy comparisons.

**Troubleshooting**: See [references/troubleshooting.md](references/troubleshooting.md) for detailed error messages, debugging steps, and performance diagnostics.

## Hardware requirements

- **Small models (7B-13B)**: 1x A10 (24GB) or A100 (40GB)
- **Medium models (30B-40B)**: 2x A100 (40GB) with tensor parallelism
- **Large models (70B+)**: 4x A100 (40GB) or 2x A100 (80GB), use AWQ/GPTQ

Supported platforms: NVIDIA (primary), AMD ROCm, Intel GPUs, TPUs

## Resources

- Official docs: https://docs.vllm.ai
- GitHub: https://github.com/vllm-project/vllm
- Paper: "Efficient Memory Management for Large Language Model Serving with PagedAttention" (SOSP 2023)
- Community: https://discuss.vllm.ai

## Purpose

Serve LLMs at production throughput (1000+ tokens/sec per GPU) using PagedAttention and continuous batching, with an OpenAI-compatible API server, built-in quantization (AWQ/GPTQ/FP8), tensor/pipeline parallelism, and LoRA adapter hot-swapping.

## Why This Works

**Concept 1: PagedAttention — OS-Inspired KV Cache.** vLLM manages the KV cache in fixed-size blocks (pages) rather than contiguous memory, exactly like virtual memory pages in an OS. Non-contiguous physical pages are mapped to a contiguous logical view per sequence, eliminating the ~60-80% fragmentation waste of naive caching and allowing near-100% memory utilization.

**Concept 2: Continuous Batching (Iteration-Level Scheduling).** Traditional systems batch at the request level — all sequences in a batch must finish before new ones join. vLLM schedules at every decoding iteration: finished sequences are evicted immediately and new ones are prefilled in the same step. This eliminates idle GPU cycles and dramatically increases throughput under variable-length workloads.

**Concept 3: Speculative Decoding & Chunked Prefill.** vLLM decouples prefill (compute-bound) from decode (memory-bound) phases. Chunked prefill splits long contexts into smaller chunks that are interleaved with decode iterations, preventing TTFT spikes. Speculative decoding uses a draft model to guess multiple tokens per step, verified in parallel by the target model, giving 1.5-2.5× speedup on latency-sensitive workloads.

## Examples

**Good: OpenAI-Compatible Chat API with Prefix Caching**

Deploy a chat model optimized for repeated system prompts (chatbots, agents):
```bash
vllm serve mistralai/Mistral-7B-Instruct-v0.3 \
  --gpu-memory-utilization 0.95 \
  --max-model-len 16384 \
  --enable-prefix-caching \
  --port 8000
```
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="EMPTY")
# Prefix caching reduces TTFT by 40% on repeated system prompts
response = client.chat.completions.create(
    model="mistralai/Mistral-7B-Instruct-v0.3",
    messages=[{"role": "system", "content": "You are a helpful assistant."},
              {"role": "user", "content": "What is the capital of France?"}]
)
```

**Good: Offline Batch-Level Prompt Processing**

Process 50K prompts from a file with automatic batching and result writing:
```python
from vllm import LLM, SamplingParams

llm = LLM(model="meta-llama/Llama-3.1-8B-Instruct", tensor_parallel_size=2, max_model_len=4096)
params = SamplingParams(temperature=0.0, max_tokens=1024, stop=["<|eot_id|>"])

with open("prompts.jsonl") as f:
    prompts = [json.loads(line)["prompt"] for line in f]

outputs = llm.generate(prompts, params)
for out, inp in zip(outputs, prompts):
    print(f"IN: {inp[:80]}... OUT: {out.outputs[0].text[:200]}...")
```

**Good: LoRA Adapter Serving with Runtime Switching**

Serve a base model with multiple fine-tuned LoRA adapters and select per request:
```bash
vllm serve meta-llama/Llama-3.1-8B --enable-lora --max-lora-rank 64 --lora-modules code=./code-adapter chat=./chat-adapter
```
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="EMPTY")
# Request routed through the "code" adapter
resp = client.completions.create(model="meta-llama/Llama-3.1-8B", prompt="def fibonacci(n):", extra_body={"lora_name": "code"})
```

**Good: FP8 Inference on H100 for Maximum Throughput**

Enable FP8 quantization at serve time (H100 native) for 2× throughput vs BF16:
```bash
vllm serve meta-llama/Llama-3.1-70B-Instruct \
  --quantization fp8 \
  --tensor-parallel-size 4 \
  --gpu-memory-utilization 0.95 \
  --max-num-seqs 256
# 70B model fits on 4×H100 with ~1.5× throughput over BF16
```

## Anti-Patterns

**Anti-Pattern 1: Using Non-Power-of-2 Tensor Parallelism.** vLLM requires the number of tensor-parallel GPUs to be a power of 2 (1,2,4,8). Using 3 or 6 GPUs silently falls back to a suboptimal distribution with load imbalance. Always use n=1,2,4,8 for TP.

**Anti-Pattern 2: Serving Without Prefix Caching for Agent/Chain Workloads.** If your workload shares a common prefix (system prompt, conversation history), omitting `--enable-prefix-caching` misses 30-50% TTFT reduction. The cache auto-detects shared prefix blocks with no code changes.

**Anti-Pattern 3: Setting `--max-model-len` Exceeding Available KV Cache.** Picking a model length that exceeds the physical KV cache (dependent on GPU memory × gpu-memory-utilization) causes silent fallback to CPU offloading or OOM. Calculate with: `num_layers × 2 × num_heads × head_dim × max_model_len / (block_size × 1024³)`.

**Anti-Pattern 4: Exposing the Raw Server Without Rate Limits.** vLLM has no built-in rate limiting. A single client flooding requests will consume all KV cache slots and starve other users. Always deploy behind a reverse proxy (Nginx / Envoy) with request queuing and per-token rate limits.

## When NOT to Use

- **Single-offline generation (research/prototyping):** vLLM's initialization overhead (~10-30s to load weights) is wasted on one-off generations. Use HuggingFace transformers directly.
- **CPU-only inference:** vLLM is GPU-native; for CPU inference use llama.cpp with GGUF quantization.
- **Non-transformer architectures:** vLLM only supports decoder-only and encoder-decoder transformer LMs with RoPE/ALiBi position encoding.
- **Edge / mobile deployment:** vLLM requires CUDA, ROCm, or XLA — no CoreML or TFLite support.
- **Custom sampling strategies (beam search, contrastive):** vLLM exposes top-k, top-p, temperature, frequency/presence penalty, and beam search (limited). Complex custom logit processors require engine modification.
- **When NVIDIA isn't the primary GPU:** While vLLM supports AMD ROCm and Intel XPU, performance and feature parity lag behind CUDA significantly.

## Cross-References

- [peft](../training/peft/SKILL.md) — Create LoRA adapters with PEFT, then serve them with vLLM's `--enable-lora`
- [outlines](../inference/outlines/SKILL.md) — Use Outlines' `outlines.models.vllm(...)` backend for structured generation with vLLM serving
- [pytorch-fsdp](../training/pytorch-fsdp/SKILL.md) — FSDP for training large models that vLLM can then serve via tensor parallelism
- **tensorrt-llm** — NVIDIA's alternative for absolute peak performance on H100 clusters
- **huggingface-tgi** — HuggingFace's production inference server; simpler but less flexible than vLLM



