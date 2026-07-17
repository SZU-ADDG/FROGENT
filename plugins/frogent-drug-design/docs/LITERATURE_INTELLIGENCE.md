# FROGENT Literature Intelligence Workflow

## 用户能力

FROGENT 当前具备一个可组合运行的 literature intelligence 核心。

它从用户问题和待核验的模型知识候选出发，经过真实数据库、OA、bounded reader workers、筛选、working memory 与 synthesis，最后返回带来源边界、coverage gaps 和 checkpoint 的结果。

当前既可从 Python workflow 调用，也可通过 plugin-side launcher 将只读 `sources/frogent/app_v4.py` 接到 FROGENT Agent。默认 Agent roles 使用 ChatGPT bundled Codex 的 `gpt-5.6-sol`、medium reasoning，无需 OpenAI API key。

## 输入契约

- 明确问题、使用场景和精确 `as_of`。
- 用 `SearchPlan` 固定来源、纳入排除条件与 stop rules。
- 用 `ResearchQuery` 提供显式 source-query pairs。
- 模型知识只生成 `KnowledgeCandidate` 检索种子。
- PMID、DOI、标题、作者、课题组与事实在外部核验前保持 unverified。

## 实际用户流程

### 1. 问题与模型知识候选

Agent 先理解用户问题，再把模型记忆中的论文、作者、标识符和事实转成待核验候选。

候选需要携带 verification query。核验失败的候选进入 coverage gap，停留在 evidence 与 working memory 之外。

### 2. Europe PMC 与 PubMed

- Europe PMC 用于宽检索、PMCID 发现、作者 metadata 和引用/参考文献入口。
- PubMed ESearch/EFetch 用于独立标识符、题名、摘要和出版 metadata 核验。
- 每次检索保留 source、query、`as_of`、原始记录和 provenance。
- 单个 provider 失败会成为 coverage gap，后续来源和 counterevidence query 继续运行。

### 3. OA 与 abstract fallback

Europe PMC 记录含 PMCID 时，workflow 可获取 OA `fullTextXML` 并生成 `ArtifactRef`。

OA 超时、解析失败或全文不可用时，Agent 保留 abstract-only 路径，并明确记录 coverage gap。

全文保留在 artifact 边界；Main 只接收结构化 reader 输出和失败信息。

### 4. Bounded reader workers

- Canonical records 按 paper/study family 去重。
- 每个 family 形成独立 `ReaderTask`。
- `max_readers` 限制并行度，避免无界并发和 Main context 污染。
- Reader 输出 claim、locator、研究上下文、方向、量级、限制和 integrity status。
- 身份错配、畸形输出或单个 reader 失败被隔离，并写入 coverage gap。

### 5. Screener、EvidenceLedger 与 working memory

Screener 对结构化 `ReaderReport` 做 include、exclude 或 uncertain 决策。

`EvidenceLedger` 分层保存 canonical record、screening decision 和 admitted excerpt。

只有 admitted evidence ID 能进入 working memory。Excluded、uncertain、raw text 和 failed reader output 保持隔离。

Counterevidence 与支持性 evidence 使用同一准入和 provenance 标准。

### 6. Synthesis

Synthesizer 只使用当前 admitted evidence，并显式携带 coverage gaps。

Source-study answer 先回答目标论文自己的结论；current-evidence answer 单列后续反证、更新和领域变化。

Verdict calibration 同时检查作者结论、统计支持、效应量和决策意义，避免把轻微数值差异直接映射成肯定结论。

输出应包含 `as_of`、证据 locator、counterevidence、限制和未决问题。

### 7. Checkpoint、resume 与 revocation

- `WorkflowCheckpoint` 保存已完成 query、records、reader reports、gaps 和 revoked IDs。
- Resume 跳过已完成 query，继续未完成的 workflow。
- Correction、retraction 或新排除决定撤回对应 evidence。
- Working memory 随 ledger reconciliation 更新，再执行 synthesis。

## 如何调用

1. 构造 `ResearchRequest`，包含 plan、source-query pairs 和可选 knowledge candidates。
2. 配置 Europe PMC/PubMed providers、OA resolver、Reader、Synthesizer 与 Screener。
3. 用 `ExecutionContext` 和 `HarnessPolicy` 调用 `ResearchController.run(...)`。
4. 检查 `ResearchResult` 的 records、reader reports、ledger、working-memory IDs、gaps、answer 和 checkpoint。
5. 恢复时传回 checkpoint；撤回时传入 `revoked_record_ids`。

Harness 的权限、预算、事件与恢复边界见 [HARNESS.md](HARNESS.md)。

## AuthorLead 与 optional providers

- `AuthorLead` 从已检索记录的 provider metadata 提取作者、ORCID 和 affiliation。
- AuthorLead 用于作者网络、课题组和 watchlist 扩展，不提高 evidence strength。
- OpenAlex 配置 `OPENALEX_API_KEY` 后可提供作者、机构和 cited-by graph；缺少凭据时形成 coverage gap。
- Unpaywall 配置联系邮箱后可返回 OA fallback；Europe PMC OA 失败信息继续保留，避免 fallback 掩盖主来源故障。
- `ResearchExpander` 已把 verified author leads、citations、references 与 optional OpenAlex expansion 接入有界 Agent loop；达到 expansion query budget 后立即停止额外网络调用。

## app_v4 与 Codex runtime

- `scripts/run_app_v4_research.py` 从 plugin runtime 导入只读 `sources/frogent/app_v4.py`，并把原 assistant manager 替换为 `AppV4ResearchManager`。
- `CodexPlanner`、`CodexReader`、`HybridScreener` 与 `CodexSynthesizer` 已提供严格结构化输出和 evidence-ID 约束。
- SQLite `ResearchMemory` 持久化 conversation turns、checkpoint、admitted evidence、answer versions 与 revocation；OA 全文不写入 memory 数据库。
- app_v4 继续使用原有 register、login、chat history、attachments 与 SSE `content/stop/[DONE]` 协议。
- 启动前安装 `requirements-app-v4.txt`，设置非空 `SECRET_KEY`，并将 `FROGENT_CODEX_EXECUTABLE` 指向可用 Codex executable。默认不设置墙钟 timeout。
- 一次完整 app_v4 → Codex → live literature SSE 请求仍待 Codex 使用额度恢复后验收。

## 52-case performance loop

当前 exposed capability pack 包含 36 条 PubMedQA、2 条 BioASQ 和 14 条 LongMemEval，共 52 条；52/52 均完成，0 fail、0 timeout、0 missing。

- PubMedQA target PMID hit@1、hit@5、hit@10 均为 `100%`；strict label accuracy 为 `63.89%`，macro F1 为 `62.14%`。
- 13 个 strict mismatch 经 source-study 逐案例复核后，7 个属于 oracle gap、3 个属于 Agent error、3 个有歧义；非歧义病例 source-correct 为 `30/33`。
- 三个实际 synthesis error 在相同 evidence 上应用 source-study/current-evidence 分层后均被修复。
- BioASQ exact answer 为 `2/2`；旧 gold-document recall@10 为 0，检索结果包含可核验的新来源，因此该旧 gold 指标不能代表当前检索失败。
- Citation resolvable rate 为 `99.45%`。
- LongMemEval 初始 clean correctness 为 `7/14`。P1/P2/P3 已围绕 session bundle、用户事实、意图扩展、教育阶段、偏好约束和同 session 关联修复 retrieval。

P3 对四个历史失败案例的 retrieval-only 复核已覆盖全部关键事实。Answer-level 复测在模型生成前遇到 Codex usage limit，结果保持 `not_measured`，失败记录已保留。

## 下一步

1. Codex 使用额度恢复后，先复跑 P3 的 4 条 answer-level memory case，得到效果反馈前冻结 memory retrieval 行为。
2. 完成一次 app_v4 → Codex → live literature 的真实登录、chat、SSE 与持久化验收。
3. 扩充 BioASQ multi-document 与 LongMemEval memory task，针对真实错误继续优化 Agent。
4. Literature 与 memory workflow 稳定后，再接药物设计模型、RDKit、结构分析、对接与 PLIP 工具链。
