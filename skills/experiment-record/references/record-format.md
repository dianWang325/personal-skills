# 实验数据约定（schema_version: 1）

运行 `scripts/records.py template --output <file>` 获取骨架。`record.json` 是事实来源；同目录 `README.md`、根 `INDEX.md` 由脚本生成，补充内容应写入 JSON，避免 rebuild 丢失手写内容。可在各对象扩展字段，不改变已有字段含义。

| 字段 | 内容 |
|---|---|
| title / purpose | 简明标题；目的可为 null |
| execution | started_at / ended_at，精确到分钟；timezone 独立保存，如 Asia/Shanghai 或 UTC+08:00；time_basis 描述时间证据 |
| status | unknown / success / failed / interrupted / partial；success 指记录所描述的实验任务完成，不能只看服务启动 |
| model | name、path、revision、dtype、quantization；路径和模型名分别保存 |
| environment | machines（别名、NPU 型号/卡数、驱动/固件、操作系统）、container（镜像 tag 和 digest）、versions（vllm、vllm_ascend、triton、cann、torch、torch_npu、python）；版本对象包含 version、commit、dirty 等已知事实，未知为 null |
| deployment | topology、commands、environment_variables、core_config；TP/DP/PP/EP、PD、图模式、max_model_len、max_num_seqs、max_num_batched_tokens、KV cache dtype、显存利用率、量化、投机解码等按实际保存，不预设默认值 |
| benchmark | tool/version、commands、workload、warmup、runs；workload 保留数据集、请求数、输入/输出 token、并发、请求率、seed；每个 run 保存成功/失败数、持续时间和 metrics |
| metrics | 每项明确 name、value、unit、statistic（mean/p50/p99 等）、scope；例如 TTFT ms、TPOT ms/token、output throughput token/s，区分输出与总 token 吞吐 |
| outcome | 结果摘要、证据支持的结论、限制；无压测则明确无压测结果，不填 0 |
| pitfalls | 可选数组；每项记录现象、触发条件、影响、尝试/处理、验证结果和根因可信度，不把猜测写为定论 |
| evidence | 每项包含 field、source、lines 或 excerpt、kind（log/user_statement/manifest）；来源冲突保留双方及待确认项 |
| artifacts | path 或 external_path、sha256、kind、redacted、note；优先实验目录相对路径，摘要使用相对链接；未复制日志标明 external_path |
| missing_information | 缺失或冲突信息；可记录后续补采命令建议，但不能自动执行实验或远端命令 |
| related_records / tags | 关联实验 id、便于查找的标签 |

`id`、`created_at` 和 `schema_version` 由脚本填写。不要填写虚构的实验作为初始化数据。无开始时间时目录使用 `undated-<归档日期时间>-<slug>`，索引日期显示“未知”，未来补齐时间无需重命名目录或更改 id。

没有用户日志时仅初始化空仓库。记录可不完整，但需要可追溯。粘贴的日志标注用户提供，行号只针对确实保留的文本，不编造原文件行号。模型 revision、镜像 digest、commit、dirty 状态缺失会限制复现能力，应诚实列出。
