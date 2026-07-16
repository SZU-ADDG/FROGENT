# Learnings

## [LRN-20260716-003] best_practice

**Logged**: 2026-07-16T15:15:14+08:00
**Priority**: high
**Status**: promoted
**Area**: tests

### Summary
Effect eval 必须向 candidate 公开合法输出所需的精确 schema tokens，同时隔离 evaluator-owned reference。

### Details
当 evaluator 对 source route、status 或 wave 使用精确枚举，而 common worker contract 只给自然语言名称时，fresh worker 会因为猜错接口 token 被当成能力失败。这种误差会污染 baseline 与 Skill arm，也无法解释真实 retrieval planning 效果。公开接口 schema 不会泄漏 oracle；record IDs、match groups、relevance labels 和 scoring requirements 仍需隐藏。

### Suggested Action
在 candidate freeze 前把字段、容器类型、必填约束和允许 enum IDs 写入共同、逐字节绑定的 worker contract，并用 mutation test固定。Worker contract 对所有 arms相同；evaluator-owned corpus、oracle 与 match rules不进入 candidate prompt。

### Metadata
- Source: code_review
- Related Files: plugins/frogent-drug-design/evals/plan-forward-v1.worker-common.txt, plugins/frogent-drug-design/tests/test_plan_eval.py
- Tags: evaluation, candidate-contract, schema, isolation, fairness
- Pattern-Key: eval.expose_schema_hide_oracle
- Recurrence-Count: 1
- First-Seen: 2026-07-16
- Last-Seen: 2026-07-16
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260716-002] best_practice

**Logged**: 2026-07-16T14:45:00+08:00
**Priority**: high
**Status**: promoted
**Area**: tests

### Summary
Locked effect eval 必须绑定 evaluator implementation、用实际行为验证声明，并为失败运行保存正式负向结果。

### Details
仅绑定 case、oracle、corpus 与 worker prompt，仍允许 matcher、schema 或 scoring code 在 candidate freeze 后漂移。Python 子模块加载还会先执行包 `__init__` 及 eager imports；漏绑这条 import-time 闭包会留下 lock 后漂移路径。Revision logical key 与实际 path 未精确绑定时，多个 key 也可能重定向到同一文件。仅按声明的 source map 计分会让没有对应 query 的 route 获得满分。CLI 在 missing、invalid 或 failed output 时直接抛错，则负向实验无法进入长期审计资产；结构与身份合法的预算/route policy 违规若在 schema 层丢弃，同样会损失 raw plan 和逐 run failure evidence。Temporal gate 也要覆盖进入 raw audit 的所有带日期元数据，避免 cutoff 后信息通过辅助字段泄漏。

### Suggested Action
Manifest 或 bundle identity 逐字节绑定 evaluator modules、包初始化与递归 eager-import 闭包，并固定 logical asset/revision key 到唯一 relative path。Source-route coverage 由 query routes 计算并与 source map 双向核对；published、online 与 event dates 都进入角色明确的 as-of policy。Schema 只拒绝畸形、身份错误或泄漏输入；结构合法的 candidate policy 违规进入 replay findings 与 hard gate。Runner 对 complete、missing、invalid、failed 和 policy-violating inputs 都生成 deterministic result，保存受控 input digest、stable taxonomy、raw plan 与 worker completion summary，同时拒绝敏感 evaluator payload。

### Metadata
- Source: code_review
- Related Files: plugins/frogent-drug-design/frogent_plugin/plan_eval_assets.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_replay.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_runner.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_v2_assets.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_v2_schema.py
- Tags: evaluation, preregistration, evaluator-identity, negative-results, temporal-cutoff
- Pattern-Key: eval.bind_evaluator_and_preserve_negative_results
- Recurrence-Count: 2
- First-Seen: 2026-07-16
- Last-Seen: 2026-07-16
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260716-001] best_practice

**Logged**: 2026-07-16T14:17:24+08:00
**Priority**: high
**Status**: promoted
**Area**: tests

### Summary
检索规划效果评测必须使用 grouped alias semantics，并绑定实际 Skill、reference 与 worker input identity。

### Details
自然语言 query、concept block 和 stop rule 无法用 exact string equality 可靠评分；单层 `match_all`/`match_any` 也无法表达“每个概念组任选一个 alias、所有概念组均满足”。这会系统性漏记合理同义表达，或强迫 candidate 猜 evaluator 的固定措辞。只在 manifest 中写 Skill 路径也无法证明 paired arm 的唯一变量，因为 Skill/reference 内容可能在运行前后变化，candidate 还可自报 profile。

### Suggested Action
Frozen replay 使用统一 normalization 和 `all groups / any alias per group` 语义；concept、stop-rule 和 record matcher 都保存 stable requirement IDs 与 matched IDs。Manifest 逐字节绑定 Skill、reference、共同 prompt/schema 和 baseline instruction；每个 forward output 校验 Main 生成的 worker-input receipt。Corpus loader 同时拒绝重复 canonical IDs、跨 case oracle 引用与不精确补造日期。

### Metadata
- Source: code_review
- Related Files: plugins/frogent-drug-design/frogent_plugin/plan_eval_schema.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_replay.py, plugins/frogent-drug-design/frogent_plugin/plan_eval_runner.py
- Tags: evaluation, retrieval-planning, aliases, preregistration, worker-identity
- Pattern-Key: eval.grouped_alias_identity
- Recurrence-Count: 1
- First-Seen: 2026-07-16
- Last-Seen: 2026-07-16
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-011] best_practice

**Logged**: 2026-07-15T23:48:30+08:00
**Priority**: high
**Status**: promoted
**Area**: tests

### Summary
Memory 效果评测必须区分 evidence admission、working-memory retention 与 revocation precision。

### Details
只用 admitted evidence 计算 useful recall 会让 working memory 为空的 candidate 仍取得满分。只计算 stale evidence 的撤回召回会放过对有用 evidence 的过度撤回。Cross-case leakage 若缺少全局唯一、可判定的 case evidence namespace，也会把合法复用与污染混在一起。三种偏差都会把优化方向推向丢失有用信息的 memory 策略。

### Suggested Action
Useful evidence recall 基于 `memory ∩ admitted ∩ qualified ∩ evaluator-owned traceable`；revocation accuracy 同时计入 stale evidence 的正确撤回和 admissible evidence 的未误撤；benchmark case 的 evidence IDs 保持跨 case 唯一。为 memory omission、over-revocation 与 duplicate cross-case evidence ID 建立 mutation tests。

### Metadata
- Source: code_review
- Related Files: plugins/frogent-drug-design/frogent_plugin/eval_metrics.py, plugins/frogent-drug-design/frogent_plugin/eval_manifest.py
- Tags: memory, evaluation, revocation, retention, leakage
- Pattern-Key: evaluation.separate_admission_retention_revocation
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-010] best_practice

**Logged**: 2026-07-15T23:22:13+08:00
**Priority**: high
**Status**: promoted
**Area**: tests

### Summary
效果评测必须把 execution completion、effect outcome 和 promotion eligibility 分开，并保存负向实验。

### Details
对 Rosin、Pio、Taci 与 Apollo 的只读审计表明，可信的 Agent 改进循环需要冻结 baseline、candidate、panel、scoring policy、provider snapshot 和 memory snapshot，每轮仅开放一个可归因变量。工程执行完成不代表效果改善，效果失败也仍然是有价值的实验结果。缺少独立 oracle 的指标应保持 `not_measured`，baseline 与 candidate 覆盖不一致时应保持 `not_comparable`。负向 delta、超时和失败 case 需要进入正式结果资产，禁止被总分或低层收益抵消。仓库内可见的 case 与 oracle 都属于 exposed data，hidden held-out 需要由独立 score owner 在 candidate freeze 后保管和执行。

### Suggested Action
FROGENT eval kernel 为每轮生成 content-addressed preregistration、scorecards、delta、failure clusters 和 supervised decision；分别记录 completion、effect 与 promotion 状态。默认 regression 使用 frozen snapshot，live provider 只进入独立 canary。负向回归、未声明变化、时间泄漏和 gold 泄漏直接阻断 promotion。

### Metadata
- Source: architecture_review
- Related Files: AGENTS.md, plugins/frogent-drug-design/AGENTS.md
- Tags: evaluation, ablation, promotion-gate, negative-result, replay
- Pattern-Key: evaluation.separate_completion_effect_promotion
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-009] best_practice

**Logged**: 2026-07-15T23:22:13+08:00
**Priority**: high
**Status**: promoted
**Area**: backend

### Summary
文献 canonical record 与 query hit occurrence 必须分层保存，重复召回不能中断多查询检索。

### Details
多条 query 或多个 source 经常召回同一 PMID、DOI 或 registry record。只按 record ID 直接写唯一 ledger 会把正常重复命中当成错误，同时丢失 query-to-record provenance。检索层应保留每次 hit 的 call、capability、source、query 和 record link，并在 canonical record 层去重。一致重复继续执行，内容冲突的同 ID 记录 fail closed 且保留前序审计材料。

### Suggested Action
使用 typed retrieval hit links 记录 occurrence；结果分别报告 raw hit count 与 unique record count。固定一致重复、冲突重复、跨 source study-family 和空执行计划 case，并在 retrieval effect eval 中单独计算 duplicate rate、dedup correctness 与 provenance completeness。

### Metadata
- Source: code_review
- Related Files: plugins/frogent-drug-design/frogent_plugin/retrieval.py, plugins/frogent-drug-design/skills/plan-literature-search/references/query-strategy.md
- Tags: retrieval, provenance, deduplication, evidence-ledger
- Pattern-Key: retrieval.separate_hits_from_canonical_records
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: plugins/frogent-drug-design/AGENTS.md

---

## [LRN-20260715-008] correction

**Logged**: 2026-07-15T23:41:00+08:00
**Priority**: critical
**Status**: promoted
**Area**: backend

### Summary
FROGENT 当前优化与效果评测聚焦 retrieval、Deep Research 和 memory management，药物设计模型与完整制药 workflow 暂缓。

### Details
用户要求像 Rosin、Pio、Taci、Apollo 一样建立持续验证循环，逐个评测 Skills，并评测整体 workflow 的真实效果。当前最重要的三个效果面是检索、Deep Research 和记忆管理。依赖尚未接入模型的药物设计任务不进入当前优化主线；runtime/harness 与可独立优化的研究 Skills 优先。

### Suggested Action
建立 versioned manifest、locked cases、runner、baseline/ablation profiles、结果资产和回归门禁；严格区分 contract/control-plane 通过与真实效果提升。每轮先跑 baseline，再做单一假设改动，在相同 locked eval 上复测并保留失败案例。

### Metadata
- Source: user_feedback
- Related Files: AGENTS.md, plugins/frogent-drug-design/AGENTS.md
- Tags: retrieval, deep-research, memory, eval-loop, skill-ablation
- Pattern-Key: evaluation.research_memory_effect_loop
- Recurrence-Count: 1
- First-Seen: 2026-07-15
- Last-Seen: 2026-07-15
- Promoted: AGENTS.md, plugins/frogent-drug-design/AGENTS.md

---

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
## [LRN-20260716-004] best_practice

**Logged**: 2026-07-16T23:59:45+08:00
**Priority**: high
**Status**: pending
**Area**: eval

### Summary
Versioned eval 的 sealed worker receipt 必须把 `eval_id` 纳入 digest payload，防止跨版本相同 arm 输入发生 identity collision。

### Details
PLAN forward v4 初版沿用 v3 receipt payload；current arm 的 candidate-visible bytes 与 v3 对应输入相同，导致 v4 `skill_a` receipt 与 v3 digest 重合。即使两轮使用不同 manifest 和 evaluator revision，worker receipt 本身也无法表达所属 eval 版本。把 `eval_id` 绑定进 v4 receipt 后，每个 sealed input 同时具备 case、arm、replicate、assets 与 eval-version identity。

### Suggested Action
所有新 eval version 的 receipt constructor 都显式纳入 `eval_id`，并增加跨版本 digest 不相等测试；manifest、envelope SHA 与 evaluator revision 按依赖链重算。

### Metadata
- Source: simplify-and-harden
- Related Files: plugins/frogent-drug-design/frogent_plugin/plan_eval_v4_assets.py, plugins/frogent-drug-design/tests/test_plan_eval_v4.py
- Tags: eval-identity, worker-receipt, cross-version-isolation
- Pattern-Key: harden.eval_receipt_version_binding
- Recurrence-Count: 1
- First-Seen: 2026-07-16
- Last-Seen: 2026-07-16

---
