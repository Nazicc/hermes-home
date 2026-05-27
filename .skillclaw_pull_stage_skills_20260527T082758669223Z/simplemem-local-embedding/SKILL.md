---
name: simplemem-local-embedding
description: "Use when SimpleMem embedding download fails due to HuggingFace SSL blocking in mainland China, or when configuring a local embedding model cache for SimpleMem using sirchmunk MCP server. Sets SIMPLEMEM_EMBEDDING_MODEL to a sirchmunk local cache path instead of a HuggingFace model ID. NOT for: HuggingFace is accessible normally, need to use standard HuggingFace model IDs, tasks not involving SimpleMem, or non-HuggingFace model sources."
category: general
---

## SimpleMem 本地 Embedding 配置（规避 HuggingFace SSL 阻断）

### 核心问题

HuggingFace 在中国大陆/CGN 环境会被 SSL 阻断，导致 `SIMPLEMEM_EMBEDDING_MODEL` 设为 HuggingFace 模型 ID 时下载超时失败。

- `HF_ENDPOINT=https://hf-mirror.com` 镜像在此场景下不可靠
- 解决方案：用 sirchmunk MCP server 将模型缓存到本地，然后通过本地绝对路径加载

错误示例：

SSLError: HTTPSConnectionPool(host='huggingface.co', port=443)


### 关键发现

1. `SIMPLEMEM_EMBEDDING_MODEL` 必须设为**本地绝对路径**，不能用 HuggingFace 模型 ID
2. 路径使用 sirchmunk 缓存，格式为 `~/.hermes/sirchmunk-data/.cache/huggingface/sentence-transformers__<model-name>/`
3. LLM API key 通过环境变量传递，不传参（传参可能 propagate 不到 LLM backend）
4. `add_dialogue(speaker, content, timestamp)` — 三个独立参数，不是 Dialogue 对象，timestamp 可为 `None`
5. `finalize()` 必须在 `add_dialogue` 后调用，才会 flush 数据到存储后端

### 环境准备

bash
# 安装 simplemem 和 sentence-transformers
~/.openharness-venv/bin/pip install simplemem sentence-transformers

# 确认 sirchmunk 缓存中有目标模型
ls ~/.hermes/sirchmunk-data/.cache/huggingface/hub/


sirchmunk 缓存路径格式：
- HuggingFace hub 格式：`~/.hermes/sirchmunk-data/.cache/huggingface/hub/models--<org>--<model-name>/snapshots/...`
- sentence-transformers 格式（推荐）：`~/.hermes/sirchmunk-data/.cache/huggingface/sentence-transformers__<model-name>/`
- 模型缓存：`~/.hermes/sirchmunk-data/.cache/models/`

### 可用本地模型

| 模型 | 维度 | 路径格式 |
|------|------|----------|
| paraphrase-multilingual-MiniLM-L12-v2 | 384 | `~/.hermes/sirchmunk-data/.cache/models/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| bge-small-zh-v1.5 | 384 | `~/.hermes/sirchmunk-data/.cache/huggingface/hub/models--BAAI--bge-small-zh-v1.5/snapshots/...` |
| all-MiniLM-L6-v2 | 384 | `~/.hermes/sirchmunk-data/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/...` |
| all-MiniLM-L12-v2 | 384 | `~/.hermes/sirchmunk-data/.cache/huggingface/sentence-transformers__all-MiniLM-L12-v2/` |

> ⚠️ `SIMPLEMEM_EMBEDDING_MODEL` 必须是**本地绝对路径**，不能用 HuggingFace 模型 ID（如 `BAAI/bge-small-zh-v1.5`）。

### 环境变量配置

bash
export SIMPLEMEM_EMBEDDING_MODEL="/Users/can/.hermes/sirchmunk-data/.cache/huggingface/sentence-transformers__all-MiniLM-L12-v2/"
export SIMPLEMEM_EMBEDDING_DIM="384"
export SIMPLEMEM_LLM_PROVIDER="openai"
export SIMPLEMEM_LLM_BASE_URL="http://127.0.0.1:30000/v1"
export SIMPLEMEM_LLM_MODEL="MiniMax-M2.7-1c5efd08"
export OPENAI_API_KEY="sk-cp-..."  # MiniMax via SkillClaw


| 变量名 | 值 | 说明 |
|--------|-----|------|
| `SIMPLEMEM_EMBEDDING_MODEL` | 本地绝对路径 | **不能用 HuggingFace 模型 ID** |
| `SIMPLEMEM_EMBEDDING_DIM` | `384` | 必须与模型输出维度匹配 |
| `SIMPLEMEM_STORAGE_TYPE` | `LanceDB` | 存储后端类型 |
| `SIMPLEMEM_LLM_API_KEY` | `xxx` | MiniMax API key（SiliconFlow 兼容） |
| `SIMPLEMEM_LLM_BASE_URL` | `https://api.minimax.chat/v1` | LLM API 地址 |
| `SIMPLEMEM_LLM_MODEL` | `MiniMax-Text-01` | LLM 模型名称 |

### Python 配置

python
import os
os.environ.update({
    "SIMPLEMEM_EMBEDDING_MODEL": "/Users/can/.hermes/sirchmunk-data/.cache/huggingface/sentence-transformers__all-MiniLM-L12-v2/",
    "SIMPLEMEM_EMBEDDING_DIM": "384",
    "SIMPLEMEM_LLM_PROVIDER": "openai",
    "SIMPLEMEM_LLM_BASE_URL": "http://127.0.0.1:30000/v1",
    "SIMPLEMEM_LLM_MODEL": "MiniMax-M2.7-1c5efd08",
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
})

from simplemem import SimpleMemSystem

# 初始化（embedding_dim 与模型输出维度匹配）
system = SimpleMemSystem(embedding_dim=384)


### API 调用流程

SimpleMem 的内存管理需要三步：添加对话、持久化、查询。

python
from simplemem import SimpleMemSystem

# 初始化
system = SimpleMemSystem(embedding_dim=384)

# 添加单条对话（三个独立参数，timestamp 可为 None）
system.add_dialogue("user", "我在天融信做安全服务", None)
system.add_dialogue("assistant", "好的，记录在案", None)

# ⚠️ 必须调用 finalize() 将数据写入存储
system.finalize()

# 检索
results = system.retrieve("我的工作经历是什么？", top_k=3, hybrid=True)
for r in results:
    print(f"  [{r['score']:.3f}] {r['speaker']}: {r['content']}")

# 反射（可选，不同 API 版本方法名不同）
system.reflect(num_rounds=2, num_workers=8)  # 版本 A
# 或
system.run_reflection_rounds(n_rounds=2)      # 版本 B

# 生成回答（方法名因版本而异）
answer = system.generate_answer("我以前在哪里工作？")  # 版本 A
# 或 system.ask(...) 或 system.answer(...)         # 版本 B
print(f"回答: {answer}")


### 验证脚本

python
#!/Users/can/.openharness-venv/bin/python3
import os
os.environ["SIMPLEMEM_EMBEDDING_MODEL"] = "/Users/can/.hermes/sirchmunk-data/.cache/models/"
os.environ["SIMPLEMEM_STORAGE_TYPE"] = "LanceDB"

from simplemem import SimpleMemSystem

sys = SimpleMemSystem(embedding_dim=384)
sys.add_dialogue("user", "你好", None)
sys.add_dialogue("assistant", "你好，我是Can", None)
sys.finalize()

results = sys.hybrid_retrieve("Can", top_k=2)
print(f"检索到 {len(results)} 条结果")


### 完整 API 参考

python
# 初始化
system = SimpleMemSystem(embedding_dim=384)
# 或传入所有参数
system = SimpleMemSystem(
    embedding_model="/path/to/local/model",
    llm_provider="openai",
    llm_base_url="http://127.0.0.1:30000/v1",
    llm_model="MiniMax-M2.7-1c5efd08",
)

# 添加对话（三个独立参数，不是 Dialogue 对象）
system.add_dialogue(speaker: str, content: str, timestamp: str | None)

# ⚠️ 必须调用，否则内存不会持久化
system.finalize()

# 检索
system.retrieve(query: str, top_k: int = 5, hybrid: bool = True)
system.hybrid_retrieve(query: str, top_k: int = 5, alpha: float = 0.5)

# 反思（方法名因 API 版本而异）
system.reflect(num_rounds: int = 2, num_workers: int = 8)   # 版本 A
system.run_reflection_rounds(n_rounds: int)                 # 版本 B

# 生成回答（方法名因版本而异）
system.generate_answer(question: str, top_k: int = 3)  # 版本 A
system.ask(question: str, top_k: int = 3)              # 版本 B
system.answer(query: str)                               # 版本 B


### 关键注意事项

| 发现 | 正确做法 | 错误做法 |
|------|----------|----------|
| Embedding 模型路径 | 本地绝对路径（sirchmunk 缓存） | HuggingFace 模型 ID（如 `sentence-transformers/all-MiniLM-L6-v2`） |
| 添加对话 | `add_dialogue(speaker, content, timestamp)` | `add_dialogues([Dialogue(...)])` — 这个 API 不存在 |
| 触发处理 | 必须调用 `finalize()` | 不调用 finalize() 会导致 retrieval 返回空结果 |
| HuggingFace SSL | 已被中国运营商阻断 | 依赖 HF_ENDPOINT 镜像通常不可靠 |
| Python 路径 | `~/.openharness-venv/bin/python3` | 使用 hermes-agent 的 venv |

- Embedding 维度必须与模型输出维度匹配（所有可用模型均为 384）
- LLM API key 通过环境变量传递，不传参
- MiniMax API 需要 `tiktoken` 做 token 估算，首次使用前确保安装：`pip install tiktoken`
- 模型格式：本地路径下的模型必须是 compatible 格式

### 故障排查

| 错误 | 原因 | 修复 |
|------|------|------|
| `SSLError: connection refused` | HuggingFace 被阻断 | 改用本地缓存路径 |
| SSL 超时 / 连接失败 | `SIMPLEMEM_EMBEDDING_MODEL` 使用 HuggingFace 模型 ID 而非本地路径 | 改用 sirchmunk 缓存的本地绝对路径 |
| `AttributeError` on `finalize` | 忘记调用 `system.finalize()` | 在所有 `add_dialogue` 后添加 `system.finalize()` |
| `add_dialogues()` 不存在 | API 版本差异 | 使用 `add_dialogue(speaker, content, timestamp)` 单条添加 |
| `RuntimeError: index not finalized` | 检索前忘记调用 `finalize()` | 添加 `mem.finalize()` 或 `system.finalize()` |
| `ModuleNotFoundError: simplemem` | pip install 路径问题 | 检查 .venv 激活状态 |
| 向量维度不匹配 | `SimpleMemSystem(embedding_dim=...)` 与模型输出维度不一致 | 确认模型维度为 384 |
| retrieval 返回空结果 | 未调用 `finalize()` | 添加 `system.finalize()` |

### Docker Compose 部署

如需用 PostgreSQL 替代默认存储，参考 `simplestorage-adapter` skill 中的 Docker Compose 配置。

### 相关技能

- `simplemem-integration` — SimpleMem MCP server 集成基础
- `simplestorage-adapter` — SimpleMem 后端存储切换（PostgreSQL/pgvector）
- `simplerag-siliconflow` — SimpleMem + SiliconFlow/MiniMax API 路由配置
