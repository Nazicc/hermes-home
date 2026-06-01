---
name: outlines
description: Guarantee valid JSON/XML/code structure during generation, use Pydantic models for type-safe outputs, support local models (Transformers, vLLM), and maximize inference speed with Outlines - dottxt.ai's structured generation library
version: 1.0.0
author: Orchestra Research
license: MIT
dependencies: [outlines, transformers, vllm, pydantic]
metadata:
  hermes:
    tags: [Prompt Engineering, Outlines, Structured Generation, JSON Schema, Pydantic, Local Models, Grammar-Based Generation, vLLM, Transformers, Type Safety]

---

# Outlines: Structured Text Generation

## When to Use This Skill

Use Outlines when you need to:
- **Guarantee valid JSON/XML/code** structure during generation
- **Use Pydantic models** for type-safe outputs
- **Support local models** (Transformers, llama.cpp, vLLM)
- **Maximize inference speed** with zero-overhead structured generation
- **Generate against JSON schemas** automatically
- **Control token sampling** at the grammar level

**GitHub Stars**: 8,000+ | **From**: dottxt.ai (formerly .txt)

## Installation

```bash
# Base installation
pip install outlines

# With specific backends
pip install outlines transformers  # Hugging Face models
pip install outlines llama-cpp-python  # llama.cpp
pip install outlines vllm  # vLLM for high-throughput
```

## Quick Start

### Basic Example: Classification

```python
import outlines
from typing import Literal

# Load model
model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")

# Generate with type constraint
prompt = "Sentiment of 'This product is amazing!': "
generator = outlines.generate.choice(model, ["positive", "negative", "neutral"])
sentiment = generator(prompt)

print(sentiment)  # "positive" (guaranteed one of these)
```

### With Pydantic Models

```python
from pydantic import BaseModel
import outlines

class User(BaseModel):
    name: str
    age: int
    email: str

model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")

# Generate structured output
prompt = "Extract user: John Doe, 30 years old, john@example.com"
generator = outlines.generate.json(model, User)
user = generator(prompt)

print(user.name)   # "John Doe"
print(user.age)    # 30
print(user.email)  # "john@example.com"
```

## Core Concepts

### 1. Constrained Token Sampling

Outlines uses Finite State Machines (FSM) to constrain token generation at the logit level.

**How it works:**
1. Convert schema (JSON/Pydantic/regex) to context-free grammar (CFG)
2. Transform CFG into Finite State Machine (FSM)
3. Filter invalid tokens at each step during generation
4. Fast-forward when only one valid token exists

**Benefits:**
- **Zero overhead**: Filtering happens at token level
- **Speed improvement**: Fast-forward through deterministic paths
- **Guaranteed validity**: Invalid outputs impossible

```python
import outlines

# Pydantic model -> JSON schema -> CFG -> FSM
class Person(BaseModel):
    name: str
    age: int

model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")

# Behind the scenes:
# 1. Person -> JSON schema
# 2. JSON schema -> CFG
# 3. CFG -> FSM
# 4. FSM filters tokens during generation

generator = outlines.generate.json(model, Person)
result = generator("Generate person: Alice, 25")
```

### 2. Structured Generators

Outlines provides specialized generators for different output types.

#### Choice Generator

```python
# Multiple choice selection
generator = outlines.generate.choice(
    model,
    ["positive", "negative", "neutral"]
)

sentiment = generator("Review: This is great!")
# Result: One of the three choices
```

#### JSON Generator

```python
from pydantic import BaseModel

class Product(BaseModel):
    name: str
    price: float
    in_stock: bool

# Generate valid JSON matching schema
generator = outlines.generate.json(model, Product)
product = generator("Extract: iPhone 15, $999, available")

# Guaranteed valid Product instance
print(type(product))  # <class '__main__.Product'>
```

#### Regex Generator

```python
# Generate text matching regex
generator = outlines.generate.regex(
    model,
    r"[0-9]{3}-[0-9]{3}-[0-9]{4}"  # Phone number pattern
)

phone = generator("Generate phone number:")
# Result: "555-123-4567" (guaranteed to match pattern)
```

#### Integer/Float Generators

```python
# Generate specific numeric types
int_generator = outlines.generate.integer(model)
age = int_generator("Person's age:")  # Guaranteed integer

float_generator = outlines.generate.float(model)
price = float_generator("Product price:")  # Guaranteed float
```

### 3. Model Backends

Outlines supports multiple local and API-based backends.

#### Transformers (Hugging Face)

```python
import outlines

# Load from Hugging Face
model = outlines.models.transformers(
    "microsoft/Phi-3-mini-4k-instruct",
    device="cuda"  # Or "cpu"
)

# Use with any generator
generator = outlines.generate.json(model, YourModel)
```

#### llama.cpp

```python
# Load GGUF model
model = outlines.models.llamacpp(
    "./models/llama-3.1-8b-instruct.Q4_K_M.gguf",
    n_gpu_layers=35
)

generator = outlines.generate.json(model, YourModel)
```

#### vLLM (High Throughput)

```python
# For production deployments
model = outlines.models.vllm(
    "meta-llama/Llama-3.1-8B-Instruct",
    tensor_parallel_size=2  # Multi-GPU
)

generator = outlines.generate.json(model, YourModel)
```

#### OpenAI (Limited Support)

```python
# Basic OpenAI support
model = outlines.models.openai(
    "gpt-4o-mini",
    api_key="your-api-key"
)

# Note: Some features limited with API models
generator = outlines.generate.json(model, YourModel)
```

### 4. Pydantic Integration

Outlines has first-class Pydantic support with automatic schema translation.

#### Basic Models

```python
from pydantic import BaseModel, Field

class Article(BaseModel):
    title: str = Field(description="Article title")
    author: str = Field(description="Author name")
    word_count: int = Field(description="Number of words", gt=0)
    tags: list[str] = Field(description="List of tags")

model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")
generator = outlines.generate.json(model, Article)

article = generator("Generate article about AI")
print(article.title)
print(article.word_count)  # Guaranteed > 0
```

#### Nested Models

```python
class Address(BaseModel):
    street: str
    city: str
    country: str

class Person(BaseModel):
    name: str
    age: int
    address: Address  # Nested model

generator = outlines.generate.json(model, Person)
person = generator("Generate person in New York")

print(person.address.city)  # "New York"
```

#### Enums and Literals

```python
from enum import Enum
from typing import Literal

class Status(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class Application(BaseModel):
    applicant: str
    status: Status  # Must be one of enum values
    priority: Literal["low", "medium", "high"]  # Must be one of literals

generator = outlines.generate.json(model, Application)
app = generator("Generate application")

print(app.status)  # Status.PENDING (or APPROVED/REJECTED)
```

## Common Patterns

### Pattern 1: Data Extraction

```python
from pydantic import BaseModel
import outlines

class CompanyInfo(BaseModel):
    name: str
    founded_year: int
    industry: str
    employees: int

model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")
generator = outlines.generate.json(model, CompanyInfo)

text = """
Apple Inc. was founded in 1976 in the technology industry.
The company employs approximately 164,000 people worldwide.
"""

prompt = f"Extract company information:\n{text}\n\nCompany:"
company = generator(prompt)

print(f"Name: {company.name}")
print(f"Founded: {company.founded_year}")
print(f"Industry: {company.industry}")
print(f"Employees: {company.employees}")
```

### Pattern 2: Classification

```python
from typing import Literal
import outlines

model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")

# Binary classification
generator = outlines.generate.choice(model, ["spam", "not_spam"])
result = generator("Email: Buy now! 50% off!")

# Multi-class classification
categories = ["technology", "business", "sports", "entertainment"]
category_gen = outlines.generate.choice(model, categories)
category = category_gen("Article: Apple announces new iPhone...")

# With confidence
class Classification(BaseModel):
    label: Literal["positive", "negative", "neutral"]
    confidence: float

classifier = outlines.generate.json(model, Classification)
result = classifier("Review: This product is okay, nothing special")
```

### Pattern 3: Structured Forms

```python
class UserProfile(BaseModel):
    full_name: str
    age: int
    email: str
    phone: str
    country: str
    interests: list[str]

model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")
generator = outlines.generate.json(model, UserProfile)

prompt = """
Extract user profile from:
Name: Alice Johnson
Age: 28
Email: alice@example.com
Phone: 555-0123
Country: USA
Interests: hiking, photography, cooking
"""

profile = generator(prompt)
print(profile.full_name)
print(profile.interests)  # ["hiking", "photography", "cooking"]
```

### Pattern 4: Multi-Entity Extraction

```python
class Entity(BaseModel):
    name: str
    type: Literal["PERSON", "ORGANIZATION", "LOCATION"]

class DocumentEntities(BaseModel):
    entities: list[Entity]

model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")
generator = outlines.generate.json(model, DocumentEntities)

text = "Tim Cook met with Satya Nadella at Microsoft headquarters in Redmond."
prompt = f"Extract entities from: {text}"

result = generator(prompt)
for entity in result.entities:
    print(f"{entity.name} ({entity.type})")
```

### Pattern 5: Code Generation

```python
class PythonFunction(BaseModel):
    function_name: str
    parameters: list[str]
    docstring: str
    body: str

model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")
generator = outlines.generate.json(model, PythonFunction)

prompt = "Generate a Python function to calculate factorial"
func = generator(prompt)

print(f"def {func.function_name}({', '.join(func.parameters)}):")
print(f'    """{func.docstring}"""')
print(f"    {func.body}")
```

### Pattern 6: Batch Processing

```python
def batch_extract(texts: list[str], schema: type[BaseModel]):
    """Extract structured data from multiple texts."""
    model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")
    generator = outlines.generate.json(model, schema)

    results = []
    for text in texts:
        result = generator(f"Extract from: {text}")
        results.append(result)

    return results

class Person(BaseModel):
    name: str
    age: int

texts = [
    "John is 30 years old",
    "Alice is 25 years old",
    "Bob is 40 years old"
]

people = batch_extract(texts, Person)
for person in people:
    print(f"{person.name}: {person.age}")
```

## Backend Configuration

### Transformers

```python
import outlines

# Basic usage
model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")

# GPU configuration
model = outlines.models.transformers(
    "microsoft/Phi-3-mini-4k-instruct",
    device="cuda",
    model_kwargs={"torch_dtype": "float16"}
)

# Popular models
model = outlines.models.transformers("meta-llama/Llama-3.1-8B-Instruct")
model = outlines.models.transformers("mistralai/Mistral-7B-Instruct-v0.3")
model = outlines.models.transformers("Qwen/Qwen2.5-7B-Instruct")
```

### llama.cpp

```python
# Load GGUF model
model = outlines.models.llamacpp(
    "./models/llama-3.1-8b.Q4_K_M.gguf",
    n_ctx=4096,         # Context window
    n_gpu_layers=35,    # GPU layers
    n_threads=8         # CPU threads
)

# Full GPU offload
model = outlines.models.llamacpp(
    "./models/model.gguf",
    n_gpu_layers=-1  # All layers on GPU
)
```

### vLLM (Production)

```python
# Single GPU
model = outlines.models.vllm("meta-llama/Llama-3.1-8B-Instruct")

# Multi-GPU
model = outlines.models.vllm(
    "meta-llama/Llama-3.1-70B-Instruct",
    tensor_parallel_size=4  # 4 GPUs
)

# With quantization
model = outlines.models.vllm(
    "meta-llama/Llama-3.1-8B-Instruct",
    quantization="awq"  # Or "gptq"
)
```

## Best Practices

### 1. Use Specific Types

```python
# ✅ Good: Specific types
class Product(BaseModel):
    name: str
    price: float  # Not str
    quantity: int  # Not str
    in_stock: bool  # Not str

# ❌ Bad: Everything as string
class Product(BaseModel):
    name: str
    price: str  # Should be float
    quantity: str  # Should be int
```

### 2. Add Constraints

```python
from pydantic import Field

# ✅ Good: With constraints
class User(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=0, le=120)
    email: str = Field(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")

# ❌ Bad: No constraints
class User(BaseModel):
    name: str
    age: int
    email: str
```

### 3. Use Enums for Categories

```python
# ✅ Good: Enum for fixed set
class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Task(BaseModel):
    title: str
    priority: Priority

# ❌ Bad: Free-form string
class Task(BaseModel):
    title: str
    priority: str  # Can be anything
```

### 4. Provide Context in Prompts

```python
# ✅ Good: Clear context
prompt = """
Extract product information from the following text.
Text: iPhone 15 Pro costs $999 and is currently in stock.
Product:
"""

# ❌ Bad: Minimal context
prompt = "iPhone 15 Pro costs $999 and is currently in stock."
```

### 5. Handle Optional Fields

```python
from typing import Optional

# ✅ Good: Optional fields for incomplete data
class Article(BaseModel):
    title: str  # Required
    author: Optional[str] = None  # Optional
    date: Optional[str] = None  # Optional
    tags: list[str] = []  # Default empty list

# Can succeed even if author/date missing
```

## Comparison to Alternatives

| Feature | Outlines | Instructor | Guidance | LMQL |
|---------|----------|------------|----------|------|
| Pydantic Support | ✅ Native | ✅ Native | ❌ No | ❌ No |
| JSON Schema | ✅ Yes | ✅ Yes | ⚠️ Limited | ✅ Yes |
| Regex Constraints | ✅ Yes | ❌ No | ✅ Yes | ✅ Yes |
| Local Models | ✅ Full | ⚠️ Limited | ✅ Full | ✅ Full |
| API Models | ⚠️ Limited | ✅ Full | ✅ Full | ✅ Full |
| Zero Overhead | ✅ Yes | ❌ No | ⚠️ Partial | ✅ Yes |
| Automatic Retrying | ❌ No | ✅ Yes | ❌ No | ❌ No |
| Learning Curve | Low | Low | Low | High |

When to choose Outlines:
- Using local models (Transformers, llama.cpp, vLLM)
- Need maximum inference speed
- Want Pydantic model support
- Require zero-overhead structured generation
- Control token sampling process

When to choose alternatives:
- Instructor: Need API models with automatic retrying
- Guidance: Need token healing and complex workflows
- LMQL: Prefer declarative query syntax

## Performance Characteristics

Speed:
- **Zero overhead**: Structured generation as fast as unconstrained
- **Fast-forward optimization**: Skips deterministic tokens
- **1.2-2x faster** than post-generation validation approaches

Memory:
- FSM compiled once per schema (cached)
- Minimal runtime overhead
- Efficient with vLLM for high throughput

Accuracy:
- **100% valid outputs** (guaranteed by FSM)
- No retry loops needed
- Deterministic token filtering

## Resources

- **Documentation**: https://outlines-dev.github.io/outlines
- **GitHub**: https://github.com/outlines-dev/outlines (8k+ stars)
- **Discord**: https://discord.gg/R9DSu34mGd
- **Blog**: https://blog.dottxt.co

## See Also

- `references/json_generation.md` - Comprehensive JSON and Pydantic patterns
- `references/backends.md` - Backend-specific configuration
- `references/examples.md` - Production-ready examples

## Purpose

Guarantee valid JSON, XML, code, or regex structure during LLM generation by constraining the token sampling process at the logit level — no retries, no regex parsing, no post-hoc validation.

## Why This Works

**Concept 1: Logit-Level FSM Masking.** Outlines converts a schema (JSON Schema, Pydantic model, regex, or CFG) into a Finite State Machine (FSM). At each decoding step, the FSM's current state determines which tokens are valid next entries. Invalid tokens have their logits set to -inf before softmax, making them impossible to sample. This is orders of magnitude faster than generate-then-validate.

**Concept 2: Fast-Forward Optimization (Deterministic Path Shortcut).** When the FSM has exactly one valid next token (e.g., whitespace after a comma in JSON, or a closing brace), Outlines skips the model forward pass entirely and appends the token directly. In structured outputs where ~40-60% of positions are deterministic, this yields net speedup over unconstrained generation.

**Concept 3: Schema-to-Grammar Compilation.** A Pydantic model → JSON Schema → Context-Free Grammar → FSM. Field constraints (min_length, pattern, ge/le, Literal, Enum) are compiled into the grammar, so generated outputs satisfy all constraints by construction — no Pydantic validation errors at runtime.

## Examples

**Good: Type-Safe Information Extraction from Noisy Text**

Extract structured invoice data with field-level constraints:
```python
from pydantic import BaseModel, Field
from typing import Literal
import outlines

class InvoiceLine(BaseModel):
    description: str = Field(max_length=200)
    quantity: int = Field(ge=1, le=999)
    unit_price: float = Field(gt=0, le=1_000_000)
    currency: Literal["USD", "EUR", "GBP", "JPY"]

class Invoice(BaseModel):
    invoice_number: str = Field(pattern=r"INV-\d{6}")
    lines: list[InvoiceLine]
    total: float

model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")
generator = outlines.generate.json(model, Invoice)
invoice = generator("Extract: INV-004237, 3x Widgets @ $12.50, 2x Gadgets @ $99.95, total $237.40")
# invoice.total == 237.40 — guaranteed valid float
# invoice.invoice_number matches "INV-004237" — guaranteed by regex
```

**Good: Structured Classification with Logit-Biased Choices**

Classify support tickets into predefined categories with guaranteed bounds:
```python
from pydantic import BaseModel, Field
from typing import Literal
import outlines

class TicketClassification(BaseModel):
    category: Literal["billing", "technical", "account", "feature_request"]
    priority: Literal["P0", "P1", "P2", "P3"]
    confidence: float = Field(ge=0.0, le=1.0)

model = outlines.models.transformers("mistralai/Mistral-7B-Instruct-v0.3")
classifier = outlines.generate.json(model, TicketClassification)
result = classifier("Ticket: User cannot log in after password reset")
# Guaranteed: result.category in {"billing","technical","account","feature_request"}
```

**Good: Regex-Guided Structured Generation for Phone Numbers**

Generate synthetic data matching a specific phone pattern without post-processing:
```python
import outlines
model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")
phone_gen = outlines.generate.regex(model, r"\(\d{3}\) \d{3}-\d{4}")
phone = phone_gen("Generate a US phone number:")
# "(555) 123-4567" — guaranteed match; no post-filtering needed
```

**Good: Multi-Entity Extraction with Nested Enums**

Extract all named entities and their relationships from a passage:
```python
from pydantic import BaseModel
from typing import Literal

class Relation(BaseModel):
    subject: str
    predicate: Literal["works_at", "founded", "acquired", "invests_in"]
    object: str

class KnowledgeGraph(BaseModel):
    entities: list[dict]  # allowed to be flexible
    relations: list[Relation]

model = outlines.models.vllm("meta-llama/Llama-3.1-8B-Instruct")
generator = outlines.generate.json(model, KnowledgeGraph)
kg = generator("Elon Musk founded SpaceX in 2002. He also works at Tesla.")
# kg.relations[0].predicate == "founded" — guaranteed one of the Literal values
```

## Anti-Patterns

**Anti-Pattern 1: Using Outlines with API-Only Models for Complex Schemas.** Outlines' OpenAI backend has limited FSM control — the API model may still produce invalid JSON if the prompt doesn't instruct correctly. For production schema-guaranteed output with API models, use *Instructor* (which retries on validation failure) instead.

**Anti-Pattern 2: Overly Complex Nested Pydantic Models Without Testing.** A schema with 10+ nesting levels and dozens of fields can produce a very large FSM that takes seconds to compile. Profile with `%time` before production use. If compilation exceeds 5s, flatten the schema or split into multiple generation passes.

**Anti-Pattern 3: Using `str` Instead of `Literal` for Fixed-Vocabulary Fields.** Fields like `category: str` open the FSM to any string, defeating the purpose of structured generation. Always use `Literal["a", "b", "c"]` or `Enum` for bounded categorical fields — this dramatically shrinks the FSM and improves generation quality.

**Anti-Pattern 4: Not Providing Context in the Prompt.** Outlines constrains *structure* but not *content*. Without clear extraction instructions, the model may fill fields with plausible but wrong values. Always include the source text and a clear instruction in the prompt string, even though Outlines guarantees the shape.

## When NOT to Use

- **API model backends (OpenAI, Anthropic):** Outlines cannot apply logit masking to remote API calls. Use *Instructor* for API models, which retries until valid output.
- **Generation with free-form creativity:** If the output doesn't need a fixed schema (story generation, open-ended chat), Outlines adds unnecessary overhead and restricts the output space.
- **Real-time streaming with mid-generation schema changes:** Outlines compiles the FSM once upfront; changing the schema mid-generation requires creating a new generator.
- **When the schema is trivial (single boolean or integer):** A simple `generate.choice(model, ["yes","no"])` is overkill — a well-crafted prompt with logit bias is simpler.
- **Models without a tokenizer that exposes a vocabulary:** Outlines needs the full token → logit mapping to build the FSM mask. Some quantized GGUF backends may not support this.
- **Very large vocabularies (>300K tokens):** The FSM mask operation scales with vocabulary size and can become the bottleneck for decoding speed.

## Cross-References

- **vllm** — Use `outlines.models.vllm(...)` backend for structured generation at production throughput
- **peft** — Fine-tune models with PEFT adapters, then use Outlines for structured inference on the adapted model
- **pytorch-fsdp** — Train large models with FSDP for distributed training, then use Outlines for structured inference
- **accelerate** — Use with Outlines for distributed structured generation across GPUs
- **instructor** — Alternative for API models with automatic retry on validation failure


