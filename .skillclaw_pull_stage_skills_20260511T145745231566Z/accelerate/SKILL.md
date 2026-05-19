---
name: accelerate
description: "Use when you need to add distributed training support (DeepSpeed, FSDP, Megatron, DDP) to existing PyTorch scripts. Simplest distributed training API — 4 lines to add distributed support. Unified API across all distributed backends. Automatic device placement and mixed precision (FP16/BF16/FP8). NOT for: production inference serving, CPU-only environments, or single-GPU training that doesn't need distribution."
category: general
---

## Use when / NOT for

**Use when:**
- You have an existing `train.py` that runs on a single GPU and want to scale to multiple GPUs or nodes
- You want a single code path that works across DDP/FSDP/DeepSpeed/Megatron
- You need automatic device placement and mixed precision (FP16/BF16/FP8)
- You want interactive config or YAML config file instead of manual launcher setup
- You're using HuggingFace Transformers, Diffusers, or timm and want distributed training
- You need FSDP with activation checkpointing and CPU offloading

**NOT for:**
- Production inference serving (see vllm, tensorrt-llm)
- CPU-only environments without GPU support
- Single-GPU training that doesn't need distribution
- Complex multi-runtime orchestration needing full Megatron flexibility (use torchtitan)
- Projects requiring PyTorch Lightning high-level abstractions

## Quick Start

### Minimal example (4 lines)

python
# Before: single GPU training
import torch
model = torch.nn.Linear(10, 2)
optimizer = torch.optim.Adam(model.parameters())
dataloader = torch.utils.data.DataLoader(dataset, batch_size=32)

# After: distributed with 4 lines
from accelerate import Accelerator
accelerator = Accelerator()
model, optimizer, dataloader = accelerator.prepare(model, optimizer, dataloader)

for batch in dataloader:
    optimizer.zero_grad()
    loss = model(batch).mean()
    accelerator.backward(loss)  # NOT loss.backward()
    optimizer.step()


### Launch command

bash
# Single node, multi-GPU
accelerate launch train.py --config default_config.yaml

# Multi-node (SLURM example)
srun accelerate launch train.py \
  --config default_config.yaml \
  --num_processes=8 \
  --num_machines=2 \
  --machine_rank=$SLURM_PROCID


### Interactive configuration

bash
accelerate config


Questions:
- Which machine? (single/multi GPU/TPU/CPU)
- Mixed precision? (no/fp16/bf16/fp8)
- DeepSpeed? (no/yes)
- FSDP? (no/yes)

## Typical default_config.yaml

yaml
compute_environment: LOCAL_MACHINE
debug: false
distributed_type: MULTI_GPU
downcast_bf16: no
machine_rank: 0
main_training_function: main
mixed_precision: bf16
num_machines: 1
num_processes: 8
use_cpu: false
rdzv_backend: static
same_network: true


## Launch Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--config` | str | `None` | Path to config file |
| `--num_processes` | int | `None` | Number of processes (defaults to GPU count) |
| `--num_machines` | int | `1` | Number of nodes |
| `--machine_rank` | int | `0` | Rank of this machine |
| `--main_training_function` | str | `main` | Name of main training function |
| `--mixed_precision` | str | `None` | "fp16", "bf16", or "no" |
| `--use_deepspeed` | bool | `False` | Enable DeepSpeed ZeRO |
| `--zero_stage` | int | `3` | DeepSpeed ZeRO stage (2 or 3) |
| `--gradient_accumulation_steps` | int | `1` | Gradient accumulation steps |
| `--gradient_checkpointing` | bool | `False` | Enable gradient checkpointing |

## DeepSpeed Configuration

### Via YAML config

yaml
deepspeed_config:
  gradient_accumulation_steps: 4
  gradient_clipping: 1.0
  offload_optimizer_devices: cpu
  offload_param_devices: cpu
  zero3_init_flag: true
  zero3_save_16bit_model: true
  zero_stage: 3


### Via Python API

python
from accelerate import Accelerator
from accelerate.utils import DeepSpeedPlugin

deepspeed_plugin = DeepSpeedPlugin(
    zero_stage=3,
    gradient_accumulation_steps=4,
    offload_params_device="cpu",
    offload_optimizer_device="cpu",
)
accelerator = Accelerator(deepspeed_plugin=deepspeed_plugin)


### ZeRO Stages

| Stage | Description | Memory Savings |
|-------|-------------|----------------|
| ZeRO-1 | Shards gradients across GPUs | ~50% |
| ZeRO-2 | Shards gradients + optimizer states | ~75% |
| ZeRO-3 | Shards gradients + optimizer + parameters | ~90% |

## FSDP Configuration

### Via YAML config

yaml
fsdp_config:
  sharding_strategy: 1  # FULL_SHARD
  backward_prefetch: backward_prefetch
  mixed_precision: bf16
  activation_checkpointing: true
  activation_checkpointing_reentrant: false
  auto_wrap_policy: transformers
  min_num_params: 1e8
  cpu_ram_efficient_loading: true


### Via Python API

python
from accelerate import Accelerator, FullyShardedDataParallelPlugin

fsdp_plugin = FullyShardedDataParallelPlugin(
    sharding_strategy="FULL_SHARD",  # ZeRO-3 equivalent
    auto_wrap_policy="TRANSFORMER_AUTO_WRAP",
    cpu_offload=False
)
accelerator = Accelerator(
    mixed_precision='bf16',
    fsdp_plugin=fsdp_plugin
)


### FSDP Launch Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--fsdp` | str | `None` | FSDP wrapping algorithm |
| `--fsdp_config` | str | `None` | Path to FSDP config YAML |
| `--fsdp_min_num_params` | int | `1e8` | Min params for auto-wrap |
| `--fsdp_sharding_strategy` | int | `1` | 1=FULL_SHARD, 2=SHARD_GRAD_OP, 3=NO_SHARD |
| `--fsdp_cpu_offload` | bool | `False` | Offload parameters to CPU |
| `--fsdp_auto_wrap` | bool | `False` | Auto-wrap transformers |

## Mixed Precision

### BF16 (recommended for Ampere+)

python
accelerator = Accelerator(mixed_precision="bf16")
# Or in config: mixed_precision: bf16
# downcast_bf16: "loose" allows some bf16 computation if memory is tight


### FP16 (older GPUs)

python
accelerator = Accelerator(mixed_precision="fp16")
# Gradient scaling is handled automatically


### FP8 (H100+)

python
accelerator = Accelerator(mixed_precision="fp8")


## Gradient Accumulation

python
accelerator = Accelerator(gradient_accumulation_steps=4)

model, optimizer, dataloader = accelerator.prepare(model, optimizer, dataloader)

for batch in dataloader:
    with accelerator.accumulate(model):
        optimizer.zero_grad()
        loss = model(batch)
        accelerator.backward(loss)
        optimizer.step()


**Effective batch size**: `batch_size * num_gpus * gradient_accumulation_steps`

## Gradient Checkpointing

python
from transformers import AutoModelForCausalLM

model = AutoModelForCausalLM.from_pretrained("gpt2")
model.gradient_checkpointing_enable()

# Or via config:
# gradient_checkpointing: true
# activation_checkpointing: true (in fsdp_config)


## Device Placement

Accelerate handles device placement automatically after `prepare()`:

python
# Automatic — model, optimizer, scheduler all on correct devices
model, optimizer, scheduler = accelerator.prepare(model, optimizer, scheduler)

# No manual .to('cuda') needed!
# batch = batch.to('cuda')  # NOT NEEDED


## Multi-GPU Training with Transformers

python
from accelerate import Accelerator
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from datasets import load_dataset
from torch.utils.data import DataLoader

accelerator = Accelerator(mixed_precision="bf16")

model_name = "bert-base-uncased"
model = AutoModelForSequenceClassification.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)

dataset = load_dataset("imdb", split="train")
dataset = dataset.map(
    lambda x: tokenizer(x["text"], padding=True, truncation=True, max_length=512),
    batched=True
)
train_loader = DataLoader(dataset, batch_size=16, shuffle=True)

model, train_loader = accelerator.prepare(model, train_loader)

model.train()
for epoch in range(3):
    for batch in train_loader:
        outputs = model(**batch)
        loss = outputs.loss
        accelerator.backward(loss)
        optimizer.step()
        optimizer.zero_grad()


## Distributed Checkpointing

python
# Save only on main process
if accelerator.is_main_process:
    accelerator.save_state('checkpoint/')

# Load on all processes
accelerator.load_state('checkpoint/')


## Troubleshooting

### CUDA out of memory

1. Enable DeepSpeed ZeRO-3 with CPU offload:
python
deepspeed_plugin = DeepSpeedPlugin(
    zero_stage=3,
    offload_params_device="cpu",
    offload_optimizer_device="cpu",
)


2. Reduce batch size and enable gradient accumulation

3. Use `downcast_bf16: "loose"` if memory is still tight

### "Process group has not been initialized"

Ensure you call `accelerator.prepare()` before using the model. Never create optimizers or schedulers before prepare.

### Multi-node training fails with rendezvous timeout

Ensure `same_network: true` is set and all nodes can reach each other on the same port. Use `--main_training_function main` explicitly if using a class-based Trainer.

### FSDP with activation checkpointing OOM

Set `activation_checkpointing_reentrant: false` or try `activation_checkpointing_num_layers: 2` to reduce checkpoint granularity.

### Different results across runs

Ensure same random seed:
python
from accelerate.utils import set_seed
set_seed(42)


## Key Advantages

- **4 lines**: Minimal code changes from single-GPU
- **Unified API**: Same code for DDP, DeepSpeed, FSDP, Megatron
- **Automatic**: Device placement, mixed precision, sharding
- **Interactive config**: `accelerate config` for quick setup
- **Single launch**: `accelerate launch` works everywhere
- **HuggingFace standard**: Used by Transformers, TRL, PEFT, Diffusers

## Resources

- Docs: https://huggingface.co/docs/accelerate
- GitHub: https://github.com/huggingface/accelerate
- Examples: https://github.com/huggingface/accelerate/tree/main/examples
- Version: 1.0+

## Advanced Topics

- **Megatron integration**: See `references/megatron-integration.md` for tensor/pipeline/sequence parallelism
- **Custom plugins**: See `references/custom-plugins.md` for custom distributed plugins
- **Performance tuning**: See `references/performance.md` for profiling and optimization
