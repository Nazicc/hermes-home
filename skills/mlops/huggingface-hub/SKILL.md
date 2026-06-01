---
name: huggingface-hub
description: "Use when downloading, uploading, searching, or managing Hugging Face models, datasets, or Spaces — or when managing HF repos, querying datasets with SQL, deploying inference endpoints, or managing buckets. Works with the `hf` CLI and `huggingface_hub` Python package. NOT for: general file downloads from arbitrary URLs, non-HuggingFace model hosting, model training/fine-tuning, running local inference with llama.cpp/vllm (use those skills instead), or when the native HuggingFace SDK (Python) is more convenient than the CLI."
category: general
---

## Install

bash
pip install huggingface_hub
# or
brew install huggingface-hub  # macOS

# Verify
hf --version


## Auth

bash
# Login (interactive — opens browser for token)
hf login

# Or set token directly
huggingface-cli login
# → Enter your HF token (from https://huggingface.co/settings/tokens)

# Read token from env (recommended for non-interactive use)
export HF_TOKEN=hf_xxxxx


## CLI (`hf`)

### Download
bash
# Download a model (all files)
hf download meta-llama/Llama-3.1-8B

# Download specific files
hf download bigcode/starcoder2-3b --filename config.json
hf download meta-llama/Llama-2-7b --include "*.safetensors"

# Download to a specific directory
hf download mistralai/Mistral-7B-v0.3 --local-dir ./models/mistral

# Download a dataset
hf download datasets wikitext --save-history

# Full directory via snapshot-download
hf hub snapshot-download <repo_id> [--local-dir <path>]


### Upload
bash
# Upload a file
hf upload username/my-model ./pytorch_model.bin --message "initial upload"

# Upload folder (handles multipart automatically)
hf upload my-org/my-model ./local_folder --message "initial upload"

# Upload with specific repo type
hf upload username/my-dataset ./data/ --repo-type dataset


### Search models/datasets
bash
hf search models --type text-classification
hf search datasets emoji
hf search models "text-classification" --limit 5
hf search datasets "chinese" --limit 5
hf hub search "text-classification" --author "distilbert"


### Manage repos
bash
hf repo create username/my-model --type model
hf repo ls
hf ls username/model-name


### Spaces & Inference Endpoints
bash
# Spaces
hf space create username/my-space --sdk streamlit
hf space replica username/my-space

# Inference endpoints (requires Pro+ subscription)
hf endpoint create --compute gpu --repo-id my-org/my-model
hf endpoints create --repo-id meta-llama/Llama-3-8B-Instruct

# Or via REST API
curl -X POST "https://api.endpoints.huggingface.cloud/v2/endpoint" \
  -H "Authorization: Bearer $HF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model": "meta-llama/Llama-2-7b-hf", "compute": {"accelerator": "gpu", "instanceSize": "medium"}}'


## Python API

python
from huggingface_hub import (
    snapshot_download, upload_folder, upload_file,
    HfApi, list_models, list_datasets
)
from datasets import load_dataset

api = HfApi()  # reads HF_TOKEN from env by default

# Upload file
api.upload_file(
    path_or_fileobj="./config.json",
    path_in_repo="config.json",
    repo_id="username/my-model",
    repo_type="model",
)

# Upload folder
api.upload_folder(
    folder_path="./outputs",
    repo_id="my-org/my-model",
    repo_type="model",
)

# Download model snapshot (all files, cached)
model_dir = snapshot_download("meta-llama/Llama-3.1-8B")
print(model_dir)  # ~/.cache/huggingface/hub/models--meta-llama--Llama-3.1-8B

# Download with token (private/gated models)
model_dir = snapshot_download(
    repo_id="meta-llama/Llama-2-7b-hf",
    cache_dir="./models",
    token=os.getenv("HF_TOKEN")
)

# Load model directly (downloads if needed)
from transformers import AutoModel
model = AutoModel.from_pretrained("meta-llama/Llama-2-7b-hf", token=os.getenv("HF_TOKEN"))

# Search models
results = api.list_models(task="text-classification", sort="downloads", direction=-1, limit=5)
for model in results:
    print(model.id, model.downloads)

# Load dataset (standard)
ds = load_dataset("philschmid/gpt-3.5-books", split="train")

# Load dataset (streaming for large datasets)
ds = load_dataset("philschmid/gpt-3.5-books", streaming=True, split="train")

# Dataset with SQL
ds = load_dataset("hf://datasets/lamini/lamini-docs", split="train")


## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `HF_TOKEN` | `~/.cache/huggingface/token` | Auth token for private repos |
| `HF_HOME` | `~/.cache/huggingface/` | Cache location |
| `HF_ENDPOINT` | `https://huggingface.co` | Override for enterprise/proxy |
| `HF_HUB_ENABLE_HF_TRANSFER` | `0` | Set to `1` for faster transfers |

**China region mirror:** `HF_ENDPOINT=https://hf-mirror.com`

## Decision Tree

1. **What is the target?** Model, dataset, Space, or repo?
2. **Is it public or private?** Public → no token needed. Private/gated → requires `HF_TOKEN`.
3. **Python or CLI?** Python (`huggingface_hub`) for scripts; CLI (`hf`) for quick one-liners.
4. **For downloads:**
   - Quick load: `from_pretrained()` or `load_dataset()`
   - Full directory: `snapshot_download()` or `hf hub snapshot-download`
   - Single file: `hf hub download <model>/<file>`
5. **For uploads:** Use `upload_folder()` or `hf upload` — requires `HF_TOKEN` with write permission.
6. **For search:** Use `list_models()` / `list_datasets()` with filters, or `hf search`.
7. **For dataset SQL:** Use `hfql` CLI or `load_dataset("hf://datasets/<repo_id>", sql=...)`.
8. **For large datasets:** Use streaming (`load_dataset(..., streaming=True)`).

## Edge Cases

| Situation | Solution |
|-----------|----------|
| Large model (50GB+) | Use `hf download --resume`; check disk space first |
| Gated model (Llama, StarCoder, etc.) | Set `HF_TOKEN`; run `hf login` first; accept terms at huggingface.co |
| Rate limiting | Set `HF_ENDPOINT` to a mirror; add `HF_HUB_ENABLE_HF_TRANSFER=1` |
| Network timeout | Use `--local-dir-use-symlinks False`; retry |
| Network interruption during download | Use `resume_download=True` in `snapshot_download()` or `hf download --resume` |
| Enterprise HF (hf.co/moon-enterprise) | Set `HF_ENDPOINT` env var to your enterprise URL |
| China region SSL | Use `HF_ENDPOINT=https://hf-mirror.com` |
| Partial download | Use `--resume` to continue; delete incomplete file first |
| Duplicate downloads | `hf download` is idempotent; `snapshot_download` skips if cache exists |
| Upload conflicts | Use `--create` flag or specify `repo_type` to avoid overwrite errors |
| Very large models/datasets | Use streaming (`load_dataset(..., streaming=True)`) or `hf_hub_download` for individual files |
| Model not loading (RAM/VRAM) | Use `from_pretrained(..., low_cpu_mem_usage=True)` or `device_map="auto"` |
| `huggingface_hub` not installed | `pip install huggingface_hub` — same package provides CLI |

## Quick Reference

| Operation | CLI | Python |
|-----------|-----|--------|
| Search models | `hf search models <query>` | `list_models(search=...)` |
| Search datasets | `hf search datasets <query>` | `list_datasets(search=...)` |
| Download model | `hf download <repo_id>` | `snapshot_download()` |
| Upload file | `hf upload <repo_id> <file>` | `api.upload_file()` |
| Upload folder | `hf upload <repo_id> ./folder` | `api.upload_folder()` |
| Create repo | `hf repo create <name> --type <type>` | `api.create_repo()` |
| List repos | `hf ls` | `api.list_models()` / `list_datasets()` |
| Download dataset | `hf download datasets/<id>` | `load_dataset()` |
| Login | `hf login` | — |

## Health Check

bash
# Verify hf CLI
hf --version

# Verify auth
hf whoami

# Verify Python package
python3 -c "import huggingface_hub; print(huggingface_hub.__version__)"

# Check token is readable
cat ~/.cache/huggingface/token 2>/dev/null || echo "No token cached"

## Purpose

The Hugging Face Hub is the central repository ecosystem for the ML community — hosting over 500,000 models, 100,000 datasets, and 100,000 Spaces (demo apps). This skill exists to streamline every interaction with the Hub: downloading models and datasets, uploading artifacts, searching for assets, managing repositories, creating Spaces, and deploying Inference Endpoints. The `huggingface_hub` Python package and the `hf` CLI together provide a unified interface to this ecosystem, handling authentication, caching, resumable downloads, and version management so practitioners can focus on model development instead of file management.

## Why This Works

**Concept 1: Content-Addressable Caching.** The Hub's `snapshot_download` and `from_pretrained` use a content-addressable cache under `~/.cache/huggingface/hub/`. Files are stored by content hash, not by filename, so the same model downloaded from two different repo IDs shares physical storage. This eliminates redundant downloads when switching between model variants, branches, or revisions. The cache is LRU-evicted — infrequently used models are automatically cleaned up, while frequently used ones stay hot.

**Concept 2: Gated Repository Access Control.** Private and gated models (Llama, StarCoder, Gemma) use a two-layer access model: (a) authentication via `HF_TOKEN` verifies identity, and (b) gated repos additionally require the user to accept license terms on the Hub website before granting download access. This enables organizations to distribute proprietary models with per-user license tracking while maintaining the same download API as public repos. The token can be scoped to read-only for inference or read-write for uploading.

**Concept 3: Streaming Dataset Loading.** The `datasets` library's streaming mode (`load_dataset(..., streaming=True)`) fetches and processes data on-the-fly without downloading the entire dataset to disk. This is transformative for large datasets (hundreds of GBs or more) — instead of waiting hours for a download and exhausting disk space, the data is streamed in shards, processed, and discarded. Combined with iterable-style batching and multi-processing, streaming makes billion-example datasets practical on a laptop.

## Examples

**Good:** Downloading a gated model for fine-tuning. Set `export HF_TOKEN=hf_xxxx` (a read-only token from your HF settings), then run `snapshot_download("meta-llama/Llama-3.1-8B", token=os.getenv("HF_TOKEN"))`. The 15GB model downloads with automatic resume support — if your connection drops, re-running continues from where it stopped. The cached files can be used by any subsequent `from_pretrained()` call without re-downloading.

**Good:** Uploading a fine-tuned model to a team organization. After training, call `api.upload_folder(folder_path="./output_model", repo_id="my-org/my-finetuned-model", repo_type="model")`. This uploads all files in the folder with automatic multipart handling for large files. Add `--message "v1 after DPO on 5k examples"` via the CLI version to attach a commit message. Team members can then download the model with `snapshot_download("my-org/my-finetuned-model")`.

**Good:** Searching for Chinese text-classification models. Run `list_models(task="text-classification", search="chinese", sort="downloads", direction=-1, limit=5)` to find the top 5 most-downloaded Chinese text classification models. The API returns model IDs, download counts, pipeline tags, and last-updated timestamps. Use this to quickly identify community-vetted models for a task before training your own.

**Good:** Deploying a Space for model demos. Use `hf space create my-org/chat-demo --sdk gradio` to create a Gradio-based demo Space. Configure secrets (HF_TOKEN, API keys) via the Space settings page. The Space auto-deploys on every git push to its repository. This is the fastest way to share an interactive demo of your model with stakeholders without managing infrastructure.

## Anti-Patterns

**Anti-Pattern 1: Calling `from_pretrained()` in a loop.** Loading the same model inside a training loop (e.g., re-loading it each epoch) wastes time and disk writes. `from_pretrained` checks the cache every call, but the cache lookup itself is not free — for a 7B model this adds 5-10 seconds per call. Load the model once before the loop and pass it as an argument to the training function.

**Anti-Pattern 2: Using non-streaming load for huge datasets.** Calling `load_dataset("bigcode/the-stack-dedup", split="train")` without `streaming=True` attempts to download the entire 3TB dataset to your local disk. This will fill your disk, take hours, and likely crash. Always use `streaming=True` for datasets larger than your available RAM, or use `split="train[:1%]"` to load only a sample.

**Anti-Pattern 3: Committing HF tokens to version control.** Hard-coding `HF_TOKEN=hf_xxxx` in Python scripts or configuration files that get committed to git is a security incident waiting to happen. Once pushed to a public repo, the token is compromised — it can be used to access all repos your token has access to. Use environment variables (`os.getenv("HF_TOKEN")`) or `.env` files that are `.gitignore`-d. HF's secret scanning will detect leaked tokens and auto-revoke them, but by then the damage may be done.

**Anti-Pattern 4: Uploading 1GB+ files without multipart awareness.** The `hf upload` CLI handles multipart automatically, but the raw `api.upload_file()` Python method has a 5GB per-file limit. For larger files, use `api.upload_folder()` or the CLI — both chunk the upload into 5GB parts. If you hit network timeouts on large uploads, set `HF_HUB_ENABLE_HF_TRANSFER=1` for faster parallel transfers.

## When NOT to Use

- When downloading arbitrary files from non-HuggingFace URLs — use `curl` or `wget` instead
- When running local inference — use vLLM, llama.cpp, or TGI (the Hub is for model storage, not serving)
- When doing model training or fine-tuning — use TRL, PEFT, or Axolotl; the Hub is your data source, not your training tool
- When you need to store non-ML data — use S3, GCS, or a general-purpose file server
- When deploying to production inference at scale — use HF Inference Endpoints or a self-hosted solution; the Hub API has rate limits
- When authentication is not required — `hf download` on public repos works without any token; only add tokens for gated/private models

## Cross-References

**trl-fine-tuning** (skills/trl-fine-tuning/SKILL.md) — Download base models from the Hub for RLHF and upload trained adapters back

**peft** (skills/mlops/training/peft/SKILL.md) — Download PEFT-format models from the Hub for memory-efficient fine-tuning

**accelerate** (skills/accelerate/SKILL.md) — Configure distributed training with models downloaded via the Hub

**llama-cpp** (skills/mlops/inference/llama-cpp/SKILL.md) — Download GGUF-format models from the Hub for local CPU/GPU inference

**vllm** (skills/mlops/inference/vllm/SKILL.md) — Download models from the Hub for production serving with continuous batching

