# FROGENT（COMMSBIO-26-4686-T）大修与逐条回复计划

## 1. 文件状态

- 用途：内部修订控制、逐条回复起草和稿件同步。
- 当前 readiness：`blocked`。
- 解除阻塞的条件：完成 G0 基准与能力事实核查，确认八项任务的真实定义、评分、工具权限和实际 provider。
- 回复原则：每条审稿意见都以一个明确结果结束：
  - `clarified_in_response_only`
  - `revised_in_manuscript`
  - `revised_in_both`
  - `respectfully_declined_with_justification`
- 稿件位置目前均为 planned location。完成正文修改后，应替换为最终 section、figure、table、page 和 line。
- 内部完成窗口：2026-07-30 至 2026-08-12，共 14 天。全部实验、正文、SI、代码/界面修改、point-by-point response 和投稿文件均纳入本轮。
- 2026-07-30 执行检查点：首批当前可执行的非 GPU 工作已完成，包含 255 项完整测试、73 项 evidence regression、89 项 molecular-tool regression、远端 73 项 evidence regression、live literature smoke、Capability-52 rescore、Vina/PLIP/Dimorphite/PDB2PQR 真实 CPU 案例和 37 页论文构建。
- 2026-07-30 第二批检查点：完成 Capability-52 的 50,000 次 bootstrap/95% CI、八项 benchmark datasheet、6-case evidence reliability/recovery panel、63 项 focused tests、Europe PMC 单查询与四任务重复运行、Vina seed stability、12-case protonation panel、3-case receptor pH panel、live RCSB target/pocket repeat，以及远端 Python 3.11/RDKit source-copy-safe CPU validation。
- 2026-07-30 第三批检查点：完成语义双评与 κ、统计分析入口、matched-resource 与真实 subagent 消融、8-case live evidence 独立裁决、structured retrieval、evidence propagation、Luteolin 独立性、ADMET/property、raw/local/redocking、multi-target docking、PLIP parser、DAVIS screening、GLP1R audit、safety contract、telemetry、HLE access audit 和近期 baseline 审计。
- 2026-07-31 GPU 检查点：CBGBench 首轮 45/45 正式生成任务完成（5 pockets × 3 seeds × 3 models，22,500 raw attempts）。TargetDiff、DiffSBDD、Pocket2Mol 分别获得 7,263、1,809、753 个 valid molecules，三个模型的 mean job QED 分别为 `0.458/0.234/0.128`。观察到跨 seed 与跨 pocket 波动后，按独立 post-outcome replication amendment 启动 seed 47/59/71 的 45-job 扩展矩阵；用户随后要求暂停，六个 worker 与 finalizer 已正常停止，保留 15 个 terminal jobs、4 个 interrupted job directories 和 26 个未启动任务，不生成终态或 pooled manifest。GPU 1/3/4/5/6/7 已释放；GPU 0 的 TrioMol2/既有服务和 GPU 2 的第三方生产服务保持原状。每小时自动续跑已暂停。GLP1R–肽 AF3 8/8 任务完成并取回结果包。
- 2026-08-01 GPU 恢复检查点：用户授权继续后，新建 `gpu-followup-20260801/cbgbench-seed-extension-resume-r01/`，继承暂停 run 中 15 个 exit-zero Pocket2Mol jobs，并重新执行全部 30 个 TargetDiff/DiffSBDD 逻辑任务，覆盖 4 个先前中断任务和 26 个未启动任务。GPU 1/3/4/5/6/7 六个 shard 均已进入真实推理，利用率 `98–100%`；旧 run 保持只读。自动 finalizer 将生成完整 45-job 扩展 manifest 与 90-job 六 seed pooled manifest，每小时 follow-up 已恢复。
- 2026-08-01 18:36 GPU 进度检查点：resume run 已完成首个 pocket（1IEP）的 6/6 TargetDiff/DiffSBDD jobs，全部 exit zero；30 个 resume jobs 当前为 6 terminal-success、6 running、18 unstarted。1IEP 三个新 seeds 中 TargetDiff 得到 `460/449/468` 个 valid molecules，DiffSBDD 得到 `107/99/123` 个 valid molecules。Open Babel stereochemistry diagnostics 与少量 `AtomValenceException` 作为 candidate-level reconstruction evidence 保留，未造成 job failure。六个 worker 已进入 2HYY，GPU 1/3/4/5/6/7 利用率 `88–100%`，finalizer 持续存活；完整稳定性结论继续等待 30/30 resume jobs 与两个终态 manifests。
- 2026-08-01 19:41 双进程调度检查点：按用户确认的每卡双进程能力，新增透明 scheduling amendment 与隔离 helper root `gpu-followup-20260801/cbgbench-seed-extension-dual-process-helper-r01/`。原 6 个 workers 保留 2HYY/4WA9，6 个 helper workers 预占 3CS9/1M17，12 个逻辑 jobs 同时运行且互斥；existing finalizer 已记录 `live_workers=12`。GPU 1/3/4/5/6/7 的显存占用由约 `3.9 GiB` 提升至 `7.9 GiB`，六卡利用率均为 `100%`，helper stderr 为 0。GPU 0/2 的既有服务保持原状。
- 2026-08-01 19:46 GPU 进度检查点：resume run 达到 7/30 terminal-success，新增完成项为 `targetdiff-2hyy-s71-n500-resume-r01`，exit zero；其 worker 已无缝进入 4WA9，当前 11 个逻辑 jobs 运行、12 个未启动、0 个失败。12 个 workers 与 finalizer 均存活，worker stderr 均为 0；GPU 1/3/4/5/6/7 保持双进程负载，利用率为 `88–100%`、显存约 `6.9–8.0 GiB`。运行卷剩余约 429 GB，现有 95% 占用未阻断本轮生成。TrioMol2 保持 2 succeeded、1 running、12 queued，TrioPep 保持 4 queued，两个服务器 poller 均存活且下载失败数为 0。
- 2026-08-01 Trio control-plane 检查点：TrioMol2 已推进至 2 succeeded、1 running、12 queued。前两个成功任务各产生 16 个 artifacts；其中 64.6–64.8 MB 的 search trajectory 超出现有 45 MiB SSH relay 上限。已在服务器隔离根 `gpu-followup-20260801/triomol2-server-poller-r02/` 建立流式、逐 artifact 校验的恢复抓取，32/32 artifacts 完整下载且 checksum/size 验证通过。TrioMol2 与 4-task TrioPep 的 15 分钟轮询均已迁移到服务器常驻进程；本地旧 monitor 已停止，后续 TrioMol2 执行、抓取与终态验收留在服务器。
- 2026-07-31 provider 检查点：DirectMultiStep flash/explorer 与 FragGen 三轮共 39/39 typed live MCP calls 成功；每轮 DirectMultiStep 10/10 返回非空且 root 与目标一致的 RDKit-valid 路线，每轮 FragGen 返回 15/15 valid molecules。13 个调用定义中 12 个三轮响应文本完全一致，DirectMultiStep 路线集合平均两两 Jaccard `0.973`，FragGen 分子集合为 `1.000`。用户确认正式多肽对接方法为 MDockPeP2 与 ADCP：MDockPeP2 三次历史 glucagon run 已完成独立审计；ADCP v1.1 采用 3GBQ、1CKB、1ABO 三套晶体参考复合物做主 redocking，并对 29 aa GLP-1R 候选执行明确标记为长度外推的探索性压力测试。TrioPep 4 个已提交任务保留为补充 provider signal，AF3/ESMFold 保留为 sequence-to-complex 结构对照。
- 2026-07-31 ESMFold/AF3 检查点：从 TrioPep 生产目录只读复制 8.45 GB ESMFold 权重，在隔离环境完成 GLP1R ECD–肽 8 sequences × 3 seeds、3 recycles 的 24/24 正式预测。Mean pTM `0.636`、mean pLDDT `64.99`、峰值分配显存 `8314 MiB`；glucagon 预测 pose 与 4ZGM deposited Semaglutide 坐标的 cross-ligand CA distance 为 `28.619 Å`，该值不再标作 glucagon native-pose RMSD。追加 3GBQ、1CKB、1ABO 三个实验复合物的 9/9 reference runs，平均 peptide CA RMSD `6.526 Å`，仅 1/3 complexes 达到 ≤2 Å（3GBQ `2.123 Å`、1CKB `1.542 Å`、1ABO `15.914 Å`）。AF3 的 8/8 GLP1R-ECD–肽任务完成：mean pair-ipTM `0.755`，Tirzepatide 置信度最高；sequence-mapped Semaglutide 对 4ZGM 的受体对齐肽 CA RMSD 为 `8.133 Å`，native-contact recall/precision 为 `0.882/0.732`。AF3–ESMFold receptor-aligned peptide pose RMSD 平均/最大 `31.513/36.545 Å`，AF3 pair-ipTM 与 ESMFold pTM 的排序相关为 `ρ=-0.119`。这些 confidence 排名只作为有限优先级信号，成功、失败、provider disagreement 与参数敏感性共同限制 sequence-only complex prediction 和 docking accuracy 主张。
- 对应勾选状态见 `FROGENT_experiment_checklist.md`；首轮证据与 claim limits 见 `runtime/evaluation/revision-20260730/nongpu-local/manifest.json`。
- 第二批证据与 claim limits 见 `runtime/evaluation/revision-20260730/nongpu-next/manifest.json`；远端 CPU 细节见 `runtime/evaluation/revision-20260730/nongpu-next/remote/final-manifest.json`。
- 第三批证据、负向结果与未测量边界见 `runtime/evaluation/revision-20260730/nongpu-final/manifest.json`；审稿意见映射见 `docs/manuscript/revision-evidence-ledger.md`。
- ADCP 正式 reference-redocking 矩阵 9/9 完成并独立评分：平均 top-1/top-5/top-10 backbone RMSD 为 `11.262/5.840/4.690 Å`，对应 native-contact recovery 为 `0.271/0.564/0.593`。G0 和 S1 的稿件级重算继续依赖八项 benchmark 样本级输出、scorer、case IDs、seeds、baseline 配置和 figure source tables。De novo generation 的三 seed 主矩阵已完成，六 seed 稳定性扩展已在隔离 resume run 恢复；GLP1R AF3 结构与跨 provider 分析已完成；多肽 docking 按 MDockPeP2 与 ADCP 的真实方法推进。

## 2. 修订主张

FROGENT 的主张先限定为一项待验证的研究假设：

> FROGENT 通过任务分解、基于 evidence 的 context 管理、专业工具路由和 Forge–Gauge 反馈，提高多阶段药物设计任务中的检索质量、科学决策质量与 tool-use reliability。

Matched-resource comparison 与关键组件 CPU 消融为 orchestration 主张提供了受限证据。三项真实生成模型对照和 TrioMol2 study 正在运行；摘要、引言和讨论的最终范围将在 GPU 结果完成后冻结。

## 3. 全局修改位置

| Location ID | Planned manuscript location | 内容 |
|---|---|---|
| M-ABS | Abstract | 任务范围、核心贡献、主要结果、效率主张 |
| M-INT | Introduction | 研究缺口、近期系统、新颖性边界 |
| M-ARCH | Methods — Architecture and orchestration | task decomposition、状态、context、memory、停止与恢复 |
| M-TOOLS | Methods — Agents, tools and models | 每个 Agent 的真实工具、模型、版本和回退 |
| M-BENCH | Methods — Benchmark design | 八项任务 datasheet、权限、评分、评价者 |
| M-STAT | Methods — Statistical analysis | 分析单位、检验、效应量、置信区间、多重校正 |
| M-CONF | Methods — Structure preparation | 小分子与肽构象、受体准备、docking 后处理 |
| M-RES | Results | benchmark、matched-resource comparison、消融、生成与证据实验 |
| M-DISC | Discussion | 贡献范围、tradeoff、限制和适用条件 |
| F-1 | Revised Figure 1 | 能力、Agent、工具和 benchmark 对应关系 |
| F-3 | Revised Figure 3 | 八项任务名称、量纲和结果展示 |
| T-1 | Main Table 1 | 八项任务—Agent—工具—数据—评分—基线 |
| T-2 | Main Table 2 | matched-resource comparison 与架构消融 |
| T-3 | Main Table 3 | 生成模型、构象与 docking 结果 |
| SI-1 | Supplementary Table 1 | Agent、provider、tool、model、version、license、I/O |
| SI-2 | Supplementary Methods 1 | prompts、SOP、预算、重试、停止条件 |
| SI-3 | Supplementary Benchmark Datasheets | 数据来源、样本、gold、评分和泄漏控制 |
| SI-4 | Supplementary Results | 统计全表、失败归因、运行稳定性与成本 |
| SI-5 | Supplementary Traces | 可审计的计划、工具调用、证据和结果轨迹 |

### 3.1 第三批证据到稿件的映射

| Evidence block | 当前结果 | 可支持内容 | 必须保留的边界 |
|---|---|---|---|
| Semantic adjudication + statistics | 28 cases 双评，κ 0.647；统计入口 10/10 tests | M-BENCH、M-STAT、SI-3/4 | 八项 headline results 等待样本级输入 |
| Matched-resource + real-agent ablation | 130/130 worker outputs；Full `9.367/10`；Full–direct `0.067`、Full–single `0.033`、Full–no-context `0.167`；w/o Retrieve `-7.000`、w/o Gauge `-0.800` | M-ARCH、M-RES、T-2、SI-5 | 多 Agent 使用 3 workers；小型 exposed/frozen panel；三项主比较均无强显著优势 |
| Live/structured evidence | live repeat、独立 adjudication、24 structured calls、4/4 propagation | M-ARCH、M-RES、SI-4/5 | ACTT-1 temporal failure 与 DrugBank 403 保持可见 |
| Molecular/docking | property、ADMET、pose/PLIP、5-structure docking、DAVIS screening | M-CONF、M-RES、T-3、SI-4 | docking score 仅作计算信号；DAVIS ρ 0.115 |
| Safety/telemetry | 23/23 safety cases；70 telemetry records | M-TOOLS、M-DISC、SI-1/4 | token、queue 和 energy 为 `not_measured` |
| HLE/baselines/manuscript QA | HLE access protocol、近期系统矩阵、30-item issue ledger | M-INT、M-BENCH、F-3、SI-1/3 | HLE performance 与 baseline numerical reproduction 为 `not_measured` |

## 4. Editor atomic response map

### E-1. 科学新颖性和架构贡献

- Paraphrase：稿件尚未证明 FROGENT 相对现有集成系统的科学新颖性，也未隔离 orchestration 的贡献。
- Triage：`high-risk criticism`
- Taxonomy：citation or positioning；evidence or interpretation
- Severity：`blocking`
- Decision：agree
- Action：补充近期系统定位；完成 matched-resource comparison、架构消融和底层生成模型对照；根据结果限定主张。
- Outcome：`revised_in_both`
- Evidence：S2、S3
- Planned locations：M-ABS、M-INT、M-RES、M-DISC、T-2、T-3

### E-2. 方法透明度与可复现性

- Paraphrase：Agent、模型、prompt、工具、运行规则和复现实例需要系统说明。
- Triage：`evidence gap`
- Taxonomy：methodological；data, code, or materials
- Severity：`major`
- Decision：agree
- Action：发布可验证的配置表、SOP、prompt、版本化代码入口和最小复现实例；删除凭据与受限信息。
- Outcome：`revised_in_both`
- Evidence：G0、D1
- Planned locations：M-ARCH、M-TOOLS、SI-1、SI-2

### E-3. 八项 benchmark 的定义和验证

- Paraphrase：八项任务的名称、输入、gold、评分、评价者、最大分和绝对质量需要严格核查。
- Triage：`high-risk criticism`
- Taxonomy：methodological；statistical
- Severity：`blocking`
- Decision：agree
- Action：完成全量样本级审计、评分修正、泄漏检查和重新计算；评分口径变化时重新生成主结果。
- Outcome：`revised_in_both`
- Evidence：G0、S1
- Planned locations：M-BENCH、M-STAT、F-3、T-1、SI-3、SI-4

### E-4. Baseline、公平性和消融

- Paraphrase：需要资源匹配的 baseline 和能隔离关键组件的消融。
- Triage：`high-risk criticism`
- Taxonomy：evidence or interpretation；methodological
- Severity：`blocking`
- Decision：agree
- Action：在相同模型、工具、数据和预算下进行直接工具、单 Agent、关键组件消融和完整 FROGENT 比较。
- Outcome：`revised_in_both`
- Evidence：S2
- Planned locations：M-BENCH、M-RES、T-2、SI-4

### E-5. 稿件与 Agent 行为不一致

- Paraphrase：论文中的工具和能力声明必须与真实部署一致。
- Triage：`high-risk criticism`
- Taxonomy：data, code, or materials
- Severity：`blocking`
- Decision：agree
- Action：完成声明—provider—endpoint—测试结果矩阵；能力保持 live、deferred、case-study-only 或 removed 四种明确状态。
- Outcome：`revised_in_both`
- Evidence：G0
- Planned locations：M-TOOLS、F-1、SI-1

### E-6. 内容重复

- Paraphrase：重复架构和工作流叙述应压缩，为方法和验证留出篇幅。
- Triage：`clarity problem`
- Taxonomy：editorial or presentation
- Severity：`minor`
- Decision：agree
- Action：正文保留核心逻辑；完整 SOP、prompt、工具清单和轨迹移入 SI。
- Outcome：`revised_in_both`
- Planned locations：全文、SI-1、SI-2、SI-5

## 5. Reviewer 1 atomic response map

### R1-0a. 新颖性相对近期文献不足

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：补充 Prompt-to-Pill、CLADD、Robin 及检索截止日前的相关系统；完成能力矩阵和可执行子集比较。
- Outcome：`revised_in_both`
- Evidence：S2、D2
- Planned locations：M-INT、M-DISC、SI-1

### R1-0b. Few-shot 或微调信息不足

- Triage：`clarity problem`
- Severity：`major`
- Decision：agree
- Action：核实参数更新事实；分别使用 fine-tuning、few-shot prompting 或 in-context learning 的准确术语，报告示例来源、数量和防泄漏检查。
- Outcome：`revised_in_both`
- Evidence：G0
- Planned locations：M-TOOLS、SI-2

### R1-0c. Benchmark 方法和可复现性不足

- Triage：`evidence gap`
- Severity：`blocking`
- Decision：agree
- Action：与 E-2、E-3 联动完成。
- Outcome：`revised_in_both`
- Evidence：G0、S1
- Planned locations：M-BENCH、M-STAT、SI-3、SI-4

### R1-0d. Agent 输出与稿件存在差异

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：与 E-5 联动完成，不以单次聊天回答代替真实 capability audit。
- Outcome：`revised_in_both`
- Evidence：G0
- Planned locations：M-TOOLS、F-1、SI-1

### R1-0e. 内容重复

- Triage：`clarity problem`
- Severity：`minor`
- Decision：agree
- Action：与 E-6 联动完成。
- Outcome：`revised_in_both`
- Planned locations：全文

### R1-1a. 双空格、拼写和语法

- Triage：`clarity problem`
- Severity：`minor`
- Decision：agree
- Action：运行全文检查并人工复核。
- Outcome：`revised_in_both`
- Planned locations：全文

### R1-1b. 粘连词

- Triage：`clarity problem`
- Severity：`minor`
- Decision：agree
- Action：修复 `agentfunctions` 等粘连词。
- Outcome：`revised_in_both`
- Planned locations：全文

### R1-1c. Figures 8–9 与 “provided below” 不一致

- Triage：`clarity problem`
- Severity：`minor`
- Decision：agree
- Action：改为稳定的 figure number 引用，并核对排版后位置。
- Outcome：`revised_in_both`
- Planned locations：Figures 8–9 附近正文

### R1-2. 八项任务缺少统计显著性

- Triage：`high-risk criticism`
- Taxonomy：statistical
- Severity：`major`
- Decision：agree
- Action：预先定义分析单位、primary contrasts、exact/paired test、效应量、95% CI 和 Holm family；小样本不报告不稳定的高分位数。
- Outcome：`revised_in_both`
- Evidence：S1
- Planned locations：M-STAT、M-RES、SI-4

### R1-3a. Luteolin 是 DrugBank 已知候选

- Triage：`high-risk criticism`
- Severity：`major`
- Decision：agree
- Action：将其定位为 known-candidate retrieval/evidence integration 案例；删除 “rediscovered” 和新发现含义。
- Outcome：`revised_in_both`
- Evidence：S4
- Planned locations：M-RES、M-DISC

### R1-3b. 已知候选缺少引用

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：为候选提供可核验来源、数据库版本、访问日期、证据类型和唯一标识符。
- Outcome：`revised_in_both`
- Evidence：S4
- Planned locations：M-RES、SI-5

### R1-3c. 生成分子与已知抑制剂的相似性

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：报告标准化后的最近邻、ECFP4 Tanimoto、scaffold overlap、训练集近邻和靶点活性物近邻。
- Outcome：`revised_in_both`
- Evidence：S3
- Planned locations：M-RES、T-3、SI-4

### R1-3d. 禁用 DrugBank 的文献驱动重定位

- Triage：`evidence gap`
- Severity：`major`
- Decision：partially agree
- Action：完成小型预注册 study，评估 evidence-supported prioritization、citation support 和 hallucination。避免把文献推断写成已验证疗效。
- Outcome：`revised_in_both`
- Evidence：S4
- Planned locations：M-RES、M-DISC、SI-4

### R1-4a. 遗漏 Prompt-to-Pill、CLADD 和 Robin

- Triage：`high-risk criticism`
- Severity：`major`
- Decision：agree
- Action：补充文献和能力矩阵。
- Outcome：`revised_in_both`
- Evidence：D2
- Planned locations：M-INT、M-DISC

### R1-4b. 首创性主张过强

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：删除无法核验的 `first`；根据完成的证据改写成范围明确的差异化主张。
- Outcome：`revised_in_both`
- Planned locations：M-ABS、M-INT、M-DISC

### R1-4c. 近期系统是否加入 benchmark

- Triage：`scope mismatch`
- Severity：`major`
- Decision：partially agree
- Action：代码、输入输出和评价器可公平对齐时运行比较；其余系统提供能力级比较并说明不可执行原因，不把缺失记为零分。
- Outcome：`revised_in_both`
- Evidence：D2
- Planned locations：M-BENCH、M-RES、SI-4

### R1-5a. 小分子和肽构象如何生成

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：记录真实 sequence/SMILES-to-3D、质子化、互变异构体、采样、最小化、受体准备和 docking 流程。
- Outcome：`revised_in_both`
- Evidence：G0、S3
- Planned locations：M-CONF、SI-1

### R1-5b. Glucagon 二级结构来源与验证

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：提供 Glucagon 真实调用轨迹；用结构数据库或文献参考验证，并对小型参考肽集报告 agreement 和结构误差。
- Outcome：`revised_in_both`
- Evidence：S3
- Planned locations：M-CONF、M-RES、SI-5

### R1-5c. 3D 生成后再次 docking 的必要性

- Triage：`high-risk criticism`
- Severity：`major`
- Decision：agree
- Action：比较 raw pose、局部最小化和 redocking 的 clash、位移、RMSD、score 和 PLIP interaction retention；依据结果保留、限定或移除统一 redocking。
- Outcome：`revised_in_both`
- Evidence：S3
- Planned locations：M-CONF、M-RES、T-3

### R1-6. 缺少每个 Agent 的资源、工具和模型清单

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：SI 提供 Agent、provider、版本、license、I/O、关键参数、访问条件、失败和回退；不发布凭据。
- Outcome：`revised_in_both`
- Evidence：G0、D1
- Planned locations：M-TOOLS、SI-1、SI-2

### R1-7. Algorithm 1 的 memory 和 synthesis 不清楚

- Triage：`clarity problem`
- Severity：`major`
- Decision：agree
- Action：按真实实现重写状态更新和 synthesis 伪代码；区分 transient run state、working memory 和持久 memory；声明 evidence admission、冲突、撤回和终止规则。
- Outcome：`revised_in_both`
- Evidence：G0
- Planned locations：M-ARCH、SI-5

### R1-8a. HLE 主观题如何评分

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：核对原评测协议；客观题按确定性规则，主观题按盲法双评或经过人工校准的独立 judge；报告 rubric、一致性和分歧解决。
- Outcome：`revised_in_both`
- Evidence：G0、S1
- Planned locations：M-BENCH、SI-3

### R1-8b. QED 被错误视为预测任务

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：将 RDKit QED 从 property-prediction accuracy 中移出；如保留，只作为 tool-call/parse reliability 单独报告，并重新计算受影响结果。
- Outcome：`revised_in_both`
- Evidence：G0、S1
- Planned locations：M-BENCH、F-3、T-1、SI-3

### R1-8c. Virtual screening 可能只测工具调用

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：定义任务真实目标；共享同一 docking backend 和预算，比较 direct tool、baseline agents 和 FROGENT；逐例解释零分。
- Outcome：`revised_in_both`
- Evidence：S2
- Planned locations：M-BENCH、M-RES、T-2

### R1-8d. SA 指标方向写反

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：修正正文、图例和评分代码；审计所有样本并重新计算受影响结果。
- Outcome：`revised_in_both`
- Evidence：G0、S1
- Planned locations：M-BENCH、F-3、SI-3

### R1-8e. 逆合成路线正确性如何判定

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：全量计分使用统一规则；若 headline score 依赖人工判断，对全部计分样本进行盲法双评。专家抽样只用于验证自动评分器。
- Outcome：`revised_in_both`
- Evidence：S1
- Planned locations：M-BENCH、SI-3、SI-4

### R1-9a. 最终报告无法下载

- Triage：`scope mismatch`
- Severity：`minor`
- Decision：agree
- Action：本轮提供 Markdown、PDF 和 Word 导出，并验证下载文件可打开、内容与当前 run 一致。
- Outcome：`revised_in_both`
- Planned locations：M-DISC 或 revised interface

### R1-9b. 缺少分子可视化和结构下载

- Triage：`scope mismatch`
- Severity：`minor`
- Decision：agree
- Action：本轮提供结构文件下载并接入 Mol*、JSmol 或等价 viewer，完成代表性分子与复合物的可视化 smoke test。
- Outcome：`revised_in_both`
- Planned locations：M-DISC 或 revised interface

### R1-9c. 安全 guardrails 应在稿件中说明

- Triage：`evidence gap`
- Taxonomy：ethics or compliance
- Severity：`major`
- Decision：agree
- Action：描述真实安全边界、拒绝策略、日志和人工复核；任何有效性主张都附带代表性测试。
- Outcome：`revised_in_both`
- Evidence：D3
- Planned locations：M-ARCH、M-DISC、SI-4

### R1-9d. 肽构象能力和完成时间

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：突出可验证的肽 workflow，报告前端响应、任务提交和完整计算的独立时延。
- Outcome：`revised_in_both`
- Evidence：S3、X1
- Planned locations：M-RES、SI-4

### R1-9e. MDockPeP2、ADCP 与稿件 provider 一致性

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：核实 MDockPeP2 与 ADCP 的实际调用、版本、输入、采样、输出和回退；修正论文、prompt、图或部署声明。
- Current status：用户确认 MDockPeP2 与 ADCP 为正式多肽对接方法。MDockPeP2 endpoint、source、三次历史输出和隔离运行条件已核实；prospective rerun 受 Modeller license 限制。ADCP 未出现在两个声明的生产目录或 `/work` 文件名盘点中；官方 ADCP 0.0.25 / v1.1.21 隔离 runtime、三套 AGFR target 和三例 a07 canary 已验证，正式 3 complexes × 3 seeds、每任务 100 replicas 的 reference-redocking 矩阵 9/9 完成。独立 receptor-frame 评分得到平均 top-1/top-5/top-10 backbone RMSD `11.262/5.840/4.690 Å`，native-contact recovery `0.271/0.564/0.593`，支持保留“top-k 采样可部分恢复界面、原始 ranking 仍弱”的限定结论。TrioPep/AF3 只承担补充 provider/结构证据。
- Outcome：`revised_in_both`
- Evidence：G0
- Planned locations：M-TOOLS、F-1、SI-1

### R1-9f. rDock 声明与 RNA–ligand 实际能力不一致

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：核实 endpoint 和最小 smoke test；将其标记为 live、deferred 或 removed。
- Current status：两个声明的生产目录中未发现 rDock 安装、endpoint 或 checkpoint，无法执行真实 smoke test；论文中的 rDock 与 RNA–ligand live-capability 声明标记为 `removed_unverified`。
- Outcome：`revised_in_both`
- Evidence：G0
- Planned locations：M-TOOLS、F-1、SI-1

## 6. Reviewer 2 atomic response map

### R2-1a. 贡献、pipeline 和 accuracy 指标含糊

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：建立 claim–evidence table，定义每个任务、比较对象和 primary metric；摘要仅保留有结果支持的主张。
- Outcome：`revised_in_both`
- Planned locations：M-ABS、M-INT、T-1

### R2-1b. Efficiency 主张缺少证据

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：统一记录 wall time、token、调用、重试和本地资源；闭源云端能耗记为 `not_measured`。证据不足时删除效率提升主张。
- Outcome：`revised_in_both`
- Evidence：X1
- Planned locations：M-ABS、M-RES、SI-4

### R2-2a. 系统能力与正式评测未分开

- Triage：`clarity problem`
- Severity：`major`
- Decision：agree
- Action：每项能力标记 benchmark-evaluated、case-study-only、supported-unassessed 或 deferred。
- Outcome：`revised_in_both`
- Planned locations：F-1、T-1、M-DISC

### R2-2b. 图 11 和其他 workflow 缺少 benchmark 映射

- Triage：`clarity problem`
- Severity：`major`
- Decision：agree
- Action：为每个 workflow 指向 benchmark 和结果；缺少定量评测时改称 illustrative case 或从主张中移出。
- Outcome：`revised_in_both`
- Planned locations：workflow figures、T-1

### R2-3a. Agent 价值与底层工具能力未分离

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：matched-resource comparison 与 architecture ablation。
- Outcome：`revised_in_both`
- Evidence：S2
- Planned locations：M-RES、T-2

### R2-3b. 工具失败与 Agent 错误未区分

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：用互斥标注手册区分 planning、routing、parameter、tool、parse、evidence、hallucination 和 synthesis errors，并报告一致性。
- Outcome：`revised_in_both`
- Evidence：S2
- Planned locations：M-RES、SI-4

### R2-3c. 每项实验的最高分不清

- Triage：`clarity problem`
- Severity：`major`
- Decision：agree
- Action：分别报告 scoring maximum、direct-tool baseline 和 adjudicated reference；避免把 direct-tool 结果称为理论上限。
- Outcome：`revised_in_both`
- Evidence：S1、S2
- Planned locations：M-BENCH、T-1、SI-3

### R2-4. 时间、资源、成本和能耗

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：执行 X1；远端或闭源服务无法测量的能耗明确记为 `not_measured`。
- Outcome：`revised_in_both`
- Evidence：X1
- Planned locations：M-RES、SI-4

### R2-5. 固定 SOP 与动态规划的边界

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：公开固定步骤、分支和停止规则；在少量上下文变化与工具故障情境中比较 fixed workflow 和 dynamic planning。
- Outcome：`revised_in_both`
- Evidence：S2
- Planned locations：M-ARCH、M-RES、SI-2、SI-4

### R2-6. Agentic baseline 配置不完整

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：报告模型、prompt、上下文、工具、预算、重试和停止规则；区分 matched-resource 与 native-capability 结果。
- Outcome：`revised_in_both`
- Evidence：G0、S2
- Planned locations：M-BENCH、SI-1、SI-2

### R2-7a. 八项任务名称不一致

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：统一 Figure 1、Figure 3、正文、数据和代码中的名称；HLE 仅保留真实含义。
- Outcome：`revised_in_both`
- Evidence：G0
- Planned locations：F-1、F-3、M-BENCH

### R2-7b. 分数尺度和绝对质量难以解释

- Triage：`clarity problem`
- Severity：`major`
- Decision：agree
- Action：报告 raw score、maximum、normalized score、sample size、simple baseline 和 CI；雷达图仅作概览。
- Outcome：`revised_in_both`
- Evidence：S1
- Planned locations：F-3、T-1、SI-4

### R2-8a. 交叉引用过多

- Triage：`clarity problem`
- Severity：`minor`
- Decision：agree
- Action：核心方法在正文自洽呈现；SI 承载完整细节；核对全部编号。
- Outcome：`revised_in_both`
- Planned locations：全文

### R2-8b. 承诺的 SOP 和 prompts 缺失

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：补充实际使用的版本化 prompt 和 SOP；去除凭据、token 和受限 endpoint。
- Outcome：`revised_in_both`
- Evidence：D1
- Planned locations：SI-2

### R2-9a. 代码链接失效

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：从干净环境验证主仓库、安装入口、最小示例和数据访问。
- Outcome：`revised_in_both`
- Evidence：G0、D1
- Planned locations：Code Availability、SI-1

### R2-9b. 单盲评审下匿名链接缺少必要性

- Triage：`clarity problem`
- Severity：`minor`
- Decision：agree
- Action：按期刊政策提供主 GitHub 地址和版本化 release；删除失效匿名跳转。
- Outcome：`revised_in_both`
- Planned locations：Code Availability

## 7. Reviewer 3 atomic response map

### R3-M1. HLE 身份和 Figure 3 标签冲突

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：与 R1-8a、R2-7a 联动完成；说明来源、构建、许可、版本和评分。
- Outcome：`revised_in_both`
- Evidence：G0、S1
- Planned locations：M-BENCH、F-3、SI-3

### R3-M2a. 结构化数据库权限造成资源不公平

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：matched-resource、literature-only 和 FROGENT w/o structured DB 对照。
- Outcome：`revised_in_both`
- Evidence：S2
- Planned locations：M-RES、T-2

### R3-M2b. Retrieve 的查询、解析和整合机制不透明

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：报告 query construction、entity normalization、API parsing、deduplication、evidence merging 和 recovery。
- Outcome：`revised_in_both`
- Evidence：G0、S2
- Planned locations：M-ARCH、M-TOOLS、SI-5

### R3-M3. 检索可靠性、不确定性和冲突处理

- Triage：`high-risk criticism`
- Severity：`major`
- Decision：agree
- Action：在一致、冲突、过时和缺失 evidence 的小型真实任务集上测试 citation support、conflict detection、uncertainty calibration 和 downstream propagation。
- Outcome：`revised_in_both`
- Evidence：S4
- Planned locations：M-ARCH、M-RES、SI-4

### R3-M4. Orchestration 相对工具和数据库的贡献

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：direct tool、single Agent、multi-agent w/o working context 与 Full FROGENT 的 matched-resource comparison。
- Current result：Full–direct `0.067/10`、Full–single `0.033/10`、Full–no-context `0.167/10`；Full–no-context 的 95% CI 为 `[0.000, 0.333]`。三项主比较均不支持宽泛 superiority 表述。
- Outcome：`revised_in_both`
- Evidence：S2
- Planned locations：M-RES、T-2

### R3-M5a. Retrieve Agent 消融

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：仅在依赖检索的任务上运行 w/o Retrieve。
- Current result：5 个适用 cases 的 paired difference 为 `7.000/10`，95% CI `[5.200, 8.500]`，wins/ties/losses `5/0/0`。
- Outcome：`revised_in_both`
- Evidence：S2
- Planned locations：M-RES、T-2

### R3-M5b. Gauge Agent 消融

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：仅在设计和筛选任务上运行 w/o Gauge。
- Current result：5 个适用 cases 的 paired difference 为 `0.800/10`，95% CI `[0.000, 1.600]`，wins/ties/losses `3/1/1`。
- Outcome：`revised_in_both`
- Evidence：S2、S3
- Planned locations：M-RES、T-2、T-3

### R3-M5c. Forge–Gauge 迭代消融

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：single-pass 与 iterative loop 比较，记录每轮反馈、候选变化和停止原因。
- Current status：TrioMol2 15 个共同预算任务已提交，固定池、single-pass 和最多三轮 iterative 分析协议已冻结；首任务运行中，其余排队。
- Outcome：`revised_in_both`
- Evidence：S3
- Planned locations：M-RES、T-3、SI-5

### R3-M5d. Global-context 消融

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：先由 G0 确认真实 context/memory 实现，再设计保留工具和预算的消融。
- Current result：Full–no-context 为 `0.167/10`，95% CI `[0.000, 0.333]`；资源差异已明确记录为三个 workers 对一个 worker。
- Outcome：`revised_in_both`
- Evidence：G0、S2
- Planned locations：M-ARCH、M-RES、T-2

### R3-M6. De novo generation 的底层模型贡献

- Triage：`high-risk criticism`
- Severity：`blocking`
- Decision：agree
- Action：仅纳入真实部署且可复现的生成模型；在相同 pocket、sample count、post-processing、evaluator 和 compute budget 下比较独立模型、固定最佳模型、单轮选择和 Forge–Gauge 迭代。
- Current status：TargetDiff、Pocket2Mol、DiffSBDD checkpoint 与可执行 snapshot 已核实；45 个正式独立模型任务已在 6 张 RTX 4090 上启动。PocketFlow 与 MolCRAFT 未在用户指定的两个生产目录中发现 checkpoint，保持缺失资产记录。
- Outcome：`revised_in_both`
- Evidence：G0、S3
- Planned locations：M-RES、T-3、SI-4

### R3-m1. Task decomposition 的随机性

- Triage：`evidence gap`
- Severity：`major`
- Decision：agree
- Action：重复运行代表性样本，报告 task success、score CI、plan/tool sequence variation、model version、temperature、cache 和 retry。
- Outcome：`revised_in_both`
- Evidence：S2
- Planned locations：M-ARCH、M-RES、SI-4

### R3-m2. `agentfunctions` 拼写

- Triage：`clarity problem`
- Severity：`minor`
- Decision：agree
- Action：改为 `The Retrieve agent functions ...` 并纳入全文检查。
- Outcome：`revised_in_both`
- Planned locations：对应正文

### R3-m3. Figure 1 中 BioData 被裁切

- Triage：`clarity problem`
- Severity：`minor`
- Decision：agree
- Action：调整画布和导出边界，按最终栏宽核对 PDF/SVG。
- Outcome：`revised_in_both`
- Planned locations：F-1

## 8. 作者必须确认的决策

| ID | 决策 | 影响 |
|---|---|---|
| A-1 | 参数微调、few-shot prompting 和 in-context learning 的真实使用方式 | R1-0b、方法与泄漏审计 |
| A-2 | 八项 benchmark 的原始数据、评分脚本和 Figure 1/3 对应关系 | 所有 headline results |
| A-3 | 每个 Agent 和 provider 的真实 live/deferred 状态 | R1-9e/f、R2-2、R3-M6 |
| A-4 | 是否有两名独立评价者完成 HLE 主观题和逆合成评分 | S1 |
| A-5 | 可执行的近期系统和生成模型范围 | D2、S3 |
| A-6 | 已决定：Markdown/PDF/Word 导出、结构下载和 3D viewer 全部纳入本轮 | R1-9a/b |
| A-7 | 已决定：内部完成日为 2026-08-12 | 两周冲刺 |

## 9. 回复信写作模板

每个 atomic comment 使用以下结构：

```text
Comment [ID]
[Reviewer comment or faithful paraphrase]

Response
We agree / partially agree / respectfully disagree that [precise issue].
We have [concrete action]. [Primary result with effect size and uncertainty, when applicable.]
We have therefore [retained / narrowed / removed] the claim that [claim].

Changes in the manuscript
- Section [name], page [x], lines [y–z]: [specific edit]
- Table/Figure [identifier]: [specific result]
- Supplementary [identifier]: [methods, prompts, logs, or full results]
```

在实验完成前使用 planned response，不写 “we have added” 或具体结果。正文完成后再将时态改为已完成，并填入精确位置。

## 10. Readiness transitions

1. `blocked`：G0 未完成，benchmark、能力或主张仍存在事实冲突。
2. `needs_author_input`：G0 完成，A-1 至 A-7 仍有关键决策。
3. `draft_with_placeholders`：实验设计冻结，正文正在修改，结果或位置仍待填写。
4. `ready_to_submit`：全部 atomic comments 有明确 outcome；正文、clean copy、marked copy、SI、代码链接和在线表格完成独立核对。
