---
name: trl-fine-tuning
description: "Fine-tune LLMs using reinforcement learning with TRL — SFT for instruction tuning, DPO for preference alignment, PPO/GRPO for reward optimization, and reward model training. Use when need RLHF, align model with preferences, or train from human feedback. Works with HuggingFace Transformers. NOT for: training from scratch, inference serving, or non-reinforcement learning approaches."
category: general
---

# TRL - Transformer Reinforcement Learning

Fine-tune LLMs using reinforcement learning with TRL — SFT for instruction tuning, DPO for preference alignment, PPO/GRPO for reward optimization, and reward model training.

## Quick Start

**Installation**:
bash
pip install transformers torch trl peft datasets accelerate


**SFT (instruction tuning)**:
python
from trl import SFTTrainer

trainer = SFTTrainer(
    model="Qwen/Qwen2.5-0.5B",
    train_dataset=dataset,  # Prompt-completion pairs
)
trainer.train()


**DPO (align with preferences)**:
python
from trl import DPOTrainer
from transformers import TrainingArguments

training_args = TrainingArguments(
    output_dir="model-dpo",
    per_device_train_batch_size=4,
    learning_rate=5e-7,
    bf16=True,
)

trainer = DPOTrainer(
    model=model,
    args=training_args,
    beta=0.1,
    train_dataset=preference_dataset,  # chosen/rejected pairs
    processing_class=tokenizer
)
trainer.train()


## Workflows

### Workflow 1: Full RLHF Pipeline (SFT → Reward Model → PPO)

Complete pipeline from base model to human-aligned model.


RLHF Training:
- [ ] Step 1: Supervised fine-tuning (SFT)
- [ ] Step 2: Train reward model
- [ ] Step 3: PPO reinforcement learning
- [ ] Step 4: Evaluate aligned model


**Step 1: Supervised Fine-Tuning**

python
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from trl import SFTTrainer

# Load model
model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-0.5B")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-0.5B")
tokenizer.pad_token = tokenizer.eos_token

# Configure training
training_args = TrainingArguments(
    output_dir="Qwen2.5-0.5B-SFT",
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-5,
    num_train_epochs=1,
    bf16=True,
    logging_steps=10,
    save_strategy="epoch",
)

# Train
trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    processing_class=tokenizer,
    max_seq_length=4096,
)
trainer.train()
trainer.save_model()


**Step 2: Train Reward Model**

python
from transformers import AutoModelForSequenceClassification
from trl import RewardTrainer

# Load SFT model as base
model = AutoModelForSequenceClassification.from_pretrained(
    "Qwen2.5-0.5B-SFT",
    num_labels=1  # Single reward score
)
tokenizer = AutoTokenizer.from_pretrained("Qwen2.5-0.5B-SFT")

# Train reward model
trainer = RewardTrainer(
    model=model,
    args=training_args,
    train_dataset=rm_dataset,  # needs columns: prompt, chosen, rejected
    processing_class=tokenizer,
)
trainer.train()
trainer.save_model()


**Step 3: PPO Reinforcement Learning**

bash
python -m trl.scripts.ppo \
    --model_name_or_path Qwen2.5-0.5B-SFT \
    --reward_model_path Qwen2.5-0.5B-Reward \
    --dataset_name trl-internal-testing/descriptiveness-sentiment-trl-style \
    --output_dir Qwen2.5-0.5B-PPO \
    --learning_rate 3e-6 \
    --per_device_train_batch_size 64 \
    --total_episodes 10000


**Step 4: Evaluate**

python
from transformers import pipeline

generator = pipeline("text-generation", model="Qwen2.5-0.5B-PPO")
output = generator("Explain quantum computing to a 10-year-old", max_length=200)[0]["generated_text"]
print(output)


### Workflow 2: Simple Preference Alignment with DPO

Align model with preferences without reward model training.


DPO Training:
- [ ] Step 1: Prepare preference dataset
- [ ] Step 2: Configure DPO
- [ ] Step 3: Train with DPOTrainer
- [ ] Step 4: Evaluate alignment


**Dataset format**:

{
  "prompt": "What is the capital of France?",
  "chosen": "The capital of France is Paris.",
  "rejected": "I don't know."
}


**Configure and Train**:
python
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from trl import DPOTrainer

model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-0.5B-Instruct")

training_args = TrainingArguments(
    output_dir="Qwen2.5-0.5B-DPO",
    per_device_train_batch_size=4,
    learning_rate=5e-7,
    num_train_epochs=1,
    bf16=True,
    max_prompt_length=512,
    max_length=1024,
    logging_steps=10,
)

trainer = DPOTrainer(
    model=model,
    args=training_args,
    beta=0.1,  # KL penalty strength
    train_dataset=preference_dataset,
    processing_class=tokenizer,
)
trainer.train()
trainer.save_model()


**CLI alternative**:
bash
trl dpo \
    --model_name_or_path Qwen/Qwen2.5-0.5B-Instruct \
    --dataset_name argilla/Capybara-Preferences \
    --output_dir Qwen2.5-0.5B-DPO \
    --per_device_train_batch_size 4 \
    --learning_rate 5e-7 \
    --beta 0.1


### Workflow 3: Memory-Efficient Online RL with GRPO

Train with reinforcement learning using minimal memory. For in-depth GRPO guidance, see **[references/grpo-training.md](references/grpo-training.md)**. A production-ready training script is in **[templates/basic_grpo_training.py](templates/basic_grpo_training.py)**.


GRPO Training:
- [ ] Step 1: Define reward function
- [ ] Step 2: Configure GRPO
- [ ] Step 3: Train with GRPOTrainer


**Step 1: Define reward function**

python
def reward_function(completions, **kwargs):
    """
    Compute rewards for completions.
    Returns:
        List of reward scores (floats)
    """
    rewards = []
    for completion in completions:
        # Example: reward based on length and unique words
        score = len(completion.split())  # Favor longer responses
        score += len(set(completion.lower().split()))  # Reward unique words
        rewards.append(score)
    return rewards


Or use a reward model:
python
from transformers import pipeline

reward_model = pipeline("text-classification", model="reward-model-path")

def reward_from_model(completions, prompts, **kwargs):
    full_texts = [p + c for p, c in zip(prompts, completions)]
    results = reward_model(full_texts)
    return [r["score"] for r in results]


**Step 2 & 3: Configure and Train**

python
from trl import GRPOTrainer
from transformers import TrainingArguments

training_args = TrainingArguments(
    output_dir="Qwen2-GRPO",
    per_device_train_batch_size=4,
    num_train_epochs=1,
    learning_rate=1e-5,
    bf16=True,
)

trainer = GRPOTrainer(
    model="Qwen/Qwen2-0.5B-Instruct",
    reward_funcs=reward_function,
    args=training_args,
    train_dataset=dataset,  # Prompt-only dataset
)
trainer.train()


**CLI**:
bash
trl grpo \
    --model_name_or_path Qwen/Qwen2-0.5B-Instruct \
    --dataset_name trl-lib/tldr \
    --output_dir Qwen2-GRPO \
    --num_generations 4


## LoRA Configuration

For memory-efficient fine-tuning, use PEFT with LoRA:

python
from peft import LoraConfig, get_peft_model

lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()
# trainable params: 4M || all params: 8B || trainable%: 0.05%


## Dataset Formatting

Use chat templates for multi-turn conversations:

python
def format_for_sft(example):
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": example["instruction"]},
        {"role": "assistant", "content": example["response"]},
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False)

train_dataset = train_dataset.map(lambda x: {"text": format_for_sft(x)})


## Memory Optimization

python
# Enable gradient checkpointing
model.gradient_checkpointing_enable()

# Use 4-bit quantization (QLoRA)
from transformers import BitsAndBytesConfig
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
)

# Or 8-bit
bnb_config = BitsAndBytesConfig(load_in_8bit=True)


## When to Use vs Alternatives

**Use TRL when:**
- Need to align model with human preferences
- Have preference data (chosen/rejected pairs)
- Want to use reinforcement learning (PPO, GRPO)
- Need reward model training
- Doing RLHF (full pipeline)

**Method selection**:
- **SFT**: Have prompt-completion pairs, want basic instruction following
- **DPO**: Have preferences, want simple alignment (no reward model needed)
- **PPO**: Have reward model, need maximum control over RL
- **GRPO**: Memory-constrained, want online RL
- **Reward Model**: Building RLHF pipeline, need to score generations

**Use alternatives instead:**
- **HuggingFace Trainer**: Basic fine-tuning without RL
- **Axolotl**: YAML-based training configuration
- **Unsloth**: Fast LoRA training
- **vLLM**: Inference serving

## Common Issues

**OOM during DPO/SFT training**:
python
# Reduce batch size and sequence length
training_args = TrainingArguments(
    per_device_train_batch_size=1,
    gradient_accumulation_steps=8,
)
# Enable gradient checkpointing
model.gradient_checkpointing_enable()


**Poor alignment quality (DPO)**:
python
# Higher beta = more conservative (stays closer to reference)
trainer = DPOTrainer(..., beta=0.5)

# Lower beta = more aggressive alignment
trainer = DPOTrainer(..., beta=0.01)


**Reward model not learning**:
python
training_args = TrainingArguments(
    learning_rate=1e-5,
    num_train_epochs=3,
)
# Ensure preference dataset has clear winners


**PPO training unstable**:
python
# Adjust KL coefficient and clip range
ppo_config = PPOConfig(
    kl_coef=0.1,  # Increase from 0.05
    cliprange=0.1,  # Reduce from 0.2
)


## Hardware Requirements

| Method | VRAM (7B model) | Notes |
|--------|-----------------|-------|
| SFT | 16GB | With LoRA |
| DPO | 24GB | Stores reference model |
| PPO | 40GB | Policy + reward model |
| GRPO | 24GB | Memory efficient |

- **GPU**: NVIDIA (CUDA required)
- **Multi-GPU**: Supported via `accelerate`
- **Mixed precision**: BF16 recommended (A100/H100)

## Merging LoRA Adapters

python
from peft import PeftModel

base_model = AutoModelForCausalLM.from_pretrained("base_model")
merged_model = PeftModel.from_pretrained(base_model, "./lora_output").merge_and_unload()
merged_model.save_pretrained("./merged_output")


## Advanced Topics

- **SFT training guide**: See [references/sft-training.md](references/sft-training.md) for dataset formats, chat templates, packing strategies, and multi-GPU training.
- **DPO variants**: See [references/dpo-variants.md](references/dpo-variants.md) for IPO, cDPO, RPO, and other DPO loss functions.
- **Reward modeling**: See [references/reward-modeling.md](references/reward-modeling.md) for outcome vs process rewards and evaluation.
- **GRPO deep dive**: See [references/grpo-training.md](references/grpo-training.md) for expert-level patterns and troubleshooting.
- **Online RL methods**: See [references/online-rl.md](references/online-rl.md) for PPO, GRPO, RLOO, and OnlineDPO.

## Resources

- Docs: https://huggingface.co/docs/trl/
- GitHub: https://github.com/huggingface/trl
- Examples: https://github.com/huggingface/trl/tree/main/examples/scripts
- Papers: InstructGPT (2022), DPO (2023), GRPO (2024)
