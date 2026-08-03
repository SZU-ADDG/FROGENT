# FROGENT

FROGENT 是面向生物医学研究与药物设计的 Agent。它把模型的世界知识、药化经验和
机制推理用于提出有区分度的方案，再用文献、数据库和科学工具校准身份、证据、风险
与优先级。

## 核心能力

- 生物医学检索：Europe PMC、PubMed、OpenAlex、Unpaywall、ClinicalTrials.gov、
  RCSB PDB、PubChem 和 OA 全文；
- 定性科学判断：针对缺少可靠 discriminator 的问题生成并排序可执行假设；
- memory：evidence admission、跨会话检索、checkpoint、resume 和 revocation；
- 分子工具：RDKit identity、PubChem verification、ADMET-AI、Vina、Meeko、
  PDB2PQR/PROPKA、Dimorphite-DL 和 PLIP；
- MCP：标准 MCP providers 与只读 TrioWorkspace control plane；
- Agent harness：统一 context、policy、tool budget、events、evidence gate 和恢复。

## 项目结构

| 路径 | 职责 |
|---|---|
| `agent/` | Agent runtime，按 app、core、research、design、molecular、docking、llm、evaluation 分域 |
| `skills/` | 面向研究任务的可执行 Skills |
| `mcp/` | MCP server 与 TrioWorkspace adapter |
| `app/` | Flask app、模板和静态资源 |
| `evaluation/` | 当前 cases、52-case benchmark 与 scoring |
| `tests/` | runtime、workflow、failure recovery 和架构回归 |
| `docs/` | 当前架构、harness、检索、判断和评测说明 |
| `scripts/` | app、评测、smoke test、全量检查和仓库审计入口 |
| `runtime/` | 本地 venv、工具、数据库、缓存和 generated artifacts；仅 README 进入 Git |

插件 manifest 位于仓库根目录的 `.codex-plugin/`、`.mcp.json` 和 `.app.json`。仓库
导航直接对应 Agent 产品，无复制源码、历史评测代际或重构流水账。

## 运行

复制 `.env.example` 为本地 `.env` 并填写实际需要的配置。OpenAI API key 不是
subagent worker 的运行条件；各外部 provider 只按自身要求配置凭据。

首次安装同时准备 Python runtime 与 Word 导出依赖：

```bash
python3 -m pip install -r requirements.txt
npm ci --ignore-scripts
```

```bash
runtime/app/venv/bin/python scripts/run_app.py
```

应用入口提供登录、会话、附件、Markdown/PDF/Word 报告导出和 SSE contract，Planner、Reader、
Screener、Synthesizer、定性设计、ADMET 与 docking workflow 由 `agent/` 接管。

## 验证

```bash
runtime/app/venv/bin/python scripts/check.py
python3 scripts/audit_repository.py
```

`scripts/check.py` 运行当前完整测试和 active research evaluation。仓库审计验证
Agent-first 顶层结构、tracked runtime 边界、历史材料清理、文件体积和 symlink。

## 版本管理

- 功能和整理工作使用 `codex/*` 分支；
- coherent capability block 独立提交；
- 大范围重构先推送恢复检查点；
- `runtime/` payload 保持本地，源码、配置、测试和必要质量证据进入 Git。

当前架构见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)，Agent harness 见
[docs/HARNESS.md](docs/HARNESS.md)。
