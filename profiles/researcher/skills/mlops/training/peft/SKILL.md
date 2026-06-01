---
name: peft
description: "Parameter-efficient fine-tuning for LLMs using LoRA, QLoRA, and 25+ methods. Use when fine-tuning large models (7B-70B) with limited GPU memory, when you need to train <1% of parameters with minimal accuracy loss, or for multi-adapter serving. HuggingFace's official library integrated with transformers ecosystem. NOT for: full-model fine-tuning, training from scratch, or inference-only workloads."
category: general
---

# PEFT (Parameter-Efficient Fine-Tuning)

Fine-tune LLMs by training <1% of parameters using LoRA, QLoRA, and 25+ adapter methods.

## When to use PEFT

**Use PEFT/LoRA when:**
- Fine-tuning 7B-70B models on consumer GPUs (RTX 4090, A100)
- Need to train <1% parameters (6MB adapters vs 14GB full model)
- Want fast iteration with multiple task-specific adapters
- Deploying multiple fine-tuned variants from one base model

**Use QLoRA (PEFT + quantization) when:**
- Fine-tuning 70B models on single 24GB GPU
- Memory is the primary constraint
- Can accept ~5% quality trade-off vs full fine-tuning

**Use full fine-tuning instead when:**
- Training small models (<1B parameters)
- Need maximum quality and have compute budget
- Significant domain shift requires updating all weights

## Quick start

### Installation

bash
# Basic installation
pip install peft

# With quantization support (recommended)
pip install peft bitsandbytes

# Full stack
pip install peft transformers accelerate bitsandbytes datasets


### LoRA fine-tuning (standard)

python
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import get_peft_model, LoraConfig, TaskType
from datasets import load_dataset

# Load base model
model_name = "meta-llama/Llama-3.1-8B"
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype="auto", device_map="auto")
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = tokenizer.eos_token

# LoRA configuration
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=16,                          # Rank (8-64, higher = more capacity)
    lora_alpha=32,                 # Scaling factor (typically 2*r)
    lora_dropout=0.05,             # Dropout for regularization
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],  # Attention layers
    bias="none"                    # Don't train biases
)

# Apply LoRA
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# Output: trainable params: 13,631,488 || all params: 8,043,307,008 || trainable%: 0.17%

# Prepare dataset
dataset = load_dataset("databricks/databricks-dolly-15k", split="train")

def tokenize(example):
    text = f"### Instruction:\n{example['instruction']}\n\n### Response:\n{example['response']}"
    return tokenizer(text, truncation=True, max_length=512, padding="max_length")

tokenized = dataset.map(tokenize, remove_columns=dataset.column_names)

# Training
training_args = TrainingArguments(
    output_dir="./lora-llama",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    fp16=True,
    logging_steps=10,
    save_strategy="epoch"
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized,
    data_collator=lambda data: {"input_ids": torch.stack([f["input_ids"] for f in data]),
                                 "attention_mask": torch.stack([f["attention_mask"] for f in data]),
                                 "labels": torch.stack([f["input_ids"] for f in data])}
)

trainer.train()

# Save adapter only (6MB vs 16GB)
model.save_pretrained("./lora-llama-adapter")


### QLoRA fine-tuning (memory-efficient)

python
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
from peft import get_peft_model, LoraConfig, prepare_model_for_kbit_training

# 4-bit quantization config
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",           # NormalFloat4 (best for LLMs)
    bnb_4bit_compute_dtype="bfloat16",   # Compute in bf16
    bnb_4bit_use_double_quant=True       # Nested quantization
)

# Load quantized model
model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-3.1-70B",
    quantization_config=bnb_config,
    device_map="auto"
)

# Prepare for training (enables gradient checkpointing)
model = prepare_model_for_kbit_training(model)

# LoRA config for QLoRA
lora_config = LoraConfig(
    r=64,                              # Higher rank for 70B
    lora_alpha=128,
    lora_dropout=0.1,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    bias="none",
    task_type="CAUSAL_LM"
)

model = get_peft_model(model, lora_config)
# 70B model now fits on single 24GB GPU!


## LoRA parameter selection

### Rank (r) - capacity vs efficiency

| Rank | Trainable Params | Memory | Quality | Use Case |
|------|-----------------|--------|---------|----------|
| 4 | ~3M | Minimal | Lower | Simple tasks, prototyping |
| **8** | ~7M | Low | Good | **Recommended starting point** |
| **16** | ~14M | Medium | Better | **General fine-tuning** |
| 32 | ~27M | Higher | High | Complex tasks |
| 64 | ~54M | High | Highest | Domain adaptation, 70B models |

### Alpha (lora_alpha) - scaling factor

python
# Rule of thumb: alpha = 2 * rank
LoraConfig(r=16, lora_alpha=32)  # Standard
LoraConfig(r=16, lora_alpha=16)  # Conservative (lower learning rate effect)
LoraConfig(r=16, lora_alpha=64)  # Aggressive (higher learning rate effect)


### Target modules by architecture

python
# Llama / Mistral / Qwen
target_modules = ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

# GPT-2 / GPT-Neo
target_modules = ["c_attn", "c_proj", "c_fc"]

# Falcon
target_modules = ["query_key_value", "dense", "dense_h_to_4h", "dense_4h_to_h"]

# BLOOM
target_modules = ["query_key_value", "dense", "dense_h_to_4h", "dense_4h_to_h"]

# Auto-detect all linear layers
target_modules = "all-linear"  # PEFT 0.6.0+


## Loading and merging adapters

### Load trained adapter

python
from peft import PeftModel, AutoPeftModelForCausalLM
from transformers import AutoModelForCausalLM

# Option 1: Load with PeftModel
base_model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.1-8B")
model = PeftModel.from_pretrained(base_model, "./lora-llama-adapter")

# Option 2: Load directly (recommended)
model = AutoPeftModelForCausalLM.from_pretrained(
    "./lora-llama-adapter",
    device_map="auto"
)


### Merge adapter into base model

python
# Merge for deployment (no adapter overhead)
merged_model = model.merge_and_unload()

# Save merged model
merged_model.save_pretrained("./llama-merged")
tokenizer.save_pretrained("./llama-merged")

# Push to Hub
merged_model.push_to_hub("username/llama-finetuned")


### Multi-adapter serving

python
from peft import PeftModel

# Load base with first adapter
model = AutoPeftModelForCausalLM.from_pretrained("./adapter-task1")

# Load additional adapters
model.load_adapter("./adapter-task2", adapter_name="task2")
model.load_adapter("./adapter-task3", adapter_name="task3")

# Switch between adapters at runtime
model.set_adapter("task1")  # Use task1 adapter
output1 = model.generate(**inputs)

model.set_adapter("task2")  # Switch to task2
output2 = model.generate(**inputs)

# Disable adapters (use base model)
with model.disable_adapter():
    base_output = model.generate(**inputs)


## PEFT methods comparison

| Method | Trainable % | Memory | Speed | Best For |
|--------|------------|--------|-------|----------|
| **LoRA** | 0.1-1% | Low | Fast | General fine-tuning |
| **QLoRA** | 0.1-1% | Very Low | Medium | Memory-constrained |
| AdaLoRA | 0.1-1% | Low | Medium | Automatic rank selection |
| IA3 | 0.01% | Minimal | Fastest | Few-shot adaptation |
| Prefix Tuning | 0.1% | Low | Medium | Generation control |
| Prompt Tuning | 0.001% | Minimal | Fast | Simple task adaptation |
| P-Tuning v2 | 0.1% | Low | Medium | NLU tasks |

### IA3 (minimal parameters)

python
from peft import IA3Config

ia3_config = IA3Config(
    target_modules=["q_proj", "v_proj", "k_proj", "down_proj"],
    feedforward_modules=["down_proj"]
)
model = get_peft_model(model, ia3_config)
# Trains only 0.01% of parameters!


### Prefix Tuning

python
from peft import PrefixTuningConfig

prefix_config = PrefixTuningConfig(
    task_type="CAUSAL_LM",
    num_virtual_tokens=20,      # Prepended tokens
    prefix_projection=True       # Use MLP projection
)
model = get_peft_model(model, prefix_config)


## Integration patterns

### With TRL (SFTTrainer)

python
from trl import SFTTrainer, SFTConfig
from peft import LoraConfig

lora_config = LoraConfig(r=16, lora_alpha=32, target_modules="all-linear")

trainer = SFTTrainer(
    model=model,
    args=SFTConfig(output_dir="./output", max_seq_length=512),
    train_dataset=dataset,
    peft_config=lora_config,  # Pass LoRA config directly
)
trainer.train()


### With Axolotl (YAML config)

yaml
# axolotl config.yaml
adapter: lora
lora_r: 16
lora_alpha: 32
lora_dropout: 0.05
lora_target_modules:
  - q_proj
  - v_proj
  - k_proj
  - o_proj
lora_target_linear: true  # Target all linear layers


### With vLLM (inference)

python
from vllm import LLM
from vllm.lora.request import LoRARequest

# Load base model with LoRA support
llm = LLM(model="meta-llama/Llama-3.1-8B", enable_lora=True)

# Serve with adapter
outputs = llm.generate(
    prompts,
    lora_request=LoRARequest("adapter1", 1, "./lora-adapter")
)


## Performance benchmarks

### Memory usage (Llama 3.1 8B)

| Method | GPU Memory | Trainable Params |
|--------|-----------|------------------|
| Full fine-tuning | 60+ GB | 8B (100%) |
| LoRA r=16 | 18 GB | 14M (0.17%) |
| QLoRA r=16 | 6 GB | 14M (0.17%) |
| IA3 | 16 GB | 800K (0.01%) |

### Training speed (A100 80GB)

| Method | Tokens/sec | vs Full FT |
|--------|-----------|------------|
| Full FT | 2,500 | 1x |
| LoRA | 3,200 | 1.3x |
| QLoRA | 2,100 | 0.84x |

### Quality (MMLU benchmark)

| Model | Full FT | LoRA | QLoRA |
|-------|---------|------|-------|
| Llama 2-7B | 45.3 | 44.8 | 44.1 |
| Llama 2-13B | 54.8 | 54.2 | 53.5 |

## Common issues

### CUDA OOM during training

python
# Solution 1: Enable gradient checkpointing
model.gradient_checkpointing_enable()

# Solution 2: Reduce batch size + increase accumulation
TrainingArguments(
    per_device_train_batch_size=1,
    gradient_accumulation_steps=16
)

# Solution 3: Use QLoRA
from transformers import BitsAndBytesConfig
bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4")


### Adapter not applying

python
# Verify adapter is active
print(model.active_adapters)  # Should show adapter name

# Check trainable parameters
model.print_trainable_parameters()

# Ensure model in training mode
model.train()


### Quality degradation

python
# Increase rank
LoraConfig(r=32, lora_alpha=64)

# Target more modules
target_modules = "all-linear"

# Use more training data and epochs
TrainingArguments(num_train_epochs=5)

# Lower learning rate
TrainingArguments(learning_rate=1e-4)


## Best practices

1. **Start with r=8-16**, increase if quality insufficient
2. **Use alpha = 2 * rank** as starting point
3. **Target attention + MLP layers** for best quality/efficiency
4. **Enable gradient checkpointing** for memory savings
5. **Save adapters frequently** (small files, easy rollback)
6. **Evaluate on held-out data** before merging
7. **Use QLoRA for 70B+ models** on consumer hardware

## References

- **[Advanced Usage](references/advanced-usage.md)** - DoRA, LoftQ, rank stabilization, custom modules
- **[Troubleshooting](references/troubleshooting.md)** - Common errors, debugging, optimization

## Resources

- **GitHub**: https://github.com/huggingface/peft
- **Docs**: https://huggingface.co/docs/peft
- **LoRA Paper**: arXiv:2106.09685
- **QLoRA Paper**: arXiv:2305.14314
- **Models**: https://huggingface.co/models?library=peft

## Purpose

Fine-tune large language models (7B-70B) by training <1% of parameters with low-rank adapters, enabling consumer-GPU fine-tuning and multi-adapter serving with near-full-fine-tuning quality.

## Why This Works

**Concept 1: Low-Rank Decomposition.** Full weight matrices W ∈ ℝ^(d×k) receive updates ΔW that are factored into two low-rank matrices A ∈ ℝ^(d×r) and B ∈ ℝ^(r×k) where r ≪ min(d,k). This constrains the update to a low-dimensional subspace — most task-specific adaptation is inherently low-rank, so the restricted parameterization captures the essential signal while cutting trainable parameters by 100-1000×.

**Concept 2: Quantized Forward Pass, LoRA Backward.** QLoRA keeps the base model in 4-bit NF4 (NormalFloat4) format throughout forward/backward passes, while maintaining LoRA adapters in full BF16/FP16 precision. Gradients flow only through the LoRA weights; the frozen base model is dequantized on-the-fly to BF16 for computation. This trades ~5% quality for 4× memory savings, fitting 70B models on single 24 GB GPUs.

**Concept 3: Adapter Merging & Swapping.** LoRA adapters are linear transformations that can be merged into the base weights (ΔW = AB) for zero-overhead inference, or kept separate for runtime switching. Multiple adapters can coexist in memory — enabling A/B testing, task routing, and personalized serving from one base model without reloading.

## Examples

**Good: Domain-Adapting a Code Model with QLoRA**

Fine-tune CodeLlama-34B on internal JavaScript codebases using a single RTX 4090:
```python
from transformers import AutoModelForCausalLM, BitsAndBytesConfig
from peft import prepare_model_for_kbit_training, LoraConfig, get_peft_model

bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype="bfloat16", bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained("codellama/CodeLlama-34b-Python-hf", quantization_config=bnb_config, device_map="auto")
model = prepare_model_for_kbit_training(model)
lora_config = LoraConfig(r=32, lora_alpha=64, target_modules="all-linear", lora_dropout=0.1)
model = get_peft_model(model, lora_config)
# Trains ~0.07% of parameters on single 24GB GPU
```

**Good: Multi-Task Adapter Serving for Customer Support**

Serve one Llama-3-70B base with three task-specific adapters and switch at request time:
```python
from peft import PeftModel, AutoPeftModelForCausalLM

model = AutoPeftModelForCausalLM.from_pretrained("./adapters/summarization")
model.load_adapter("./adapters/sentiment", adapter_name="sentiment")
model.load_adapter("./adapters/translation", adapter_name="translation")

model.set_adapter("sentiment")
response_sent = model.generate(**inputs)  # Sentiment adapter active
model.set_adapter("translation")
response_trans = model.generate(**inputs)  # Translation adapter active
```

**Good: LoRA with DoRA (Weight-Decomposed Adaptation)**

PEFT 0.14+ supports DoRA which learns a magnitude vector separately from the direction update, often outperforming standard LoRA at the same rank:
```python
from peft import LoraConfig

lora_config = LoraConfig(
    r=16, lora_alpha=32, use_dora=True,  # Enable DoRA
    target_modules="all-linear"
)
model = get_peft_model(model, lora_config)
# DoRA typically matches full-ft quality at rank 8-16
```

**Good: Merging Adapters for One-Step Deployment**

Merge adapter into weights so inference has zero overhead — no PEFT dependency needed at serving time:
```python
model = AutoPeftModelForCausalLM.from_pretrained("./adapter")
merged = model.merge_and_unload()                 # Merge A×B into W
merged.save_pretrained("./merged-model")          # Save as normal HF model
tokenizer.save_pretrained("./merged-model")
```

## Anti-Patterns

**Anti-Pattern 1: Overly High Rank Wasting Memory.** Setting r=128+ for simple tasks (classification, sentiment) wastes GPU memory with no quality gain. Start with r=8-16 and increase only if validation metrics plateau.

**Anti-Pattern 2: Training Biases (bias="all").** Setting `bias="all"` in LoraConfig trains the full bias vectors — on Llama-3-70B this adds ~260M extra parameters (nearly 2% of total), defeating the purpose of PEFT. Keep `bias="none"`.

**Anti-Pattern 3: Wrong Target Modules for Architecture.** Using `["q_proj", "v_proj"]` only on a model where LoRA on MLP layers matters more (e.g., CodeLlama benefits significantly from `gate_proj`/`up_proj`/`down_proj`). Use `target_modules="all-linear"` unless you have a specific ablation-driven reason not to.

**Anti-Pattern 4: Merging Adapter Too Early Without Eval.** Calling `merge_and_unload()` without evaluating the merge quality first. Merging can compound quantization errors on quantized models. Always run a validation batch before and after merge to confirm loss hasn't spiked.

## When NOT to Use

- **Full fine-tuning small models (<1B):** For a 500M-param model, the overhead of LoRA's forward-pass logic costs more than training the full weights directly.
- **Training from scratch:** PEFT adapters presuppose a pretrained base model. There's nothing to adapt on randomly initialized weights.
- **Inference-only workloads:** If you never train adapters, there's no benefit — use the raw model or a merged checkpoint.
- **Heavy domain shift (e.g., GPT → medical):** When the target domain has radically different token distributions, low-rank updates lack the capacity to remap the entire representation space.
- **Varying input/output dimensions:** PEFT adapters require fixed model architecture — you cannot use them to change vocabulary size or hidden dimensions.
- **Mobile/Core ML edge deployment:** Adapter merging + custom ops aren't supported on CoreML/TFLite without manual conversion scripts.

## Cross-References

- [vllm](../inference/vllm/SKILL.md) — Serve LoRA adapters with PagedAttention and continuous batching
- [pytorch-fsdp](pytorch-fsdp/SKILL.md) — Shard LoRA-base model parameters across GPUs for even larger base models
- **trl** — PEFT integrates natively with TRL's SFTTrainer, DPOTrainer, and GRPOTrainer
- **bitsandbytes** — Required for QLoRA's 4-bit NormalFloat quantization
- **axolotl** — YAML-driven fine-tuning framework that wraps PEFT for declarative adapter configs
