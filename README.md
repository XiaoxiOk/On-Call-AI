# On-Call Assistant

一个前后端分离 Web 应用，用于从 SOP 文档中检索故障处理流程，并提供基于工具调用的 On-Call 助手对话能力。

项目包含三条能力链路：

- Phase 1：基于 `jieba + rank_bm25` 的关键词检索
- Phase 2：基于 `sentence-transformers` 的语义检索，结合 chunk 检索、BM25 补充分数和标题加权
- Phase 3：基于 LangChain Agent 的流式问答，支持 `read_file` 工具调用过程透传到前端

## 1. 技术栈

后端：

- Python 3.12
- FastAPI
- uv
- BeautifulSoup4
- jieba
- rank-bm25
- sentence-transformers
- numpy
- langchain
- langchain-openai

前端：

- Vue 3
- Vite
- TypeScript
- Vant 4

## 2. 目录结构

```text
.
├─ app/
│  ├─ api/
│  │  ├─ routes/
│  │  │  ├─ v1.py
│  │  │  ├─ v2.py
│  │  │  └─ v3.py
│  │  └─ router.py
│  ├─ core/
│  │  └─ config.py
│  ├─ schemas/
│  ├─ services/
│  │  ├─ agent.py
│  │  ├─ documents.py
│  │  ├─ runtime.py
│  │  └─ search.py
│  └─ utils/
├─ data/
│  └─ sop-*.html
├─ frontend/
│  ├─ src/
│  │  ├─ components/
│  │  ├─ lib/
│  │  ├─ router/
│  │  ├─ types/
│  │  └─ views/
│  ├─ package.json
│  └─ .env.example
├─ main.py
├─ pyproject.toml
├─ uv.lock
└─ .env.example
```

### 后端

后端运行在项目根目录，负责：

- 启动时读取 `data/*.html`
- 清洗 HTML，过滤 `<script>` 和 `<style>`
- 构建 Phase 1 的 BM25 索引
- 构建 Phase 2 的 chunk 级向量索引
- 提供 `/v1`、`/v2`、`/v3` 三组接口
- 在 Phase 3 中通过 SSE 流式返回模型输出和工具调用轨迹

### 前端

前端位于 `frontend/`，负责：

- 提供三个阶段的交互页面
- 使用 `fetch` 调用 `/v1/search` 和 `/v2/search`
- 使用 `fetch + ReadableStream` 消费 `/v3/chat` 的 SSE 数据流
- 以消息气泡方式展示 Agent 输出和中间 trace




## 3.核心接口

### 3.1 健康检查

- `GET /health`

### 3.2 Phase 1：关键词检索

- `GET /v1/search?q=...`

返回关键词检索结果：

- `id`
- `title`
- `snippet`
- `score`

### 3.3 Phase 2：语义检索

- `GET /v2/search?q=...`

返回语义检索结果：

- `id`
- `title`
- `snippet`
- `score`


### 3.4 Phase 3：On-Call 助手 Agent

- `POST /v3/chat`

请求体：

```json
{
  "message": "服务器挂了，先查什么？",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

响应为 `text/event-stream`，前端会接收以下事件：

- `status`
- `trace`
- `token`
- `message`
- `error`
- `done`



## 4. 配置说明

### 4.1后端配置

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

根目录 `.env` 主要配置项：

- `APP_CORS_ORIGINS`
  允许本地前端跨域访问，默认允许 `http://localhost:5173` 和 `http://127.0.0.1:5173`
- `DATA_DIR`
  SOP 数据目录，默认是 `data`
- `SEARCH_TOP_K`
  Phase 1 返回条数
- `SEMANTIC_TOP_K`
  Phase 2 返回条数
- `EMBEDDING_MODEL_NAME`
  默认是 `BAAI/bge-small-zh-v1.5`
- `OPENAI_API_KEY`
  默认通过 `${AGENT_API_KEY}` 读取系统环境变量
- `OPENAI_BASE_URL`
  默认是 `https://dashscope.aliyuncs.com/compatible-mode/v1`
- `OPENAI_MODEL`
  Phase 3 所使用的大模型名称
- `OPENAI_TEMPERATURE`
  模型温度

### 4.2 API Key 配置方式

推荐不要把 key 明文写入 `.env`，直接在 Windows 系统环境变量中配置：

```powershell
$env:AGENT_API_KEY="你的Key"
```

如果你已经在系统环境变量中持久化设置过 `AGENT_API_KEY`，重开终端即可生效。

### 4.3 前端配置

复制前端环境变量模板：

```powershell
Copy-Item frontend\\.env.example frontend\\.env
```

`frontend/.env` 目前主要配置：

- `VITE_API_BASE_URL`
  默认指向 `http://127.0.0.1:8000`
---

## 5. 安装依赖
### 5.1 环境要求

- Python `>= 3.12`
- Node.js `>= 20`
- npm
- 已安装 `uv`

如果你的终端里还不能直接使用 `uv`，可以用 `python -m uv` 代替。
### 5.2 后端

如果是首次初始化：

```powershell
uv sync
```

如果你的环境里只能通过 Python 调用 `uv`：

```powershell
python -m uv sync
```

### 5.3 前端

```powershell
cd frontend
npm install
```
---

## 6. 启动方式

### 6.1 启动后端

在项目根目录执行：

```powershell
uv run uvicorn main:app --reload
```

如果当前终端里 `uv` 不在 PATH：

```powershell
python -m uv run uvicorn main:app --reload
```

后端默认地址：

- `http://127.0.0.1:8000`

### 6.2 启动前端

在另一个终端中执行：

```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

前端默认地址：

- `http://127.0.0.1:5173`

### 6.3 生产构建前端

```powershell
cd frontend
npm run build
```
---

## 7. 快速验证

### 7.1 检查后端健康状态

```powershell
curl http://127.0.0.1:8000/health
```

### 7.2 调用 Phase 1

```powershell
curl "http://127.0.0.1:8000/v1/search?q=OOM"
```

### 7.3 调用 Phase 2

```powershell
curl "http://127.0.0.1:8000/v2/search?q=服务器挂了"
```

### 7.4 调用 Phase 3

```powershell
curl -N -X POST "http://127.0.0.1:8000/v3/chat" `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"服务器挂了，先查什么？\",\"history\":[]}"
```
---

## 8. 当前实现说明

### Phase 1

- 启动时读取 `data/*.html`
- 使用 BeautifulSoup 清洗 HTML
- 使用 `jieba` 分词
- 使用 `rank_bm25` 建立索引
- 返回包含高亮片段的搜索结果

### Phase 2

- 启动时加载 embedding 模型
- 将文档按章节和故障场景切成 chunk
- 对 `title + chunk` 建立向量索引
- 查询时按 `best_chunk` 排序
- 用 BM25 和标题相似度做轻量加权

Phase 2 当前采用轻量级、可解释的混合检索：

- 先按 SOP 章节和场景对文档做 chunk 切分
- 查询时对每个文档取 `best_chunk` 作为主语义分
- 使用 BM25 作为轻量补充分数，而不是主排序信号
- 对文档标题做单独向量化，作为领域提示信号
- 对少量口语化宕机查询做窄范围语义扩展，例如“服务器挂了”

### Phase 3

- Agent 使用 LangGraph 的 `create_react_agent`
- 唯一工具是 `read_file(fname: str) -> str`
- 读取的内容是 HTML 去标签后的纯文本
- 通过 `StreamingResponse` 向前端推送 token 和工具事件


---

## 9. 常见问题

### 9.1 `npm` 提示找不到 `package.json`

请确认你是在 `frontend/` 目录执行前端命令，或者使用：

```powershell
npm --prefix frontend run dev -- --host 127.0.0.1
```

### 9.2 Phase 2 首次启动较慢

首次加载 `BAAI/bge-small-zh-v1.5` 可能需要下载模型。若本机没有缓存，请确保可以访问模型源，或者提前准备本地缓存。

### 9.3 `/v3/chat` 返回配置错误

请检查：

- `AGENT_API_KEY` 是否已在系统环境变量中生效
- `OPENAI_BASE_URL` 是否为目标兼容接口
- `OPENAI_MODEL` 是否是该服务端点可用的模型名

### 9.4 CORS 失败

请确认前端地址已包含在 `APP_CORS_ORIGINS` 中。

---

## 10. 开发建议

- 后端调试优先看 `app/services/documents.py` 和 `app/services/search.py`
- Agent 流式问题优先看 `app/services/agent.py` 和 `app/api/routes/v3.py`
- 前端 Phase 页面分别在 `frontend/src/views/`

## 11. 效果预览

### 11.1 Overview

![0_Overview](screenshot\0_Overview.png)

### 11.2 Phase 1:关键词检索

![01_关键词检索_show](screenshot\01_关键词检索_show.png)

### 11.3 Phase 2: 语义检索
![02_语义检索_show](screenshot\02_语义检索_show.png)

### 11.4 Phase 3

![03_On-Call助手_show](screenshot\03_On-Call助手Agent_show.png)
