# Errors

此文件用于记录命令、远端连接及外部工具错误。

## [ERR-20260715-014] initial_git_diff_whitespace

**Logged**: 2026-07-15T23:28:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
首次暂存后的 `git diff --cached --check` 发现来源盘点文档两行尾随空格。

### Error
```
copy-plan/source-inventory.md:3: trailing whitespace
copy-plan/source-inventory.md:4: trailing whitespace
```

### Context
- 敏感字段、大文件和符号链接检查均已完成。
- Git 暂存已经发生，commit 尚未执行。

### Suggested Fix
移除两行尾随空格，重新暂存并重跑 `git diff --cached --check`。

### Metadata
- Reproducible: yes
- Related Files: copy-plan/source-inventory.md

### Resolution
- **Resolved**: 2026-07-15T23:29:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已使用精确补丁移除尾随空格，等待最终 Git 门禁重跑。

---

## [ERR-20260715-013] secret_scan_shell_quoting

**Logged**: 2026-07-15T22:50:00+08:00
**Priority**: low
**Status**: resolved
**Area**: security

### Summary
候选提交文件的补充敏感字段扫描使用了含单引号字符类的 shell 正则，zsh 在传给 `rg` 前将其解析成了错误 glob。

### Error
```
zsh: bad pattern
```

### Context
- 文件清单和大文件检查已经完成。
- 正则扫描没有执行，项目文件没有因此发生修改。

### Suggested Fix
将正则作为单独参数安全传递给 `rg`，或使用避免 shell 引号冲突的表达式，再检查退出状态。

### Metadata
- Reproducible: yes
- Related Files: .gitignore

### Resolution
- **Resolved**: 2026-07-15T22:51:00+08:00
- **Commit/PR**: N/A
- **Notes**: 改用安全双引号表达式重跑，并将第三方 sources、数据库和模型权重加入 Git 排除规则。

---

## [ERR-20260715-012] codex_thread_creation_timeout

**Logged**: 2026-07-15T22:23:58+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
并行创建 FROGENT 实现层与文档层会话时，Codex App 的两个 create_thread 请求均在返回会话 ID 前超时。

### Error
```
implementation: Timeout
documentation: Timeout
```

### Context
- 两个会话都以本地 FROGENT project target 创建。
- 当前验收层已经重命名并取得 thread ID。
- 超时可能发生在会话已进入后台队列之后，直接重试存在重复创建风险。

### Suggested Fix
先通过 list_threads 查询最近会话与初始任务；确认缺失的角色后再单独重试，并在创建后补发三方 thread ID 和交接协议。

### Follow-up
- 后端仅返回当前验收层；已验收实现层已经成功归档。
- 多次失败的文档层创建没有生成 thread ID，因此无法通过归档接口定位。
- Codex App 禁止 Computer Use 控制自身界面，当前可用恢复路径是完全退出应用后重新打开并重新同步任务列表。

### Metadata
- Reproducible: unknown
- Related Files: AGENTS.md

### Resolution
- **Resolved**: 2026-07-15T23:24:00+08:00
- **Commit/PR**: N/A
- **Notes**: 用户清理失败卡片后，使用短启动 prompt 成功创建文档任务；取得 thread ID 后设置英文名称并发送完整工作包，流程稳定完成。

---

## [ERR-20260715-011] learning_insert_context

**Logged**: 2026-07-15T21:00:00+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
写入用户纠正记录时，补丁假设最新 Learning 位于文件首项，实际首项仍为远端边界记录。

### Error
```
apply_patch verification failed: Failed to find expected lines in .learnings/LEARNINGS.md
```

### Context
- 同一补丁计划新增 Learning 与 Feature Request。
- 上下文验证失败，两个目标文件都没有发生修改。

### Suggested Fix
以文件头和当前第一个唯一条目 ID 为精确上下文，分别更新 Learning 与 Feature Request，验证后再解决本错误。

### Metadata
- Reproducible: yes
- Related Files: .learnings/LEARNINGS.md, .learnings/FEATURE_REQUESTS.md

### Resolution
- **Resolved**: 2026-07-15T21:17:25+08:00
- **Commit/PR**: N/A
- **Notes**: 已按文件真实首项分开写入 Learning 与 Feature Request；纠正规则随后提升到根目录和插件 AGENTS.md。

---

## [ERR-20260715-010] skill_batch_patch_context

**Logged**: 2026-07-15T17:41:00+08:00
**Priority**: low
**Status**: resolved
**Area**: refactor

### Summary
批量更新六个 Skill 时，其中一份 UI 提示的脚手架文本与补丁预期不一致，补丁上下文校验失败。

### Error
```
apply_patch verification failed: Failed to find expected lines in skills/evaluate-candidate/agents/openai.yaml
```

### Context
- 补丁包含 Skill 正文、UI 提示、runtime 配置与测试文件。
- 上下文验证阶段失败，整份补丁没有应用，项目文件保持原状。

### Suggested Fix
先读取六份实际 UI 提示，再按精确文本分组应用补丁；正文替换与提示修复分别验证。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/skills/*/agents/openai.yaml

### Resolution
- **Resolved**: 2026-07-15T17:46:07+08:00
- **Commit/PR**: N/A
- **Notes**: 已读取六份实际提示并分组应用精确补丁；六个 Skill 通过官方 quick validator，插件整体通过官方 validator。

---

## [ERR-20260714-001] remote_du

**Logged**: 2026-07-14T20:00:26+08:00
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary
当前 SSH 账号无法读取 MCP 目录中的 3 个子目录，完整目录大小统计被中断。

### Error
```
du: cannot read directory '/work/pqh/projects/agent/mcp-toolset/DirectMultiStep/data/compounds': Permission denied
du: cannot read directory '/work/pqh/projects/agent/mcp-toolset/Trio-pep/targets/xod/ligands': Permission denied
du: cannot read directory '/work/pqh/projects/agent/mcp-toolset/Trio-pep/targets/xod/structures': Permission denied
```

### Context
- 通过 `doomx_3nd` 以只读方式执行远端目录大小统计。
- `/work/pqh/projects/agent/` 的可访问部分显示为 `69G`。
- 命令因 `set -e` 在第一个 `du` 返回非零状态后停止，尚未统计 FROGENT 目录。

### Suggested Fix
分别统计两个目录并容忍单个目录的读取错误；检查拒绝访问路径的所有者、权限与 ACL。若需要完整大小或完整复制，由有权限的账号读取，或由用户授权后协调权限调整。

### Metadata
- Reproducible: yes
- Related Files: AGENTS.md

### Resolution
- **Resolved**: 2026-07-14T20:02:09+08:00
- **Commit/PR**: N/A
- **Notes**: 服务器允许当前账号无交互使用只读 `sudo du`，已取得 MCP 完整占用 `70G`；普通权限下可访问部分为 `69G`。

---

## [ERR-20260715-009] skill_default_prompt_shell_expansion

**Logged**: 2026-07-15T17:35:08+08:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
批量初始化 Skills 时，shell 展开了默认提示中的 `$skill-name`，六份 UI 提示缺少 Skill 名称。

### Error
```
default_prompt values were generated as "Use -<suffix> ...".
```

### Context
- 六个 Skill 目录及其基础元数据均已成功创建。
- 只有 `agents/openai.yaml` 的 `default_prompt` 受到影响。
- 原因是命令字符串经过 shell 解析时没有保留字面量 `$`。

### Suggested Fix
使用 `apply_patch` 写入完整的 `$skill-name` 字面量，随后运行 `quick_validate.py` 校验每个 Skill。

### Metadata
- Reproducible: yes
- Related Files: plugins/frogent-drug-design/skills/*/agents/openai.yaml

### Resolution
- **Resolved**: 2026-07-15T17:46:07+08:00
- **Commit/PR**: N/A
- **Notes**: 六份 default_prompt 已使用 apply_patch 写入完整的字面量 `$skill-name`，架构测试与六个 Skill 官方校验全部通过。

---

## [ERR-20260715-008] dynamic_import_dataclass_registration

**Logged**: 2026-07-15T13:44:42+08:00
**Priority**: low
**Status**: resolved
**Area**: testing

### Summary
合成样例验证通过 `importlib` 动态加载脱敏器时，模块未先注册到 `sys.modules`，Python 3.13 的 `dataclass` 处理失败。

### Error
```
AttributeError: 'NoneType' object has no attribute '__dict__'
```

### Context
- 错误发生在测试夹具导入阶段。
- 脱敏器源码和项目源文件没有发生额外修改。

### Suggested Fix
在 `exec_module` 前执行 `sys.modules[spec.name] = module`，再运行合成规则样例。

### Metadata
- Reproducible: yes
- Related Files: scripts/sanitize_imported_sources.py

### Resolution
- **Resolved**: 2026-07-15T13:44:42+08:00
- **Commit/PR**: N/A
- **Notes**: 修正动态导入注册后，Cookie、PubMed 邮箱和前端认证日志三条合成样例分别命中预期规则。

---

## [ERR-20260715-007] sanitizer_mode_argument_omitted

**Logged**: 2026-07-15T13:43:28+08:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
验证新增脱敏规则时遗漏必需的 `--check` 模式参数，脚本只打印用法并退出。

### Error
```
sanitize_imported_sources.py: error: one of the arguments --check --apply is required
```

### Context
- 命令没有进入扫描流程。
- 没有修改任何项目文件。

### Suggested Fix
使用 `python3 scripts/sanitize_imported_sources.py --check` 执行只读验收。

### Metadata
- Reproducible: yes
- Related Files: scripts/sanitize_imported_sources.py

### Resolution
- **Resolved**: 2026-07-15T13:43:28+08:00
- **Commit/PR**: N/A
- **Notes**: 已使用 `--check` 重跑；扫描 982 个文本文件，待变更文件和残留文件均为 0。

---

## [ERR-20260715-006] target_discovery_cookie_redaction_gap

**Logged**: 2026-07-15T13:40:43+08:00
**Priority**: critical
**Status**: open
**Area**: security

### Summary
架构深读发现 TargetDiscovery 中两个硬编码会话 Cookie，源码上下文输出触及了对应字面值。

### Error
```
Two session cookie literals appeared in tool output; values are intentionally omitted here.
```

### Context
- 先前脱敏规则覆盖常见凭据名称，未覆盖字典键形式的站点会话 Cookie。
- 本地源码中的两个值已改为环境变量引用。
- AST 复扫确认敏感字典键对应的非空字符串字面量为 0。
- 对话工具日志可能仍保留早期输出副本。

### Suggested Fix
由具备权限的维护者在对应站点撤销或轮换这两个会话 Cookie；脱敏器增加敏感字典键和值的 AST 规则，源码上下文输出前统一遮罩高熵字符串。

### Metadata
- Reproducible: yes
- Related Files: sources/mcp/mcp-toolset/TargetDiscovery/disease2target.py, scripts/sanitize_imported_sources.py

---

## [ERR-20260715-005] learning_error_id_collision

**Logged**: 2026-07-15T13:35:56+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
新增错误记录前只读取了文件尾部，遗漏了文件前部已有的当天编号，产生两个临时重复 ID。

### Error
```
ERR-20260715-001 and ERR-20260715-002 were already in use.
```

### Context
- 记录文件按追加位置混排，编号顺序无法从文件尾部推断。
- 重复编号只影响学习日志标识，没有影响源代码。

### Suggested Fix
生成新编号前检索整份文件中同日前缀的全部 ID，再选择未占用的最大编号加一。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-15T13:35:56+08:00
- **Commit/PR**: N/A
- **Notes**: 本次新增条目已重编号为 003、004；本条使用 005，并完成全文件唯一性核对。

---

## [ERR-20260715-004] pubmed_email_patch_context_mismatch

**Logged**: 2026-07-15T13:34:44+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
批量移除多个历史版本中的 PubMed 硬编码邮箱时，补丁假设各文件使用同一字面量，首个文件上下文校验失败。

### Error
```
apply_patch verification failed: Failed to find expected lines
```

### Context
- 脱敏扫描确认五个 Python 文件存在同类邮箱配置。
- 各历史版本的具体字面量存在差异。
- 失败补丁没有修改任何源文件。

### Suggested Fix
逐文件读取命中行，在内存中构造精确补丁，并在修改后复扫邮箱模式。

### Metadata
- Reproducible: yes
- Related Files: sources/frogent/QAM_v1.py, sources/frogent/QAM_v2.py, sources/frogent/QAM_v3.py, sources/frogent/QAM_v4.py, sources/frogent/test_multi_agents_cor2.py

### Resolution
- **Resolved**: 2026-07-15T13:35:56+08:00
- **Commit/PR**: N/A
- **Notes**: 已逐文件构造精确补丁；五个文件 AST 解析成功，目标邮箱复扫命中为 0。

---

## [ERR-20260715-003] git_status_before_repository_init

**Logged**: 2026-07-15T13:32:05+08:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
架构盘点期间在尚未初始化 Git 的项目根目录执行了只读状态查询，命令立即退出。

### Error
```
fatal: not a git repository (or any of the parent directories): .git
```

### Context
- 当前本地目录仍处于精简复制与脱敏后的预版本控制阶段。
- 命令只读取仓库状态，没有修改项目文件。
- 该失败不影响后续静态架构分析。

### Suggested Fix
在执行 Git 查询前先验证 `.git` 是否存在；项目初始化 Git 后再运行状态检查。

### Metadata
- Reproducible: yes
- Related Files: AGENTS.md

### Resolution
- **Resolved**: 2026-07-15T13:32:05+08:00
- **Commit/PR**: N/A
- **Notes**: 已确认根目录没有 `.git`，后续盘点改用文件系统与 AST 只读查询。

---

## [ERR-20260715-002] pre_sanitization_log_redaction_gap

**Logged**: 2026-07-15T02:59:23+08:00
**Priority**: critical
**Status**: open
**Area**: security

### Summary
前置上下文检查遮罩了内网地址、Token 与凭据 URI，但遗漏了 SSH 示例调用中的位置参数密码，导致一个字面凭据出现在工具输出中。

### Error
```
One sensitive literal appeared in tool output; the value is intentionally omitted here.
```

### Context
- 暴露发生在本地脱敏写入之前的只读上下文检查。
- 本地源码中的对应字面值已替换为环境变量，后续内容扫描和 AST 扫描的残留均为 0。
- 对话日志可能保留早期工具输出，项目文件无法消除该日志副本。

### Suggested Fix
由具备权限的维护者轮换对应 SSH 凭据。后续敏感文件检查只输出文件名、规则类型和计数；确需查看上下文时，先遮罩所有字符串字面量和位置参数。

### Metadata
- Reproducible: yes
- Related Files: AGENTS.md, scripts/sanitize_imported_sources.py

---

## [ERR-20260715-001] sanitizer_dry_run_residual_classification

**Logged**: 2026-07-15T02:50:36+08:00
**Priority**: medium
**Status**: resolved
**Area**: tooling

### Summary
本地脱敏器首轮干跑将安全占位值判为残留凭据，并遗漏了无尾逗号形式的数据库套接字参数。

### Error
```
sanitizer dry-run exited with status 2; residual_files=7
```

### Context
- 干跑只在内存中生成候选变更，未修改任何复制后的源码。
- 残留类型均为 `literal_secret_assignment`，集中在示例 API 配置与部署文档。
- 数据库参数规则原先要求尾逗号，无法覆盖调用中的最后一个关键字参数。

### Suggested Fix
明确识别 `EMPTY`、redacted、placeholder 等安全占位值；允许数据库调用的最后一个参数省略尾逗号；再次执行全量干跑并要求残留计数归零。

### Metadata
- Reproducible: yes
- Related Files: scripts/sanitize_imported_sources.py

### Resolution
- **Resolved**: 2026-07-15T02:53:17+08:00
- **Commit/PR**: N/A
- **Notes**: 已识别安全占位值、覆盖无尾逗号参数并对文档中的真实字面凭据使用环境变量占位；第二轮全量干跑扫描 982 个文本文件，敏感残留计数为 0。

---

## [ERR-20260714-004] rsync_manifest_filename_encoding

**Logged**: 2026-07-14T21:42:34+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
FROGENT dry-run 清单包含本地 locale 无法转换的远端文件名字节，`awk` 校验提前停止。

### Error
```
awk: towc: multibyte conversion failure
```

### Context
- 错误发生在本地解析 rsync dry-run 文件名清单时。
- 远端存在一个部署文档文件名，其编码与本地 UTF-8 locale 不兼容。
- rsync 处于 dry-run，源端和本地目标均未发生变更。

### Suggested Fix
对 rsync 清单输出和后续文本处理统一设置 `LC_ALL=C`，按原始字节处理文件名；复制后在本地项目目录内单独记录异常名称，等待重构阶段处理。

### Metadata
- Reproducible: yes
- Related Files: copy-plan/rsync-code-only.rules

### Resolution
- **Resolved**: 2026-07-14T21:43:58+08:00
- **Commit/PR**: N/A
- **Notes**: 设置 `LC_ALL=C` 后按原始字节完成清单校验；`app_v4.py`、依赖文件与前端资源均已确认入选。

---

## [ERR-20260714-003] rsync_remote_filter_merge

**Logged**: 2026-07-14T21:15:16+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
远端 rsync sender 将本地 merge 规则文件路径解释为远端路径，code-only dry-run 在传输前停止。

### Error
```
rsync: [sender] failed to open exclude file copy-plan/rsync-code-only.rules: No such file or directory (2)
rsync error: error in file IO (code 11) at exclude.c(1481) [sender=3.2.7]
```

### Context
- 本地使用 openrsync 2.6.9 兼容实现，远端为 rsync 3.2.7。
- `-f 'merge copy-plan/rsync-code-only.rules'` 由远端 sender 解析。
- dry-run 在构建文件列表前失败，远端和本地源代码均未发生变更。

### Suggested Fix
从本地项目目录读取规则文件，将每一条规则转换为独立的 `-f` 命令行参数，由本地 rsync 随协议发送给远端 sender。

### Metadata
- Reproducible: yes
- Related Files: copy-plan/rsync-code-only.rules

### Resolution
- **Resolved**: 2026-07-14T21:43:58+08:00
- **Commit/PR**: N/A
- **Notes**: 已从本地规则文件读取每条规则并展开为独立 `-f` 参数；MCP 与 FROGENT 的 code-only dry-run 均成功。

---

## [ERR-20260714-002] remote_inventory_awk

**Logged**: 2026-07-14T21:01:23+08:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
远端目录下钻统计中的 `awk` 字段符号被 shell 提前展开，过滤表达式缺少字段操作数。

### Error
```
awk: cmd. line:1:  >= 10485760
awk: cmd. line:1:  ^ syntax error
```

### Context
- 通过 SSH 执行只读 `du | awk | sort` 统计。
- `awk` 程序置于远端双引号中，`$1` 被远端 shell 展开为空字符串。
- 扫描未完成，远端文件没有发生变更。

### Suggested Fix
在远端双引号中将字段符号写为 `\$1`，或采用安全的脚本传递方式，确保 `awk` 收到完整表达式。

### Metadata
- Reproducible: yes
- Related Files: AGENTS.md

### Resolution
- **Resolved**: 2026-07-14T21:09:52+08:00
- **Commit/PR**: N/A
- **Notes**: 已转义 `awk` 的字段符号并启用 `pipefail`，两套远端目录的只读分层统计成功完成。

---

## [ERR-20260714-005] learning_resolution_patch_context

**Logged**: 2026-07-14T21:44:35+08:00
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
更新两个错误条目时，补丁假设条目按编号排列，实际文件顺序不同导致上下文校验失败。

### Error
```
apply_patch verification failed: Failed to find expected lines
```

### Context
- 多次追加记录时使用了通用分隔符上下文，新条目被插入到首个匹配位置。
- 失败补丁没有修改文件内容。

### Suggested Fix
先读取当前文件，再以唯一错误 ID 和完整相邻内容作为补丁上下文；完成更新后重新验证条目状态和归属。

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-07-14T21:45:00+08:00
- **Commit/PR**: N/A
- **Notes**: 已按唯一错误 ID 和实际相邻条目更新状态，并准备再次核对整份记录。

---
