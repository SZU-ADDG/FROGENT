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
- 2026-08-01 20:47 GPU 进度检查点：2HYY 的 6/6 TargetDiff/DiffSBDD 扩展 jobs 全部 exit zero，resume run 达到 12/30 terminal-success、12 running、6 unstarted、0 failed。2HYY 三个新 seeds 中 TargetDiff 得到 `436/450/449` 个 valid molecules，DiffSBDD 得到 `108/85/103` 个 valid molecules。12 个 workers 当前并行处理 3CS9 与 4WA9，worker stderr 均为 0；GPU 1/3/4/5/6/7 利用率均为 `100%`、显存约 `6.9–7.0 GiB`，finalizer 存活。运行卷剩余约 429 GB。TrioMol2 保持 2 succeeded、1 running、12 queued，TrioPep 保持 4 queued，两个服务器 poller 均存活且下载失败数为 0。
- 2026-08-01 21:49 持续运行检查点：resume run 维持 12/30 terminal-success、12 running、6 unstarted、0 failed，3CS9 与 4WA9 的 12 个 jobs 持续真实推理。12 个 workers、finalizer 和两个 Trio server pollers 均存活，worker stderr 与 Trio 下载失败数均为 0。GPU 1/3/4/5/6/7 利用率 `99–100%`、显存约 `6.9–7.0 GiB`；GPU 0 的 TrioMol2/既有服务与 GPU 2 的第三方服务保持原进程归属。运行卷剩余约 429 GB。TrioMol2 保持 2 succeeded、1 running、12 queued，TrioPep 保持 4 queued。
- 2026-08-01 23:50 GPU 进度检查点：resume run 达到 26/30 terminal-success、4 running、0 unstarted、0 failed。3CS9 与 4WA9 的 12 个扩展 jobs 全部 exit zero；3CS9 的 TargetDiff/DiffSBDD valid molecules 为 `412/418/462` 与 `71/54/84`，4WA9 为 `495/495/498` 与 `168/134/153`。1M17 已有两个 TargetDiff jobs terminal-success，其余 4 个 jobs 在 GPU 3/4/5/7 继续运行；GPU 1/6 已释放，finalizer 存活。TrioMol2 推进至 3 succeeded、1 running、11 queued，TrioPep 保持 4 queued，两个服务器 poller 均存活且下载失败数为 0。并行启动 CPU-only `gpu-followup-20260801/cbgbench-novelty-pocket-r01/`，按冻结协议分析 45/45 primary jobs 的 identity uniqueness、Bemis–Murcko scaffold、同 pocket 参考配体 ECFP4 距离和几何 pocket compatibility；训练集与已知活性物最近邻保持 `not_measured`，等待版本化 comparison collections。
- 2026-08-01 23:55 novelty/pocket 终态：CPU-only `cbgbench-novelty-pocket-r01` 完成 45/45 primary jobs、9,825 个生成 SDF；9,767 个解析成功，58 个 molecule-level parse failures 作为输入质量证据保留。TargetDiff、DiffSBDD、Pocket2Mol 的 identity uniqueness 为 `1.000/1.000/0.965`，unique scaffold per parsed molecule 为 `0.997/0.866/0.458`；相对同 pocket 参考配体的 mean ECFP4 Tanimoto 为 `0.093/0.065/0.055`，三个模型均无 exact identity、reference scaffold match 或 Tanimoto ≥0.5。10 Å pocket-compatible rate 均为 `1.000`；severe receptor-clash-free rate 为 `1.000/0.942/0.996`，DiffSBDD 在 1M17 为最低的 `0.854`。该结果支持局部结构多样性与 pocket geometry 描述，并将训练集/已知活性物 novelty 保持为 `not_measured`。TrioMol2 第三个成功任务的 16 个 artifacts 已全部验证，累计 48/48。
- 2026-08-02 00:51 CBGBench 扩展终态：30/30 resume jobs 全部 exit zero，暂停源继承的 15 个 Pocket2Mol jobs 与 30 个 TargetDiff/DiffSBDD jobs 组成完整 45/45 extension matrix；`final-manifest.json` 与 `combined-six-seed-manifest.json` 均已生成并通过 45/45、90/90 terminal-success 验证。六张实验 GPU 已释放，GPU 0 与 GPU 2 的既有服务保持原进程归属。
- 2026-08-02 00:55 六 seed 稳定性结论：独立 `gpu-followup-20260802/cbgbench-six-seed-stability-r01/` 完成 90/90 jobs 的 model–pocket–seed 分析。三项模型排序在 primary、extension 和 pooled 中保持一致：valid rate 与 QED 均为 TargetDiff > DiffSBDD > Pocket2Mol，SA 由易到难为 Pocket2Mol < TargetDiff < DiffSBDD。Primary-versus-pooled model–pocket rank correlation 为 valid rate `ρ=0.993`、QED `ρ=0.971`、SA `ρ=0.704`。TargetDiff primary→pooled 的 QED 为 `0.458→0.408`、valid rate 为 `0.968→0.949`；extension-minus-primary 的 pocket-cluster 95% CI 分别为 `[-0.188,-0.004]` 与 `[-0.073,-0.006]`，绝对性能存在 seed sensitivity。DiffSBDD QED/valid rate 为 `0.234→0.211`、`0.241→0.236`，Pocket2Mol 为 `0.128→0.129`、`0.100→0.102`。逐 pocket 最大变化集中在 TargetDiff 的 2HYY/3CS9；全部 reconstruction errors 为低频 `AtomValenceException`，最高为 extension DiffSBDD–3CS9 的 `11/1500=0.73%`，未造成 job failure。论文可保留模型相对排序和 TargetDiff 的 valid/QED优势，同时报告绝对值对 seed 的敏感性；三 seed结果继续作为 primary，六 seed pooled 作为 post-outcome stability extension。
- 2026-08-02 02:05 ChEMBL known-active 终态：CPU-only `gpu-followup-20260802/cbgbench-known-active-neighbors-r03/` 对 9,767 个已解析 primary 分子完成 target-matched nearest-neighbor 分析。版本记录为 ChEMBL 37（release 2026-05-01）；冻结条件为 human single-protein target、binding IC50、nM、relation `=`、standard flag、pChEMBL ≥6，得到 ABL1 1,653 个与 EGFR 8,072 个 canonical actives。TargetDiff、DiffSBDD、Pocket2Mol 的 mean nearest-active ECFP4 Tanimoto 为 `0.176/0.143/0.120`，最大值为 `0.405/0.256/0.217`；9,767/9,767 均低于 0.5。Typed-Boolean 修正后 exact active-scaffold overlap 为 TargetDiff `2/7253=0.028%`、DiffSBDD `0/1771`、Pocket2Mol `1/743=0.135%`，合计 `3/9767=0.031%`。该结果支持相对本次冻结 ChEMBL 强活性集合的低结构相似性；generator training-set novelty 与其他数据库/assay 类型的穷尽性继续标记 `not_measured`。r01 的协议时间字段错误与 r02 的 aggregate Boolean 类型错误均保留为失败证据，稿件固定引用 r03。
- 2026-08-02 03:16 持续巡检与训练集合扩展：CBGBench resume/extension/combined manifests 继续通过 45/45 与 90/90 terminal-success，六张实验 GPU 保持空闲；GPU 0 的 TrioMol2/既有服务与 GPU 2 的第三方服务保持原进程归属，运行卷剩余约 429 GB。TrioMol2 仍为 3 succeeded、1 running、11 queued，48/48 已完成 artifacts 验证；TrioPep 仍为 4 queued，两个 poller 均存活且 download failures 为 0。为直接关闭 R1-3c 的 training-set nearest-neighbor 缺口，冻结 `cbgbench-crossdocked-training-proxy-r03`：使用 CBGBench 配置声明的 CrossDocked2020 train split、公开数据 revision `87ca3754...` 和安全 pickle-opcode SMILES 提取。r01/r02 输入传输失败证据保留；r03 的 3.76 GB LMDB 正在压缩传输，完成字节数验证后将自动启动 32-worker CPU analysis。该集合在缺少 checkpoint 原始数据 digest 时明确标记为 declared-training-corpus proxy。
- 2026-08-02 03:26 CrossDocked training-proxy 终态：`gpu-followup-20260802/cbgbench-crossdocked-training-proxy-r04/` 完成公开 revision `87ca3754...` 的 executable train membership 分析。公开 split 声明 100,000 个 train names，其中 99,990 个按 CBGBench dataloader 语义映射至 processed LMDB，覆盖率 99.99%；安全 opcode 提取 99,990/99,990 成功，去重为 10,404 个 canonical training-proxy molecules。9,767/9,767 个生成分子均无 exact canonical identity；TargetDiff、DiffSBDD、Pocket2Mol 的 mean nearest-train ECFP4 Tanimoto 为 `0.216/0.189/0.203`，最大值为 `0.453/0.682/0.474`，仅 DiffSBDD 有 `1/1771` 个分子达到 ≥0.5，全部低于 0.7。Exact training-proxy scaffold overlap 为 `56/7253=0.772%`、`133/1771=7.510%`、`116/743=15.612%`，说明 fingerprint-level identity/高相似性很低，同时 Pocket2Mol 与 DiffSBDD 存在需要披露的 scaffold reuse。r01/r02 为输入传输失败，r03 因过严 completeness check 停在 incomplete；r04 对齐实际 loader membership 后成为 final。Checkpoint 原始 training-file digest 与未公开 pretraining/fine-tuning corpora继续保持未确认。远端 final manifest 验证后，本地 3.80 GB 临时传输输入已通过 dry-run、路径、进程与恢复检查清理；远端 final evidence 和公开版本化来源均保留。
- 2026-08-02 03:31 终态复核：ChEMBL r03 与 CrossDocked training-proxy r04 final manifests 均保持 `complete`，CBGBench 已完成矩阵未重复提交。GPU 1/3/4/5/6/7 空闲；GPU 0 的 TrioMol2/既有服务使用约 10.1 GiB，GPU 2 的第三方服务使用约 24.1 GiB，进程归属未改变；运行卷剩余约 406 GB。TrioMol2 保持 3 succeeded、1 running、11 queued，48 个 artifacts 已验证且 download failures 为 0；TrioPep 保持 4 queued、0 download failures，两个 15 分钟服务器 poller 均存活。
- 2026-08-02 03:51 持续巡检：CBGBench resume 30/30 与暂停源 15/15 exit zero，final/combined manifests 继续通过 45/45 与 90/90；30 个 resume stderr 仅含已计入 manifest 的低频 molecule reconstruction warnings，未发现 traceback、OOM、runtime error、segmentation fault 或 killed。GPU 1/3/4/5/6/7 空闲，GPU 0/2 原进程归属保持不变，运行卷剩余约 406 GB。TrioMol2 保持 3 succeeded、1 running、11 queued，48 个 artifacts 已验证；TrioPep 保持 4 queued，两个 poller 均存活且 download failures 为 0。R1-3c 的 ECFP4、scaffold、training-proxy 和 target-active checklist 条目已按三个 versioned final analyses 闭合；checkpoint-exact 与未披露训练语料继续列为范围边界。
- 2026-08-02 04:51 持续巡检：CBGBench resume 30/30 与暂停源 15/15 继续保持 exit zero，45/45 extension 与 90/90 combined manifests 未变化，stderr 未发现 fatal pattern。GPU 1/3/4/5/6/7 空闲，GPU 0/2 保持既有进程归属，运行卷剩余约 406 GB。TrioMol2 保持 3 succeeded、1 running、11 queued；当前 2HYY seed 17 task 位于 progress 3/5，其运行进程持续使用 CPU 且仍持有已登记 GPU context，未见终态或失败事件。TrioPep 保持 4 queued；两个服务器 poller 均存活，48 个已完成 artifacts 校验有效且 download failures 为 0。当前无新增终态、失败、恢复动作或主张变化，未重复启动已闭合实验。
- 2026-08-02 05:52 持续巡检：CBGBench resume 与 carried jobs 继续为 30/30、15/15 exit zero，extension/combined manifests 保持 45/45、90/90，fatal stderr count 为 0。GPU 1/3/4/5/6/7 空闲；GPU 0 的既有服务与 TrioMol2 task 合计使用约 10.6 GiB，GPU 2 的第三方进程使用约 24.1 GiB，进程归属未改变；运行卷剩余约 406 GB。TrioMol2 保持 3 succeeded、1 running、11 queued，2HYY seed 17 task 仍为 progress 3/5，其进程持续使用约 132% CPU 并持有 GPU context；TrioPep 保持 4 queued。两个 poller 存活，48 个 artifacts 校验有效且 download failures 为 0。本轮无新终态、失败、恢复动作或主张变化，未重复提交已闭合 panel。
- 2026-08-02 06:53 持续巡检：CBGBench resume/carried jobs 与 45/45 extension、90/90 combined manifests 继续保持完整终态，fatal stderr count 为 0。GPU 1/3/4/5/6/7 空闲；GPU 0 与 GPU 2 的既有进程归属未改变，运行卷剩余约 406 GB。TrioMol2 仍为 3 succeeded、1 running、11 queued，2HYY seed 17 task 保持 progress 3/5；其进程已连续运行约 9 小时，持续使用约 130% CPU 并持有约 1.5 GiB GPU context，现场证据显示任务仍活跃。TrioPep 维持 4 queued，两个 poller 存活，48 个 artifacts 校验有效且 download failures 为 0。本轮无新增终态或失败，未干预 control-plane task，未重复运行已闭合实验。
- 2026-08-02 07:53 持续巡检：CBGBench resume/carried jobs 继续为 30/30、15/15 exit zero，45/45 extension 与 90/90 combined manifests 保持完整，fatal stderr count 为 0。GPU 1/3/4/5/6/7 空闲；GPU 0/2 既有进程归属未改变，运行卷剩余约 406 GB。TrioMol2 保持 3 succeeded、1 running、11 queued；2HYY seed 17 task 仍为 progress 3/5，其进程连续运行约 10 小时并持续使用约 127% CPU、约 1.5 GiB GPU context，仍属于活跃计算。TrioPep 保持 4 queued；两个 poller 均存活，48 个 artifacts 校验有效且 download failures 为 0。本轮无新终态、失败、恢复动作或主张变化，未重复启动已闭合实验。
- 2026-08-02 08:54 持续巡检：CBGBench resume/carried jobs 仍为 30/30、15/15 exit zero，45/45 extension 与 90/90 combined manifests 完整，fatal stderr count 为 0。GPU 1/3/4/5/6/7 空闲；GPU 0/2 既有进程归属未改变，运行卷剩余约 406 GB。TrioMol2 保持 3 succeeded、1 running、11 queued；2HYY seed 17 task 仍为 progress 3/5，其进程连续运行约 11 小时并持续使用约 125% CPU、约 1.5 GiB GPU context，仍有现场活跃计算信号。TrioPep 保持 4 queued；两个 poller 均存活，48 个 artifacts 校验有效且 download failures 为 0。本轮无新增终态、失败、恢复动作或主张变化，未干预现有任务，未重复启动已闭合实验。
- 2026-08-02 09:30 用户范围纠正：TrioMol2 未出现在论文中，立即从大修实验主线、完成条件、稿件证据和每小时终态等待中排除。现有 3 个 succeeded tasks 与 48 个已验证 artifacts 只保留为历史运行记录，不进行终态分析；禁止新增、补跑或恢复 TrioMol2。现场核查确认已验证 LAN control plane 仅提供 submit/get/artifact routes，没有 cancel route；为遵守 control-plane-only 与既有任务不可干预边界，未直接修改 TrioWorkspace database/job files，也未直接终止 worker。当前 1 running、11 queued tasks 不再阻塞修订或进入稿件。每小时 automation 已移除 TrioMol2 轮询和实验优先级；Agent 自有 TrioMol2 poller PID 689528 已经按精确进程校验后停止，TrioPep poller 与 TrioMol2 control-plane task 均保持原状态。
- 2026-08-02 09:53 Forge–Gauge 前瞻实验启动：确认上一轮 CBGBench 45/45 extension 与 90/90 combined 已终态，GPU 1/3/4/5/6/7 当时空闲；随后冻结 matched-budget 协议，以 5 pockets × 3 prospective seeds 比较 `fixed_best`（每 cell 1,500 次 TargetDiff）、`single_pass`（三模型各 500 次）和 `iterative`（首轮三模型各 250 次，Gauge 按 valid rate/QED/favorable SA 决定第二轮 750 次分配）。r01 的 12 个 worker 因相对 job-TSV 路径在进入 workspace 后失效，全部在创建 job state 前退出，0 次模型推理；自有 controller 经 PID/命令核实后停止，失败根原样保留。仅修正路径解析的 r02 已在全新 run 根启动：12/12 workers 存活，六张卡各两个进程，GPU 利用率均为 100%，显存约 6.7–7.9 GiB；首批 12 个 TargetDiff jobs 进入真实采样且无 fatal worker stderr。为保持远端状态 append-only，初始 controller 经精确 PID/命令核实后换成新文件名的 append-only controller，12 个 GPU jobs 全程未中断。该 controller 将自动等待 105 个 phase-1 jobs、冻结 15 个 Gauge 决策、启动 15 个 phase-2 jobs并生成 `final-manifest.json`；当前无数值结论。
- 2026-08-02 10:09 持续巡检：Forge–Gauge r02 phase 1 为 12 running、0 terminal、0 failed、93 unstarted；12 个初始 TargetDiff jobs 均持续产生采样文件，12 个推理进程与 append-only controller 存活，fatal stderr count 为 0。GPU 1/3/4/5/6/7 均保持双进程，现场利用率 `79–100%`、显存约 `6.7–7.9 GiB`；GPU 0/2 的既有进程归属未改变，运行卷剩余约 406 GB。`gauge-decisions.json`、phase-2 jobs 与 `final-manifest.json` 尚未到生成条件；r01 保持原样。TrioPep poller 存活，4 个 supplementary tasks 仍 queued、0 download failures。本轮没有终态、失败、恢复动作或主张变化，未重复提交任何 job。
- 2026-08-02 11:11 持续巡检：Forge–Gauge r02 phase 1 仍为 12 running、0 terminal、0 failed、93 unstarted；12 个 TargetDiff jobs 已分别产生 172–256 个 SDF，最新文件持续写入，12 个推理进程、12 个 worker roots 与 append-only controller 均存活，fatal stderr count 为 0。GPU 1/3/4/5/6/7 每卡两个进程，现场利用率 `55–100%`、显存约 `6.7–7.9 GiB`；GPU 0/2 原进程归属未改变，运行卷剩余约 406 GB。Gauge decisions、phase 2 和 final manifest 尚未触发；r01 保持 0 job state、0 推理且无存活进程。TrioPep poller 存活，4 个 supplementary tasks 保持 queued、0 download failures。本轮没有新终态、失败、恢复动作或主张变化，未重复提交任何 job。
- 2026-08-02 12:11 持续巡检：Forge–Gauge r02 phase 1 继续为 12 running、0 terminal、0 failed、93 unstarted；12 个 TargetDiff jobs 已分别产生 285–480 个 SDF，最新文件持续写入，12 个推理进程、12 个 worker roots 与 append-only controller 均存活，fatal stderr count 为 0。GPU 1/3/4/5/6/7 每卡两个进程且现场利用率均为 `100%`，显存约 `6.7–7.9 GiB`；GPU 0/2 原进程归属未改变，运行卷剩余约 406 GB。Gauge decisions、phase 2 和 final manifest 尚未触发；r01 继续保持 0 job state、0 推理且无存活进程。TrioPep poller 存活，4 个 supplementary tasks 保持 queued、0 download failures。本轮没有新终态、失败、恢复动作或主张变化，未重复提交任何 job。
- 2026-08-02 13:11 持续巡检：Forge–Gauge r02 phase 1 保持 12 running、0 terminal、0 failed、93 unstarted；12 个 TargetDiff jobs 已分别产生 429–704 个 SDF，最新文件持续写入，12 个推理进程、12 个 worker roots 与 append-only controller 均存活，fatal stderr count 为 0。GPU 1/3/4/5/6/7 每卡两个进程，现场利用率 `92–100%`、显存约 `6.7–7.9 GiB`；GPU 0/2 原进程归属未改变，运行卷剩余约 406 GB。Gauge decisions、phase 2 和 final manifest 尚未触发；r01 保持 0 job state、0 推理且无存活进程。TrioPep poller 存活，4 个 supplementary tasks 继续 queued、0 download failures。本轮没有新终态、失败、恢复动作或主张变化，未重复提交任何 job。
- 2026-08-02 14:09 持续巡检：Forge–Gauge r02 phase 1 保持 12 running、0 terminal、0 failed、93 unstarted；12 个 TargetDiff jobs 已分别产生 538–896 个 SDF，最新文件持续写入，12 个推理进程、12 个 worker roots 与 append-only controller 均存活，fatal stderr count 为 0。GPU 1/3/4/5/6/7 每卡两个进程且现场利用率均为 `100%`，显存约 `6.7–7.9 GiB`；GPU 0/2 原进程归属未改变，运行卷剩余约 406 GB。Gauge decisions、phase 2 和 final manifest 尚未触发；r01 保持 0 job state、0 推理且无存活进程。TrioPep poller 存活，4 个 supplementary tasks 继续 queued、0 download failures。本轮没有新终态、失败、恢复动作或主张变化，未重复提交任何 job。
- 2026-08-02 15:13 持续巡检：Forge–Gauge r02 phase 1 仍为 12 running、0 terminal、0 failed、93 unstarted；12 个 TargetDiff jobs 已分别产生 673–1,119 个 SDF，最新文件持续写入，12 个推理进程、12 个 worker roots 与 append-only controller 均存活，fatal stderr count 为 0。GPU 1/3/4/5/6/7 每卡两个进程，现场利用率 `52–100%`、显存约 `6.7–7.9 GiB`；GPU 0/2 原进程归属未改变，运行卷剩余约 406 GB。Gauge decisions、phase 2 和 final manifest 尚未触发；r01 保持 0 job state、0 推理且无存活进程。TrioPep poller 存活，4 个 supplementary tasks 继续 queued、0 download failures。本轮没有新终态、失败、恢复动作或主张变化，未重复提交任何 job。
- 2026-08-02 16:15 持续巡检：Forge–Gauge r02 phase 1 保持 12 running、0 terminal、0 failed、93 unstarted；12 个 TargetDiff jobs 已分别产生 818–1,342 个 SDF，最新文件持续写入，12 个推理进程、12 个 worker roots 与 append-only controller 均存活，fatal stderr count 为 0。GPU 1/3/4/5/6/7 每卡两个进程，现场利用率 `99–100%`、显存约 `6.7–7.9 GiB`；GPU 0/2 原进程归属未改变，运行卷剩余约 406 GB。Gauge decisions、phase 2 和 final manifest 尚未触发；r01 保持 0 job state、0 推理且无存活进程。TrioPep poller 存活，4 个 supplementary tasks 继续 queued、0 download failures。本轮没有新终态、失败、恢复动作或主张变化，未重复提交任何 job。
- 2026-08-02 17:17 Forge–Gauge 进度、恢复与 ETA 检查点：r02 phase 1 当前为 `3 terminal-success / 1 failed / 12 running / 89 unstarted`。三个 4WA9 fixed-best TargetDiff jobs 均 exit zero；`single-pass-single-pocket2mol-1iep-s109-n500-r02` 在双进程同卡条件下运行至 3/16 batches 后触发 CUDA OOM，失败时该进程占用 17.11 GiB、同卡进程占用 3.74 GiB，2.87 GiB 的新分配超过剩余 2.67 GiB。失败 job、telemetry 与三个成功终态原样保留；等待授权 GPU 可独占时在全新 amendment 根精确补跑该逻辑 job，禁止重跑 exit-zero jobs。其余 12 个 jobs、worker roots 与 controller 仍存活，GPU 1/3/4/5/6/7 现场利用率均为 100%，磁盘剩余约 406 GB。按已完成 n1500 jobs、历史 n500 模型耗时和 12-lane 队列重算：phase 1 与精确补跑预计于 2026-08-03 18:00 前完成，Gauge/phase 2/final manifest 预计于 2026-08-04 01:00 前完成，配对统计、pocket/clash geometry、分层 docking 后处理与文档同步的主线目标为 2026-08-04 12:00，保守缓冲至 2026-08-04 18:00。TrioPep queued supplementary panel 与依赖授权 Modeller license/live endpoint 的 MDockPeP2 prospective rerun不作为论文范围内主线完成门槛。
- 2026-08-02 17:24 Forge–Gauge 失败扩展检查点：r02 phase 1 更新为 `3 terminal-success / 2 failed / 12 running / 88 unstarted`。同一 worker-10/Pocket2Mol lane 的 `single-pass-single-pocket2mol-3cs9-s83-n500-r02` 在 9/16 batches 后再次因双进程显存叠加触发 CUDA OOM；失败进程为 17.07 GiB，同卡长期 TargetDiff 进程为 3.74 GiB。该结果确认恢复调度必须按模型显存类别分离。r02 的 12 个 workers 与 controller 继续存活，GPU 1/3/4/5/6/7 均为 100% 利用率，磁盘剩余约 406 GB；worker-10 已进入下一项 Pocket2Mol，继续保留其真实终态以冻结完整失败清单。Pocket2Mol lane 终态后，将在全新精确 retry 根把失败项分配到独占授权 GPU；三个 exit-zero jobs 禁止重复运行。TrioPep 4-task supplementary panel 保持 queued、0 download failures。当前 ETA 维持主线 2026-08-04 12:00、保守缓冲至 18:00。
- 2026-08-02 18:34 Forge–Gauge 自动恢复升级：r02 phase 1 为 `11 terminal-success / 4 failed / 11 running / 79 unstarted`，worker-10 已自然完成，worker-4 继续独占 GPU 6 运行剩余 Pocket2Mol shard；其余五张授权卡维持双进程，GPU 1/3/4/5/6/7 均为 100% 利用率，磁盘剩余约 405 GB。前三个 OOM 来自同卡显存叠加；第四个 `single-pass-single-pocket2mol-2hyy-s97-n500-r02` 在独占 GPU 上仍达到 20.80 GiB，并因追加 3.50 GiB 失败，证明 batch size 32 对部分轨迹超过 24 GiB。预先建立的 batch-32 retry-r01 与 recovery-r03 已在 0 retry job state、0 retry/phase-2 inference 时按精确 PID 停止并原样保留。新建并启动 retry-r02 controller：等待两条 Pocket2Mol lane 终态后冻结全部非零 exit tags，在独占 GPU 6 以 batch size 8、相同 pocket/seed/attempt budget 精确恢复；新 recovery-r04 controller 将等待 r02 的 105 个 phase-1 终态与 retry-r02 final manifest，按逐 tag 来源映射合并 105 个 exit-zero 逻辑 jobs，随后自动生成 15 个 Gauge decisions、启动 15 个 phase-2 jobs 并生成 final manifest。两个新 controller 均存活，成功 job 禁止重复运行；主线 ETA 维持 2026-08-04 12:00，保守缓冲至 18:00。TrioPep 4-task supplementary panel保持 queued、0 download failures。
- 2026-08-02 18:36 自动恢复现场确认：r02 phase 1 达到 `11 terminal-success / 5 failed / 11 running / 78 unstarted`。worker-4 在独占 GPU 6 又完成两个 Pocket2Mol jobs，并新增一个 `iterative-round1-pocket2mol-2hyy-s109-n250-r02` 非零终态；该 lane 尚余两个预注册 jobs。retry-r02 controller PID 877169 持续等待 worker-4 自然结束，随后才冻结失败列表并启动 batch-8 精确补跑；recovery-r04 controller PID 877170 持续等待完整 105-job terminal state。两者 stderr 为空，未创建 retry job state、未重复提交成功项。batch-8 amendment、失败集合冻结规则和逐 tag recovery merge 已提交至 Git `445626e`。
- 2026-08-02 19:34 Forge–Gauge 恢复修正与续跑：r02 phase 1 达到 `16 terminal-success / 5 failed / 10 running / 74 unstarted`，GPU 1/3/4/5/7 继续处理原队列。retry-r02 在任何 retry job state 或推理前停止，原因是 freeze helper 将 Pocket2Mol 任务错误归纳为 worker-4/10 两条 shard，并在其他 shard 的 Pocket2Mol job 尚未终态时拒绝冻结；recovery-r04 随后经 PID/命令核实停止于 phase-1 merge、Gauge 和 phase 2 之前。新 retry-r03 固定 19:25 快照中的 5 个非零终态 tags，在独占 GPU 6 以 batch size 8 顺序精确补跑，首项已进入真实推理，GPU 6 约占 5.38 GiB、现场利用率 72%；新 recovery-r05 等待 105 个 r02 phase-1 终态与 retry-r03 manifest，若后续出现新增失败会在 merge 前写明缺口并停止，禁止不完整合并。已完成 r02 jobs 均未重跑；主线 ETA 维持 2026-08-04 12:00，保守缓冲至 18:00。
- 2026-08-02 20:32 Forge–Gauge 精确补跑终态与动态恢复：retry-r03 已于 19:48 完成冻结的 5/5 jobs，全部 exit zero、batch size 8，无 fatal stderr。r02 phase 1 当前为 `25 terminal-success / 7 failed / 10 running / 63 unstarted`；新增失败为 `single-pass-single-pocket2mol-1iep-s97-n500-r02` 与 `single-pass-single-pocket2mol-2hyy-s109-n500-r02`。二者已在新 retry-r04 冻结并于独占 GPU 6 顺序补跑，首项真实推理利用率约 82%、显存约 4.92 GiB。固定单一 retry 根的 recovery-r05 经精确 PID/命令核实停止于 merge、Gauge 和 phase 2 之前；新 recovery-r06 已启动并等待全部 105 个 source jobs，随后从所有 complete exact-retry manifests 动态建立一次性 tag-to-source map。任何新增失败都会等待新精确 retry 覆盖，完整 105/105 exit-zero 来源验证通过后才进入 Gauge 与 15 个 phase-2 jobs。r02 append-only controller 与 10 个剩余 workers 均存活，GPU 1/3/4/5/7 持续推理，GPU 0/2 进程归属不变，磁盘剩余约 405 GB。主线 ETA 维持 2026-08-04 12:00，保守缓冲至 18:00。
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

Matched-resource comparison 与关键组件 CPU 消融为 orchestration 主张提供了受限证据。三项真实生成模型对照及六 seed 稳定性分析已完成；TrioMol2 已按论文范围纠正从修订主线排除，摘要、引言和讨论的最终范围不再等待其终态。

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
- Current status：TrioMol2 未出现在论文中，用户已于 2026-08-02 将其从大修范围排除。15 个历史提交任务中 3 个 succeeded，其余 control-plane 状态不进入论文证据或完成条件；single-pass/iterative 分析取消，禁止新增或补跑 TrioMol2。
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
