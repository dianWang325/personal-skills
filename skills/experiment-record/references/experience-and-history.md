# 修订历史、排查过程和经验复用

扩展现有 schema_version 1；不增加实验目录层级，不迁移旧数据，不要求外部索引服务。旧记录缺少这些字段表示未记录，不据此补造经历。

## 1. 结论修订 revision_history

修改已有记录前先读当前 JSON 和证据，把当前完整 JSON 复制到临时文件并修改，再运行：

```powershell
python <skill>/scripts/records.py --root D:\experiment update --record <实验ID> --input <修改后的完整JSON> --reason '新证据及修正原因'
```

update 保留 id、created_at，自动追加 revision_history、更新 updated_at，并重建摘要和索引。每次事件包含 id、recorded_at（含时区的归档时间）、reason、before_sha256、after_sha256 和 changes。changes 按顶层字段保存 before/after 及字段此前/此后是否存在，可以回看被修正的结论及当时依据。未改动的字段不复制。归档修订时间不是实验执行时间。

不要手改或删除历史事件；临时 JSON 中保留原 revision_history。update 会拒绝改写历史和删除/改写已有 attempts、lessons、reuse_feedback；需要修正它们时追加新条目，并以 supersedes 引用同一数组中此前的条目 ID。旧条目不删除，复盘采用替代关系解释当前结论。id 在各自数组内唯一，建议 attempt-001、lesson-001、feedback-001。新增记录初始历史为空。

摘要是当前事实的阅读视图，包含修订历史；旧判断被保留不表示仍成立。rebuild 只生成视图，不替代 update，不自动制造历史。对使用 update 前已发生的手动修改无法恢复；哈希用于一致性检查，不是防篡改签名或结论真实性证明。

## 2. 排查尝试 attempts

有排查时按实际顺序追加，包含失败、无效和被否定的路线，不只保留最后修复方案。每项：

| 字段 | 内容 |
|---|---|
| id / recorded_at / execution_time | 稳定条目 ID、记录时间、已知的实际尝试时间（未知为 null，时区独立说明） |
| hypothesis | 本次检验的假设；未知为 null |
| action | 实际尝试措施、命令/脚本及配置变化 |
| result | 观测结果，包括无效、中断、污染或未完成的对照 |
| assessment | supported / refuted / inconclusive / out_of_scope，描述对假设的支持程度，不表示实验运行状态 |
| scope / excluded / unresolved | 证据适用范围、已排除项及仍未解决问题；无法排除时不能写入 excluded |
| evidence_refs / run_refs | 依据和关联测量轮次；evidence_refs 为数组，未知时为空并补充缺失信息 |
| supersedes | 可选，纠正此前条目时引用此前条目 ID |

“修改后未复现”不自动证明因果或排除其他原因。存在跨 case 污染、版本变化或负载变化时明确记录限制。

## 3. 条件化经验 lessons

仅在实验确有可复用发现时提炼，不要求每次都有经验。与原始实验事实并存，不能以经验摘要替代材料。每项包含：

- id、claim（经验或假设）、status（hypothesis/observed/validated/refuted/superseded）。一次观测通常为 observed；validated 需明确验证证据和范围，不因归档、检索命中或用户点赞升级。
- conditions 对象：模型/revision、NPU/拓扑、镜像与相关软件版本、配置、负载、特性实际生效路径、触发条件等有关系的限制。未知值用 null，不能解释为所有环境都适用。
- counterexamples、limitations：已知反例和限制，没有反例证据只表示未记录反例。
- evidence_refs、run_refs、related_records：支持/反证材料、关联轮次和实验。validated 必须有 evidence_refs。
- supersedes：修正经验时追加新条目并指向旧 ID。旧条目仍保留，不以修改旧 claim 的方式破坏后来反馈的版本归属。

## 4. 按问题检索 retrieval

retrieval 包含 symptoms、error_keywords、features、fixes、keywords 五个字符串数组，记录真实现象、原始错误关键词、相关特性及处理办法；无证据的处理建议不得混入已验证修复。

```powershell
python <skill>/scripts/records.py --root D:\experiment search --query 'CPP 回退'
python <skill>/scripts/records.py --root D:\experiment search --query 'unsupported' --model Qwen --feature CPP
python <skill>/scripts/records.py --root D:\experiment search --tag regression --from 2026-10-01 --to 2026-10-31
```

search 直接读取 record.json，支持 --query、--model、--tag、--status、--feature、--from、--to；日期包含首尾，按执行开始时间筛选，未知时间单列。query 以空白分词、忽略大小写、所有词均需命中；不做语义扩展，不扫描原始日志，不需要向量数据库。它搜索当前 JSON 中所有字段，返回匹配字段与最多 20 条片段；默认排除 revision_history，可用 --include-history 查看被修订的旧内容。先检索关键词/模型，再按条件筛选，命中只表示材料相关，不证明结论正确；命中旧经验/排除项时须读取状态、supersedes 及关联证据。

## 5. 本地完整性校验 verify

```powershell
python <skill>/scripts/records.py --root D:\experiment verify
python <skill>/scripts/records.py --root D:\experiment verify --record <实验ID>
```

只读检查：JSON 结构与目录 ID、登记的本地附件存在性/字节 SHA256、各层 script_refs/artifact_refs 是否登记并存在、修订历史可逆性与前后哈希、复用反馈是否指向确切经验内容。拒绝绝对路径、越出本实验目录的引用，包括符号链接跳转。外部路径仅报告未验证，不自动联网获取，也不以“外部路径存在”冒充已归档。

退出码 0=passed，1=failed（缺文件、哈希不符、引用无效、历史不一致等），2=incomplete（缺哈希、外部附件未校验等）；机器可读输出包含 errors、warnings、records_checked、files_hashed。局部记录出错不吞掉其他记录的校验结果。无实验的空仓库是有效空结果。

verify 不是事实验证器，不证明实验成功、特性生效、完整采集了全部日志或结论正确，也不会自动改写哈希掩盖差异。有差异先查来源，确需替换附件时保留旧快照，用 update 追加说明及新引用。未登记的磁盘文件不在附件哈希校验范围内。

历史 artifact_refs 可以引用结果目录；此时目录中的文件须分别登记 artifacts 并有哈希，空目录或未登记文件报告为不完整。script_refs、service_config_refs、benchmark_config_refs、log_refs 应指向具体文件，不以目录替代明确绑定。

## 6. 复用反馈 reuse_feedback

在实际复用经验的实验中追加反馈，不自动为了验证经验运行实验。lesson_ref 包含原经验 record_id、lesson_id、lesson_sha256；用以下命令获得精确内容哈希：

```powershell
python <skill>/scripts/records.py --root D:\experiment lesson-digest --record <来源实验ID> --lesson <经验ID>
```

其余字段：id、recorded_at、outcome（effective/ineffective/limited/inconclusive）、conditions（本次条件）、deviations（与原经验条件差异）、reason、evidence_refs、run_refs。已知有效/失效/受限需要证据；证据不足使用 inconclusive。所在 record.json 就是本次应用实验；不要把反馈时间当作执行时间。更正反馈同样追加 supersedes。

反馈反映特定条件下对特定经验内容的复验，不是投票统计；不同条件下失效不自动推翻原经验，相同条件下反例须追加修正说明。复盘汇总被重复支持、受到限制、被否定的经验，并返回原始实验链接。verify 会检查引用与 lesson_sha256，避免经验被改写后旧反馈仍指向新说法。

## 归档与复盘流程

归档时提取实际尝试、适用条件和检索词；补充或修正已有记录使用 update。相关脚本/结果归档完成后运行 verify；发现缺失如实报告，先保存已有材料，不为得到 passed 而补造证据。复盘结合原始结果、结论修订、失败路线和复用反馈，不只汇总最后成功案例。所有内容留在原浅目录的 JSON、摘要和 evidence 中，不另建公共知识发布体系。

设计参考：[knowledge-vllm-ascend](https://github.com/pisceskkk/knowledge-vllm-ascend) 对过程保留、摘要与证据分离、修订及反馈版本归属的处理；本实现适配私人实验档案，未引入其公开发布的脱敏、审核或 Bot 工作流。
