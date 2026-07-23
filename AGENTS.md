# FROGENT Agent Instructions

## 强制工作原则

- 完整理解并落实用户的每项要求，持续推进到结果符合验收标准。
- 禁止使用“否定前项、转折后项”的对立纠正式句型。
- 每个项目都要初始化并持续维护 `AGENTS.md`。
- 每次任务都要使用 `self-improvement` 技能；开始主要工作前检查 `.learnings/`，出现错误、用户纠正、知识缺口或可复用经验时立即记录。
- 始终保持目录结构整洁；临时文件集中放置并在交付前清理。
- 以最终结果为优先，完整验证关键结论，禁止省略必要步骤。

## 目的优先与复杂度预算

- 最终目的始终是提升 FROGENT 作为 Agent 的实际能力，重点包括 retrieval、Deep Research、memory management、定性科学判断与 tool use。
- 文档、Git、测试、评测、实验和工程化设施都是实现目的的手段；每项工作必须说明对 Agent 行为、质量判断或下一步优化决策的直接贡献。
- 采用足以回答当前问题的最小复杂度。辅助工作的规模一旦超过 Agent 能力实现与误差分析本身，应立即暂停、简化并重新对齐目标。
- 小型完整实验优先于持续扩展评测基础设施；评测结果必须能导向明确的 Agent 改动，无法影响决策的审计细节不进入主线。
- 每轮交付至少包含一项可感知的 Agent 行为改善，或一项能明确排除错误方向的有效实验结论。

## Agent 性能主线

- 先搭建可工作的完整 Agent workflow，再对完成的能力块做整体测试；早期架构可以基于领域经验与合理约束推进，无需对每个微小改动单独消融。
- 先判断问题属于 `qualitative`、`quantitative` 或 `hybrid`。目标对齐、经过校准且覆盖当前设计空间的可靠 discriminator 可以驱动算法、模型、进化或强化学习优化；缺少这种 discriminator 或仍有关键科学选择时，由 Agent 负责生成并排序假设。
- FROGENT 必须主动运用模型已有的世界知识、文献记忆、药化经验、机制推理与领域直觉生成设计假设。对于湿实验前无法充分验证的修饰，仍要给出有区分度、按优先级排序且说明核心依据的可执行方案。
- 工具用于校准假设、发现冲突、排除明显风险和调整优先级。工具缺失或预测能力有限时，Agent 继续提供专家级判断，并清楚区分知识驱动建议、计算信号、文献 evidence 与实验事实。
- 面向药化学家的输出先给推荐、排序、预期收益与 tradeoff，再给最小必要的不确定性和验证实验。避免重复免责声明、防御性拒答，以及因缺少完美验证而放弃有价值的判断。
- 不确定性必须改变置信度、排序或下一实验，不能消除推荐。高优先级探索性方案应同时给出 rationale、预期失败模式和最有信息量的 falsification experiment。
- 检索同时利用数据库路由、OA 全文、作者与课题组网络、引用关系和模型已有知识；模型记忆产生待验证候选，外部来源负责核实，禁止把模型记忆直接当作证据。
- 大批文献优先交给隔离的 reader subagents 并行处理，Main 只接收结构化 evidence 与失败信息，控制上下文污染。
- Skills 要把数据库、RDKit、结构分析、对接、PLIP 及其他科研工具内化为可执行 workflow；重要判断尽量用工具或数据验证，并记录适用范围与失败条件。
- 工作 memory 通过 evidence 准入、文档记录、压缩摘要、用户偏好和可撤回更新持续演化，避免上下文压缩造成关键决策丢失。
- 完成一个 coherent capability block 后，优先在已有公开数据集或真实任务集上并行测试整体性能；先确认 Agent 能解决见过或可验证的问题，再扩展到未知分子与完整药物设计任务。
- 搜索与研究 runtime 默认不设置固定墙钟 timeout；停止条件来自证据充分性、查询与工具预算、重复结果收敛、明确工具失败、用户指令或可选部署上限。
- 并行 subagents 自身具备模型能力，无需 OpenAI API key；批量任务优先直接使用 subagents 作为 Agent workers，外部数据库凭据仅按各 provider 的实际要求配置。

## 术语与核心架构

- 项目文档和沟通统一使用 `runtime`，不翻译该术语。
- FROGENT 的三项产品核心功能是信息检索、定性科学判断与工具使用；所有模块必须直接服务于 retrieval quality、decision quality 或 tool-use reliability。
- FROGENT 同时优化 retrieval、Deep Research、memory、定性科学判断和 tool use。已经接入的药物设计能力进入可执行 workflow；真实 provider、模型或实验条件尚未接入的部分保持 deferred，并继续给出知识驱动的优先级建议。
- FROGENT 的核心同时包含生物医学文献 evidence pipeline 与显式 agent harness。
- 文献原始记录、筛选账本、qualified evidence 和 synthesis 分层保存；未经筛选的结果禁止进入工作 memory。
- Harness 统一负责 context 装配、策略、状态、工具预算、evidence 准入、事件、停止和恢复。

## 效果评测循环

- Eval 的唯一用途是判断 Agent 是否更会检索、研究、管理 memory、进行定性科学判断或使用工具，并据此决定下一步改动；静态检查只证明代码边界，不能证明能力提升。
- 先完成一个 coherent capability block，再运行相同真实任务或公开数据集做前后比较和逐案例误差分析。Workflow 稳定且确实需要归因时才做 Skill 消融。
- 首要验收信号包括任务成功率、有效证据召回、引用与来源正确性、反证保留、memory 污染与撤回、工具失败恢复、延迟和成本；没有可靠 oracle 的指标明确记为 `not_measured`。
- Live provider 用于验证当前真实可用性，小型 frozen snapshot 用于防回归。不得修改 gold、阈值或评测口径来制造提升。
- 每轮保留足以复盘的最小资产：任务集、运行入口、原始输出、逐案例结果和失败分析。只有正式冻结的 benchmark 或外部复现需要时才记录 digest；禁止为日常小改动扩展 SHA 链、sealed envelope 或多版本审计设施。
- 仓库内可见 case 视为 exposed data；真正需要无泄漏结论时再由独立 score owner 管理 hidden held-out。
- 负向结果、超时、工具错误和失败案例都要保留，因为它们直接决定 Agent 的修复方向。
- 文献 query hit 与 canonical record 分层保存；一致重复保留 query-to-record links，冲突记录隔离并报告。
- Memory 验收区分 evidence admission、working-memory retention 与 revocation，避免 raw result、错误引用或 stale evidence 污染回答。

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

## Deletion Safety
- 删除属于高风险操作。禁止通过临时 inline Python、未经审查的 `rm -rf` 或未经测试的 `shutil.rmtree` 直接清理项目或实验目录；禁止从 manifest 的可选字段直接构造删除路径。
- 第一轮检查为语义范围检查：逐项列出目标、来源、原因、文件数和总大小，确认没有仍需保留或正在运行的结果。
- 第二轮检查为路径安全检查：先验证原始路径字符串非空，再执行 `resolve()`；目标必须严格位于用户指定删除根之下。`.`、`/`、项目根和 `outputs/` 根永久拒绝；完整 run 根仅在用户明确指定并加入显式 allowlist 后允许。
- 第三轮检查为运行与恢复检查：核对 PID、进程组、打开文件、manifest、报告、备份和快照，并生成 dry-run 删除清单复核路径数量、总大小及保留项。
- 三轮检查必须独立通过且范围完全一致。空字段、相对路径、软链接越界、数量异常、范围扩大或命中活跃任务时立即终止。
- 实际删除只能由经过测试的项目脚本按显式 allowlist 逐个处理解析后的绝对路径；禁止 wildcard 扩大范围，禁止在项目根递归遍历未知目标。
- 已完成正式任务删除前，先保存并验证可读的只读精简结果包；删除后立即反向核对非目标资产、活跃进程、manifest 和报告，并记录审计清单。
