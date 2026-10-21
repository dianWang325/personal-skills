# 实验数据约定（schema_version: 1）

运行 `scripts/records.py template --output <file>` 获取骨架。`record.json` 是事实来源；同目录 `README.md`、根 `INDEX.md` 由脚本生成，补充内容应写入 JSON，避免 rebuild 丢失手写内容。可在各对象扩展字段，不改变已有字段含义。

| 字段 | 内容 |
|---|---|
| title / purpose | 简明标题；目的可为 null |
| execution | started_at / ended_at，精确到分钟；timezone 独立保存，如 Asia/Shanghai 或 UTC+08:00；time_basis 描述时间证据 |
| status | unknown / success / failed / interrupted / partial；success 指记录所描述的实验任务完成，不能只看服务启动 |
| model | name、path、revision、dtype、quantization；路径和模型名分别保存 |
| environment | machines（别名、NPU 型号/卡数、驱动/固件、操作系统）、container（镜像 tag 和 digest）、versions（vllm、vllm_ascend、triton、cann、torch、torch_npu、python）；版本对象包含 version、commit、dirty 等已知事实，未知为 null |
| environment.versions.aisbench / aisbench_auto_tools_prefix | 独立保存评测工具与辅助工具的运行时版本号、commit、dirty、实际路径/运行环境和版本证据；没有版本元数据时可用内容 SHA256 标识。使用但未知时明确列入缺失项，不能以路径名或另一个工具版本替代 |
| deployment | topology、commands、environment_variables、core_config；TP/DP/PP/EP、PD、图模式、max_model_len、max_num_seqs、max_num_batched_tokens、KV cache dtype、显存利用率、量化、投机解码等按实际保存，不预设默认值 |
| runtime_features | 各特性的 requested、observed_status、scope、events、evidence_refs、run_refs、impact，分别保存请求配置与实际生效/回退；具体见 [特性记录约定](runtime-features.md)。旧记录未含此字段仍可读取，不补造历史状态 |
| benchmark | tool/version、commands、workload、warmup、runs；workload 保留数据集、请求数、输入/输出 token、并发、请求率、seed；每个 run 保存成功/失败数、持续时间和 metrics |
| benchmark.runs 的配置—日志绑定 | run_id、service_instance、service_config_refs、benchmark_config_refs、log_refs、log_completeness；原始压测日志必须全文本地归档，不能用摘要或外部路径替代。详见 [压测追溯约定](benchmark-traceability.md) |
| accuracy | 精度评测工具、命令、datasets、evaluation_config、逐轮/逐数据集/子任务结果与原始报告引用 |
| tests | 测试工具、命令、test_type、selection、case_matrix、criteria、逐轮/逐用例结果、失败详情与原始报告引用 |
| metrics | 每项明确 name、value、unit、statistic（mean/p50/p99 等）、scope；例如 TTFT ms、TPOT ms/token、output throughput token/s，区分输出与总 token 吞吐 |
| outcome | 结果摘要、证据支持的结论、限制；无压测则明确无压测结果，不填 0 |
| pitfalls | 可选数组；每项记录现象、触发条件、影响、尝试/处理、验证结果和根因可信度，不把猜测写为定论 |
| evidence | 每项包含 field、source、lines 或 excerpt、kind（log/user_statement/manifest）；来源冲突保留双方及待确认项 |
| artifacts | path 或 external_path、sha256、kind、redacted、note；优先实验目录相对路径，摘要使用相对链接；未复制日志标明 external_path |
| artifacts 的远端采集信息 | source 中保存 host/port/user/container/path（已知项），retrieved_at 含时区；sha256 为本地归档字节哈希，可另存 source_sha256 及校验结果。默认原样保存、redacted=false；区分完整文件与摘录，采集时快照不自动等于运行时版本 |
| deployment / benchmark / accuracy / tests 的 script_refs | 指向 artifacts 中归档脚本的相对路径；不同轮次使用不同快照时在 runs[].script_refs 中关联。已提供的服务拉起/压测/评测/测试脚本必须原样保存实际内容，不只保留命令或源路径 |
| missing_information | 缺失或冲突信息；可只读查询相关远端文件/版本并记录补采建议，不能自动执行实验或修改环境 |
| related_records / tags | 关联实验 id、便于查找的标签 |
| revision_history | update 自动追加的修订原因、记录时间、前后字段及内容哈希；不手改历史，不将修订时间当实验执行时间 |
| attempts | 排查假设、尝试措施、实际结果、支持/反驳/未决判断、排除项、范围与证据；失败路线同样保留 |
| lessons | claim、status、conditions、counterexamples、limitations、evidence_refs；修正通过新条目 supersedes 关联原条目 |
| retrieval | symptoms、error_keywords、features、fixes、keywords 字符串数组，供问题检索与索引展示 |
| reuse_feedback | 对来源实验中某条经验确切内容哈希的应用反馈：有效/失效/受限/未决、本次条件差异、证据及测量轮次 |

`id`、`created_at` 和 `schema_version` 由脚本填写。目录直接位于实验仓库根目录，命名为 `YYYYMMDDHHMM_模型名`；重名加 `_02`、`_03`。模型名称优先取 model.name，再取 model.path 的最后一段，未知用 unknown-model。不要填写虚构的实验作为初始化数据。无开始时间时目录使用 `undated_<归档日期时间>_<模型名>`，索引日期显示“未知”，未来补齐时间无需重命名目录或更改 id。

没有用户日志时仅初始化空仓库。记录可不完整，但需要可追溯。粘贴的日志标注用户提供，行号只针对确实保留的文本，不编造原文件行号。模型 revision、镜像 digest、commit、dirty 状态缺失会限制复现能力，应诚实列出。

以上修订/经验字段为可选兼容扩展，旧 schema v1 无需迁移，具体格式与 search/update/verify/lesson-digest 用法见 [过程与经验约定](experience-and-history.md)。目录仍为 YYYYMMDDHHMM_模型名，材料仍保存于本实验 evidence/，不引入更深层的任务/知识目录。结构/哈希校验不代表事实或结论已验证。

涉及压测、精度评测或测试时，必须遵循 [验证明细约定](validation-details.md)，保存相应完整配置、执行细节、详细结果和证据。三类对象均使用 performed、details_status 和 artifact_refs。新模板包含 accuracy/tests，历史 schema v1 未含这些字段仍可读取，不自动补造历史结果。脚本检查字段类型、完整度状态的一致性与 complete 的基本材料引用；材料真实性和内容完整度须由 Codex 核对。

脚本 artifacts 增加 source（原路径/消息）、execution_match（confirmed/unverified/mismatch，需运行证据才能标 confirmed）。sha256 针对保存的归档副本，不冒称原始文件哈希；如另有可信原文件哈希可单独记 source_sha256。注明是否改写、片段和缺少依赖等限制；同名不同内容分别保存，不覆盖历史快照。新增 script_refs 为兼容性扩展，旧记录未包含时仍可读取。
