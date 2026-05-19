---
name: weights-and-biases
description: "Track ML experiments with automatic logging, visualize training in real-time, optimize hyperparameters with sweeps, and manage model registry with W&B - collaborative MLOps platform. Use when: user wants to track ML experiments, log training metrics, visualize results, run hyperparameter sweeps, or manage model versions. NOT for: non-ML experiments, simple file logging, or when TensorBoard is sufficient."
category: ml-infrastructure
---

## Weights & Biases: ML Experiment Tracking & MLOps

## When to Use This Skill

Use Weights & Biases (W&B) when you need to:
- **Track ML experiments** with automatic metric logging
- **Visualize training** in real-time dashboards
- **Compare runs** across hyperparameters and configurations
- **Optimize hyperparameters** with automated sweeps
- **Manage model registry** with versioning and lineage
- **Collaborate on ML projects** with team workspaces
- **Track artifacts** (datasets, models, code) with lineage

**Users**: 200,000+ ML practitioners | **GitHub Stars**: 10.5k+ | **Integrations**: 100+

## Core Features

### Automatic Experiment Logging
- **Metrics**: Training/validation loss, accuracy, learning rate, custom metrics
- **System Stats**: GPU utilization, memory, CPU usage
- **Artifacts**: Model checkpoints, datasets, evaluation results
- **Code**: Git state, diffs, and environment info

### Training Visualization
- Live metric plots during training
- Comparison across multiple runs
- Histograms and distribution plots
- Gradient flow visualization
- Feature importance charts

### Hyperparameter Sweeps
- **Search strategies**: Grid search, random search, Bayesian optimization
- **Early stopping**: Automatic termination of underperforming runs
- **Parallel execution**: Run multiple configurations simultaneously
- **Visualization**: Parameter importance, correlation analysis

### Model Registry
- Version control for models
- Stage transitions (staging → production)
- Model metadata and lineage tracking
- Integration with deployment pipelines

## Installation

bash
# Install W&B
pip install wandb

# Login (creates API key)
wandb login

# Or set API key programmatically
export WANDB_API_KEY=your_api_key_here


## Quick Start

### Basic Experiment Tracking

python
import wandb

# Initialize a run
run = wandb.init(
    project="my-project",
    config={
        "learning_rate": 0.001,
        "epochs": 10,
        "batch_size": 32,
        "architecture": "ResNet50"
    }
)

# Training loop
for epoch in range(run.config.epochs):
    train_loss = train_epoch()
    val_loss = validate()
    
    wandb.log({
        "epoch": epoch,
        "train/loss": train_loss,
        "val/loss": val_loss,
        "train/accuracy": train_acc,
        "val/accuracy": val_acc
    })

wandb.finish()


### With PyTorch

python
import torch
import wandb

# Initialize
wandb.init(project="pytorch-demo", config={
    "lr": 0.001,
    "epochs": 10
})

# Watch model for automatic logging
wandb.watch(model)

# Training loop
for epoch in range(config.epochs):
    for batch_idx, (data, target) in enumerate(train_loader):
        output = model(data)
        loss = criterion(output, target)
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        if batch_idx % 100 == 0:
            wandb.log({"loss": loss.item(), "epoch": epoch, "batch": batch_idx})

wandb.finish()


## Configuration Tracking

python
config = {
    "model": "ResNet50",
    "pretrained": True,
    "learning_rate": 0.001,
    "batch_size": 32,
    "epochs": 50,
    "optimizer": "Adam",
    "dataset": "ImageNet",
    "augmentation": "standard"
}

wandb.init(project="my-project", config=config)
lr = wandb.config.learning_rate
batch_size = wandb.config.batch_size


## Metric Logging

python
# Log scalars
wandb.log({"loss": 0.5, "accuracy": 0.92})

# Log multiple metrics
wandb.log({
    "train/loss": train_loss,
    "val/loss": val_loss,
    "learning_rate": current_lr,
    "epoch": epoch
})

# Log with custom x-axis
wandb.log({"loss": loss}, step=global_step)

# Log images
wandb.log({"examples": [wandb.Image(img) for img in images]})

# Log histograms
wandb.log({"gradients": wandb.Histogram(gradients)})

# Log tables for interactive exploration
table = wandb.Table(columns=["epoch", "loss", "accuracy"])
for epoch in range(10):
    table.add_data(epoch, losses[epoch], accuracies[epoch])
wandb.log({"metrics_table": table})


## Model Checkpointing

python
import torch
import wandb

# Save checkpoint
checkpoint = {
    'epoch': epoch,
    'model_state_dict': model.state_dict(),
    'optimizer_state_dict': optimizer.state_dict(),
    'loss': loss,
}
torch.save(checkpoint, 'checkpoint.pth')
wandb.save('checkpoint.pth')

# Use Artifacts (recommended)
artifact = wandb.Artifact('model', type='model')
artifact.add_file('checkpoint.pth')
wandb.log_artifact(artifact)


## Hyperparameter Sweeps

### Define Sweep Configuration

python
sweep_config = {
    'method': 'bayes',  # or 'grid', 'random'
    'metric': {'name': 'val/accuracy', 'goal': 'maximize'},
    'parameters': {
        'learning_rate': {'distribution': 'log_uniform', 'min': 1e-5, 'max': 1e-1},
        'batch_size': {'values': [16, 32, 64, 128]},
        'optimizer': {'values': ['adam', 'sgd', 'rmsprop']},
        'dropout': {'distribution': 'uniform', 'min': 0.1, 'max': 0.5}
    }
}

sweep_id = wandb.sweep(sweep_config, project="my-project")


### Training Function

python
def train():
    run = wandb.init()
    model = build_model(wandb.config)
    optimizer = get_optimizer(wandb.config.optimizer, wandb.config.learning_rate)
    
    for epoch in range(NUM_EPOCHS):
        train_loss = train_epoch(model, optimizer, wandb.config.batch_size)
        val_acc = validate(model)
        wandb.log({"train/loss": train_loss, "val/accuracy": val_acc})

wandb.agent(sweep_id, function=train, count=50)


### Sweep Strategies

python
# Grid search - exhaustive
sweep_config = {'method': 'grid', 'parameters': {'lr': {'values': [0.001, 0.01, 0.1]}}}

# Random search
sweep_config = {'method': 'random', 'parameters': {'lr': {'distribution': 'uniform', 'min': 0.0001, 'max': 0.1}}}

# Bayesian optimization (recommended)
sweep_config = {'method': 'bayes', 'metric': {'name': 'val/loss', 'goal': 'minimize'}, 'parameters': {...}}


### Sweep via YAML (CLI)

yaml
# sweep.yaml
method: bayes
metric:
  name: val_loss
  goal: minimize
parameters:
  learning_rate:
    min: 0.0001
    max: 0.1
    distribution: log_uniform
  batch_size:
    values: [16, 32, 64]


bash
wandb sweep project/sweep.yaml
wandb agent project/sweep-id


## Artifacts

### Log Artifacts

python
artifact = wandb.Artifact(
    name='training-dataset',
    type='dataset',
    description='ImageNet training split',
    metadata={'size': '1.2M images', 'split': 'train'}
)
artifact.add_file('data/train.csv')
artifact.add_dir('data/images/')
wandb.log_artifact(artifact)


### Use Artifacts

python
run = wandb.init(project="my-project")
artifact = run.use_artifact('training-dataset:latest')
artifact_dir = artifact.download()
data = load_data(f"{artifact_dir}/train.csv")


### Model Registry

python
model_artifact = wandb.Artifact('resnet50-model', type='model', metadata={'accuracy': 0.95})
model_artifact.add_file('model.pth')
wandb.log_artifact(model_artifact, aliases=['best', 'production'])
run.link_artifact(model_artifact, 'model-registry/production-models')


## Weave (LLM Tracing)

Weave provides automatic tracing for LLM applications:

python
from weave import WeaveClient

client = WeaveClient()

@weave.op()
def generate_response(prompt: str) -> str:
    return llm_call(prompt)

response = generate_response("Hello, world!")  # Automatically traced


## CLI Commands

bash
# Login
wandb login
wandb login --relogin

# Initialize a run
wandb run --python train.py

# Sync local runs
wandb sync

# Sweep operations
wandb sweep project/sweep.yaml
wandb agent project/sweep-id

# Artifact management
wandb artifact put -n model/model-name /path/to/model
wandb artifact get user/project/model-name:v0

# Model registry
wandb registry MODEL create <model-name>
wandb registry MODEL add <model-name>:<version>


## Framework Integrations

### HuggingFace Transformers

python
from transformers import Trainer, TrainingArguments
import wandb

wandb.init(project="hf-transformers")

training_args = TrainingArguments(
    output_dir="./results",
    report_to="wandb",
    run_name="bert-finetuning",
    logging_steps=100,
    save_steps=500
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset
)
trainer.train()


### PyTorch Lightning

python
from pytorch_lightning import Trainer
from pytorch_lightning.loggers import WandbLogger

wandb_logger = WandbLogger(project="lightning-demo", log_model=True)

trainer = Trainer(logger=wandb_logger, max_epochs=10)
trainer.fit(model, datamodule=dm)


### Keras/TensorFlow

python
import wandb
from wandb.keras import WandbCallback

wandb.init(project="keras-demo")
model.fit(
    x_train, y_train,
    validation_data=(x_val, y_val),
    epochs=10,
    callbacks=[WandbCallback()]
)


## Best Practices

### 1. Organize with Tags and Groups

python
wandb.init(
    project="my-project",
    tags=["baseline", "resnet50", "imagenet"],
    group="resnet-experiments",
    job_type="train"
)


### 2. Log Everything Relevant

python
wandb.log({
    "gpu/util": gpu_utilization,
    "gpu/memory": gpu_memory_used,
    "git_commit": git_commit_hash,
    "data/train_size": len(train_dataset),
    "data/val_size": len(val_dataset)
})


### 3. Use Descriptive Names

python
wandb.init(name="bert-base-lr0.001-bs32-epoch10")


### 4. Save Important Artifacts

python
artifact = wandb.Artifact('final-model', type='model')
artifact.add_file('model.pth')
wandb.log_artifact(artifact)


### 5. Use Offline Mode for Unstable Connections

python
import os
os.environ["WANDB_MODE"] = "offline"
wandb.init(project="my-project")
# Later: wandb sync <run_directory>


## Visualization & Analysis

### Custom Charts

python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot(x, y)
wandb.log({"custom_plot": wandb.Image(fig)})

# Log confusion matrix
wandb.log({"conf_mat": wandb.plot.confusion_matrix(
    y_true=ground_truth, preds=predictions, class_names=class_names
)})


### Reports
- Combine runs, charts, and text
- Markdown support
- Embeddable visualizations
- Team collaboration

## Team Collaboration

Runs are automatically shareable via URL. Create a team account at wandb.ai, add team members, and set project visibility (private/public).

## Environment Variables

| Variable | Description |
|----------|-------------|
| `WANDB_API_KEY` | API key for authentication |
| `WANDB_PROJECT` | Default project name |
| `WANDB_ENTITY` | Team/organization name |
| `WANDB_MODE` | `online` (default), `offline`, or `disabled` |
| `WANDB_DIR` | Local directory for offline storage |

## Troubleshooting

### Offline Mode
python
wandb.init(mode="offline")
# Later sync: wandb sync


### Large File Handling
python
wandb.init(exclude_fn=lambda path: path.endswith(".bin"))


### Slow Networking
python
wandb.init(batch_size=100)  # Increase logging batch size


### Authentication Errors
bash
wandb login --relogin


## Quick Reference

| Operation | Command/Code |
|-----------|---------------|
| Initialize run | `wandb.init(project="name")` |
| Log metric | `wandb.log({"loss": 0.5})` |
| Watch model | `wandb.watch(model)` |
| Log artifact | `wandb.log_artifact(artifact)` |
| Create sweep | `wandb sweep sweep.yaml` |
| Sync offline | `wandb sync ./wandb` |

## Pricing

- **Free**: Unlimited public projects, 100GB storage
- **Academic**: Free for students/researchers
- **Teams**: $50/seat/month, private projects, unlimited storage
- **Enterprise**: Custom pricing, on-prem options

## Resources

- **Documentation**: https://docs.wandb.ai
- **GitHub**: https://github.com/wandb/wandb (10.5k+ stars)
- **Examples**: https://github.com/wandb/examples
- **Community**: https://wandb.ai/community
- **Discord**: https://wandb.me/discord

## See Also

- `references/sweeps.md` - Comprehensive hyperparameter optimization guide
- `references/artifacts.md` - Data and model versioning patterns
- `references/integrations.md` - Framework-specific examples
