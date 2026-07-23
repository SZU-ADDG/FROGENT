# FROGENT Plugin Instructions

- 插件核心功能是信息检索、定性科学判断与工具使用；优先保障检索质量、来源可追溯、设计优先级、工具选择、参数验证、结果规范化和失败恢复。
- 当前效果优化覆盖 retrieval、Deep Research、memory、定性科学判断与已接入的药物设计 tool workflows；真实 provider 或实验条件缺失的部分保留为明确 capability gap。
- 每个设计问题先判断为 `qualitative`、`quantitative` 或 `hybrid`。只有目标对齐、经过校准且覆盖当前设计空间的 discriminator 才能主导 quantitative 优化。
- `qualitative` 与 `hybrid` 问题必须先调用模型的世界知识、药化经验、机制推理和领域直觉形成有差异的 ranked hypotheses，再运行工具。每项假设包含具体改动、rationale、预期收益、tradeoff、失败模式与 decisive experiment。
- 工具负责身份核验、硬约束、冲突发现、风险排查和优先级校准。工具不可用或无结论时保留有价值的知识驱动建议并调整 confidence；只有硬冲突或不可违反的约束可以直接淘汰方案。
- 面向用户的设计输出先给推荐与实验顺序，再给证据分层和会改变决策的不确定性。禁止用重复免责声明或缺少完美判别器作为不提出建议的理由。
- 完成一个 coherent research capability block 后，用真实任务或公开数据集评测 retrieval、Deep Research 和 memory 表现；workflow 稳定后再做确有决策价值的消融。
- Eval 记录任务成功、证据与引用正确性、来源覆盖、反证、memory 污染与撤回、工具失败、延迟和成本；负向结果与 `not_measured` 指标同样保留。
- Live provider 验证真实可用性，小型 frozen snapshot 防回归；仓库内 case/oracle 视为 exposed data，hidden held-out 仅在需要无泄漏结论时引入。
- 评测资产保持最小充分。正式 benchmark 可保存必要 identity，日常能力开发禁止扩展 SHA 链、sealed envelope 或多版本审计设施。
- 文献 query hit occurrence 与 canonical record 分层保存，一致重复保留全部 provenance，冲突重复 fail closed。
- Memory eval 分开测量 admission、working-memory retention 与 revocation；useful recall 只统计 evaluator 可追溯的 working memory，误撤有用 evidence 与漏撤 stale evidence 都必须扣分。
- 保持 `frogent_plugin/` 扁平；新增子包前先证明独立生命周期确有必要。
- `.mcp.json` 是 MCP URL 的唯一来源，Python 与 Skills 中禁止重复端点。
- `catalog.py` 维护稳定能力 ID；修改 ID 视为破坏性变更。
- Skills 只描述任务步骤、能力选择和验收结果，避免复制长篇领域背景。
- 核心模块只使用 Python 标准库；科研依赖留在隔离 MCP runtime。
- 项目文档和沟通统一使用 `runtime`，不翻译该术语。
- Harness 是 Agent、Skills、Apps 与 MCP providers 的唯一 job 控制边界。
- 原始文献记录、筛选决定和 qualified evidence 分层保存；未经 EvidenceLedger 准入的内容禁止进入工作 memory。
- 每次文献检索与综合都要记录精确 `as_of` 日期、查询来源、排除理由和 counterevidence。
- 所有用户、会话和作业状态通过 `ExecutionContext` 显式传递。
- 文件通过 `ArtifactRef` 传递，禁止新增共享绝对工作目录。
- 新代码需要标准库单元测试，验证时不得启动数据库、模型或远程服务。

## Deletion Safety
- 删除属于高风险操作。禁止通过临时 inline Python、未经审查的 `rm -rf` 或未经测试的 `shutil.rmtree` 直接清理项目或实验目录；禁止从 manifest 的可选字段直接构造删除路径。
- 第一轮检查为语义范围检查：逐项列出目标、来源、原因、文件数和总大小，确认没有仍需保留或正在运行的结果。
- 第二轮检查为路径安全检查：先验证原始路径字符串非空，再执行 `resolve()`；目标必须严格位于用户指定删除根之下。`.`、`/`、项目根和 `outputs/` 根永久拒绝；完整 run 根仅在用户明确指定并加入显式 allowlist 后允许。
- 第三轮检查为运行与恢复检查：核对 PID、进程组、打开文件、manifest、报告、备份和快照，并生成 dry-run 删除清单复核路径数量、总大小及保留项。
- 三轮检查必须独立通过且范围完全一致。空字段、相对路径、软链接越界、数量异常、范围扩大或命中活跃任务时立即终止。
- 实际删除只能由经过测试的项目脚本按显式 allowlist 逐个处理解析后的绝对路径；禁止 wildcard 扩大范围，禁止在项目根递归遍历未知目标。
- 已完成正式任务删除前，先保存并验证可读的只读精简结果包；删除后立即反向核对非目标资产、活跃进程、manifest 和报告，并记录审计清单。
