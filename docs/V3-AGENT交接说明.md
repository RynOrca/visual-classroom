# V3 Virtual Classroom — Agent Handoff / 交接说明

> 给下一个 AI Agent 的快速上手文档。开始工作前请先阅读本文件、根目录 `AGENTS.md`、`open_notebook/AGENTS.md`、`frontend/AGENTS.md` 以及 `V3-虚拟课堂重构方案.md`。

---

## 1. 项目位置

- 本地目录：`D:/Code/Working-on-it/v3-visualclassroom`
- Git 远程：`https://github.com/RynOrca/visual-classroom.git`
- 上游：`https://github.com/lfnovo/open-notebook.git`
- 当前分支：`main`

## 2. 这是什么项目

这是一个基于 **Open Notebook** Fork 的“虚拟课堂”：

- 上传课件（PDF/PPT/MD/TXT）
- AI 自动抽取章节、知识点
- 支持刷题、错题本
- 支持生成“章节演进知识地图”
- 预留本地 UnlimitedOCR 接入

## 3. 技术栈

- 前端：Next.js 15 + React 19 + TypeScript + Tailwind CSS + shadcn/ui
- 后端：Python FastAPI + LangGraph
- 数据库：SurrealDB
- 任务队列：surreal-commands worker
- LLM：DeepSeek 已配置（API Key 在 `.env`，不要提交）

## 4. 如何启动本地服务

```bash
cd /d/Code/Working-on-it/v3-visualclassroom
./scripts/start-local.sh
```

启动后：

- 前端：http://localhost:3000
- API：http://localhost:5055/docs
- SurrealDB：http://127.0.0.1:8000

停止：

```bash
./scripts/stop-local.sh
```

> 如果端口冲突，先执行 `stop-local.sh`，再用 PowerShell 杀掉残留的 v3 进程，再 `start-local.sh`。

## 5. 已实现功能

### 后端

- 数据库 Migration 24：`chapter`、`knowledge_point`、`mistake_book`、`quiz_session`、`conversation_note`
- 数据库 Migration 25：`knowledge_map`
- 虚拟课堂核心 API：
  - `api/routers/virtual_classroom.py`
  - `api/routers/virtual_classroom_practice.py`
  - `api/routers/virtual_classroom_knowledge.py`
  - `api/routers/virtual_classroom_ocr.py`
- AI 能力：
  - 自动抽取章节
  - 自动抽取知识点
  - 自动生成题目
  - 自动生成知识地图
  - 错题自动入库

### 前端

- 页面：`/virtual-classroom`
  - 选科目/课件
  - AI 抽章节/知识点
  - 刷题、提交批改
  - 错题本
  - 知识地图展示
- 侧边栏已加入入口

## 6. 关键文件

| 用途 | 路径 |
|---|---|
| V3 方案 | `V3-虚拟课堂重构方案.md` |
| 虚拟课堂后端模块 | `open_notebook/virtual_classroom/` |
| 虚拟课堂 API | `api/routers/virtual_classroom*.py` |
| 对话整理 API | `api/routers/virtual_classroom_conversation.py` |
| 前端页面 | `frontend/src/app/(dashboard)/virtual-classroom/page.tsx` |
| 前端 API | `frontend/src/lib/api/virtual-classroom.ts` |
| 前端类型 | `frontend/src/lib/types/virtual-classroom.ts` |
| 知识地图可视化组件 | `frontend/src/components/virtual-classroom/KnowledgeMapFlow.tsx` |
| 本地 OCR 脚本 | `scripts/unlimited_ocr_local.py` |
| 本地 OCR 服务启动脚本 | `scripts/start-unlimited-ocr-server.sh` |

## 7. 下一步建议（按优先级）

1. **前端产品化**
   - 把当前功能页改成“两栏课堂 + 弹出式问答”
   - 应用 Gemini 新设计稿
2. ~~**UnlimitedOCR 真实跑通**~~（已完成）
   - 本地 llama.cpp 服务已配置（`D:\llama.cpp`，端口 `10000`）
   - `UNLIMITED_OCR_COMMAND` 已在 `.env` 设置
   - `POST /api/virtual-classroom/ocr` 可用（已通过接口测试）
   - 扫描版 PDF 会在 source 处理时自动 OCR 并写回 `Source.full_text`
   - 可执行 `scripts/start-unlimited-ocr-server.sh` 幂等启动本地 OCR 服务
3. **知识地图可视化**（部分完成）
   - 已升级为 React Flow 节点图：章节/stage 节点 + `bridgeToNext` 连线 + 可缩放/拖拽/小地图
   - 待做：L2 框架级展开、L3 错题/提问热力节点、点击节点跳回课件/对话
4. **对话整理 Agent**（已完成基础版）
   - `POST /api/virtual-classroom/conversation-notes/organize`：读取会话 Q&A，LLM 整理为知识卡片并写入 `conversation_note`
   - `GET /api/virtual-classroom/conversation-notes`：列出知识卡片
   - 前端“对话整理”区域：选择课件会话 → 整理 → 查看卡片
   - 待做：自动在问答结束后触发整理、更精确的知识点关联
5. **复习路线**
   - 基于知识地图生成“俯瞰 → 下钻”复习流程

## 8. 给其他 Agent 的硬性要求

- 先读 `AGENTS.md` 和 `docs/7-DEVELOPMENT/change-playbooks.md`
- 新增数据库表必须同时：
  - 新建 `open_notebook/database/migrations/N.surrealql`
  - 新建 `N_down.surrealql`
  - 在 `open_notebook/database/async_migrate.py` 中注册
- 后端 LLM 调用统一走 `provision_langchain_model()`
- 前端新增 UI 文案必须走 i18n（当前为了快速原型部分页面硬编码中文，后续要补）
- 不要把 API Key / `.env` 提交进 Git
- 提交前先 `git pull` / `git push` 保持同步

## 9. 可直接复制给下一个 Agent 的 Prompt

```text
请继续开发 D:/Code/Working-on-it/v3-visualclassroom 的“虚拟课堂”项目。

这是一个基于 Open Notebook 的 Fork。开始前请先阅读：
- AGENTS.md
- open_notebook/AGENTS.md
- frontend/AGENTS.md
- V3-虚拟课堂重构方案.md
- docs/V3-AGENT交接说明.md

当前已完成：
- 错题本/刷题 API
- 虚拟课堂前端页面
- 知识地图生成与展示
- UnlimitedOCR 适配层和本地脚本

接下来请优先做：<在这里写具体任务，例如“把前端改成两栏课堂+弹出问答”>

技术约束：
- 后端 FastAPI + LangGraph + SurrealDB
- 前端 Next.js + React + Tailwind + shadcn/ui
- 所有 LLM 调用走 provision_langchain_model()
- 新增 migration 要注册到 async_migrate.py
- 不要提交 .env / API Key
- 完成后更新 CHANGELOG 并 git push
```
