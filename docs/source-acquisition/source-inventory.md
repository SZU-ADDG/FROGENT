# 远端源码盘点与精简复制报告

盘点日期：2026-07-14
复制与本地脱敏完成日期：2026-07-15
远端主机：`doomx_3nd`

## 安全边界

- `/work/pqh/projects/agent/` 与 `/work/pqh/projects/Frogent1/` 全程保持只读。
- `sudo -n` 仅用于读取普通账号无权访问的路径。
- 未执行删除、移动、改名、权限修改、Git 工作区修改、依赖安装或程序启动。
- 本地项目操作范围严格限制在 `/Users/dongxu/projects/FROGENT/` 内。

## 原始体积与实际精简结果

| 来源 | 原始磁盘占用 | 最终 dry-run / 实际文件字节 | 实际文件数 | 本地磁盘占用 |
|---|---:|---:|---:|---:|
| MCP `/work/pqh/projects/agent/` | 74,317,410,304 bytes，约 70G | 8,216,868 bytes | 881 | 10,380 KiB |
| FROGENT `/work/pqh/projects/Frogent1/` | 636,248,064 bytes，约 607M | 7,955,630 bytes | 176 | 8,184 KiB |
| 合计 | 74,953,658,368 bytes，约 69.81 GiB | 16,172,498 bytes，约 15.42 MiB | 1,057 | 18,564 KiB |

实际选取字节相对原始磁盘占用减少 `99.97842334%`。最终 dry-run 的 rsync 清单项为 MCP 1,056、FROGENT 198，清单项包含文件与必要目录；最终 dry-run 与真实复制的文件字节完全一致。

## 实际复制与安全属性

- 用户于 2026-07-15 明确批准按当前 code-only 清单复制并立即在本地脱敏。
- 本地目标分别为 `sources/mcp/` 与 `sources/frogent/`，两个来源没有混合。
- rsync 使用递归、时间戳保留、`--safe-links`、空目录裁剪、10 MiB 单文件上限与读取超时；没有使用任何删除、移源或覆盖远端状态的参数。
- 复制后本地共有 1,057 个普通文件，符号链接为 0，超过 10 MiB 的文件为 0，数据库、权重、checkpoint、归档、SQL dump、pickle、字节码和日志产物为 0。
- FROGENT 入口 `sources/frogent/app_v4.py` 已落盘。

## 远端只读复核

复制前后分别读取以下检查点；inode、大小、mtime 与 ctime 均一致：

| 检查点 | inode | 大小 | mtime epoch | ctime epoch |
|---|---:|---:|---:|---:|
| `/work/pqh/projects/agent` | 2731094964 | 25 | 1770642077 | 1770642077 |
| `/work/pqh/projects/Frogent1` | 11904719374 | 4096 | 1777343184 | 1777343184 |
| `/work/pqh/projects/Frogent1/app_v4.py` | 11904719400 | 25709 | 1766492674 | 1772700226 |

这些检查点证明根目录与关键入口的元数据保持不变；执行记录中的远端命令均为 `stat`、`find`、`du`、`ls`、`file`、Git 只读查询或 rsync 只读发送端。

## MCP 主要体积来源

| 路径 | 占用 | 分类 | 精简策略 |
|---|---:|---|---|
| `mcp-toolset/mdockpep2.1/` | 36.50 GB | PDB 数据库、对接任务结果、捆绑运行时 | 保留项目源码；排除数据库、任务目录和捆绑运行时 |
| `mcp-toolset/Trio-pep/` | 26.84 GB | ESMFold、LLM 权重、GraphPep 权重、targets 结果 | 保留 Python、配置与文档；排除模型文件和 targets |
| `mcp-toolset/FragGen/` | 4.26 GB | LinkerGPT 权重 | 保留源码；排除 `.pt` 权重 |
| `mcp-toolset/CBGBench/` | 3.98 GB | 归档包、checkpoints、结果和临时数据 | 保留源码；排除归档、权重、结果和临时目录 |
| `mcp-toolset/DirectMultiStep/` | 1.91 GB | compounds 数据、checkpoints、processed 数据 | 保留源码；排除 `data/` |

最大的单文件包括：

- `Trio-pep/Judge/ESMfold/esmfold.model`：8.45 GB
- 两个 `model-00001-of-00002.safetensors`：各 4.98 GB
- `mdockpep2.1/database/pdbs.tar.gz`：4.76 GB
- `FragGen/weights/linkergpt_*.pt`：4.15 GB
- `CBGBench/moda.tar.gz`：3.70 GB
- `Trio-pep/Judge/GraphPep/models/esm2_*.pt`：2.60 GB
- `DirectMultiStep/data/compounds/eMolecules.txt`：897 MB

## FROGENT 主要体积来源

| 路径 | 占用 | 分类 | 精简策略 |
|---|---:|---|---|
| `mcp-toolset/` | 353.20 MB | p2rank 模型、二进制和 Molecular_Docking 工具 | 保留可读源码与配置；排除模型、二进制和测试输出 |
| `uploads/` | 188.37 MB | 用户上传与运行生成文件 | 整体排除 |
| `workspace/` | 75.68 MB | 运行时工具工作区 | 整体排除 |
| 三个 SQL dump | 约 10.4 MB | 数据库备份 | 通过源码白名单排除 |
| `__pycache__/`、`.idea/`、日志 | 少量 | 缓存、编辑器状态、运行日志 | 整体排除 |

## 入选内容验证

- `app_v4.py`：已入选。
- `requirements.txt`：已入选。
- `config.py`：已入选并完成本地脱敏。
- FROGENT `assets/`：8 个清单项。
- FROGENT `templates/` 与 `templates1/`：15 个模板清单项。
- MCP 各工具均保留源码清单：CBGBench、admet_ai、plip、dockstring、DirectMultiStep、Trio-pep、FragGen、mdockpep2.1、p2rank_2.5、TargetDiscovery。
- 实际复制结果中的 `.model`、`.safetensors`、`.pt`、`.ckpt`、`.zst`、`.sql`、归档、pickle、字节码和日志文件数量为 0。

## 本地脱敏结果

脱敏器 `scripts/sanitize_imported_sources.py` 先执行只读干跑，在敏感残留归零后才执行原子写入。它扫描了 982 个 UTF-8 文本文件，实际修改 16 个文件：

| 规则 | 替换数 |
|---|---:|
| API / provider Token | 8 |
| 应用密钥与数据库 URI 配置 | 3 |
| SSH 主机、账号、密码赋值 | 24 |
| SSH/SCP 位置参数调用 | 3 |
| 数据库连接参数 | 5 |
| 内网地址 | 63 |
| 部署文档中的字面凭据示例 | 2 |
| 新增必要的 `import os` | 3 |

- 代码中的运行时敏感值统一改为 `os.getenv(...)`；注释与文档改为命名占位符。
- `.env.example` 提供 19 个空值配置键，真实值数量为 0；`.gitignore` 忽略 `.env` 与其本地变体，同时保留 `.env.example`。
- 脱敏后再次运行脚本，结果为 `files_to_change=0`、`residual_files=0`，说明处理可重复且已收敛。
- 独立正则扫描得到：provider Token 0、带凭据 URI 0、私钥块 0、SSH 字面赋值 0、内网地址 0。`uv.lock` 中形似内网地址的数字属于依赖版本号，已按上下文保留。
- 独立 AST 扫描得到硬编码敏感常量 0。
- 过程中没有生成含原始值的备份；临时文件、Python 缓存与本地符号链接均为 0。
- 日志复核发现，前置上下文检查的一条 SSH 字面密码曾出现在工具输出中；本报告不记录该值，本地副本已完成清除。对话日志可能保留早期输出，建议由有权限的维护者轮换对应凭据。

## 源码语法基线

本地只做静态 AST 解析，没有启动应用、安装依赖或执行项目测试。复制前的源码已有 4 个语法错误；脱敏后的错误文件和行号完全一致，因此本次处理没有引入新的语法错误：

- `sources/frogent/QAM_v1_anonymous.py`：第 337 行
- `sources/mcp/mcp-toolset/mdockpep2.1/mdockpep2.1.py`：第 870 行
- `sources/mcp/mcp-toolset/mdockpep2.1/valid_GLPR.py`：第 24 行
- `sources/mcp/mcp-toolset/mdockpep2.1/valid_HLA.py`：第 9 行

## 统一的本地目录结构

```text
/Users/dongxu/projects/FROGENT/
├── .env.example
├── .gitignore
├── AGENTS.md
├── .learnings/
├── docs/source-acquisition/
│   ├── README.md
│   ├── rsync-code-only.rules
│   └── source-inventory.md
├── scripts/
│   └── sanitize_imported_sources.py
└── sources/
    ├── mcp/
    └── frogent/
```

两个来源位于同一个项目根目录，来源边界清晰；后续重构可以在新的本地目录结构中逐步整合。

## 完成状态

- [x] 用户批准当前 code-only 规则。
- [x] 两个本地目标的规范化路径均位于项目根目录内。
- [x] 最终 dry-run 与实际复制字节一致。
- [x] 远端只读复制完成，没有使用破坏性参数。
- [x] 文件数、大小、入口、链接和禁入产物完成核验。
- [x] 本地敏感信息脱敏完成，复扫残留为 0。
- [x] 远端关键元数据与复制前一致。

当前本地源码已满足进入版本控制准备与重构整理的安全前置条件；本次任务没有初始化 Git。

## TrioWorkspace MCP 增量（2026-07-23）

- 来源：`doomx_3nd:/work/doomx/TrioWorkspace/`，原始占用约 82G。
- 精确只读清单：`docs/source-acquisition/trioworkspace-control-plane.files`。
- 本地边界：`sources/trioworkspace/`，与既有两个来源保持隔离。
- dry-run 与实际复制一致：41 个普通文件、212,252 bytes、符号链接 0。
- 入选内容只含 control-plane、数据库契约、worker、五个 compute adapters、healthchecks、
  launch contracts 与 accepted release metadata；69G runtime、模型、环境、任务、数据库、密钥、
  日志、cache 和结果工件均未复制。
- 复制前后远端根与 control-plane server 的 inode、大小、mtime、ctime 完全一致；未执行远端写入、
  安装、启动、停止或任务提交。
- 脱敏器新增独立 `trioworkspace` source scope，扫描总数由 982 增至 1,023；首次本地处理修改
  4 个 source snapshot 文件，收敛复扫为 `files_to_change=0`、`residual_files=0`。
- 新 MCP 通过本地 stdio server 经 SSH 执行一次性 remote relay。HMAC secret 仅由远端 relay
  内存读取，FROGENT 本地配置、模型上下文和日志均不接触该值。
