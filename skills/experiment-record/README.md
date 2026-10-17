# experiment-record 使用说明书

把实验日志和已知环境交给 Codex，生成可追溯的实验记录，后续可以查找做过的实验、比较结果并进行阶段复盘。支持成功、失败、中断和只完成部分步骤的实验。

## 安装

需要 Python 3，归档脚本仅使用标准库，无需安装 torch 或访问 NPU。

将本目录完整复制到 `$CODEX_HOME/skills/experiment-record`；未设置 `CODEX_HOME` 时使用 `~/.codex/skills/experiment-record`。在新会话中使用 `$experiment-record` 调用。

默认实验仓库为 `D:\experiment`，也可以在请求中指定其他路径。使用其他路径时，调用脚本同样传入 `--root`。安装 skill 本身不会自动创建实验记录或 Git 仓库；首次使用新目录时可以让 Codex 初始化目录、说明文件和空索引，需要 Git 管理时明确要求初始化 Git。

## 第一次记录实验

把运行日志作为附件、可访问的本地文件路径或聊天文本提供给 Codex，再发送：

```text
用 $experiment-record 把这次实验记录到 D:\experiment。
日志在：<本地日志路径>，另附部署和压测命令。
执行时间：<日期和大约时间>，时区：<已知时区>。
模型：<模型名称或路径>。
机器/环境：<机器别名、NPU 型号和卡数、镜像、已知软件版本>。
实验目的：<可选>。
遇到的问题：<可选>。
日志中没有的信息标为未知。
```

尖括号内容由你填写；不需要每项都提供。Codex 会从已有日志提取可确认的信息，缺失项列入待补信息，不会用当前环境推测过去的版本，也不会把归档时间当作执行时间。

建议同时提供服务端日志、部署命令、压测命令和压测汇总。日志只能证明启动完成时，记录会注明尚无完成压测的证据。

## 一条记录包含什么

| 内容 | 记录范围 |
|---|---|
| 执行时间 | 开始/结束时间精确到分钟，独立标注时区与时间依据 |
| 模型 | 名称、路径、revision、dtype、量化方式 |
| 机器 | 机器别名、NPU 型号/卡数、操作系统、驱动/固件等已知信息 |
| 环境 | 镜像 tag/digest，vLLM、vLLM-Ascend、Triton、CANN、torch、torch_npu、Python 版本或 commit |
| 部署 | 实际命令、环境变量、拓扑、TP/DP/PP/EP、图模式、上下文长度、调度和 KV cache 等核心参数 |
| 压测 | 工具、命令、数据集、输入/输出长度、请求数、并发/QPS、预热、每轮指标及失败请求 |
| 结果 | 结果摘要、证据支持的结论、适用范围与限制 |
| 可选内容 | 实验目的、踩坑现象、处理过程、验证结果 |
| 可追溯信息 | 日志来源、关键片段或行号、附件路径/哈希、缺失项、关联实验、标签 |

完整字段约定见 [record-format.md](references/record-format.md)。版本未知时留空；没有压测结果时不填零。根因猜测与已验证结论分开保存。

## 文件在哪里

```text
D:\experiment\
├── README.md
├── AGENTS.md
├── INDEX.md                         实验总索引
├── experiments\YYYY\MM\<id>\
│   ├── record.json                  结构化事实来源
│   ├── README.md                    从 JSON 生成的实验摘要
│   └── evidence\                   脱敏日志或摘录
└── reviews\
    └── YYYY-MM-DD-主题.md           按需生成的复盘
```

时间未知的实验 ID 带 `undated-` 前缀，目录按归档年月放置；索引仍显示执行时间未知。补齐执行时间后保持 ID 和目录稳定。

同一配置的多轮测量可以归为一条记录；模型、代码、拓扑或关键配置变化时拆分并关联。UUID 后缀防止目录重名，但语义去重由 Codex 阅读日志和既有记录完成，脚本不会自动判断两份日志是否来自同一次运行。

## 补充、检索与复盘

补充已有记录：

```text
用 $experiment-record 补充实验 <实验 ID>：
这是当时的镜像 digest 和 vllm-ascend commit，请更新已有记录，保留证据来源。
```

检索历史：

```text
用 $experiment-record 找出 Qwen 在 TP8 配置下做过的实验，列出环境、吞吐、TTFT 和记录链接。
```

阶段复盘：

```text
用 $experiment-record 复盘 2026-10-01 到 2026-10-31 的实验。
按模型分组，比较条件一致的实验，整理结果、反复遇到的问题、证据不足的结论和下一步建议。
把复盘保存到 D:\experiment\reviews。
```

复盘会链接原始记录。模型、硬件、版本、输入/输出长度、负载、精度、预热或指标口径不同，都会影响可比性；单次测量不会被描述为已证明的稳定提升。执行时间未知的实验无法可靠归入时间区间，会单独提示。

不会自动设置定期任务。希望每周或每月复盘时，另行明确要求创建自动化。

## 手动使用归档脚本

通常让 Codex 操作即可。以下是 Windows 默认安装路径示例；其他安装位置替换脚本路径。PowerShell 中运行：

```powershell
$recordScript = "$env:USERPROFILE\.codex\skills\experiment-record\scripts\records.py"

# 生成 JSON 骨架；输出文件必须尚不存在。
python $recordScript template --output 'D:\experiment\draft.json'

# 填写 draft.json 后归档；title 必填，其他字段遵循骨架类型。
python $recordScript --root 'D:\experiment' add --input 'D:\experiment\draft.json' --slug 'qwen-tp8'

# 修改已归档 record.json 后，重新生成所有实验摘要和总索引。
python $recordScript --root 'D:\experiment' rebuild

# 按执行开始日期筛选，包含首尾两日；同时返回时间未知的记录。
python $recordScript --root 'D:\experiment' list --from 2026-10-01 --to 2026-10-31
```

`add` 归档填好的 JSON 并生成摘要和索引；日志解读、证据复制、脱敏、语义去重以及复盘由 Codex 完成。脚本不会自动解析原始日志或采集环境。草稿不属于实验记录，归档完成后可自行移走。

`record.json` 是事实来源。不要直接修改生成的实验 `README.md` 或 `INDEX.md`，否则 `rebuild` 会覆盖这些修改；补充说明应写入对应 JSON 字段。

## 日志与数据保存

日志保留脱敏副本或注明来源的摘录。大文件可以只记录外部路径和 SHA256，此时文件尚未复制到实验仓库，仍需单独保存或备份。私密数据和凭据不进入记录。

个人 skills GitHub 仓库保存可复用 skill 代码和本说明书；本地实验仓库保存真实实验数据。记录操作不会自动 Git 提交、推送或执行远端命令；需要这些操作时另行提出。
