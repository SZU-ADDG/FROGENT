# FROGENT Literature Intelligence Workflow

## 用户能力

FROGENT 当前具备一个可组合运行的 literature intelligence 核心。

它从用户问题和待核验的模型知识候选出发，经过真实数据库、OA、bounded reader workers、筛选、working memory 与 synthesis，最后返回带来源边界、coverage gaps 和 checkpoint 的结果。

当前既可从 Python workflow 调用，也可通过 plugin-side launcher 将只读 `sources/frogent/app_v4.py` 接到 FROGENT Agent。独立部署可选用 ChatGPT bundled Codex 的 `gpt-5.6-sol`、medium reasoning；开发与批量评测直接使用 subagents 承担 Agent roles，两条路径都无需 OpenAI API key。

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

Europe PMC 记录含 PMCID 时，workflow 优先获取 OA `fullTextXML` 并生成 `ArtifactRef`。JATS parser 保留 title、abstract、named sections 与 paragraph locators，同时排除 references。

Primary OA 失败后，runtime 依次尝试 NCBI PMC BioC 与 OpenAlex repository discovery，最后保留 abstract-only 路径。Repository discovery 只接受 exact repository locations，并过滤 PubMed 与 publisher locations；每次降级都明确记录 coverage gap 与版本边界。

全文保留在 artifact 边界；Main 只接收结构化 reader 输出和失败信息。

### 4. Bounded reader workers

- Canonical records 按 paper/study family 去重。
- 每个 family 形成独立 `ReaderTask`。
- 选定记录的 OA resolve→Reader pipelines 在 `max_readers` 内并发运行，reports/events 仍按 first-hit 顺序汇总；单路失败被隔离并回退到 abstract。
- Deterministic packing 在既有 char cap 下优先保留 title、abstract、Results、Discussion、Conclusion、Correction、Limitations 与 Counterevidence；无结构全文采用 balanced head/tail。
- Repository PDF 进入 Reader 前需要通过 20 MB 与 PDF signature gates；`pypdf>=6,<7` 提取 page-addressable markers，并把 truncation、OCR unavailable、encrypted 或 malformed 状态写成显式 gap。
- Publication Reader 会从 PubMed 的 direct NCT accessions，或 relation type 为 `RESULT`/`DERIVED` 的 exact PMID references，自动补充 ClinicalTrials.gov evidence；`BACKGROUND` trials 保持排除。
- Registry evidence 保留 link provenance、status/date、design、enrollment、arms/interventions、sponsor、全部 primary outcomes 的 bounded descriptions、前 10 个 secondary outcomes 与 omitted count、results-posting state，以及 current-mutable/`as_of` 限制。
- Reader 必须比较 publication 的 observed design/outcomes 与 registry 的 planned evidence；protocol fields 不能作为 observed efficacy 或 safety。Registry failure 保持局部隔离，article/abstract Reader 继续运行。
- 60k pack 同时保留 article/PDF evidence 与 bounded registry evidence。
- 每个 OA→registry→Reader document 生成 typed telemetry：`record_id`、最终 `source_path`（`jats`、`bioc`、`repository_pdf`、`abstract`、`oa_fallback`、`other_full_text`）、preparation/reader/total seconds、`completed`/`reader_failed`、fallback 与 `packed_chars`。
- `ReadBatch` 保持 first-hit report/telemetry order，并记录 observed peak Reader concurrency。单个 Reader failure 只省略该 report，保留 `reader_failed` telemetry 与 gap，其余 documents 继续。
- `ResearchResult`、`WorkflowCheckpoint` 与 SQLite 持久化 document telemetry/peak，不保存 OA/full text；resume 与 revoke 保留这些测量。`CodexReader` 复用已生成的 bounded pack，避免重复 packing。
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
- 四个角色均使用 native output schema 与 typed validation；synthesis 与 memory answer 的 evidence-ID 语义错误最多 repair 一次，仍失败时返回可审计的 partial answer 或 abstention。
- SQLite `ResearchMemory` 持久化 cross-chat conversation turns、checkpoint、admitted evidence、answer versions 与 revocation；OA 全文不写入 memory 数据库。
- app_v4 继续使用原有 register、login、chat history、attachments 与 SSE `content/stop/[DONE]` 协议。
- 启动前安装 `requirements-app-v4.txt`，设置非空 `SECRET_KEY`，并将 `FROGENT_CODEX_EXECUTABLE` 指向可用 Codex executable。默认不设置墙钟 timeout。
- `pypdf>=6,<7` 是默认 app dependency；repository PDF provenance 保留 repository、host、landing page、version 与 license。
- subagent-native live probe 已通过真实 Europe PMC/OA、Reader、Screener、evidence admission、Synthesizer、SSE、history 与 SQLite checkpoint。独立部署时仍可由 bundled Codex adapter 提供同一组 roles。

## 52-case performance loop

当前 exposed capability pack 包含 36 条 PubMedQA、2 条 BioASQ 和 14 条 LongMemEval，共 52 条；52/52 均完成，0 fail、0 timeout、0 missing。

- PubMedQA target PMID hit@1、hit@5、hit@10 均为 `100%`；strict label accuracy 为 `63.89%`。
- 13 个 strict mismatch 经 source-study 逐案例复核后，7 个属于 oracle gap、3 个属于 Agent error、3 个有歧义；非歧义病例 source-correct 为 `30/33`。
- 三个实际 synthesis error 在相同 evidence 上应用 source-study/current-evidence 分层后均被修复。
- BioASQ exact answer 为 `2/2`；旧 gold-document recall@10 为 0，检索结果包含可核验的新来源，因此该旧 gold 指标不能代表当前检索失败。
- Citation resolvable rate 为 `99.45%`。
- LongMemEval baseline clean correctness 为 `7/14`。
- P1 real blind rerun 修复 duration sum、relative event order 和 project count；7 个此前失败 case 中，3 个 fully correct、3 个 partial/cautious、1 个 wrong。
- P2 real blind rerun 4/4 completed 并改善 retrieval，answers 仍偏保守或方向错误。
- P3 保持 8 hits / 8000 chars，并加入 direct matched companions、education-stage intent、显式 preference/time constraints 与 qualified same-session linkage。

P3 retrieval-only diagnostic 已覆盖三个 education answer sessions、coupon 与 Target context、early guitar comparison 与 later usage，并把 `9:30` preference session 排名第一。

P3 answer-level rerun 改由 collaboration subagents 直接读取真实 FROGENT retrieval bundles 并作 evidence-bound reasoning，4/4 completed、零 CLI、零 API key。逐例复核为 2 correct、2 partial/cautious、0 clearly wrong：Target 与晚间活动约束正确；教育聚合漏报 PCC 两年；购琴回答利用了 Stratocaster、Les Paul 与 open-D 证据，但比较维度仍不完整。

## Memory P4 effect

P4 为显式四位年份范围增加 source-grounded stage timeline retrieval，并为显式 comparison 增加 evidence checklist：current context、target/change、usage、fit/physical、performance、preference/avoid。缺少的维度必须在回答中披露。

Fresh direct-subagent evaluation 使用 `007/008/009/014`，直接读取 FROGENT memory bundles，无 nested Codex CLI 或 API key：

- `007` 保留全部 source-stated stages 与 known durations，报告 8 个 known years；Associate start/duration 与 Master's completion 缺失，因此对 complete total abstain。Exposed oracle 额外采用的两年 Associate duration 没有 source 明文支持，属于 oracle/source-grounding limitation，不能记作 Agent regression。
- `008` 保持 qualified same-session Target inference，并引用两个 evidence IDs。
- `009` 基于 repertoire 与 open-D evidence 给出具体 Stratocaster-vs-Les Paul A/B plan，同时披露 neck、weight、tone/performance、pickups、budget 与 preference evidence 缺口。
- `014` 初版因 comparison markers 泄漏到普通 recommendation intent 而回退。P0/P1 将 preference/time/scope/constraint retrieval 与 compare/evaluate/replace/upgrade retrieval 分开；fresh rerun 恢复 joint-friendly、early-evening、yoga/flexibility 与 `9:30` wind-down 回答，compare/upgrade-only distractor hits 为 0。

当前结论：P4 改善显式 comparison synthesis，并保持 source-grounded timeline reasoning；普通 recommendation regression 已修复。低价值 generic-word noise 仍可观察，但没有进入 support IDs。

## Reader Block 1 effect

Live P0 暴露了明确的 provider boundary：PMID 28781108 / PMC5831666 的 Europe PMC `fullTextXML` 返回 404，NCBI PMC BioC 返回 `author_manuscript`，OA API 同时报告 `idIsNotOpenAccess`。Runtime 仅在 primary OA 失败后使用 NCBI BioC，保留该 coverage gap 与版本边界，排除 `REF` passages；两条全文路径均失败时回退到 abstract。HTTP、search 与 research 默认没有固定墙钟 timeout，部署方仍可设置显式正值 override。

Fresh direct-subagent effect evaluation 未使用 nested CLI、API key 或固定 timeout，panel 包含 PMID 28781108、38101901、38598572、39919773，以及 Expression of Concern PMID 42330995：

- `5/5` identity 与 coverage levels 正确；`4/4` trials 的 primary effects 带 locators。
- `4/4` trials 保留 counterevidence、safety 与 limitations；EOC 双向关联、状态保持 unresolved，未被称为 retraction。
- Synthesis 使用 admitted PMIDs 之外的 citation 数为 0，并分开 source-study verdict 与 current-evidence verdict。
- 241606-byte BioC author manuscript 被解析为 50606 evidence chars；title、abstract、Results、Discussion、table、primary `-3.5` effect 与 disease-modification uncertainty 均保留，`REF` 被排除，在 60k cap 下没有 truncation。

该 panel 的证据结论是：随机人体证据尚未建立 GLP-1 receptor agonists 能减缓 Parkinson disease progression。较小的 exenatide/lixisenatide phase-2 motor signals 仍可能来自持续 symptomatic effects 或 exploratory signals；NLY01 为 null，较大的 96-week exenatide phase 3 为 null 且必须携带 unresolved EOC。即使降低 integrity-qualified phase 3 的权重，NLY01 与 unresolved positive trials 仍使 progression slowing 处于 unproven。GI intolerance 与 weight loss 反复出现，当前证据不支持 individualized benefit-risk claim。

Throughput latency 本轮未计时，状态为 `not_measured`；synthetic synchronization 只证明 concurrent pipeline behavior。Reader Block 1 当时的直接能力缺口是 institutional-repository discovery：PMID 39919773 存在可用的 UCL repository PDF，Europe PMC metadata 未提供 full text，当时的 runtime 未自动发现该 PDF。下述 Repository PDF Reader block 已关闭该缺口。

## Repository PDF Reader effect

OpenAlex repository discovery 已接在 Europe PMC/BioC 之后。Runtime 只使用 exact repository locations，过滤 PubMed 与 publisher locations，并在 `ArtifactRef` 中保留 repository、host、landing page、version 与 license。PDF 下载和解析默认没有固定墙钟 timeout，同时受 20 MB 与 signature gates 约束。

真实 PMID 39919773 canary 在显式 `FROGENT` User-Agent 下完成 full metadata→UCL repository PDF→`pypdf`：总耗时 6.101 秒，下载 469065 bytes，解析 11 pages、58886 chars 与 11 个 page markers，在 60k cap 下没有 truncation。

两个 direct subagents 独立接受了 source-grounded design、effect、safety 与 limitations extraction。Primary effect 为 0.92（95% CI -1.56 to 3.39，p=.47）；Agent 同时保留 narrative 与 Table 4 的 serious-event discrepancy，以及 unresolved integrity notice。

当前 PDF 路径仍会 flatten tables/figures，OCR 不可用。Section-aware PDF packing 延后到真实 failure 出现后再决定，避免为未观察到的失败提前增加复杂度。

## ClinicalTrials evidence link effect

Fresh direct-subagent panel 验证了 publication→registry augmentation：

- PMID 38101901→NCT04154072 PASS：registry 保留 255 randomized、3 arms、36-week MDS-UPDRS II+III；publication 为 negative，registry `hasResults=false`。
- PMID 28781108→NCT01971242 首轮正确 FAIL：`measure=Efficacy` 掩盖了 endpoint description。P0 现保留 bounded primary description；fresh rerun PASS，两个 `BACKGROUND` trials 均被排除，planned 60-week OFF-med MDS-UPDRS III 与 publication observed `-3.5`、p=.0318 均保留，并把 registry 60 与 publication 62 randomized/60 analysis 记录为 qualified discrepancy。
- PMID 39919773→NCT04232969 PASS：registry 保留 194 randomized、96-week OFF-med MDS-UPDRS III；publication observed effect 为 0·92（95% CI -1·56 to 3·39，p=0·47），registry `hasResults=false`，且 current registry update 晚于 publication。

真实 UCL 60k pack 同时保留 10 个 PDF page markers、observed effect、planned endpoint 与 registry state。

当前限制：registry 是 current mutable view，无法重建历史快照；`hasResults=true` 的 result values 尚未解析；PMID discovery 只扫描前 25 条 references；没有 automated verdict；registry enrollment 语义可能与 publication 的 randomized 或 analysis population 不同。

## Mixed Reader throughput effect

Fresh real panel 使用四个 direct subagent Reader workers，无 nested Codex CLI 或 API key：

| PMID | Final source path | Preparation | Packed chars | Reader evidence |
| --- | --- | ---: | ---: | --- |
| 42113543 | JATS | 2.668s | 8,325 | Early-onset criteria 在 prospective cohorts 漏掉 68–77% variant carriers；broader testing direction 有支持，clinical utility/cost-effectiveness 未解决。 |
| 28781108 | BioC author manuscript | 4.389s | 52,236 | Week-60 MDS-UPDRS III `-3.5` signal 与 planned OFF-med endpoint 均保留；disease modification 未解决。 |
| 39919773 | UCL repository PDF | 6.145s | 60,000 | 0.92（95% CI -1.56 to 3.39，p=.47）支持 negative disease-modification result；serious-event narrative/table discrepancy 保留。 |
| 38101901 | Abstract fallback | 1.160s | 5,598 | 两个 NLY01 doses 均 negative；gastrointestinal/nausea counterevidence 保留，registry protocol fields 未被当作 observed outcomes。 |

同一 batch 的 real concurrent preparation wall time 为 6.146s，observed peak=4，first-hit report/telemetry order 保持。四篇 preparation 累计约 14.363s，对 sequential sum 的 observed preparation speedup 约 2.34×。Repository 60k input 虽有 truncation，仍保留 title、observed 0.92/p=.47、10 个 PDF page markers、registry boundary 与 planned endpoint。

Reader quality 为 `4/4` identities/designs/primary findings with locators、`4/4` counterevidence/safety/limitations。三个 trial papers 均分开 publication observed results 与 ClinicalTrials.gov planned/current fields；`BACKGROUND` trial pollution=0，admitted-set-external claims=0。Live panel 的 Reader failures=0。Deterministic mixed-source test 注入一个 BioC Reader failure 后仍得到 3 reports、4 telemetry entries、peak=4 与 ordered aggregation。

测量边界：batch timing 准确覆盖 live provider/OA/PDF/registry preparation 与 concurrency；deterministic barrier 的 `reader_seconds` 包含 synchronization wait，不能代表真实 model latency。Direct worker end-to-end evidence review 可观察到 JATS 约 22s、repository 约 43s；BioC/abstract model reasoning 未单独 instrument，完整 Reader latency distribution 为 `not_measured`。该 n=4 panel 只建立方向与 failure visibility。Repository PDF 仍是 preparation bottleneck，PDF extraction/table layout 与 mutable registry snapshots 继续作为已知限制。

## Molecular identity and tool routing effect

`prepare_molecular_request` 接受 SMILES，并生成 evidence-bound molecular identity、retrieval terms 与 tool plan。App-v4 project venv 中的 RDKit 2026.03.4 会保留 original input，并计算 canonical isomeric/connectivity SMILES、InChI、InChIKey、formula、exact mass、formal charge、fragments 与 stereo information。

- 完整 salt/mixture identity 始终可选；derived parent 只作为 candidate。调用工具前必须显式选择 full identity 或 parent，并把选择绑定进 tool input。
- Multi-organic 输入必须指定 exact normalized fragment；无效 counterion selection fail closed，`[Na+]` 不能作为 parent。
- Candidate/baseline comparison 使用对称 retrieval terms、exact candidate/baseline binding 与固定 role order，并把 target/pocket 继续传到 tool plan。
- `evaluate-candidate`、`optimize-small-molecule` 与 `plan-retrosynthesis` Skills 现在都从 `prepare-molecule` 开始。

Official no-key PubChem PUG REST resolver 现在可以按 exact selected full/parent InChIKey 验证结构，或解析用户提供的 name；两条路径都要求 PubChem identity 与本地 RDKit normalization 结构一致。Provider failure 时，Agent 仍可使用本地 RDKit identity 与 tool plan。Verified CID 是 exact retrieval identity，verified title 只扩展 broad retrieval context，不能作为 experimental evidence。Resolver 不持久化 raw responses，也不需要 API key。

Candidate/baseline resolution 保持 symmetric 与 role-bound；两侧 identity 相同会阻止 false comparison。Exact InChIKey duplicate handling 允许结构一致的不完整重复：sodium acetate response 中 CID 31372 不完整、CID 517045 带 title 且完整，两者 structural fingerprints 一致，因此 runtime 只选择 CID 517045。存在结构冲突、多个完整记录或其他 ambiguity 时 fail closed；name lookup 保持 strict single-record。

Fresh forward evidence：L-lactic acid name→CID 107689 并形成 ready ADMET plan；把 caffeine structure 错标为 theobromine 会被校正或拒绝；校正后的 caffeine CID 2519 与 theobromine CID 5429 形成 distinct symmetric comparison；sodium acetate full→CID 517045、parent acetate→CID 175，scope 分开且 gaps=0。此前 bounded live metadata panel 对 aspirin、caffeine、theobromine、L-lactic acid、sodium acetate、choline 的 PubChem→RDKit agreement 为 `6/6 PASS`。

PubChem block 验收时，catalog ADMET port 9004 没有 listener；下述 in-process ADMET-AI block 已关闭该 prediction execution gap。PubChem resolver 仍是 direct runtime helper，尚未自动注入 generic Planner/factory。下述 project-local Vina/Meeko/PLIP block 已关闭 local docking 与 pose-interaction execution gap；retrosynthesis/SAR providers、Literature Skill ordering、generic target/pocket external validation 与 automated artifact acquisition 保持 pending。Charged-species exact mass 可能因 electron-mass convention 不同而有差异。

## ADMET-AI execution effect

Exact-bound ready `admet.predict` 与 `admet.compare` steps 现在通过 lazy、reusable、in-process ADMET-AI 2.0.1 执行。Direct workflows 接受 SMILES 或 PubChem-resolved names；provider gap 时保留本地 RDKit identity/tool plan，任何 identity blocker 都在 model call 前停止。每项结果继续携带 role order、full/parent scope、canonical isomeric SMILES、InChIKey、removed fragments、provider/model version；comparison 明确记录 candidate-minus-baseline deltas。

Real canaries：

| Exact-bound input | AMES | hERG | DILI |
| --- | ---: | ---: | ---: |
| Caffeine full | 0.110573 | 0.047541 | 0.932074 |
| Sodium acetate full | 0.081154 | 0.004473 | 0.427690 |
| Acetate parent | 0.048887 | 0.005175 | 0.520490 |

Caffeine candidate vs theobromine baseline 的 candidate-minus-baseline deltas 为 AMES `-0.054096`、hERG `+0.028841`、DILI `-0.022584`。Sodium acetate full 与 acetate parent 的不同输出证明 scope sensitivity；两类结果不能互换。

Cold caffeine call 为 13.181s；comparison/model-load process 为 4.179s；同一 process 内 warm salt calls 各约 0.146s。两次 fresh direct-subagent interpretation 均 PASS，并明确要求：缺少 endpoint direction、calibration、applicability、uncertainty、exposure 与实验验证时，Agent 不能据此选择 compound 或作 safety claim。

这些输出属于 computational point predictions，`experimental_evidence=false`。Calibrated per-prediction uncertainty 当前不可用，不支持 aggregate score 或 effect claim。ADMET execution block 验收时仍是 direct runtime helper；下述 app-v4 molecular chat block 已关闭 Planner/tool-event integration gap。依赖完整 drug-design/model runtime 的 workflows 继续 deferred。

## App-v4 molecular chat effect

App-v4 通过既有 payload 与 SSE contract 接受 `mode=molecular`。`mode=auto` 只把明确 ADMET action 路由到 molecular；中文“运行、执行、预测、计算、估算、比较、对比、评估”等 action 可识别，中文“文献、论文、检索、搜索”请求继续进入 research，含糊提及保持保守。

- Native molecular planner 使用严格 typed schema；candidate/baseline name 或 SMILES 必须逐字来自当前用户消息。
- Full/parent scope 的每个 arm 都必须有独立 exact selection span。跨 arm 授权、只授权一臂却应用到另一臂、非法 fragment selection 均 fail closed。
- Endpoint selection 由 runtime 决定：消息显式包含 allowlisted endpoint IDs 时按出现顺序执行；缺少显式 ID 时使用固定 `DEFAULT_ADMET_PROPERTIES`。模型不能自行选择 endpoint subset。
- Execution 保持 PubChem verified identity→RDKit exact binding→lazy reusable ADMET-AI predict/compare；candidate→baseline role order、scope、canonical isomeric SMILES、InChIKey、removed fragments、endpoint values 与 deltas 始终绑定。

SSE typed events 与 SQLite cross-chat memory 已接通。History ingest 或 exchange persistence 失败时，runtime 保留一次 molecular execution 与 completed/partial answer，追加 recoverable `memory_persistence` error，不重复模型调用。Blocked 或 same-identity request 不调用 ADMET。

Main 的真实 Flask `/api/chat` canary 使用 direct collaboration subagent 作为 planner，无 nested CLI 或 OpenAI API key。中文请求比较 caffeine 与 theobromine 的 AMES、hERG、DILI，candidate=caffeine、baseline=theobromine；HTTP 200，SSE `name=molecular`，elapsed=11.633s，SQLite 写入 user/assistant 两轮。

| Role | PubChem CID | InChIKey | AMES | hERG | DILI |
| --- | ---: | --- | ---: | ---: | ---: |
| Candidate caffeine | 2519 | RYYVLZVUVIJVGH-UHFFFAOYSA-N | 0.11057253181934357 | 0.04754055291414261 | 0.932073712348938 |
| Baseline theobromine | 5429 | YAPQBXQYLJRXSA-UHFFFAOYSA-N | 0.16466861963272095 | 0.018699243664741516 | 0.9546573758125305 |
| Candidate-minus-baseline delta | — | — | -0.05409608781337738 | +0.028841309249401093 | -0.02258366346359253 |

Typed events 覆盖 plan、identity、`admet.compare`、message、done。回答保持 computational point prediction、`experimental_evidence=false`、calibrated per-prediction uncertainty unavailable、model applicability domain 未建立、cross-endpoint score comparability 未建立等边界，不作安全、暴露量、总体分数或候选选择结论。

## Project-local Vina / Meeko / PLIP effect

此前 Vina/PLIP unavailable、效果 `not_measured` 的边界已经关闭。Project-contained runtime 提供 official AutoDock Vina 1.2.7 executable `.runtime/tools/vina/1.2.7/vina`；app-v4 venv 提供 PLIP 3.0.0、OpenBabel 3.2.1、Meeko 0.7.1、Gemmi 0.7.5 与 lxml 6.1.1。该链无需 API key，也未使用 global、Homebrew 或 Docker installation。`requirements-app-v4` 声明上述 Python dependencies，official Vina binary 继续作为独立的 project-contained executable。

- Runtime 执行 typed verified target/pocket → exact `MolecularInputBinding` → Vina poses → explicit selected-pose PLIP chain。Pose ID、rank、artifact、score direction、executable/version/argv、input artifacts 与 preparation provenance 均保持绑定；单步失败可安全局部返回。
- App-v4 路由明确的 English/Chinese docking 与 PLIP action；literature 或 ambiguous request 继续进入 research。Chat 继承 `provider.default_config`。
- Accepted canary config 为 `pose_count=9`、`exhaustiveness=8`、`cpu=4`、`seed=20260719`、`energy_range=10`，score contract 为 `vina_affinity_kcal_per_mol` / `lower_is_better`。
- Meeko provenance 必须恰好包含三步：lossless receptor normalization、ligand preparation、receptor preparation。Accepted canary 为 `moved=1`、`dropped=0`；出现 dropped 或 interrupted records 时 fail closed。

Real exposed official 1IEP redocking canary 使用 Meeko-prepared ligand/receptor。9 个 Vina scores 依次为 `-13.199, -11.240, -11.119, -10.634, -9.655, -8.954, -8.826, -8.428, -8.141`。Pose 1 的 37-heavy-atom fixed-frame RMSD 为 0.9007 Å（相对 official input/crystal-derived ligand）与 0.0535 Å（相对 official Vina pose 1）。

PLIP 以 `--nohydro --maxthreads 1` 分析显式选定的 pose 1，报告 12 个 hydrophobic interactions、MET318/ASP381 H-bonds、TYR253 pi-stack，未报告 salt bridge。相对 reference，7 个 hydrophobic residues 全部保留，MET318/ASP381 H-bonds 与 TYR253 pi-stack 保留；ASP381 salt bridge 丢失；新增 VAL256、ALA269、GLU286、LEU370 四个 hydrophobic residues。

这是一项 exposed single-target redocking diagnostic，只支持 exact-bound local tool execution、pose provenance 与 interaction comparison。它不支持 broad docking effectiveness、binding affinity、mechanism、experimental effect、applicability-domain 或 cross-target calibration claim。下述 RCSB block 已接通 explicit-PDB target/pocket acquisition；local Meeko/Vina/PLIP execution 继续通过 injectable exact-bound adapters 使用。Pose selection 由用户或 upstream workflow 显式决定。

## RCSB target identity and verified pocket effect

No-key RCSB target provider 接受显式 4-character PDB ID，验证 entry metadata、polymer `auth_asym_ids` 与下载的 legacy PDB coordinates，并把 structure 保存为 project-contained artifact，附 typed metadata 与 coordinate provenance。Verified pocket provider 接受 exact auth-numbered residues 或 exact reference-ligand identity，从 target coordinates 以显式 margin 确定性计算 angstrom box，并绑定 target artifact lineage。

- App-v4 factory 已为明确 docking request 提供 RCSB target/pocket providers；prepared Vina center/size 必须与 verified pocket geometry 完全一致。Exact target/pocket identity 因此可以到达 Vina boundary，无需模型生成 coordinates。
- Reused pocket manifest 只作为 declaration。Runtime 会重新解析当前 target artifact、重选 exact atoms、检查 alternate locations、重算 geometry，并拒绝 schema、source、numbering、center、size、method、margin 或 lineage tampering。Artifact round-trip 保留 residue/reference-ligand lineage。
- Real bounded 1IEP canary 下载的 PDB artifact 为 434,565 bytes，验证 auth chains A/B。Official archive identities 为 STI:A:201 与 STI:B:202；另一个 prepared complex 中的 STI:A:999 被正确拒绝，同时返回 STI:A:201 candidate。
- Exact STI:A:201 pocket 的 center 为 `(15.190, 53.903, 16.917)` Å，size 为 `(18.664, 26.739, 23.526)` Å，margin=5.0 Å；Main independent artifact revalidation PASS。

当前 provider 只支持 legacy PDB，mmCIF compatibility 与 UniProt/name-to-PDB mapping 仍 pending。Ambiguous multi-model 或 alternate-location records fail closed。下述 dynamic block 已接通 newly acquired target 与 exact selected molecule 的 Vina-ready preparation；pose selection 保持 explicit policy。这一 exposed 1IEP case 不支持 general docking effectiveness 或 affinity claim。

## Dynamic RCSB → RDKit → Meeko → Vina effect

Normal `mode=docking` 现在可以使用 explicit RCSB PDB ID、auth chain、exact reference-ligand pocket 与 exact selected molecular binding，动态生成可执行的 Vina inputs。Ligand chain 将 selected canonical isomeric SMILES/InChIKey/scope 绑定到 deterministic RDKit ETKDG conformer（typed method、seed、`max_iterations`、threads），依次生成 SDF 与 project-local Meeko ligand PDBQT。Receptor chain 从 current RCSB artifact 选择一个 exact auth chain，应用 explicit component policy，生成 selected receptor PDB 与 project-local Meeko receptor PDBQT，再绑定 exact verified pocket box 进入 Vina。

- Runtime defaults 为 9 poses、exhaustiveness 8、cpu 4、seed 20260719、energy range 10.0，score contract 为 `vina_affinity_kcal_per_mol` / `lower_is_better`；没有 default wall-clock timeout。
- Disconnected identity、conformer/stereo drift、unapproved HETATM/cofactor/metal、wrong chain/reference ligand、interrupted residue、selected polymer altloc、missing/extra/duplicate/coordinate-moved receptor heavy atom，以及 path/config/tool failure 都会在 Vina 前 fail closed。Safe partial result 保留 molecule、target 与 pocket lineage。
- Factory 只在 project-contained Vina executable、Meeko ligand preparation executable 与 Meeko receptor preparation executable 三条路径全部配置时启用；缺少任一路径时 docking 保持 safely blocked。
- P0 review 已把 actual conformer settings、exact receptor heavy-atom preservation、deterministic factory config 与 polymer-altloc blocking 纳入 runtime contract。

Real exposed 1IEP dynamic canary 使用 exact cationic ligand InChIKey `KTUFNOKKBVMGRW-UHFFFAOYSA-O`（37 heavy atoms）与 verified STI:A:201 pocket：center `(15.190, 53.903, 16.917)` Å，size `(18.664, 26.739, 23.526)` Å。A-chain 的 2,229 个 polymer heavy atoms 经 Meeko 后保持 zero missing、extra 与 coordinate drift；component policy 移除 exact STI 37 atoms、99 A-chain waters 与 approved 4 chloride atoms，并排除 B chain。

Preparation 约 2.698s，Vina 约 8.280s，wall 10.991s；9 个 scores 为 `[-12.975, -10.030, -9.966, -9.646, -9.362, -9.341, -9.246, -9.101, -9.081]`。Main independent 37-heavy-atom mapping 得到 dynamic pose 1 对 official crystal-derived ligand 的 fixed-frame RMSD 1.142008 Å，对 earlier accepted Vina pose 1 的 RMSD 1.418959 Å。这只是一项 exposed single-case redocking signal，不支持 general docking quality、affinity 或 cross-target claim。

## Dynamic selected-pose PLIP effect

Normal `mode=docking` 已支持 exact target/pocket/molecule → dynamic Vina → current-message explicit pose ID 或 rank → resolved generated pose ID/artifact → project-contained PLIP。Interaction analysis 必须且只能指定一个 pose ID/rank；runtime 不自动选择 lowest-score 或“best” pose。

- Dynamic assembler 重新验证 molecule scope/SMILES/InChIKey、target/pocket geometry/artifacts 与 pose rank/ID/artifact；解析 `SMILES`、`SMILES IDX`、`H PARENT`，生成带 bond records 的 LIG:Z:1 complex。Receptor atom serials 原样保留，ligand serials 从 retained receptor maximum serial + 1 开始。
- Factory 要求显式 project-contained `FROGENT_PLIP_EXECUTABLE` 与 version；default timeout 保持 `None`。PLIP 缺失或失败时，已完成 docking 作为 safe partial 保留。
- Typed events/SSE 包含 requested rank、resolved rank/pose ID、complex artifact、preparation provenance、command 与 interactions。

当前 accepted post-H 1IEP evidence 使用 pose `dynamic-rcsb-1iep-20260719-pose-1` / rank 1、molecule InChIKey `KTUFNOKKBVMGRW-UHFFFAOYSA-O`、target 1IEP、pocket `rcsb-pocket-sti-a-201` 与 ligand LIG:Z:1。Complex 包含 2,229 receptor `ATOM` records、37 ligand heavy atoms 与 3 exact `H PARENT` pose hydrogens；40 个 ligand coordinates 与 Vina pose 完全一致，max delta=0.0。Serial sets unique/disjoint：receptor max=2229，ligand=2230..2269。

PLIP 3.0.0 exit 0、1.539s，得到 12 interactions：hydrophobic LEU248/TYR253/VAL256/ALA269/LYS271/VAL299/ILE313/THR315/LEU370/ASP381、ASP381 salt bridge、TYR253 pi stack。

- 对 corrected reference：共享 hydrophobic LEU248/TYR253/LYS271/ILE313/THR315/ASP381、ASP381 salt 与 TYR253 pi；丢失 hydrophobic PHE382 与 MET318/ASP381 H-bonds；新增 hydrophobic VAL256/ALA269/VAL299/LEU370。
- 对 earlier accepted Vina pose 1：共享 unique hydrophobic LEU248/TYR253/VAL256/ALA269/LYS271/ILE313/THR315/LEU370/ASP381 与 TYR253 pi；丢失 GLU286/PHE382 hydrophobic 与 MET318/ASP381 H-bonds；新增 VAL299 hydrophobic 与 ASP381 salt。

Historical pre-H successful run 保留 37 heavy/0 H 与同一 12-interaction fingerprint；只有 post-H run 作为当前 effect evidence。初始 chloride-policy failure directory 继续保留，并证明 component policy 会 fail closed。Explicit pose hydrogens 未恢复 reference H-bonds；protonation/tautomer/pH applicability 仍 unresolved。一个 exposed 1IEP case 不支持 general docking quality、affinity、mechanism 或 automated pose-selection validity。

## pH-aware docking state effect

Ligand state 现在通过 Dimorphite-DL 2.0.2 有界枚举 protomers，再由 app RDKit 2026.3.3 枚举并验证 tautomers。首轮返回 state ID、SMILES、charge 与 pH；用户下一条当前消息必须精确选择一个 state，runtime 不自动选择 dominant microstate。1IEP comparability arm 显式选择 `microstate-ae11f4051b56b99d`，保留 prior STI monocation SMILES、InChIKey `KTUFNOKKBVMGRW-UHFFFAOYSA-O` 与 charge +1。Panel 有 24 candidates；3 条 nonfatal warning 仅以 count 进入 Agent 输出。

Receptor state 同样要求当前消息显式给出 pH。Project-local PDB2PQR 3.7.1 与 PROPKA 3.5.1 在同一 isolated venv 中以 PARSE、pH 7.4 运行，保留 normal debump 与 H-bond optimization。Prepared PDB/PQR 执行全原子 identity、coordinate、finite charge/radius 验证；unique run-local PROPKA final sidecar 是 authoritative pKa source。

- Accepted state `receptor-1IEP-A-ph7.4-84c0d788fc7d548d` 用时 0.772s。Source/prepared heavy atoms 为 2229→2230；唯一新增 heavy atom 是 GLN:A:498 OXT `(-14.513, 52.826, 26.921)`。Prepared state 含 2,182 H，其中 1,603 个为 zero-radius H。
- Normal chemistry 产生 18 个 bounded typed side-chain moves，max displacement=2.378571 Å。完整 moves、added atom、H counts 与 state artifact identity 进入 typed Vina/PLIP lineage；Agent 只展示 deterministic top-16 move summary。
- Final P0 要求至少一个 exact pKa-bearing `ReceptorResidueState`；empty 或 rename-only parsing 在 Meeko/Vina 前 fail closed。`DockingStateLineage` 暴露 total pKa group count 与最多 16 个最接近 selected pH 的 exact groups，按 `abs(pKa-pH)`、residue ID 排序。Vina/PLIP events 与 deterministic answer 携带 group、source/prepared residue identity 与 pKa；raw PROPKA stdout/stderr/log 保持隐藏。
- Accepted state 含 98 pKa groups，包括 N+:A:225=7.83、GLU:A:286=5.49、TYR:A:353=9.55、C-:A:498=3.43。Meeko receptor 使用 exact PQR charges；只允许 exact terminal GLN498 O/OXT name/coordinate permutation 做 typed normalization，其余 drift fail closed。

Real Vina v6 固定同一 selected ligand/receptor state 与 pocket，workflow=12.820s，9 poses 的 scores 为 `[-12.974, -10.824, -9.945, -9.615, -9.528, -9.478, -9.337, -9.242, -9.194]`。Rank 1 只为 cross-run comparability 预先声明，resolved pose ID=`ph-aware-1iep-vina-final-v6-20260719-pose-1`；不作 best-pose 或 affinity claim。

Real PLIP v7 使用该 exact rank-1 pose 与同一 receptor-state/PDB/PQR lineage，用时 1.399s，报告 12 interactions：hydrophobic LEU248/TYR253/ALA269/LYS271/VAL299/ILE313/THR315/LEU370/ASP381，H-bonds MET318/ASP381，pi-stack TYR253。相对 corrected reference，hydrophobic shared=6/7，并恢复 MET318/ASP381 H-bonds 与 TYR253 pi-stack；缺少 PHE382 hydrophobic 与 ASP381 salt bridge；新增 ALA269/VAL299/LEU370。相对 prior non-pH post-H run，rank-1 score 仅从 -12.975 变为 -12.974，同时两条 reference H-bonds 恢复，表明 state preparation 可以改变 interaction classification。这只构成 exposed single-case state-sensitivity diagnostic。

严格多案例 gate 继续发挥正确拒绝能力：3PTB 因 binding-site Ca/metal-cofactor policy，1M17 因 binding-site altloc，4DFR 因 chain/MTX、chloride disposition 与 altloc ambiguity，1HSG 因 multichain binding site。它们仍需 explicit metal/cofactor、altloc 与 multichain policy 后才能执行。Microstate dominance、pKa accuracy、score calibration、affinity、mechanism、experimental correlation 与 general docking effectiveness 均未建立；single 1IEP 不能外推。

## 最新验证

- Focused：`63/63 PASS`；Main full `scripts/check.py`：`295/295 PASS`。
- Official plugin validator，以及 `prepare-molecule`、`evaluate-candidate`、`optimize-small-molecule` validators PASS。
- Sanitizer `982/0/0`；diff、architecture 与 hygiene PASS。Main 独立重解析 artifacts，确认 9 个 scores、exact PLIP residues、selected/prepared/PQR counts、OXT、moves 与 pKa lineage。

## 下一步

1. 下一 capability block 实现 explicit metal/cofactor disposition 与 explicit altloc/multichain selections。
2. 随后运行真实 multi-case executable docking/PLIP panel，并保留 pH/protonation 与 mmCIF limits。
3. 建立 model/score calibration 前不作 general docking quality 或 affinity claim；依赖未接入模型的完整 drug-design tasks 继续 deferred。
