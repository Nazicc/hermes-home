---
name: gbrain-siliconflow-debugging
description: "Debug gbrain embedding failures with SiliconFlow BAAI/bge-large-zh-v1.5 — triple root cause: MAX_CHARS too large for Chinese text, vector dimension mismatch in schema, and batch size limits."
category: debugging
---

# gbrain + SiliconFlow BAAI/bge-large-zh-v1.5 调试指南

## 环境
- **模型**: BAAI/bge-large-zh-v1.5（1024 维向量）
- **API**: SiliconFlow（base URL `https://api.siliconflow.cn/v1`）
- **数据库**: PGlite (SQLite-based) with pgvector extension，位于 `~/.gbrain/brain.pglite/`
- **CLI**: `~/bin/gbrain` → `cd ~/gbrain && bun run src/cli.ts`

## 快速诊断

bash
# 1. 检查当前 embedding 配置
cd ~/gbrain && grep -n "embedding_model\|embedding_dim\|BATCH_SIZE\|MAX_CHARS\|countWords\|chunkText" src/core/embedding-siliconflow.ts src/core/chunking.ts src/core/config.ts 2>/dev/null

# 2. 检查 SiliconFlow API 密钥和环境变量
cd ~/gbrain && source .env && echo "${SILICONFLOW_API_KEY:0:8}..."

# 3. 检查数据库 schema 实际维度
cd ~/gbrain && bun -e "
const { PGlite } = require('@electric-sql/pglite');
const { vector } = require('@electric-sql/pglite/vector');
const db = new PGlite('/Users/can/.gbrain/brain.pglite', { extensions: { vector } });
db.wait().then(() => db.query(\"SELECT attname, atttypid::regtype FROM pg_attribute WHERE attrelid = 'content_chunks'::regclass AND attname = 'embedding'\")).then(r => console.log(JSON.stringify(r.rows, null, 2))).catch(console.error);
"

# 4. 检查 config 表中的 embedding_dimensions
cd ~/gbrain && bun -e "
const { PGlite } = require('@electric-sql/pglite');
const { vector } = require('@electric-sql/pglite/vector');
const db = new PGlite('/Users/can/.gbrain/brain.pglite', { extensions: { vector } });
db.wait().then(() => db.query(\"SELECT * FROM config WHERE key = 'embedding_dimensions'\")).then(r => console.log(JSON.stringify(r.rows, null, 2))).catch(console.error);
"

# 5. 查看当前嵌入统计
cd ~/gbrain && source .env && bun run src/cli.ts stats


## 三类常见失败模式

### 1. 400 / 413 — Chunk token 超限

**症状**: `embed` 或 `embed --all` 时某些页面返回 `400 status code (no body)` 或 `413`

**根因**: `chunkText()` 在 `src/core/chunking.ts` 中使用 `countWords()` 计数，英文按空格分词，但**中文连续字符被识别为 1 个 word**（正则 `\S+` 无空格匹配）。因此一个 8000 中文字符的页面 → 1 个 8000+ char 的 chunk → ~8000 tokens（远超 bge-large-zh-v1.5 的 512 token 限制）。

**修复**: 修改 `src/core/chunking.ts` 中的 `MAX_CHARS` 从 `8000` 到 `450`:

typescript
const MAX_CHARS = 450; // ~512 tokens for Chinese; safe for bge-large-zh-v1.5 limit


然后重新 embedding：

bash
cd ~/gbrain && source .env && bun run src/cli.ts embed --all


**注意**: 修改 `MAX_CHARS` 后，已存在的 chunk 不会自动重新分片，需要先清理：

bash
# 清理所有 embedding 后重新分片
cd ~/gbrain && bun -e "
const { PGlite } = require('@electric-sql/pglite');
const { vector } = require('@electric-sql/pglite/vector');
const db = new PGlite('/Users/can/.gbrain/brain.pglite', { extensions: { vector } });
db.wait().then(() => db.query('DELETE FROM content_chunks')).then(() => console.log('Chunks cleared')).catch(console.error);
"


### 2. "expected 1536 dimensions, not 1024" — Schema 与模型不匹配

**症状**: pgvector 报错 `expected 1536 dimensions, not 1024`

**根因**: gbrain 原来使用 e5-mistral（1536 维），数据库 schema 中 `content_chunks.embedding` 列类型为 `vector(1536)`，config 表中 `embedding_dimensions = 1536`。切换到 BAAI/bge-large-zh-v1.5（1024 维）后，API 返回 1024 维向量，pgvector 拒绝写入。

**修复**: 创建并运行 `scripts/fix-schema.ts`:

typescript
// scripts/fix-schema.ts
import { PGlite } from '@electric-sql/pglite';
import { vector } from '@electric-sql/pglite/vector';

const db = new PGlite('/Users/can/.gbrain/brain.pglite', {
  extensions: { vector }
});

await db.wait();

// 1. 修改列类型
await db.query(`
  ALTER TABLE content_chunks
  ALTER COLUMN embedding TYPE vector(1024);
`);
console.log('✓ Column type changed to vector(1024)');

// 2. 清理旧维度数据
await db.query(`
  UPDATE content_chunks
  SET embedding = NULL;
`);
console.log('✓ Existing (stale) embeddings cleared');

// 3. 更新 config
await db.query(`
  UPDATE config
  SET value = '1024'
  WHERE key = 'embedding_dimensions';
`);
console.log('✓ Config updated to 1024 dimensions');

// 验证
const result = await db.query(`
  SELECT COUNT(*) as total,
         SUM(CASE WHEN embedding IS NULL THEN 1 ELSE 0 END) as null_embeds
  FROM content_chunks;
`);
console.log('Verification:', result.rows);

process.exit(0);


bash
cd ~/gbrain && source .env && bun scripts/fix-schema.ts
# 然后重新 embed
cd ~/gbrain && source .env && bun run src/cli.ts embed --all


### 3. 413 / 超时 — Batch Size 过大

**症状**: `embed --all` 时大量 413 错误或超长请求时间

**根因**: `BATCH_SIZE = 100` 在 `src/core/embedding-siliconflow.ts` 中远超 SiliconFlow 单次请求限制（~32 items）

**修复**: 修改 `src/core/embedding-siliconflow.ts`:

typescript
const BATCH_SIZE = 30; // SiliconFlow limit is ~32 items per request


### 4. 部分 chunk 400 错误（非 dimension 问题）

**症状**: 极少数页面 (如 2/53) 的所有 chunk 嵌入返回 400，但 embedding 列类型已正确。

**排查**: 检查页面内容是否为空、仅含特殊字符、或包含 API 拒绝的特殊 token。

bash
cd ~/gbrain && source .env && bun run src/cli.ts get <page_id>


**可能原因**: 页面内容为空、纯特殊字符、或 SiliconFlow 对特定字符序列返回 400。少量错误可能是内容为空或特殊字符问题，不影响核心功能。

## 完整修复流程

bash
# 1. 修改 chunking.ts — MAX_CHARS
sed -i '' 's/const MAX_CHARS = 8000/const MAX_CHARS = 450/' src/core/chunking.ts

# 2. 修改 embedding-siliconflow.ts — BATCH_SIZE
sed -i '' 's/const BATCH_SIZE = 100/const BATCH_SIZE = 30/' src/core/embedding-siliconflow.ts

# 3. 运行 schema 修复脚本
cd ~/gbrain && source .env && bun scripts/fix-schema.ts

# 4. 清理所有 embedding 重新计算
cd ~/gbrain && bun -e "
const { PGlite } = require('@electric-sql/pglite');
const { vector } = require('@electric-sql/pglite/vector');
const db = new PGlite('/Users/can/.gbrain/brain.pglite', { extensions: { vector } });
db.wait().then(() => db.query('DELETE FROM content_chunks')).then(() => { console.log('Chunks cleared'); process.exit(0); }).catch(console.error);
"

# 5. 重新 embedding
cd ~/gbrain && source .env && bun run src/cli.ts embed --all

# 6. 验证
cd ~/gbrain && source .env && bun run src/cli.ts stats
cd ~/gbrain && source .env && bun run src/cli.ts query "test query"


## 常见错误对照

| 错误 | 原因 | 修复 |
|------|------|------|
| 400 (no body) | chunk 超过 512 tokens | 降低 MAX_CHARS 至 450 |
| 413 | batch 过大 | 降低 BATCH_SIZE 至 30 |
| "expected 1536 dimensions, not 1024" | schema 维度和模型不匹配 | 运行 fix-schema.ts |
| 401 Unauthorized | API 密钥无效 | 检查 SILICONFLOW_API_KEY |
| ECONNREFUSED | SiliconFlow 服务不可达 | 检查网络或 API 余额 |

## SiliconFlow API 关键参数

| 参数 | 值 |
|------|-----|
| 模型 | BAAI/bge-large-zh-v1.5 |
| 维度 | 1024（必须与 schema 一致） |
| 单次请求上限 | ~32 条（建议 batch_size = 30） |
| 每条 token 上限 | 512（建议 MAX_CHARS = 450 以覆盖中文） |
| base URL | `https://api.siliconflow.cn/v1` |
| 端点 | `POST /v1/embeddings` |
| 环境变量 | `SILICONFLOW_API_KEY` |

## gbrain CLI 速查

| 命令 | 用途 |
|------|------|
| `bun run src/cli.ts init` | 初始化 |
| `bun run src/cli.ts add <path>` | 添加笔记 |
| `bun run src/cli.ts query "<text>"` | 语义搜索 |
| `bun run src/cli.ts stats` | 查看统计 |
| `bun run src/cli.ts embed --all` | 重新嵌入所有 |
| `bun run src/cli.ts get <id>` | 查看单条笔记 |

## 相关文件

- `src/core/embedding-siliconflow.ts` — SiliconFlow API 调用（BATCH_SIZE 配置）
- `src/core/chunking.ts` — 文本分块逻辑（MAX_CHARS 配置）
- `src/core/config.ts` — 配置文件读取
- `src/core/pglite-engine.ts` — 数据库 schema 验证
- `scripts/fix-schema.ts` — 向量维度迁移脚本
- `~/.gbrain/config.toml` — 用户配置
- `~/.gbrain/brain.pglite/` — PGlite 数据目录
