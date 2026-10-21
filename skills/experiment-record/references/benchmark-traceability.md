# 完整压测日志与服务—负载—日志对应关系

## 完整日志必须落地

压测日志必须完整复制到本实验 evidence/，保留原始字节、首尾内容、换行、工具输出和已有终端格式，不裁剪、不仅保留 grep 结果/尾部/汇总，不用摘要、截图或外部路径替代原件。完整日志便于打开定位原始输出及截图，默认不生成截图，也不为截图清理或重写日志。终端显示截断不代表原文件截断，应通过文件下载取得全文。

stdout、stderr 分开保存时分别归档并引用，不臆造原始交错顺序；仅有 stdout 时注明 stderr 是否包含/缺失。分片、轮转和多进程日志按来源顺序全部保存，并注明角色。同名不同内容分别保存，不覆盖历史日志。

远端文件已知时按现有授权自动读取/下载并核对 SHA256。运行仍在写文件、只收到聊天片段/截图、原日志已清理或无法访问时保留现有材料，log_completeness=partial/unknown，明确缺失和采集截止时间；不能声称已完整归档或自动重跑生成一份新日志冒充旧文件。以后取得全文再以新快照和 update 补充。无法证明日志覆盖完整轮次时，即使复制了整个当前文件也不能标 complete。

此要求优先于“大文件只保留外部路径”的通用例外；压测原始日志无论大小都应完整下载到本地。逐请求 JSONL、模型权重等非日志大附件仍可按原规则外部引用，不得把工具控制台输出改标为大附件规避保存。

## 每轮建立明确绑定

在 benchmark.runs 每一项保存：

| 字段 | 内容 |
|---|---|
| run_id | 本实验内唯一且稳定，如 run-001，不用同一分钟自动合并不同压测 |
| service_instance | 所连接服务的实例标识、端点、已知启动时间、机器/容器；PD/多服务保留角色及实例列表，区分重启前后服务 |
| service_config_refs | 本轮实际服务配置文件/快照的实验内相对路径数组，可覆盖多个 PD 角色；登记到 artifacts |
| benchmark_config_refs | 本轮压测配置/快照的相对路径数组；登记到 artifacts |
| log_refs | 本轮所有原始 stdout/stderr/分片日志的本地相对路径数组；登记到 artifacts，按已知顺序排列 |
| log_completeness | complete / partial / unknown；complete 要有证据覆盖整轮与本地完整日志，partial 表示只有片段/部分时间/部分来源，unknown 表示覆盖情况无法判断 |
| script_refs / artifact_refs | 已有脚本、报告等引用继续保留；不能代替上述三组明确绑定 |
| run 配置/时间/证据 | 执行命令、工作目录、环境变量、起止时间/时区、指标、状态、失败信息及关联证据照原约定保存 |

service_config_refs 代表能追溯运行配置的文件，不只是一份声明开启某特性的脚本。保留已有原始配置；必要时生成 evidence/service-config-001.json 记录日志与命令支持的有效参数、代码/镜像、拓扑与特性实际状态，标注 derived=true、来源和未知项。不能把无法证实的当前服务配置充作历史有效配置。benchmark 配置同样保留实际 CLI 覆盖、环境、数据集、并发/QPS/长度等，缺少文件时可按证据整理派生快照并明确来源。原脚本与原配置仍原样保存。

同服务多轮可共用一个已核实的服务配置引用，但压测配置和日志分别绑定；服务重启、配置或代码变化必须用新的服务实例/配置引用。多轮共用一个原始日志时允许共用 log_refs，必须逐轮注明准确的时间范围/行号来源（log_ranges 字段），不能拆分掉原始完整日志或假定相邻输出属于同轮。范围未知列入 missing_information。

## 附件登记和展示

每个配置和日志都在 artifacts 中记录 path、kind、source、retrieved_at、sha256。完整日志使用 kind=benchmark_log、content_scope=full；片段使用 content_scope=excerpt，注明缺失范围。content_scope=full 只说明所存文件是原文件的完整副本，不单独证明整轮输出齐全；run.log_completeness 表示整轮覆盖情况。校验脚本不会仅凭文件存在推断完整度。

例如本轮可以引用 evidence/service-config-001.json、evidence/benchmark-config-001.json、evidence/benchmark_run-001.log。不增加实验根目录的层级；既有 source 文件名也可保留，不要求机械重命名。

摘要会自动生成“服务配置 → 压测配置 → 压测日志”表，按 run_id 列出实例、配置和日志文件链接及完整度，方便打开日志截图。unknown/missing 不会替用户选择一套配置。

verify 检查三组引用是否登记/存在、文件 SHA256、run_id、实例信息、日志完整度声明。缺绑定、缺实例或无法确认完整日志标 incomplete；宣称 complete 却没有本地日志引用或对应附件不为 full 则 failed。未取得完整日志时必须在归档回复中说明，不能只以压测结果成功掩盖记录不完整。
