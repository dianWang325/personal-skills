# 压测、精度评测和测试的强制记录明细

实验涉及哪类验证，就完整保存哪类已有材料；未知字段用 null，同时列入 missing_information。没有证据不能推定“未执行”。同一实验可以同时包含以下三类，不要只保留其中一种。

## 共用字段

benchmark / accuracy / tests 对象各自包含：

- `performed`：true（有执行证据）、false（明确未执行）、null（未知）。
- `details_status`：complete（命令、配置、详细结果和证据都已归档）、partial（已执行但材料不全）、unknown（未知是否执行）、not_applicable（明确未执行）。complete 不表示验证通过。
- `tool`：工具名称、版本或 commit；补丁/dirty 状态如已知也保存。
- `commands`：完整命令，包括参数、启动环境变量和配置文件位置；配置文件内容或脱敏副本必须保留，不只保存路径。
- `script_refs`：已提供的压测/精度评测/测试脚本必须脱敏保存到实验 evidence/，通过 artifacts 登记来源、归档副本 SHA256 与是否匹配实际执行版本；在本字段及需要时各 runs[].script_refs 关联。服务拉起脚本使用 deployment.script_refs。仅有脚本不能证明执行结果，按日志核对；同名不同内容分别留存，配置与依赖缺失明确列出。
- `runs`：逐轮记录 run_id、起止时间/时区（已知时）、运行状态、退出码、指标/结果、失败/错误和 artifact_refs。多轮结果分别保留，汇总需说明方法，不能覆盖失败轮次或仅选最好一轮。
- 特性配置可能回退时，按 [特性记录约定](runtime-features.md) 将实际生效状态/回退事件与 run_id 关联；混合路径测得的整轮指标不能归为特性全程生效的结果。日志覆盖不足时明确标为未确认。
- `artifact_refs`：指向 artifacts 中的本地相对路径，或明确标注的外部引用。artifacts 保存 SHA256、是否脱敏及说明。

## AISBench 与辅助工具版本

凡使用 AISBench（如日志中的 ais_bench），在 `environment.versions.aisbench` 保存版本信息；凡使用 `aisbench_auto_tools_prefix`，在 `environment.versions.aisbench_auto_tools_prefix` 单独保存对应工具版本。两者分别追溯，不因工具名称相近或共用环境而合并。

有证据的版本可保存为对象：`version`、`commit`、`dirty`、`source`、`path`、`sha256`、`runtime`，未知子字段为 null。source 为版本证据来源；runtime 标明实际评测进程所在的机器/容器/解释器。不要把推理服务容器的包版本当作客户端评测工具版本。对于没有包版本或 Git 元数据的脚本，保存实际入口脚本或工具包清单及内容 SHA256，以标识使用的内容；不能只记录目录名或命令前缀。

多轮工具版本不同时在各 `runs[].tool_versions` 内保存同名键及其版本对象，顶层注明适用范围。版本无法确认时在 missing_information 中逐项注明；影响验证复现的工具版本缺失时 details_status 为 partial。明确未使用的工具在记录中注明不适用，不要求安装、自动远端采集或重跑。

## 压测 benchmark

保存 workload：数据集名称/版本、筛选/抽样规则、请求数、实际成功/失败请求数、输入/输出 token 长度或分布、并发、请求率/QPS（含无限请求率）、seed、流式配置、超时/重试；保存 warmup、轮数和持续时间。

每轮完整保留工具提供的指标表，包括请求吞吐、输出/总 token 吞吐、TTFT、TPOT、ITL、端到端时延及各分位数、错误计数。每项明确 name、value、unit、statistic、scope，保留原口径，不把 ms 转成秒后丢失说明，不把总 token 吞吐当输出吞吐。工具未输出的指标标为缺失，不补造。

至少保留压测汇总报告或完整汇总日志；工具已提供逐请求 JSON/JSONL/CSV 时登记并保存可行的副本，大文件可外部引用。模型部署配置与压测客户端配置都要记录。

## 精度评测 accuracy

保存 datasets（名称、版本、split、子任务、样本量、过滤/抽样规则）、模型/tokenizer revision、prompt/chat template、few-shot、生成参数（temperature、top_p、max_tokens、seed 等）、评分器与评分规则、归一化/后处理、判分阈值或 baseline（如有）。配置文件与实际命令一起归档。

逐数据集/子任务/轮次保留指标名、原始值、单位/量纲（0–1 比例还是 0–100 百分数）、样本数、正确/错误/无效/缺失数量（工具提供时），以及总分和加权/汇总方式。对比实验保存 baseline 标识、差值计算方式与容差。只知道总分时明确缺少分项结果。

保存评测工具原始分项报告；可获得的预测、参考答案、失败样本/错误案例按敏感性脱敏后归档或外部引用，并保留可追溯样本 ID。未提供逐样本结果时注明缺失，不声称能追溯到每道题。

## 功能/单元/集成/正确性测试 tests

保存框架与版本、测试类型、测试选择表达式/用例列表、参数矩阵（shape/dtype/layout/模式等，如适用）、fixture/输入数据、设备/运行模式、预期结果或参考实现、比较容差/通过标准。

逐轮保存总计、passed/failed/skipped/error/xfail/xpass 等工具实际状态计数，退出码和持续时间；保留用例 ID、逐用例状态及失败断言、预期/实际值、异常栈、跳过原因。大套件逐用例详情可保存在 JUnit XML/JSON/文本报告内，并从记录引用，无需全部展开到摘要中。只有汇总无逐用例报告时注明结果粒度限制。

保存原始测试报告与失败日志。部分通过、中断、未收集到测试、预期失败不能改写成“全部通过”。没有执行的计划项与实际执行项分开记录。

## 归档检查

结束前检查：能否从目录中找到实际命令及配置、完整指标/分项/用例结果、失败信息和证据？缺哪项就明确列出，并使用 partial；脚本只校验结构，完整度由 Codex 核对实际材料。复盘应考虑记录完整度，证据不足时不作通过或提升结论。
