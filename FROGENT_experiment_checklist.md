# FROGENT 大修实验与证据清单

## 0. 当前执行状态｜2026-07-31

### 状态标记

- `[x]`：已有完整运行证据，可复核。
- `🟡 首轮部分完成`：已完成首轮盘点、smoke、regression 或单案例真实运行，正式 study 仍需扩展。
- `[ ]`：尚未启动，或尚未达到正式验收标准。

### 已完成的首批非 GPU 工作

- [x] 2026-08-04 20:44 三小时巡检：Forge–Gauge 三份 final manifest 保持 `complete` 且时间戳未变；GPU 1/3/4/5/6/7 空闲，GPU 0/2 既有进程归属未变，运行卷剩余约 404 GB。未轮询 TrioMol2/TrioPep，未重复提交已闭合 panel；MDockPeP2 继续等待 provider 修复与新 canary。
- [x] Agent 模型边界已更正并冻结：FROGENT Agent=`deepseek-v4-flash` 或 `gpt-5.6-luna` + `max`，每个 run/benchmark arm 二选一并禁止混合。DeepSeek live tool-call canary 为 r01 HTTP 400（thinking/tool_choice compatibility）及修正后 r02/r03 两次 HTTP 503（provider availability），真实 DeepSeek 推理待新 canary。Luna/max 已由 ChatGPT.app bundled Codex 0.146.0-alpha.9.2 完成 read-only/ephemeral structured canary，精确返回 `{"status":"ok"}`、exit zero；PATH Codex 0.136.0 的 `max`/Luna 失败终态已保留。
- [x] Agent 模型透明度已进入稿件交付：`docs/manuscript/agent-model-rebuttal-blocks.md` 提供 Methods、Results、SI 配置表和 E-2/E-5/R1-0b/R1-0d/R1-6 回复块；provider-claim matrix 与 evidence ledger 已绑定六个 versioned canary roots。DeepSeek scientific behavior、DeepSeek/Luna comparative quality、生产部署模型身份和训练/提示隔离事实继续保持 `not_measured`，等待各自独立来源。
- [x] 论文压缩包已复制到 `docs/manuscript/Arxiv_FROGENT_20251217.zip`，24 个条目通过 `unzip -t`。
- [x] 论文源码包已完成结构、安全和材料完整性审计；确认包含 2 个 TeX、1 个 bibliography、1 个 style 和 20 个 PDF figures。
- [x] 本地项目已安全同步到 `doomx_3nd:/work/doomx/FROGENT`；远端论文 ZIP 校验通过。
- [x] 本地完整 deterministic suite：255/255 tests passed。
- [x] 本地 evidence regression：73/73 tests passed。
- [x] 本地 molecular-tool regression：89/89 tests passed。
- [x] 远端 evidence regression：73/73 tests passed；research-eval result verification passed。
- [x] Europe PMC live smoke：接纳 2 条 OA records，provider calls 1，reader tasks 2。
- [x] Capability-52 exposed rescore：52/52 cases completed，0 failed，0 timeout。
- [x] Research-eval fixture replay：执行完成并保留 `effect_outcome=not_evaluated` 与 promotion gate。
- [x] Vina 1IEP 真实 CPU docking：seed 17、exhaustiveness 8、最佳 affinity `-13.27 kcal/mol`。
- [x] PLIP 1IEP 真实 CPU 分析：1 个 binding site、10 个 hydrophobic interactions、1 个 π-stack、1 个 salt bridge。
- [x] Dimorphite-DL aspirin pH 7.0 protonation 已完成。
- [x] PDB2PQR pH 7.4：原始受体缺失 SER A438 原子的失败已保留；lineage-selected receptor 成功生成 4,411 条 atom records。
- [x] 论文源码成功构建为 37 页 PDF，无 undefined citation 或 undefined reference。
- [x] 本地和远端首轮 run 已归档；最终 manifest 位于 `runtime/evaluation/revision-20260730/nongpu-local/manifest.json`。

### 已完成的第二批非 GPU 工作

- [x] Capability-52 完成固定 seed `20260730`、50,000 次 case-level bootstrap、95% CI 和逐案例错误分层；确定性重复运行通过。
- [x] 八项论文 benchmark datasheet 首轮完成：8 个唯一任务、每项 20 个样本声明、15 个跨文档冲突和 56 个缺失字段已结构化保存。
- [x] Evidence reliability/recovery panel：6/6 runtime scenarios 与 63/63 focused tests 通过。
- [x] Europe PMC 单查询稳定性：5/5 runs 成功，ordered hits 完全一致。
- [x] Europe PMC 四任务稳定性：12/12 provider calls 成功，三个正向查询和一个零命中 negative control 的 ordered hits 均稳定。
- [x] Vina 1IEP 稳定性：5/5 CPU runs 成功；seed 17 三次最佳 affinity 均为 `-13.270 kcal/mol`。
- [x] Dimorphite-DL pH panel：4 个分子 × 3 个 pH，共 12/12 修正后 cases 成功，两次运行逐字节一致。
- [x] PDB2PQR/PROPKA pH panel：pH 5.0、7.4 和 9.0 三个 cases 全部成功，净电荷分别为 `+1`、`-8` 和 `-9`。
- [x] Live RCSB 1IEP target/pocket：3/3 repeats 的 target identity、auth chains 和 pocket geometry 一致；历史 `STI:A:999` 输入按 exact candidate `STI:A:201` fail-closed。
- [x] 远端 Python 3.11.15/RDKit 2025.9.1 验证：evidence 73/73、molecular 89/89；source-copy-safe suite 250 passed、4 optional Flask tests skipped、0 failed。
- [x] 第二批本地 manifest 位于 `runtime/evaluation/revision-20260730/nongpu-next/manifest.json`，远端 CPU manifest 已回收到同一 run tree。

### 已完成的第三批非 GPU 工作

- [x] 语义双评与共识裁决：28 个 exposed mismatches 完成两名独立 judge；raw agreement `22/28`，Cohen’s κ `0.647`，共识为 16 correct、8 partial、4 incorrect。
- [x] 可复现统计入口：实现 exact McNemar、paired sign-flip、Wilcoxon、paired/cluster bootstrap、Holm correction 与 effect size；10/10 synthetic fixture tests 通过，论文原始结果仍需样本级输出。
- [x] Matched-resource CPU panel：4 个 fixture cases 与 1 个 frozen live case 在 4 个条件下形成 20 条结果；deterministic policy proxy 的适用边界已显式记录。
- [x] 真实 subagent 消融：130/130 frozen worker outputs、70 final answers、60 specialist memos、20 blind-judge files 全部完成，0 worker failure、0 external tool call、0 GPU/API-key use。
- [x] 真实消融 paired results：Full context 得分 `9.367/10`；相对 direct、single、no-context 的均值差为 `0.067`、`0.033`、`0.167`，三者均未形成强显著优势。
- [x] 适用组件消融：移除 Retrieve 使五个检索 cases 平均下降 `7.000/10`，95% CI `[5.200, 8.500]`；移除 Gauge 使五个设计 cases 平均下降 `0.800/10`，95% CI `[0.000, 1.600]`。
- [x] 真实消融双盲评：70 responses 的 pass/fail agreement `98.6%`，Cohen’s κ `0.933`，总分 Pearson r `0.959`。
- [x] Live evidence reliability：8 个公开 Europe PMC 任务重复运行，两次 ordered-result Jaccard 均为 `1.0`；机械验收 7/8，通过 retraction、conflict、missing-evidence 和 provider-recovery gates。
- [x] 独立 live-evidence adjudication：8 cases 中 3 pass、4 partial、1 fail；ACTT-1 历史版本区分失败作为负向结果保留。
- [x] Structured retrieval：Open Targets 与 UniProt 8 cases × 3 arms，共 24 次 live calls，0 fail、0 retry；literature arm 的 disease–target macro recall 为 `22.5%`，protein–drug recall 为 `9.22%`。
- [x] Evidence downstream propagation：4/4 conflict/revocation cases 通过；unsupported carry-through 与 revoked leakage 均为 0，25 项检查和 19 项 production tests 通过。
- [x] Luteolin 独立性对照：fixed、literature-only、structured proxy 得分分别为 `1.4/2.0`、`1.8/2.0` 和 `2.0/2.0`；DrugBank direct access 因 403 保持 `not_measured`。
- [x] Molecular property panel：11 records、10 个唯一立体化学 identity 均可由 RDKit 解析，QED、SA、MW、logP、TPSA、RotB、PAINS 和 BRENK 重复运行逐字节一致。
- [x] SA 方向核查：RDKit SA score 为 `1 = easy`、`10 = difficult`，稿件中“higher SA favorable”需要修正并核对原始 scorer。
- [x] ADMET-AI 2.0.1 CPU panel：6 个分子 × 3 次，共 18/18 workflows、41 endpoints 全部有限且确定性一致；6/6 invalid controls 在预测前 fail closed。
- [x] Raw/local/redocking 与 PLIP：7 poses 完成 RMSD、clash、pocket escape 和 interaction retention；跨 seed 稳定丢失 ASP381 salt bridge，pH 5.0/7.4/9.0 fingerprints 的 Jaccard 为 `1.0`。
- [x] Multi-target docking：5 structures、15 seeds、20 PLIP reports；12/15 poses 的 RMSD ≤ 2 Å，EGFR 1M17 以 5.886 Å 稳定失败并保留完整 failure analysis。
- [x] PLIP parser baseline：12 complexes、129 interactions；direct XML 与 adapter 12/12 一致，typed parser 全案例 end-to-end exact 为 `0.667`，metal/waterbridge schema gap 已定位。
- [x] DAVIS ABL1 CPU virtual screening：direct Vina 与 FROGENT workflow 均 10/10 成功且 pose-score vectors 完全一致；Spearman ρ `0.115`、p `0.751`，证明当前 docking score 尚未形成可靠 affinity discriminator。
- [x] DAVIS JAK2 gold 修复：从新提供的 68-drug JAK2 数据中确定唯一 top-affinity 记录 Drug Index 49 / CID 25127112（pKd `10.443697`，Kd `0.036 nM`）；其磷酸盐的 largest organic fragment 与 Task 5 第 13 行 gold 立体精确一致。原始行保持 attempted `20` / exact-valid `19`，另建一个 post-hoc corrected replacement cell。
- [x] GLP1R peptide audit：完成 4ZGM 来源、序列、界面、缺失残基和图文一致性核查；识别一处 `-2.41/-2.42` 差异、重复 pose、缺失 pose，以及 Aib/脂化/末端化学表达缺口。
- [x] Safety contract panel：23/23 通过；refusal 9/9、degradation 4/4、recovery 3/3、provenance 16/16、false refusal 0/10、synthetic secret leak 0。
- [x] CPU/live telemetry：70 条 per-run records、49 条有效 summary rows、17 个 groups；记录 wall time、CPU、RSS、provider calls 和失败尝试，token/energy 保持 `not_measured`。
- [x] 近期 baseline 审计：CLADD、Prompt-to-Pill、Robin 进入 Related Work/capability matrix；Prompt-to-Pill 公开代码静态检查发现 12/13 Python files 可编译，公平数值复现保持 `not_measured`。
- [x] HLE text-only protocol/access audit：确认官方数据存在联系信息门控；冻结 text-only 选择与评分协议，未取得可合法完整复现的 20-case 内容，性能保持 `not_measured`。
- [x] 稿件 QA ledger：记录 30 个问题，其中 15 blocking、15 major；10 confirmed、8 ambiguous、12 missing-input。
- [x] 最终仓库回归：259/259 tests passed；690 个第三批 JSON assets 全部可解析；real-agent 主验证 11/11 与独立复核通过。

### GPU 与真实模型工作｜执行中

- [x] 只读核实生产目录 `/work/pqh/projects/agent/` 与 `/work/pqh/projects/Frogent1/`；确认 CBGBench 的 TargetDiff、Pocket2Mol、DiffSBDD 权重和生成入口。
- [x] 将最小代码、配置、3 个 checkpoint 和 5-pocket 输入复制到隔离 run；生产源码、权重和 Git 状态保持不变。
- [x] 冻结 CBGBench 正式矩阵：5 pockets × 3 seeds × 3 models × 500 attempts，共 45 jobs、22,500 raw attempts；canary 排除在正式统计之外。
- [x] CBGBench 正式矩阵：45/45 jobs terminal-success，完成 22,500 raw attempts；TargetDiff、DiffSBDD、Pocket2Mol 分别得到 7,263、1,809、753 个 valid molecules，mean job QED 为 `0.458/0.234/0.128`，final manifest 已生成。
- [x] CBGBench 独立 seed 扩展：15 个暂停源 Pocket2Mol jobs 继承验证通过，30/30 resume TargetDiff/DiffSBDD jobs 全部 exit zero；完整 extension 45/45、combined six-seed 90/90 manifests 均已生成。六张实验 GPU 已释放。
- [x] CBGBench 六 seed稳定性：三项模型在 valid rate、QED 和 SA 上的排序全部保持；primary-versus-pooled model–pocket Spearman ρ 为 `0.993/0.971/0.704`。TargetDiff primary→pooled QED `0.458→0.408`、valid rate `0.968→0.949`，extension-minus-primary pocket-cluster 95% CI 为 `[-0.188,-0.004]` 与 `[-0.073,-0.006]`，确认相对排序稳定且绝对性能具有 seed sensitivity。逐 pocket 最大变化集中于 TargetDiff–2HYY/3CS9；reconstruction error 最高为 DiffSBDD–3CS9 的 0.73%，0 job failure。Final manifest：`gpu-followup-20260802/cbgbench-six-seed-stability-r01/output/final-manifest.json`。
- [x] TrioMol2 历史面板：曾提交 15 tasks；用户确认该方法未出现在论文中，已从大修主线、完成条件与稿件证据排除。3 个 succeeded tasks 的 48 个 artifacts 仅保留为历史记录，禁止新增、补跑或恢复；其余 control-plane 状态不再等待。
- [x] GLP1R–肽 AF3：Glucagon、Semaglutide、Tirzepatide 与 Peptide(a–e) 共 8/8 任务完成，8 个结果包已取回；序列化学表达边界、结构、界面、reference geometry 与跨 provider disagreement 已完成分析。
- [x] 建立 TrioMol2 与 AF3 单次轮询/自动取回脚本；TrioMol2 的服务器抓取器支持超过 SSH relay 45 MiB 上限的 artifact 流式下载，并逐项执行 checksum/size 验证与失败隔离。
- [x] Trio 轮询范围已收紧：TrioMol2 与 TrioPep 均从 automation、大修终态等待、分析和抓取中移除；两个 Agent 自有 server poller 均已停止，run roots 只保留为历史 operational evidence；既有 control-plane tasks 保持原样。
- [x] DirectMultiStep/FragGen live 权重面板：13/13 typed calls 成功；10/10 retrosynthesis calls 返回非空路线且 route root 与目标一致，路线内分子字符串全部 RDKit-valid；FragGen 3 cases 返回 15/15 valid、15 unique molecules。
- [x] DirectMultiStep/FragGen 三轮稳定性重复：39/39 typed calls 成功；12/13 调用定义三轮响应文本完全一致，DirectMultiStep 路线集合平均两两 Jaccard `0.973`，FragGen 分子集合为 `1.000`；唯一变化为 aspirin/explorer 的路线集合。
- [x] TrioPep 历史 reference panel：曾提交 3GBQ、1CKB、1ABO 和 4ZGM 共 4 个 tasks；现已从大修主线、稿件证据、轮询、抓取、分析与完成条件排除，远端 control-plane 状态保持原样。
- [x] MDockPeP2 历史 glucagon audit：三次同序列 run、25,000 score rows、3,000 retained models 已复核；native-frame CA RMSD 无 ≤2 Å，最佳 superposed CA RMSD 为 `2.721 Å`，top-ranked pose 可远离 native frame，作为负向结果保留。
- [x] ADCP v1.1 正式面板：官方 ADCP 0.0.25 / v1.1.21 隔离 runtime、3GBQ/1CKB/1ABO 三套 AGFR target 和 a07 canary 均验证；正式 3 complexes × 3 seeds、每任务 100 replicas、每 replica 8–10M steps 的 9/9 任务完成。独立评分的平均 top-1/top-5/top-10 backbone RMSD 为 `11.262/5.840/4.690 Å`，native-contact recovery 为 `0.271/0.564/0.593`。29 aa glucagon/Peptide(a–e) 保持为长度外推探索分析。
- [x] ESMFold GLP1R–肽正式面板：8 sequences × 3 seeds × 3 recycles，24/24 完成；mean pTM `0.636`、mean pLDDT `64.99`、峰值分配显存 `8314 MiB`。Glucagon 预测 pose 与 4ZGM deposited Semaglutide 坐标的 cross-ligand CA distance 为 `28.619 Å`；该值不承担 glucagon native-pose 结论。
- [x] ESMFold 三复合物 reference panel：3GBQ、1CKB、1ABO 各 3 seeds，共 9/9 完成；平均 receptor-aligned peptide CA RMSD `6.526 Å`，仅 1/3 complexes 达到 ≤2 Å（分别为 `2.123/1.542/15.914 Å`），跨 seed 最大差 `0.000001 Å`。
- [x] ESMFold recycle sensitivity：4ZGM、3GBQ、1CKB、1ABO 的 1-vs-3 recycle 对照完成；3 recycles 改善 2/4 cases，平均 native pose RMSD `9.546 → 12.050 Å`，最大 protocol pose shift `16.560 Å`，确认更多 recycles 不保证 pose recovery 单调改善。
- [x] ESMFold GLP1R ranking sensitivity：8 条肽的 1-vs-3 recycle pTM/pLDDT 排名相关分别为 Spearman ρ `0.738/0.810`，top 候选一致；pose 平均/最大位移 `2.144/3.816 Å`，confidence ranking 仅作有限优先级信号。
- [x] AF3 GLP1R–肽分析：8/8 结果包完成安全检查与结构分析，mean pair-ipTM `0.755`，Tirzepatide 排名第一；sequence-mapped Semaglutide 对 4ZGM 的 receptor-aligned peptide CA RMSD `8.133 Å`，native-contact recall/precision `0.882/0.732`。AF3–ESMFold pose RMSD 平均/最大 `31.513/36.545 Å`，AF3 pair-ipTM 与 ESMFold pTM 排序相关 `ρ=-0.119`，明确限制 confidence-to-docking-accuracy 外推。
- [x] CBGBench novelty/scaffold/pocket compatibility：45/45 primary jobs、9,825 个 SDF 完成 CPU-only 分析，9,767 个解析成功、58 个 molecule-level parse failures 保留。TargetDiff/DiffSBDD/Pocket2Mol identity uniqueness 为 `1.000/1.000/0.965`，scaffold per parsed molecule 为 `0.997/0.866/0.458`，mean reference-ligand ECFP4 Tanimoto 为 `0.093/0.065/0.055`，均无 exact identity、reference scaffold match 或 Tanimoto ≥0.5；10 Å pocket-compatible rate 均为 1.000，severe clash-free rate 为 `1.000/0.942/0.996`。Final manifest：`gpu-followup-20260801/cbgbench-novelty-pocket-r01/output/final-manifest.json`。
- [x] CBGBench target-matched known-active neighbors：ChEMBL 37 的 ABL1/EGFR binding IC50（pChEMBL ≥6）集合分别去重为 1,653/8,072 个 canonical actives；9,767 个已解析生成分子全部完成 nearest-neighbor 分析。TargetDiff/DiffSBDD/Pocket2Mol mean nearest-active ECFP4 Tanimoto 为 `0.176/0.143/0.120`，最大值为 `0.405/0.256/0.217`；Tanimoto ≥0.5 均为 0，exact active-scaffold overlap 分别为 `2/7253`、`0/1771`、`1/743`。Checkpoint-exact training membership 和其他数据库/assay 类型继续标记 `not_measured`；public CrossDocked training proxy 由下一项单独报告。r01 协议时间错误与 r02 aggregate Boolean 类型错误均排除；final manifest：`gpu-followup-20260802/cbgbench-known-active-neighbors-r03/output/final-manifest.json`。
- [x] CBGBench CrossDocked training-proxy nearest neighbors：公开 split 的 100,000 个 train names 中 99,990 个按 CBGBench dataloader 映射，安全 opcode 提取 99,990/99,990 成功并去重为 10,404 个 canonical molecules。9,767 个生成分子无 exact identity；TargetDiff/DiffSBDD/Pocket2Mol mean nearest-train ECFP4 Tanimoto 为 `0.216/0.189/0.203`，最大值为 `0.453/0.682/0.474`，仅 DiffSBDD 有 `1/1771` 达到 ≥0.5。Exact scaffold overlap 为 `0.772%/7.510%/15.612%`。结果限定为 declared-training-corpus proxy，checkpoint 原始 training-file identity 未确认。Final manifest：`gpu-followup-20260802/cbgbench-crossdocked-training-proxy-r04/output/final-manifest.json`。
- [x] Forge–Gauge matched-budget prospective r02。Recovery-r06 完成 `120/120 exit zero`；15/15 Gauge decisions 选择 TargetDiff。Fixed-best/single-pass/iterative valid rate 为 `0.956/0.444/0.704`，top-50 score 为 `0.661/0.620/0.686`。Iterative 相对 single-pass 的 valid-rate 与 top-50 score 差为 `+0.260`（p=`6.10e-5`，95% CI `[0.231,0.276]`）和 `+0.066`（p=`0.0020`，CI `[0.029,0.106]`）；相对 fixed-best 的 valid rate 低 `0.252`，top-50 score 差无统计支持。Final manifest：`gpu-followup-20260802/forge-gauge-matched-budget-prospective-recovery-r06/final-manifest.json`。
- [x] Forge–Gauge top-candidate geometry / generating-model strata。r02 因 source SDF parse failure 严格终止且保留 traceback；parse-handling-only r03 完成 45/45 cells、2,250 个候选。47,333 个 source SDF 中 157 个不可解析并逐 job 记录；三条件 pocket-compatible rate 均为 `1.000`，severe-clash-free rate 为 `0.9987/0.9987/1.0000`。Top-50 composition 为 fixed-best `750 TargetDiff`、iterative `750 TargetDiff`、single-pass `743 TargetDiff + 4 Pocket2Mol + 3 DiffSBDD`。Final manifest：`gpu-followup-20260802/forge-gauge-top-candidate-geometry-r03/output/final-manifest.json`。
- [x] 2026-08-03 22:54 历史终态复核：上述三项 Forge–Gauge final manifest 保持可读且未变化；GPU 1/3/4/5/6/7 空闲，GPU 0/2 既有进程未干预，磁盘剩余约 404 GB。当时 TrioPep 为 4 queued、0 download failures；该 panel 后续已从大修范围排除且 poller 已停止。
- [x] 剩余问题 closure matrix：`docs/manuscript/unresolved-issues-closure-matrix.md` 已区分作者输入阻塞、Agent-owned 写作/交付和唯一有条件的新实验，并为每项记录缺失时的稿件收窄方案。
- [x] Error-attribution manuscript block：`docs/manuscript/error-attribution-rebuttal-blocks.md` 已覆盖 retrieval、memory propagation、repeat variation、PLIP schema、small-molecule docking、generation parsing、MDockPeP2 和 ADCP，包含可直接进入 Results/Methods/SI 的表述及 R2-3b、R2-5、R3-m1、R3-M3 point-by-point responses。
- [x] Peptide workflow manuscript block：`docs/manuscript/peptide-workflow-rebuttal-blocks.md` 已分离 structure prediction 与 peptide docking，汇总 ADCP、MDockPeP2、ESMFold、AF3 的真实状态、结构结果、失败边界及 R1-5a、R1-5b、R1-9d、R1-9e 回复；TrioPep 已从稿件证据排除。
- [x] Architecture/retrieval manuscript block：`docs/manuscript/architecture-retrieval-rebuttal-blocks.md` 已汇总 matched-resource、real-agent ablation、structured retrieval、live evidence 与 downstream propagation，形成 Methods、Results、SI 表及 R3-M2a/b、R3-M3、R3-M4、R3-M5a/b/d、R2-3a 回复块，并删除宽泛 multi-agent superiority 解释。
- [x] Benchmark corrections manuscript block：`docs/manuscript/benchmark-corrections-rebuttal-blocks.md` 已把 HLE、QED、SA、virtual screening、retrosynthesis 和八任务命名/尺度问题整理为统一 disposition table、Methods、Results 及 R1-8a–e、R2-1a、R2-3c、R2-7a/b、R3-M1 回复块；无法绑定原始 case/scorer 的 headline values 保持 `not_measured`。
- [ ] MDockPeP2 prospective rerun。🟠 **第三方 provider 修复依赖**：`doomx_5nd` 不存在用户给定的 `/work` 路径，实际只读安装位于 `doomx_3nd`；第三方 Modeller 配置中存在已脱敏的 license assignment，未复制或导出。Live MCP canary 在 MDockPeP2/Modeller 启动前因服务进程 global CWD 漂移与相对入口失败，返回缺失 `Sampling_scores_all.txt`。端口 9005 在 provider owner 修复 request-local workdir、绝对入口、CWD 恢复和并发隔离前禁止 benchmark 批跑；prospective accuracy 与 license validity 保持 `not_measured`。

### 首轮证据入口

- Local run：`runtime/evaluation/revision-20260730/nongpu-local/`
- Remote run：`doomx_3nd:/work/doomx/FROGENT/runtime/evaluation/revision-20260730/nongpu-local/`
- Final manifest：`runtime/evaluation/revision-20260730/nongpu-local/manifest.json`
- Source commit：`4a3daabc30673ad9258d964c8d8dca71b89b6f48`

### 第二批证据入口

- Local run：`runtime/evaluation/revision-20260730/nongpu-next/`
- Remote run：`doomx_3nd:/work/doomx/FROGENT/runtime/evaluation/revision-20260730/nongpu-next/`
- Final manifest：`runtime/evaluation/revision-20260730/nongpu-next/manifest.json`
- Remote CPU manifest：`runtime/evaluation/revision-20260730/nongpu-next/remote/final-manifest.json`

### 第三批证据入口

- Local run：`runtime/evaluation/revision-20260730/nongpu-final/`
- Final report：`runtime/evaluation/revision-20260730/nongpu-final/REPORT.md`
- Final manifest：`runtime/evaluation/revision-20260730/nongpu-final/manifest.json`
- Revision evidence ledger：`docs/manuscript/revision-evidence-ledger.md`
- Source commit：`4a3daabc30673ad9258d964c8d8dca71b89b6f48`

## 1. 执行原则

- 当前 readiness：`blocked`。
- 先完成 G0，随后冻结可执行范围。未确认 live 的模型、数据库或 docking provider 不进入实验承诺。
- 采用四个 coherent studies，避免把同一批样本和日志拆成重复实验。
- 每个 study 都服务于明确的 Agent 判断：
  - retrieval quality
  - decision quality
  - tool-use reliability
  - orchestration contribution
- 公开 benchmark 的原始 gold、修正后语义判定和 oracle gap 分开保存。禁止修改 gold、阈值或评分口径来制造提升。
- 同一次正式运行保留任务集、运行入口、原始输出、逐案例结果、失败分析、run 路径和最终 manifest。
- 普通开发、测试和 source-ready 阶段不生成 bundle SHA、文件级 hash 清单或 digest cascade。
- 内部执行窗口固定为 2026-07-30 至 2026-08-12，共 14 天；全部实验、分析、界面、代码、正文、SI、回复信和投稿材料均在窗口内完成。
- G0 使用前 48 小时完成；G0 结束后，S1–S4、X1、D1–D3 并行推进。

## 2. G0｜基准与真实能力核查

**目的：** 先确认论文在评什么、系统实际能做什么，再决定重跑范围。

**对应意见：** E-2、E-3、E-5；R1-0b/c/d、R1-6、R1-7、R1-8a/b/d、R1-9e/f；R2-2、R2-6、R2-7、R2-9；R3-M1、R3-M2b、R3-M5d、R3-M6

### G0-A｜八项 benchmark 事实核查

- [ ] 锁定八项任务的正式名称、目的、版本、来源和许可。🟡 **case/gold 已收到**：作者提供的 ZIP 含 8 项任务各 20 cases/reference answers，任务 5/6/7 结构齐全；正式版本、来源许可、原始执行配置和 scorer 仍待确认。证据：`docs/manuscript/eight-task-source-intake.md`。
- [ ] 建立 Figure 1、Figure 3、正文、数据文件和评分入口的对应表。🟡 **数据侧已闭合**：八项 source files 已映射并通过 schema/20-case/结构完整性审计；原始逐样本 outputs、失败行、seeds、scorer 与 Figure 1/3 aggregation 仍缺。虚拟筛选必须报告 attempted 20、valid 19。
- [ ] 核实 HLE 的真实含义、题型、样本选择和官方/原始评分协议。🟡 **exposed rerun 已完成**：author-supplied 20 cases 含 4 exact-match、16 multiple-choice；官方来源/版本/许可、授权、纳入映射与原 judge 记录仍需作者确认。
- [x] 八任务 foundational Luna/max exposed-case r01：冻结 gold 隔离、read-only/ephemeral、4-worker、零重试与 exact scorer；20/20 structured calls 成功，exact `9/20=0.450`，Wilson 95% CI `[0.258,0.658]`。Exact-match `1/4`，multiple-choice `8/16`；20/20 均报告 high confidence，其中 9 个正确。该 run 只承担 post-hoc exposed、no-tool model-boundary 证据，不重构 submitted HLE score。
- [x] 标出客观题、主观题、回归、排序、工具调用和专家判定任务。证据：八项 benchmark datasheets 与 `manuscript-qa/benchmark-observations.schema.json`。
- [x] 分开记录 scoring maximum、direct-tool baseline 和 adjudicated reference。证据：benchmark datasheets、DAVIS screening、semantic consensus 与 evidence ledger。
- [x] 核查 QED 的生成方式；RDKit 确定性计算值从 property-prediction accuracy 中移出。作者提供的 20/20 SMILES 均有效，RDKit 2026.03.3 重算 QED 经三位小数与 supplied gold 20/20 一致，MAE `0.000259`；四项 model-dependent ADMET endpoints 已在独立 exposed-case r01 中重跑，原始 aggregate score 仍未复现。
- [x] 八任务 property exposed-case rerun：ADMET-AI 2.0.1 完成 20/20。Caco-2 MAE/RMSE `0.402/0.515`、Spearman `ρ=0.501`；BBBP/CYP2D6-sub/SR-p53 accuracy `0.550/0.850/0.850`，balanced accuracy `0.550/0.786/0.472`，MCC `0.229/0.681/-0.076`。SR-p53 0/2 positives recovered，禁止用 nominal 0.85 掩盖类别失衡；原稿 `79.06` aggregate 不重构。
- [ ] 核查 SA 的方向、代码实现、图例和所有受影响结果。🟡 **第三批部分完成**：RDKit SA 方向已确认并形成修订结论；原始实现、主表样本与受影响统计待补。
- [ ] 核查逆合成原始评价者、rubric、自动工具和 LLM judge。🟡 **cases/gold 已收到**：20 targets 和 1–5 step reference routes 已冻结；原始 outputs/failures、route-equivalence rubric、judge prompt/version 与判定记录仍缺。
- [x] 八任务 retrosynthesis exposed-case r01：DirectMultiStep flash/explorer 共 `40/40` live calls 成功，20/20 × 2 均 nonempty、target-rooted、RDKit-valid。Flash/explorer top-1/top-5 完整 canonical reference-route exact match 为 `0.20/0.20` 与 `0.30/0.30`，mean top-5 best exact-reference reaction recall 为 `0.572/0.738`、precision 为 `0.575/0.592`。Exact mismatch 保留给后续 blind semantic adjudication，不标作化学失败。
- [ ] 导出全部方法的样本级结果、缺失值和失败结果。
- [ ] 检查 few-shot 示例、prompt、cache 和 working memory 与测试样本的重叠。
- [ ] 记录模型训练/发布日期与 benchmark 暴露风险。

### G0-B｜真实 capability inventory

- [x] 建立 `claim → Agent → provider → endpoint → version → test input → result` 矩阵。证据：`docs/manuscript/provider-claim-matrix.md` 已覆盖 retrieval、context/ablation、ADMET、retrosynthesis/fragment generation、Vina、PLIP、三生成模型、Forge–Gauge、MDockPeP2、ADCP、ESMFold/AF3、安全合约与 headline benchmark 边界；缺失 endpoint/version、授权材料、原始 scorer 和外部数值复现均显式标记 `not_measured`，TrioMol2 不进入稿件矩阵。
- [x] 区分 `live`、`deferred`、`case-study-only` 和 `removed`。证据：第三批 final manifest 与 revision evidence ledger。
- [x] 核实 Retrieve、Forge、Gauge 和 orchestrator 的真实工具与数据流。证据：real-agent job packets、evidence-propagation adapter、matched-resource panel 与 production regression。
- [ ] 核实 DrugBank 内容进入哪个 Agent 或 context。🟡 **第三批部分完成**：PubChem cross-reference 与 structured proxy 已审计；DrugBank direct/API 返回 403，生产 context 注入仍需部署配置。
- [x] 核实 task state、working context、working memory 和 persistent memory 的真实实现。证据：本地/远端 73 项 evidence regression，以及 research-eval fixture replay。
- [ ] 核实 TargetDiff、Pocket2Mol、DiffSBDD、PocketFlow、MolCRAFT 的部署与可复现性。🟡 **范围已核实**：前三项 checkpoint、配置、canary、primary/extension matrices 均已完成；两个生产目录仍未发现 PocketFlow/MolCRAFT 权重。DiffBP 仅发现配置和 source，配置引用的 checkpoint 缺失；DecompDiff 未发现可执行 checkpoint。
- [ ] 核实 MDockPeP2、ADCP、HADDOCK、pepATTRACT 和 rDock 的 endpoint、版本、权限和回退。🟡 **主要方法已核实**：MDockPeP2 endpoint/source/history 与第三方 Modeller license assignment 存在性已核实，credential 保持脱敏且未复制；live canary 暴露 provider CWD/相对路径故障，prospective accuracy 仍待 owner 修复。ADCP 官方 v1.1 隔离 runtime 和 9/9 reference-redocking 已完成；两个生产目录中未发现 HADDOCK、pepATTRACT 或 rDock 安装。
- [ ] 核实参数微调、few-shot prompting 和 in-context learning 的真实配置。
- [ ] 核实生产/演示环境与论文实验环境是否一致。🟡 **首轮部分完成**：已确认远端系统 Python 3.10 与当前 `StrEnum` runtime contract 不一致，并保留失败证据。
- [ ] 从干净环境验证主 GitHub、安装入口、最小示例和公开数据。🟡 **首轮部分完成**：远端 source-only copy、73 项 evidence regression 和 result verification 已通过；正式 Python 3.11+ clean environment 仍待建立。
- [x] 敏感信息扫描通过；论文 ZIP 与首轮输出未发现凭据、私有 token 或 confidential author-homepage URL。

### G0 产出

- [ ] 八项 benchmark datasheets。🟡 **第二批部分完成**：八项 first-pass datasheet 已完成并通过唯一性、样本量和 archive 一致性验证；版本、许可、case IDs 与 scorer 字段待原始材料补齐。
- [ ] capability inventory。🟡 **范围更新**：CPU/live provider inventory 已完成；TargetDiff、Pocket2Mol、DiffSBDD 为正式生成模型证据。TrioMol2 已按论文范围排除；PocketFlow、MolCRAFT 和受限 provider 继续保留缺失/待核实状态。
- [x] claim–evidence matrix。证据：`docs/manuscript/revision-evidence-ledger.md`。
- [x] baseline configuration matrix。证据：`recent-baselines/baseline-configuration-matrix.csv` 与 real-agent/matched-resource preregistration。
- [ ] 评分影响报告：哪些结果保留、重新计算或撤回。🟡 **第三批部分完成**：QED、SA、DAVIS、semantic mismatch、live evidence 和 docking/PLIP 已给出保留/限定/重算结论；八项 headline results 等待原始样本级输出。
- [ ] 作者完成 A-1 至 A-7 决策。

### G0 完成标准

- [ ] 每项 headline claim 都有真实 capability 和结果来源。
- [ ] HLE、QED、SA、逆合成和虚拟筛选无未解释冲突。
- [ ] 所有后续 study 仅使用已确认的模型、工具和任务。

## 3. S1｜Benchmark validity 与统计分析

**科学问题：** 八项结果是否具有清楚、有效且可复核的统计含义？

**对应意见：** E-3；R1-2、R1-8a/b/d/e；R2-1、R2-7；R3-M1

### S1-A｜分析计划

- [x] 为每项任务定义独立分析单位：问题、靶点、分子、复合物或路线。证据：统计 schema 与 preregistered CPU panels。
- [x] 处理同一靶点下多个分子的 cluster dependency。统计入口支持 cluster bootstrap。
- [x] 定义 primary contrasts，避免事后选择显著比较。证据：各 panel preregistration 与 frozen job manifest。
- [x] 二元配对结果使用 exact McNemar 或配对置换。统计入口已实现并通过 synthetic tests。
- [x] 连续/序数配对结果根据分布和 ties 使用 Wilcoxon、配对置换或 cluster bootstrap。统计入口已实现并通过 synthetic tests。
- [ ] 固定 bootstrap 次数和随机设置，报告 95% CI。🟡 **第二批部分完成**：Capability-52 使用 seed `20260730`、50,000 次 case-level bootstrap；论文八项 benchmark 待样本级数据进入后沿用该协议。
- [x] 定义 Holm correction family；同时报告原始值、校正值和效应量。统计入口已实现；真实八项结果等待样本级输入。
- [ ] 区分样本间变异和 LLM 重复运行变异。
- [ ] 小样本不报告不稳定的 P90/P95。

### S1-B｜主观评价

- [ ] HLE 主观题使用盲法双评，或使用经过人工校准的独立 judge。
- [ ] judge 看不到方法名称和实验条件。
- [ ] 保存 rubric、judge prompt、评价者身份类别和分歧解决规则。
- [ ] 报告 Cohen’s κ、ICC 或适合评分类型的一致性指标。
- [ ] 逆合成 headline score 若依赖人工判断，对全部计分样本进行双评。
- [ ] 若逆合成使用自动评分，全量运行自动规则，专家抽样用于验证评分器。

### S1-C｜结果展示

- [ ] 主表报告 raw score、maximum、normalized score、sample size、center、dispersion、effect size、CI 和 adjusted p。
- [ ] p-value heatmap 仅作辅助；样本级分布和 paired difference 是主要展示。
- [ ] 雷达图仅作归一化概览。
- [ ] 无显著差异时使用中性结果表述。
- [x] dataset-exact score 与 source-grounded semantic adjudication 分开报告。28 个 exposed mismatches 完成双评、共识与 κ 分析。

### S1 产出

- [ ] M-BENCH、M-STAT。
- [ ] T-1、F-3、SI-3、SI-4。
- [x] 可复现统计入口。证据：`nongpu-final/manuscript-qa/analyze_benchmarks.py` 与 10/10 tests。
- [ ] 最终 run 路径和 manifest。🟡 **第三批部分完成**：CPU 可执行统计、语义双评与问题 ledger 已冻结；S1 八项正式统计 run 等待原始样本级数据。

### S1 完成标准

- [ ] 读者能够判断每个分数的含义、上限、方向、评价者和不确定性。
- [ ] 所有“优于”主张都有预定义的配对证据。

## 4. S2｜Matched-resource comparison、orchestration 与稳定性

**科学问题：** 在资源相同时，FROGENT 的规划、路由、context 管理和错误恢复是否产生可测量价值？

**对应意见：** E-1、E-4；R1-8c；R2-3、R2-5、R2-6；R3-M2a、R3-M4、R3-M5a/b/d、R3-m1

### S2-A｜任务与条件

- [x] 从 retrieval、virtual screening、property/tool use 和 multi-step design 中选择能覆盖核心组件的任务。证据：matched-resource、real-agent、DAVIS、ADMET、structured-retrieval 与 evidence-propagation panels。
- [x] 建立 component–task relevance matrix。证据：real-agent preregistration、job manifest 与 revision evidence ledger。
- [x] 每项消融只用于相关任务。w/o Retrieve 仅覆盖检索依赖 cases，w/o Gauge 仅覆盖设计判断 cases。
- [x] 固定基础 LLM、工具、数据库、样本、预算、并发、重试和停止条件。证据：130 个 frozen real-agent job packets 与各 CPU panel preregistration。
- [ ] 使用相同的评分器和 blind adjudication。

### S2-B｜比较条件

- [x] Direct tools / fixed script。
- [x] Single ReAct Agent，使用相同 LLM 和工具。
- [x] Multi-agent without working context/memory。
- [x] FROGENT without Retrieve，仅用于检索相关任务。
- [x] FROGENT without Gauge，仅用于设计和筛选任务。
- [x] Full FROGENT。
- [x] Literature-only access。
- [x] Matched structured-database access。Open Targets 与 UniProt direct/typed adapter 已完成；DrugBank direct 为 `not_measured`。
- [x] FROGENT without structured DB。Luteolin literature-only 与 structured-retrieval literature arm 已完成。

### S2-C｜错误归因

- [ ] 预先定义互斥错误分类：
  - planning
  - routing
  - parameter
  - tool/permission
  - parsing
  - entity alignment
  - evidence support
  - hallucination
  - conflict handling
  - synthesis/format
- [ ] 两名标注者独立标注失败样本。
- [ ] 报告一致性和分歧解决。
- [ ] 对 baseline 零分逐例解释。
- [x] 报告 direct-tool baseline，避免称作 theoretical oracle。DAVIS 与 matched-resource reports 均使用 direct/fixed baseline。

### S2-D｜灵活性与稳定性

- [x] 选择 3–5 类代表任务，每类设置信息完整/缺失、首选工具可用/失败和目标约束变化。真实与 fixture panels 覆盖完整、冲突、缺失、provider failure、tool outage 和约束变化。
- [x] 比较 fixed workflow 与 dynamic planning。证据：matched-resource 与 real-agent ablation。
- [x] 记录 clarification request、fallback、constraint adherence 和 task success。证据：real-agent raw main outputs 与 validation。
- [x] 对代表性样本重复运行。Europe PMC、real-agent selected cases、Vina、ADMET、property、Dimorphite 和 RCSB 均含重复。
- [x] 报告 plan steps、tool sequence、最终 score、failure rate 和 CI。real-agent、Capability-52、DAVIS 与 matched-resource outputs 分层保存。
- [x] 保存 temperature、model version、cache、retry 和 seed 支持情况。real-agent 记录模型执行条件；deterministic tools 保存版本与 seed，缺少 API token telemetry 的字段保持 `not_measured`。

### S2 指标

- [ ] Task score 和 task completion。🟡 **第二批部分完成**：Capability-52 完成率及 benchmark score 95% CI 已生成。
- [ ] Tool-call、parse、entity alignment 和 citation success。🟡 **第二批部分完成**：Capability-52 citation resolvability 与 retrieved-set consistency 已生成 case-cluster CI。
- [x] Conflict retention 与 unsupported-claim rate。fixture 与 evidence-propagation 中 counterevidence retention 为 1.0，unsupported carry-through 为 0；真实 live synthesis 经独立 8-case adjudication。
- [x] Failure recovery。provider failure、tool outage、conflict fail-closed、correction revocation 与 invalid-input controls 已覆盖。
- [ ] Wall time、token、调用次数和重试。🟡 **第三批部分完成**：70 条 telemetry records 覆盖 CPU/live wall、CPU、RSS、provider calls 和 retry；LLM token 因当前 subagent runtime 不暴露该字段而保持 `not_measured`。
- [x] Run-to-run variation。Europe PMC、Vina、ADMET、property、Dimorphite、RCSB 与 selected agent cases 已记录重复变化。

### S2 产出

- [ ] T-2。
- [x] matched-resource comparison。
- [x] component ablation table。证据：real-agent final report 与 manifest。
- [ ] error attribution figure。
- [x] representative auditable traces。证据：real-agent raw main/specialist outputs、live-evidence raw responses 与 tool command ledgers。
- [ ] performance–cost plot。
- [x] 最终 run 路径和 manifest。证据：`nongpu-final/real-agent-ablation/`、`matched-resource/` 与第三批 final manifest。

### S2 完成标准

- [ ] 资源可得性增益与 orchestration 增益分开报告。
- [ ] 每个保留的架构主张都有对应消融。
- [ ] 单次成功运行不承担稳定性结论。

## 5. S3｜生成模型、构象与 docking

**科学问题：** FROGENT 的模型选择和 Forge–Gauge 反馈是否超出底层生成模型本身，并且构象与 docking 流程是否有数据支持？

**对应意见：** E-1；R1-3c、R1-5a/b/c、R1-9d/e；R3-M5b/c、R3-M6

### S3-A｜实验范围

- [x] 仅纳入 G0 确认 live、可复现且属于论文范围的生成模型：TargetDiff、Pocket2Mol、DiffSBDD。TrioMol2 已按用户确认排除；缺失权重模型不进入正式数值比较。
- [x] 选择小型、有代表性的蛋白 pocket 集。5 structures 覆盖 ABL1、HSP90AA1、EGFR，共 15 个 seeds 和 20 个 PLIP reports。
- [x] 固定每个 pocket 的生成数、后处理、evaluator 和 compute budget。正式 CBGBench 固定每个 model–pocket–seed 500 attempts、10 Å ligand-defined pocket、共同 evaluator；已排除的 TrioMol2 历史预算不进入论文比较。
- [x] 跨模型使用多次独立运行；seed 17/23/31 仅定义各模型内部重复，不解释为跨模型相同随机样本。
- [x] 训练集和已知活性物 comparison collections 使用明确版本：CrossDocked public proxy 固定 Hugging Face revision `87ca3754...`，ChEMBL known-actives 固定 ChEMBL 37（release 2026-05-01）与冻结 assay filters。

### S3-B｜生成模型比较

- [x] 每个论文范围内 live 生成模型独立运行：TargetDiff、Pocket2Mol、DiffSBDD 的 primary、extension 与 combined matrices 已分别完成 45/45、45/45、90/90。TrioMol2 不进入该比较。
- [x] 固定最佳单模型。15 cells × 1,500 TargetDiff attempts 完成；valid rate `0.956`，top-50 score `0.661`。
- [x] FROGENT 单轮模型选择。15 cells 的三模型均匀 single-pass 完成；valid rate `0.444`，top-50 score `0.620`。
- [x] Single-pass Forge→Gauge。候选池、top-50 汇总和 15-cell paired statistics 已进入 final manifest。
- [x] Iterative Forge↔Gauge。15/15 cells 追加 750 次 TargetDiff，matched-budget valid rate `0.704`、top-50 score `0.686`。
- [x] 记录每个 pocket 的模型选择、Gauge 反馈、候选淘汰和停止原因。`gauge-decisions.json`、120-job final manifest、paired Wilcoxon、pocket-cluster bootstrap 与失败/retry provenance 均已保存。

### S3-C｜新颖性与设计指标

- [x] 结构标准化：盐、互变异构体、立体化学。11 records 均保存标准化与立体化学 identity。
- [x] Validity、uniqueness、duplicate rate。11/11 valid、10 个 unique stereo identities；当前输入为 traceable reference panel。
- [x] ECFP4 最近邻和 Bemis–Murcko scaffold overlap：9,767 个生成分子已完成同 pocket 参考配体、ChEMBL target-active 与 CrossDocked training-proxy 三类 comparison；各模型结果和 scaffold reuse 均已分层报告。
- [x] 训练集最近邻与靶点已知活性物最近邻：CrossDocked public proxy 覆盖 99,990/100,000 declared train names；ChEMBL 37 集合含 ABL1 1,653 与 EGFR 8,072 个 canonical actives。Checkpoint-exact membership 与其他未披露训练语料保持未确认。
- [x] QED 和 SA 仅作为设计描述指标，不承担生物活性结论。property panel 与 final claim limits 已分层。
- [x] Pocket compatibility、clash 和几何指标。报告 RMSD、centroid、clash、pocket escape 与 PLIP interaction retention。
- [x] Docking/PLIP 作为计算信号，避免写成实验亲和力事实。DAVIS ρ `0.115` 的负向结果进一步限定 affinity 主张。

### S3-D｜Raw pose、minimization 与 redocking

- [ ] 固定受体准备、质子化、评分器和采样预算。🟡 **第二批部分完成**：1IEP 完成 pH 5.0/7.4/9.0 receptor panel，以及 Vina 1.2.7、exhaustiveness 8、三 seed 五次运行。
- [x] 比较 raw generated pose、local minimization 和 redocking。7-pose paired panel 已完成。
- [x] 报告 clash、pocket escape、centroid displacement、RMSD 和 score。
- [x] 报告 PLIP interaction retention、gain 和 loss。seed 23/31 稳定丢失 ASP381 salt bridge。
- [ ] 按生成模型分层分析。
- [x] 根据结果保留、限定或移除统一 redocking。当前证据支持保留为稳定性检查，并报告跨 seed interaction loss。

### S3-E｜Glucagon 与肽 docking

- [ ] 保存多肽 docking 与 sequence-to-complex 的真实流程。🟡 **部分完成**：正式 docking 方法固定为 MDockPeP2 与 ADCP；ADCP 9/9 reference-redocking 完成，MDockPeP2 历史证据完成审计。ESMFold 与 AF3 作为结构补充对照；ESMFold 24-case 与 AF3 8-case 结构分析已保存。TrioPep 已排除。
- [ ] 记录二级结构来源、模板/预测器、采样、最小化和受体准备。
- [x] 选择小型、有参考结构的 peptide–protein set。3GBQ（10 aa）、1CKB（8 aa）、1ABO（10 aa）来自 RCSB 实验复合物；4ZGM 另作 GLP1R contract-limited exploratory case。
- [ ] 报告 secondary-structure agreement、RMSD/TM-score（适用时）和 interface quality。🟡 **部分完成**：ESMFold 已报告 pTM、pLDDT、reference RMSD、predicted interface 与跨 seed 稳定性；AF3 已报告 ipTM、pLDDT、Semaglutide reference RMSD、contact recall/precision 和跨 provider pose disagreement；ADCP 已补齐 top-1/top-5/top-10 backbone RMSD 与 native-contact recovery。
- [x] 核实实际使用的 MDockPeP2 与 ADCP：MDockPeP2 生产痕迹、source 和历史输出已核实；ADCP 官方 v1.1 隔离 runtime、输入、采样、输出和独立 scorer 已验证。AF3/ESMFold 保留为补充结构证据，TrioPep 已排除。
- [ ] 报告成功率、运行时间和失败原因。🟡 **部分完成**：历史 MDockPeP2 三 run 与 ADCP 9 个正式任务的输出、RMSD、接触恢复和终态已保存；AF3/ESMFold 完整时延仍需按可用 telemetry 汇总，TrioPep 不进入等待或统计。
- [ ] 分开报告前端响应、任务提交和完整计算时间。

### S3 产出

- [ ] M-CONF。
- [ ] T-3。🟡 **核心生成结果已稿件化**：`docs/manuscript/forge-gauge-rebuttal-blocks.md` 已包含三条件 matched-budget 主表和关键 paired contrasts；`docs/manuscript/cbgbench-rebuttal-blocks.md` 已包含三模型 primary/replication/pooled、六 seed stability、novelty 与 pocket/clash 表述。仍需与 peptide docking 结果合并并分配最终表号。
- [ ] 构象准备流程图和参数表。
- [ ] 生成模型与 orchestration 对照。
- [ ] raw/minimized/redocked 对照。
- [ ] Glucagon 可审计轨迹。
- [x] 最终 run 路径和 manifest。CBGBench primary/extension/combined、六 seed stability、novelty/pocket、ChEMBL known-active、CrossDocked training-proxy、ADCP、Forge–Gauge recovery-r06 与 geometry-r03 final manifests 均已冻结；TrioPep 与 TrioMol2 均已排除。

### S3 完成标准

- [x] 底层模型强度和 FROGENT 选择/反馈贡献被分开量化：反馈分配优于均匀 single-pass，已知 fixed-best 保持 valid-rate 优势，top-50 score 差异无统计支持。
- [ ] 肽和 RNA docking 的论文声明与真实 provider 一致。
- [ ] docking 的用途由数据支持并具有明确边界。

## 6. S4｜Evidence reliability 与 DrugBank 独立性

**科学问题：** Retrieve 能否保留证据来源、识别冲突并在缺失 DrugBank 直接关系时给出可核验的候选排序？

**对应意见：** R1-3a/b/d；R3-M3

### S4-A｜Evidence record

- [x] 每条 evidence 保存来源、日期、唯一标识、支持片段、类型和支持/反对关系。证据：harness、retrieval 和 research workflow regression。
- [x] 区分数据库事实、文献结论、计算信号和模型推断。live-evidence、structured-retrieval、Luteolin 与 evidence-propagation 均保存 typed provenance。
- [x] 缺失、冲突、过时和撤回状态显式记录。证据：research-eval fixture 与 correction/revocation regression。
- [x] 未经筛选的 raw result 不进入 working memory。证据：raw-memory contamination 与 admission gate regression。
- [x] 后续判定不合格的 evidence 能从 working memory 撤回。证据：checkpoint/resume correction 和 revocation regression。

### S4-B｜可靠性任务集

- [x] 选择小型真实任务集，覆盖一致、冲突、过时和缺失 evidence。8 个公开 Europe PMC tasks 加 fixture conflict/revocation/provider-failure cases 已完成。
- [x] 使用独立评价者建立 source-grounded reference。8-case independent adjudication 与 28-case semantic double judging 已完成。
- [x] 测量 citation existence、citation support、entity alignment、conflict detection 和 appropriate uncertainty。live/fixture/structured panels 已覆盖；数值 calibration 因系统未输出统一概率而保持 `not_measured`。
- [ ] 系统输出数值置信度时报告 Brier score/reliability；否则使用预定义分级 uncertainty rubric。
- [x] 跟踪错误传播到 Forge、Gauge 和 final synthesis 的比例。4/4 adapter cases 通过，unsupported carry-through 与 revoked leakage 均为 0；production Gauge combined synthesis 缺口已明确记录。

### S4-C｜DrugBank 与文献驱动候选

- [x] 将 Luteolin 标记为 known-candidate retrieval。
- [x] 提供其 DrugBank/文献证据和可追溯 ID。PubChem 5280445、ChEMBL151、CHEBI15864、DrugBank DB15584 与 PMID 36998980 已入 ledger。
- [x] 预注册少量疾病/靶点任务。structured-retrieval 8 cases × 3 arms 已冻结。
- [x] 比较 DrugBank + literature、literature-only 和 matched baseline。DrugBank direct 403 被保留为 `not_measured`，structured proxy 与 literature-only 完成。
- [x] 禁止在 literature-only 条件下调用结构化药物—靶点直接关系。运行记录通过 provider-call validation。
- [x] 评价 evidence-supported prioritization、citation support、unsupported inference 和 hallucination。Luteolin panel 的 citation/support 为 1.0，unsupported/hallucinated 为 0。
- [x] 不使用 “validated efficacy” 描述仅由文献检索生成的候选。当前结论限定为 preclinical PPARγ mechanism evidence。

### S4 产出

- [x] Evidence reliability table。8-case live、6-case fixture 与 structured retrieval metrics 已生成。
- [x] Conflict/error propagation analysis。
- [x] DrugBank vs literature-only comparison。DrugBank direct 缺失值明确标为 `not_measured`。
- [x] Traceable candidate evidence table。
- [x] 最终 run 路径和 manifest。证据：`live-evidence/`、`structured-retrieval/`、`evidence-propagation/`、`luteolin-comparison/` 与第三批 final manifest。

### S4 完成标准

- [ ] FROGENT 能清楚区分已知数据库关联与文献支持的推断。
- [ ] 不确定性会改变候选排序、置信度或下一验证步骤。
- [ ] R3-M3 获得真实实验结果，保持 mandatory。

## 7. X1｜跨 study 的效率与资源记录

**对应意见：** R2-1b、R2-4、R1-9d

所有 S1–S4 正式运行统一记录：

- [x] End-to-end wall time。70 条 telemetry records 和独立 CPU panels 已汇总。
- [x] Agent、tool、queue 和 retry time 完成可测字段处置：tool/provider/retry time 已记录；平台 queue time 未暴露并固定为 `not_measured`，不据 wall time 推断。
- [x] Input/output token 和 LLM 调用次数完成可测字段处置：worker/tool 调用计数已保存；subagent token telemetry 未暴露并固定为 `not_measured`。
- [x] Tool/API 调用次数和可估算费用。公开 CPU/API panels 已记录 calls；免费公开接口费用为 0，外部闭源模型费用未推断。
- [x] CPU/GPU time、peak RAM/VRAM。第三批全程 CPU-only，peak RSS 已记录；GPU/VRAM 为 0/不适用。
- [x] 本地能耗字段完成主张处置：既有冻结运行未采集 CodeCarbon 或等价读数，不进行追溯估算，energy 保持 `not_measured`。
- [x] 闭源云端模型能耗写为 `not_measured`，token 仅作为 workload proxy。
- [x] 样本量足够时报告 median、IQR 和预定义高分位数。小样本组仅报告稳健统计并保留原始记录。
- [x] 可比性边界已冻结：现有材料不支持近期外部系统的硬件、区域、并发和缓存匹配，因此不作跨系统效率比较。

完成标准：

- [x] 摘要中的广义效率提升主张因缺少 matched end-to-end external comparison 决定删除；保留逐组件实测资源结果。稿件与回复块：`docs/manuscript/resource-efficiency-rebuttal-blocks.md`。

## 8. D1｜方法、代码和 SI

- [ ] M-ARCH 描述 task decomposition、context、memory、evidence admission、停止和恢复。
- [ ] Algorithm 1 与真实实现一致。
- [ ] SI-1 提供 Agent、provider、tool、model、version、license、I/O 和回退。
- [ ] SI-2 提供实际 prompt、SOP、预算、重试和停止规则。
- [ ] SI-3 提供八项 benchmark datasheets。🟡 **第二批部分完成**：first-pass machine-readable JSON 与 Markdown 已生成；原始 case/scorer 字段补齐后进入 SI。
- [ ] SI-5 提供可审计轨迹；内容限定为计划、工具调用、证据、状态和结果。🟡 **首轮部分完成**：首轮日志、逐项输出、失败证据和 manifest 已归档，尚未编入 SI。
- [ ] 主 GitHub 链接从无痕/干净环境可访问。
- [ ] 提供版本化 release、环境锁定和最小复现实例。
- [ ] Code Availability 与 Data Availability 使用稳定地址。
- [ ] Clean manuscript 和 marked manuscript 同步生成。
- [ ] 编辑部在线表格逐项完成。

## 9. D2｜近期工作与新颖性

- [x] 补充 Prompt-to-Pill、CLADD、Robin 和检索截止日前相关系统。已完成 source ledger 与 inclusion decisions。
- [x] 能力矩阵包含 pipeline stage、structured DB、generation、peptide、docking、evidence、iteration、safety 和 code availability。
- [ ] 可执行且可公平对齐的系统进入 score comparison。
- [x] 无法运行的系统保留定性比较和可核查原因。
- [x] 删除无法验证的 `first`。revision evidence ledger 将全局首创性表述列为必须收缩的 claim。
- [x] Reviewer 1 comments 3–4 的逐点回复与稿件插入块。`docs/manuscript/reviewer1-comments-3-4-rebuttal-blocks.md` 已绑定 Luteolin、生成分子相似性、近期系统与公平比较边界；最终 page/line 等待排版后填写。
- [ ] 主张由 S2、S3 结果决定。

## 10. D3｜安全、界面和编辑修改

### Mandatory

- [x] 描述真实 safety boundary、refusal policy、logging 和 human review。证据：safety-contract matrix 与 report。
- [x] 如声称 guardrail 有效，增加预定义代表性测试。23/23 contract cases 通过，适用范围限定为当前测试矩阵。
- [ ] 修复 FROGENT/FROGEN/Frogent 名称。
- [ ] 修复双空格、粘连词、`agentfunctions` 和语法。
- [ ] 修复 Figure 1 BioData 裁切。
- [ ] 修复 Figures 8–9 的位置依赖引用。
- [ ] 核对全部 section、figure、table 和 SI 引用。🟡 **首轮部分完成**：论文完成 37 页构建且无 undefined citation/reference；语义级交叉引用核对继续推进。
- [ ] 结构文件和运行元数据提供稳定下载入口。

### Mandatory product delivery

- [ ] 提供 Markdown、PDF 和 Word 导出。
- [ ] 提供 SDF、MOL2、PDB、FASTA 和运行元数据下载。
- [x] 接入 Mol*、JSmol 或等价 viewer。已实现第一方 PDB/SDF/MOL/MOL2 coordinate viewer，并完成 Chromium interaction smoke test。
- [x] 验证报告内容、结构文件和 viewer 与同一 run 一致。报告由当前会话 messages/attachments/molecules 单一 payload 生成；结构下载和 viewer 使用同一持久化 ChatFiles 记录。

## 11. 两周并行冲刺计划

### 并行工作流

| Track | 范围 | 主要产出 |
|---|---|---|
| A | G0、S1、统计和盲评 | datasheets、修正分数、统计主表 |
| B | S2、baseline、公平性、消融和稳定性 | T-2、错误归因、执行轨迹 |
| C | S3、生成、构象、docking 和肽 | T-3、pose/PLIP、Glucagon 验证 |
| D | S4、检索可靠性和 DrugBank 独立性 | evidence reliability、冲突和重定位结果 |
| E | X1、代码、复现、run manifest | 资源表、代码入口、复现实例 |
| F | 正文、SI、图表、回复信和在线表格 | clean/marked manuscript、SI、rebuttal |
| G | 报告导出、结构下载和 3D viewer | 可验证界面与 smoke-test 记录 |

### Day 1｜2026-07-30

- [ ] Track A/B/C/D/E 共同完成数据、评分、模型、工具和 provider inventory。🟡 **首轮部分完成**：CPU 入口、环境、论文材料和缺失输入 inventory 已完成。
- [ ] 核实 HLE、QED、SA、逆合成、虚拟筛选、DrugBank data flow、memory 和 live capability。🟡 **首轮部分完成**：memory 与 CPU tool path 已验证；其余项目已定位证据缺口。
- [x] Track F 建立 manuscript section、figure、table、SI 和 atomic comment 对应关系。证据：`FROGENT_revision_plan.md` 的 67 条 atomic response map 与 planned locations。
- [ ] Track G 确认报告、结构和 viewer 的现有接口。🟡 **首轮部分完成**：报告和结构输出入口已验证；viewer 与多格式导出仍待实施。

### Day 2｜2026-07-31

- [ ] G0 全部关闭；形成 benchmark datasheets、capability matrix 和重算影响清单。
- [ ] 冻结 S1–S4 样本、条件、评价器、分析单位和 primary contrasts。
- [ ] 启动盲评、matched-resource runs、生成任务和 evidence reliability 数据构建。
- [ ] Track F 完成方法与 SI 骨架；Track G 完成导出和 viewer 实施方案。

### Day 3–4｜2026-08-01 至 2026-08-02

- [ ] Track A 完成评分修正、HLE/逆合成评价和首轮统计。🟡 **提前部分完成**：Capability-52 bootstrap/CI 与 error strata 已完成；HLE/逆合成依赖原始评分材料。
- [ ] Track B 完成 direct-tool、single Agent、matched-resource 和主要组件消融首轮。
- [ ] Track C 完成独立生成模型、固定最佳模型和单轮 FROGENT 生成。
- [ ] Track D 完成一致、冲突、过时、缺失 evidence 样本和 literature-only 首轮。🟡 **提前部分完成**：6-case reliability/recovery fixture 与 4-query live retrieval stability 已完成。
- [ ] Track E 持续收集 X1；Track F 同步写 Methods；Track G 开发导出、下载和 viewer。

### Day 5–6｜2026-08-03 至 2026-08-04

- [ ] Track B 完成 global-context、Retrieve、Gauge、动态规划和故障回退条件。
- [ ] Track C 完成 Forge–Gauge 迭代、raw/minimized/redocked 和 PLIP。🟡 **范围更新**：CPU raw/minimized/redocked 与 PLIP 已完成；TrioMol2 candidate pool 已从论文与大修完成条件排除，不再承担 Forge–Gauge 证据。
- [x] Track C 完成 Glucagon 与参考肽集的构象/docking runs。ADCP 9/9、ESMFold 24/24 candidate + 9/9 reference、AF3 8/8 和 MDockPeP2 历史审计均已终态；TrioPep 已从大修范围排除，prospective MDockPeP2 因 provider operability 未闭合保持 `not_measured`。
- [ ] Track D 完成 citation support、conflict detection、uncertainty 和 downstream propagation。🟡 **提前部分完成**：citation identifier metrics、conflict detection、gap visibility 和 revocation 已完成；semantic support 与 downstream propagation 待补。
- [ ] Track G 完成首个可用版本并开始 smoke test。

### Day 7｜2026-08-05

- [ ] S1–S4 首轮运行全部结束。
- [ ] 汇总缺失、失败、超时、权限和异常结果。🟡 **首轮部分完成**：非 GPU first-pass 已汇总到 manifest；正式 S1–S4 汇总在 Day 7 更新。
- [ ] 只重跑有预定义理由的失败条件，保留原始失败记录。
- [ ] Track F 完成 Methods 初稿、benchmark mapping 和工具清单。

### Day 8–9｜2026-08-06 至 2026-08-07

- [ ] 完成必要重复运行、稳定性分析和盲评分歧解决。🟡 **提前部分完成**：Europe PMC、Vina、Dimorphite 和 RCSB 重复运行已完成；盲评分歧待正式 judge。
- [ ] 完成配对统计、effect size、CI、Holm correction 和逐案例错误分析。🟡 **提前部分完成**：Capability-52 95% CI 和逐案例错误表已完成；论文八项配对统计、effect size 与 Holm correction 待原始数据。
- [ ] 完成所有主表、补充表、pose 图、交互图和性能—成本图。
- [x] Track G 完成 Markdown/PDF/Word、结构下载和 viewer 验证。聊天历史不暴露服务器绝对路径；附件与结构下载均为登录态、owner-scoped URL。第一方 3D viewer 支持 PDB、SDF/MOL 和 MOL2。当前会话可下载 Markdown、PDF 与真实 OOXML Word；三格式保留相同英文、中文和结构清单，PDF 与 DOCX 均完成视觉渲染检查，跨用户报告访问返回 404。
- [ ] Track E 完成干净环境安装和最小复现实例首轮。

### Day 10｜2026-08-08

- [ ] 冻结最终结果、run 路径和 manifest。🟡 **第二批部分完成**：首批与第二批非 GPU run 均已冻结，最终投稿结果仍按 Day 10 冻结。
- [ ] 完成 claim–evidence review，确定摘要、引言、结果和讨论中的最终主张。
- [ ] 更新 Figure 1/3、能力状态、代码链接、安全边界和效率表述。

### Day 11–12｜2026-08-09 至 2026-08-10

- [ ] 完成正文、SI、clean manuscript 和 marked manuscript。
- [ ] 完成 67 条 atomic comments 的 point-by-point response。
- [ ] 每条回复填入 action、result、section、page、line、figure/table 和 outcome。
- [ ] 完成编辑部在线表格和投稿文件清单。

### Day 13｜2026-08-11

- [ ] 独立复现关键表格和图。
- [ ] 从干净环境核对代码、数据、模型、报告、结构下载和 viewer。
- [ ] 逐条核对审稿原文、回复、正文修改和 SI。
- [ ] 完成语言、引用、图表、敏感信息和文件一致性检查。

### Day 14｜2026-08-12

- [ ] 修复独立核对发现的全部问题。
- [ ] 完成最终 clean/marked manuscript、SI、response letter 和在线表格。
- [ ] 生成最终投稿包并执行最终 acceptance checklist。
- [ ] 全部工作完成。

## 12. Readiness gates

### Gate R0｜解除 `blocked`

- [ ] G0 完成。
- [ ] HLE、QED、SA、逆合成和工具声明冲突已处理。
- [ ] A-1 至 A-7 已决策。

### Gate R1｜进入 `draft_with_placeholders`

- [ ] S1–S4 方案冻结。
- [ ] 所有 baseline、模型和工具真实可执行。
- [ ] manuscript planned locations 已确定。

### Gate R2｜进入 `ready_to_submit`

- [ ] S1–S4 与 X1 完成，或每个未完成请求有明确且可信的 scope response。
- [ ] 所有 headline claims 与结果一致。
- [ ] 每个 atomic reviewer comment 有唯一 outcome。
- [ ] 每条回复包含准确稿件位置。
- [ ] 代码、数据、SI 和界面声明通过独立核对。
- [ ] 编辑要求的三类文件和在线表格齐全。
