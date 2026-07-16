# FROGENT Agent Instructions

## 强制工作原则

- 完整理解并落实用户的每项要求，持续推进到结果符合验收标准。
- 禁止使用“否定前项、转折后项”的对立纠正式句型。
- 每个项目都要初始化并持续维护 `AGENTS.md`。
- 每次任务都要使用 `self-improvement` 技能；开始主要工作前检查 `.learnings/`，出现错误、用户纠正、知识缺口或可复用经验时立即记录。
- 始终保持目录结构整洁；临时文件集中放置并在交付前清理。
- 以最终结果为优先，完整验证关键结论，禁止省略必要步骤。

## 术语与核心架构

- 项目文档和沟通统一使用 `runtime`，不翻译该术语。
- FROGENT 的两项产品核心功能是信息检索与工具使用；所有模块必须直接服务于 retrieval quality 或 tool-use reliability。
- 当前效果优化只聚焦 retrieval、Deep Research 和 memory management；依赖未接入药物设计模型的任务与完整制药 workflow 保持 deferred。
- FROGENT 的核心同时包含生物医学文献 evidence pipeline 与显式 agent harness。
- 文献原始记录、筛选账本、qualified evidence 和 synthesis 分层保存；未经筛选的结果禁止进入工作 memory。
- Harness 统一负责 context 装配、策略、状态、工具预算、evidence 准入、事件、停止和恢复。

## 效果评测循环

- 每个 research Skill 和整体 workflow 都必须绑定可运行 eval；仅有 contracts、fixtures 或静态检查不能宣称效果提升。
- 每轮优化固定执行 `baseline -> 单一假设改动 -> 相同 locked eval 复测 -> 逐案例误差分析 -> regression gate`。
- Eval 资产至少包含 versioned manifest、development/frozen-core/challenge cases、temporal cutoff、runner、结果文件、失败案例和 replay identity。
- 仓库内可见的 case 与 oracle 一律视为 exposed data；hidden held-out 必须由独立 score owner 在 candidate freeze 后保管，并对 candidate worker 隐藏 reference。
- Per-Skill 评测使用 no-skill、single-skill、sequential 和 full profiles；无法独立识别贡献的 Skill 必须显式标记 identifiability 限制。
- 严格区分 contract/control-plane verification 与 retrieval/Deep Research/memory 的效果评测。
- 每轮分别记录 execution completion、effect outcome 和 promotion eligibility；负向实验、超时及失败案例同样保存，缺少独立 oracle 的指标标记为 `not_measured`。
- 默认 regression 仅使用 frozen provider/corpus snapshot；live provider 进入独立 canary，禁止污染可重放 baseline。
- Retrieval eval 使用 grouped alias semantics；source-route coverage 由实际 query routes 计算并与声明双向核对。Locked pack 逐字节绑定 Skill、reference、worker input 与 evaluator implementation。
- Candidate-visible worker contract 必须公开合法输出所需的精确字段、类型和 enum tokens；evaluator-owned oracle、record IDs、match rules 与 scoring reference 保持隐藏。
- Missing、invalid、failed 与负向运行都要生成 deterministic rejected result，保存受控 input digest、stable taxonomy 和 worker completion；完整 effect result 必须由相同输入资产 exact replay 验证。
- 文献 query hit occurrence 与 canonical record 分层保存；一致重复保留全部 query-to-record links，冲突重复 fail closed。
- Memory 效果指标必须区分 evidence admission 与 working-memory retention；useful recall 以可追溯 working memory 为准，revocation 同时惩罚漏撤与误撤，跨 case evidence ID 必须具备可判定的隔离命名空间。
- 禁止通过修改 held-out 数据、gold、阈值或评测口径制造提升。

## 当前项目与远端环境

- 本地项目目录：`/Users/dongxu/projects/FROGENT/`
- 远端 SSH 主机：`doomx_3nd`
- 远端 MCP 目录：`/work/pqh/projects/agent/`
- 远端 FROGENT 前后端目录：`/work/pqh/projects/Frogent1/`
- FROGENT 运行入口：`/work/pqh/projects/Frogent1/app_v4.py`
- 两个远端目录均视为第三方源代码，用户不拥有该代码库；远端只允许查看和复制。
- 用户授权在只读查看和复制时使用 `sudo`。

## 远端安全边界

- 严禁删除、移动、改名或覆盖任何远端文件与目录。
- 严禁写入远端源目录，严禁修改权限、所有者、时间戳或 Git 工作区状态。
- 严禁执行会改变远端代码库的 `git clean`、`git reset`、`git checkout`、安装依赖、格式化及自动修复命令。
- 盘点阶段仅可使用 `stat`、`find`、`du`、`ls`、`file` 和 Git 只读查询等操作。
- `sudo` 仅用于跨越读取权限限制；所有命令必须保持只读。
- 精简复制时保留代码、配置、文档、前端资源与依赖清单，数据库、模型权重、缓存、日志、构建产物和其他大文件依据盘点结果排除。
- 两套来源统一放入本地项目根目录下的独立子目录，保留来源边界，禁止直接混合重名文件。

## 本地操作边界

- 本地项目操作范围唯一为 `/Users/dongxu/projects/FROGENT/`。
- 仅可在该目录内部创建、复制、修改、移动、整理、重构或删除项目文件。
- 严禁对该目录之外的本地文件或目录进行创建、复制、修改、移动、删除、权限变更及版本控制操作。
- 所有本地目标路径必须先验证其规范化绝对路径仍位于 `/Users/dongxu/projects/FROGENT/` 内，并防止符号链接越界。
- 从第三方源复制的代码必须先在本地执行敏感信息扫描和脱敏，再初始化或提交 Git；严禁在日志、报告或对话中展示真实凭据值。
- 精简复制统一使用 `copy-plan/rsync-code-only.rules` 的源码白名单，并维持单文件 10 MiB 上限，除非用户明确批准调整。

## 远端复制工作流

1. 先以只读方式核查远端目录的实际占用、路径状态和必要的文件概况。
2. 向用户汇报核查结果。
3. 仅在用户明确同意后，把远端内容复制到本地。
4. 复制前检查本地目标路径和冲突风险；复制完成后核对大小、文件数量及关键入口文件。
5. 在本地项目目录内完成潜在硬编码凭据脱敏，再开始版本控制与重构。

## 自我改进记录

- `.learnings/LEARNINGS.md`：记录用户纠正、知识缺口和最佳实践。
- `.learnings/ERRORS.md`：记录命令、远端连接或外部工具失败。
- `.learnings/FEATURE_REQUESTS.md`：记录当前能力无法直接满足的需求。

## Codex 任务命名

- Codex 任务名称默认使用简短英文；中文可用于任务正文、交接包和项目沟通。
- 新任务先用简短启动 prompt 创建；取得 thread ID 后再设置英文名称并发送完整工作包。
- 创建超时后先用 `list_threads` 核对是否已生成实体任务，确认缺失后才重试。

## Codex 任务生命周期

- `FROGENT Main`、`FROGENT Implementation` 和 `FROGENT Document` 是三个永久维护的长期任务，任何 agent 都禁止主动归档。
- 三个长期任务完成一轮交接后停止写入并保持 idle，等待下一轮循环。
- 只有用户明确要求时才能归档长期任务。
- 一次性、短期或可丢弃工作使用 subagent；禁止为这类工作创建新的长期 Codex 任务。
