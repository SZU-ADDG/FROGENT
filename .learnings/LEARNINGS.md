# Learnings

## [LRN-20260715-007] correction

**Logged**: 2026-07-15T23:29:00+08:00
**Priority**: critical
**Status**: promoted
**Area**: infra

### Summary
FROGENT Main、Implementation 和 Document 是三个永久维护的长期 Codex 任务，禁止主动归档。

### Details
用户的工作习惯是持续维护三个长期任务，通过实现、验收和文档之间的循环推进项目。任务完成一轮后保持空闲等待下一轮，任何一个都不能被归档。一次性、短期或可丢弃工作应使用 subagent，避免污染长期任务列表。

### Suggested Action
永久保留三个任务并使用固定 thread ID；每轮交接完成后停止写入并保持 idle。仅在用户明确要求时归档长期任务。一次性子工作使用 subagent。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md
- Tags: codex-task, lifecycle, long-running, subagent
- Pattern-Key: workflow.three_permanent_tasks
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md

---

## [LRN-20260715-006] best_practice

**Logged**: 2026-07-15T23:24:00+08:00
**Priority**: high
**Status**: promoted
**Area**: infra

### Summary
Codex 任务采用短启动指令创建，取得 thread ID 后再设置英文名称并发送完整工作包。

### Details
同项目文档任务多次携带长初始指令创建时超时并留下前端失败卡片。用户清理残留后，短英文启动指令在 1.4 秒内成功创建；随后设置英文任务名并单独发送完整交接包均成功。

### Suggested Action
创建任务时保持初始 prompt 简短，只包含角色、目录和等待指令；成功后再设置简短英文名称并发送完整 scope、权限、验收与交接协议。超时后先用 `list_threads` 去重，禁止盲目重复创建。

### Metadata
- Source: error
- Related Files: AGENTS.md
- Tags: codex-task, create-thread, handoff, timeout
- See Also: ERR-20260715-012, FEAT-20260715-003
- Pattern-Key: workflow.short_task_bootstrap
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md

---

## [LRN-20260715-005] correction

**Logged**: 2026-07-15T23:14:00+08:00
**Priority**: critical
**Status**: promoted
**Area**: backend

### Summary
FROGENT 的两项核心功能是信息检索与工具使用。

### Details
用户明确收敛产品中心：系统首先要能准确、完整、可追溯地检索信息，并能可靠选择、调用和组合工具。Literature evidence pipeline、harness、memory、Skills、Apps 与 MCP 都应服务于这两项能力，避免外围模块稀释主链。

### Suggested Action
后续重构和验收围绕 retrieval quality 与 tool-use reliability 组织；每个新增模块都要说明对检索召回、筛选保真、来源追踪、工具选择、参数验证、结果规范化或失败恢复的直接贡献。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, plugins/frogent-drug-design/AGENTS.md
- Tags: product-core, information-retrieval, tool-use, harness
- Pattern-Key: architecture.retrieval_tool_use_core
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-004] correction

**Logged**: 2026-07-15T23:10:00+08:00
**Priority**: medium
**Status**: promoted
**Area**: infra

### Summary
Codex 任务名称默认使用英文，避免在任务侧栏中使用中文命名。

### Details
用户已手动修改新建文档任务的名称，并要求后续尽量不要使用中文任务名。中文仍可用于任务内容、交接包和日常沟通。

### Suggested Action
创建任务成功后使用简短英文名称，例如 `FROGENT Docs`、`FROGENT Implementation` 和 `FROGENT Acceptance`。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md
- Tags: codex-task, naming, english-title
- Pattern-Key: workflow.task_name_english
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md

---

## [LRN-20260715-003] correction

**Logged**: 2026-07-15T20:59:18+08:00
**Priority**: high
**Status**: promoted
**Area**: backend

### Summary
FROGENT 的核心范围必须同时覆盖生物医学文献证据链与显式 harness，并统一保留 `runtime` 英文术语。

### Details
首批插件重构集中在药物设计 MCP 能力、基础契约和领域 Skills，对文献检索策略、检索动线、筛选、清洗、时间截点、证据保真、错误信息隔离和局部 memory 污染缺少系统设计；同时只提供了 capability registry，没有完整说明 FROGENT harness 的执行循环、状态边界、上下文装配、工具策略、证据账本和评估面。中文说明对 runtime 做了术语翻译，也不符合用户的项目术语偏好。

### Suggested Action
把文献调研、证据筛选和证据综合提升为核心 Skills；为检索结果建立分层保存、排除理由、来源追踪、时间截点与 memory 准入规则；新增显式 harness 契约和设计文档；项目内统一使用 `runtime`。

### Metadata
- Source: user_feedback
- Related Files: plugins/frogent-drug-design/README.md, plugins/frogent-drug-design/AGENTS.md, plugins/frogent-drug-design/frogent_plugin
- Tags: literature-research, evidence-provenance, harness, memory-hygiene, terminology
- Pattern-Key: architecture.literature_harness_core
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260714-001] knowledge_gap

**Logged**: 2026-07-14T20:00:00+08:00
**Priority**: high
**Status**: promoted
**Promoted**: AGENTS.md
**Area**: infra

### Summary
记录 FROGENT 的远端主机、项目路径、运行入口和复制授权边界。

### Details
用户指定远端 SSH 主机为 `doomx_3nd`，MCP 位于 `/work/pqh/projects/agent/`，FROGENT 前后端位于 `/work/pqh/projects/Frogent1/`，运行入口为 `app_v4.py`。当前阶段只检查两个目录的大小，获得用户明确同意后才可复制到本地。

### Suggested Action
任何远端同步任务先做只读核查并汇报；复制前等待用户明确授权，复制后验证大小、文件数量和入口文件。

### Metadata
- Source: conversation
- Related Files: AGENTS.md
- Tags: remote-sync, doomx_3nd, frogent, authorization-boundary

---

## [LRN-20260715-002] best_practice

**Logged**: 2026-07-15T13:51:08+08:00
**Priority**: high
**Status**: promoted
**Area**: backend

### Summary
科研型 MCP 插件采用“集成外壳 + runtime gateway + 隔离能力提供者”的双层架构，能够保留轻量分发并容纳异构环境。

### Details
FROGENT 当前九个 MCP 服务同时涉及 Python 3.7 至 3.11、不同 RDKit/OpenBabel/PyTorch 版本、CUDA 设备、模型 checkpoint、外部命令和共享文件目录。将它们合并进同一 Python 进程会放大依赖冲突、资源竞争与多用户数据串扰。Codex 插件外壳适合声明 Apps、MCP 与 Skills；服务端网关负责能力发现、鉴权、类型化事件和工件引用；每个科研能力继续运行在独立环境中。首批实现进一步确认：`.mcp.json` 作为连接地址的单一来源，扁平标准库 runtime 只保留契约、配置、能力目录与注册表，Skills 只引用稳定能力 ID，能够显著降低耦合与嵌套。

### Suggested Action
先建立插件清单和兼容网关，将现有九个 MCP 端点作为旧版提供者注册；Skills 只引用稳定能力 ID。随后逐个把工具迁移到独立作业目录、结构化结果和受控子进程，模型与数据库继续留在服务器资源层。

### Metadata
- Source: architecture_review
- Related Files: sources/frogent/QAM_v4.py, sources/frogent/app_v4.py, sources/mcp/mcp-toolset/DirectMultiStep/pyproject.toml, sources/mcp/mcp-toolset/dockstring/environment.yml, sources/mcp/mcp-toolset/Trio-pep/Judge/GraphPep/environment.yml
- Tags: plugin-architecture, mcp-gateway, runtime-isolation, skills, artifacts
- Pattern-Key: architecture.plugin_gateway_isolation
- Recurrence-Count: 2
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-001] best_practice

**Logged**: 2026-07-15T13:35:56+08:00
**Priority**: high
**Status**: pending
**Area**: tooling

### Summary
第三方源码脱敏需要覆盖个人标识配置和前端 runtime 日志，并同步检查所有历史副本。

### Details
架构盘点发现五份 Python 文件仍含同类 PubMed 个人邮箱配置，三份前端脚本会把注册密码写入浏览器控制台。继续深读时又发现 TargetDiscovery 字典中存在站点会话 Cookie，说明脱敏遗漏具有重复性。先前扫描更关注 API Key、Token、SSH 凭据和私网地址，因此遗漏了个人邮箱、runtime 敏感数据输出及敏感字典键。各历史版本中的字面值也可能不同，批量补丁需要逐文件生成精确上下文。

### Suggested Action
复制后脱敏增加邮箱模式、前端敏感日志规则和敏感字典键 AST 检查；对所有版本副本逐文件处理。配置型个人标识与会话值改用环境变量，密码等认证输入禁止进入日志；完成后执行命中数复扫和静态语法解析。

### Metadata
- Source: architecture_review
- Related Files: sources/frogent/QAM_v1.py, sources/frogent/QAM_v2.py, sources/frogent/QAM_v3.py, sources/frogent/QAM_v4.py, sources/frogent/test_multi_agents_cor2.py, sources/frogent/assets/app_v1.js, sources/frogent/assets/app.js, sources/frogent/templates1/app_v1.js, sources/mcp/mcp-toolset/TargetDiscovery/disease2target.py
- Tags: sanitization, pii, frontend-logging, session-cookie, version-copies

---

## [LRN-20260714-004] best_practice

**Logged**: 2026-07-14T21:48:20+08:00
**Priority**: high
**Status**: promoted
**Promoted**: AGENTS.md
**Area**: infra

### Summary
第三方科研代码迁移采用源码白名单，并在本地进入 Git 前完成硬编码凭据脱敏。

### Details
远端两个目录合计约 69.81 GiB，主要由数据库、模型权重、checkpoints、归档、上传数据和运行结果构成。依据实际文件类型和路径建立 code-only rsync 白名单后，实际复制 1,057 个文件、约 15.42 MiB，同时保留 `app_v4.py`、依赖清单、前端资源和各 MCP 工具源码。复制后先进行无写入干跑，再对 16 个本地文件执行原子脱敏；幂等复扫、独立正则扫描和 AST 扫描的敏感残留均为 0。远端根目录与关键入口的 inode、大小、mtime、ctime 在复制前后保持一致。

### Suggested Action
远端刷新继续使用 `copy-plan/rsync-code-only.rules`、10 MiB 单文件上限和无删除参数；复制后先运行脱敏干跑，残留归零后再原子写入，并通过第二次幂等检查、独立内容扫描和 AST 基线对比完成验收。敏感上下文检查只输出文件名、规则类型和计数，确需查看代码形态时先遮罩所有字符串字面量。在脱敏完成前禁止初始化或提交 Git。

### Metadata
- Source: conversation
- Related Files: AGENTS.md, copy-plan/rsync-code-only.rules, copy-plan/source-inventory.md
- Tags: selective-copy, code-only, secret-sanitization, third-party-source
- See Also: LRN-20260714-002, LRN-20260714-003

---

## [LRN-20260714-002] correction

**Logged**: 2026-07-14T20:33:29+08:00
**Priority**: critical
**Status**: promoted
**Promoted**: AGENTS.md
**Area**: infra

### Summary
远端第三方代码允许通过 `sudo` 只读查看和复制，任何删除及源目录修改均被禁止。

### Details
用户明确说明其具备服务器 `sudo` 权限，可用于读取 MCP 中普通账号无权访问的数据库、权重等目录。两个远端目录并非用户拥有的代码库，因此所有源端操作必须保持只读，禁止删除、移动、改名、覆盖、权限修改及 Git 工作区变更。当前目标是为本地重构提取代码，数据库、模型权重及其他大文件无需复制。

### Suggested Action
使用 `sudo -n` 执行只读盘点；按实际目录与文件类型生成精简复制清单。复制时保持源端只读，将 MCP 与 FROGENT 放入同一本地根目录的独立子目录，并在传输前后生成清单验证。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md
- Tags: sudo, read-only, third-party-code, no-delete, selective-copy
- See Also: LRN-20260714-001

---

## [LRN-20260714-003] correction

**Logged**: 2026-07-14T21:00:37+08:00
**Priority**: critical
**Status**: promoted
**Promoted**: AGENTS.md
**Area**: infra

### Summary
远端源代码严禁移动，本地项目操作必须严格限制在 FROGENT 项目根目录内。

### Details
用户进一步明确：服务器上的两个源代码目录不可移动；本地允许进行复制后的整理与重构，但所有本地项目文件操作只能发生在 `/Users/dongxu/projects/FROGENT/` 内，不得越过该目录边界。

### Suggested Action
远端保持全程只读；任何本地写入前验证规范化目标路径及符号链接边界，只在 FROGENT 根目录内创建独立来源子目录、清单和重构文件。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md
- Tags: path-boundary, local-only, remote-no-move, no-delete
- See Also: LRN-20260714-002

---
