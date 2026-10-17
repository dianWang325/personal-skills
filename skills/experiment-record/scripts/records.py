"""Local experiment archive helper; Python standard library only."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from urllib.parse import quote


def template():
    return {
        "schema_version": 1, "title": "", "purpose": None,
        "execution": {"started_at": None, "ended_at": None, "timezone": None, "time_basis": None},
        "status": "unknown",
        "model": {"name": None, "path": None, "revision": None, "dtype": None, "quantization": None},
        "environment": {"machines": [], "container": {"image": None, "digest": None},
                        "versions": {k: None for k in ["vllm", "vllm_ascend", "triton", "cann", "torch", "torch_npu", "python", "aisbench", "aisbench_auto_tools_prefix"]}},
        "deployment": {"topology": None, "commands": [], "environment_variables": {}, "core_config": {}},
        "benchmark": {"performed": None, "details_status": "unknown", "tool": None, "commands": [],
                      "workload": {}, "warmup": None, "runs": [], "artifact_refs": []},
        "accuracy": {"performed": None, "details_status": "unknown", "tool": None, "commands": [],
                     "datasets": [], "evaluation_config": {}, "runs": [], "artifact_refs": []},
        "tests": {"performed": None, "details_status": "unknown", "tool": None, "commands": [],
                  "test_type": None, "selection": [], "case_matrix": [], "criteria": {},
                  "runs": [], "artifact_refs": []},
        "outcome": {"summary": None, "conclusions": [], "limitations": []},
        "pitfalls": [], "evidence": [], "artifacts": [], "missing_information": [],
        "related_records": [], "tags": []}


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def validate(data):
    if data.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if not isinstance(data.get("title"), str) or not data["title"].strip():
        raise ValueError("title must be non-empty")
    if data.get("status") not in {"unknown", "success", "failed", "interrupted", "partial"}:
        raise ValueError("invalid status")
    for key in ("execution", "model", "environment", "deployment", "benchmark", "outcome"):
        if not isinstance(data.get(key), dict):
            raise ValueError(f"{key} must be an object")
    for key in ("evidence", "artifacts", "missing_information", "pitfalls", "related_records", "tags"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"{key} must be an array")
    for key in ("benchmark", "accuracy", "tests"):
        if key not in data:  # Older schema-v1 records remain readable.
            continue
        section = data[key]
        if not isinstance(section, dict):
            raise ValueError(f"{key} must be an object")
        if section.get("performed") is not None and type(section["performed"]) is not bool:
            raise ValueError(f"{key}.performed must be true, false or null")
        state = section.get("details_status")
        if state is not None and state not in {"complete", "partial", "unknown", "not_applicable"}:
            raise ValueError(f"invalid {key}.details_status")
        for field in ("commands", "runs", "artifact_refs"):
            if field in section and not isinstance(section[field], list):
                raise ValueError(f"{key}.{field} must be an array")
        if state in {"complete", "partial"} and section.get("performed") is not True:
            raise ValueError(f"{key}: complete/partial requires performed=true")
        if state == "not_applicable" and section.get("performed") is not False:
            raise ValueError(f"{key}: not_applicable requires performed=false")
        if state == "complete" and any(not section.get(field) for field in ("commands", "runs", "artifact_refs")):
            raise ValueError(f"{key}: complete requires commands, runs and artifact_refs")
    for key in ("started_at", "ended_at"):
        value = data["execution"].get(key)
        if value is not None:
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", value):
                raise ValueError(f"{key} must be YYYY-MM-DD HH:MM or null")
            datetime.strptime(value, "%Y-%m-%d %H:%M")
    start, end = (data["execution"].get(k) for k in ("started_at", "ended_at"))
    if start and end and end < start:
        raise ValueError("ended_at precedes started_at")


def render_value(value):
    if value is None:
        return "未知 / 未提供\n"
    raw = json.dumps(value, ensure_ascii=False, indent=2)
    # A fence longer than any backtick run in pasted log content.
    fence = "`" * max(3, max((len(x) + 1 for x in re.findall(r"`+", raw)), default=3))
    return f"{fence}json\n{raw}\n{fence}\n"


def describe(value, depth=0):
    """Readable nested facts, preserving arbitrary run-specific keys."""
    labels = {"started_at": "开始时间", "ended_at": "结束时间", "timezone": "时区",
              "time_basis": "时间依据", "name": "名称", "path": "路径", "revision": "Revision",
              "dtype": "数据类型", "quantization": "量化", "machines": "机器",
              "container": "容器镜像", "versions": "软件版本", "image": "镜像",
              "topology": "部署拓扑", "commands": "执行命令", "environment_variables": "环境变量",
              "core_config": "核心配置", "tool": "工具", "workload": "工作负载",
              "warmup": "预热", "runs": "各轮结果", "summary": "结果摘要",
              "conclusions": "结论", "limitations": "限制", "source": "来源", "field": "字段"}
    indent = "  " * depth
    if isinstance(value, dict):
        if not value:
            return indent + "- 未提供\n"
        parts = []
        for key, item in value.items():
            label = labels.get(key, key)
            if isinstance(item, (dict, list)) and item:
                parts.append(f"{indent}- **{label}**\n" + describe(item, depth + 1))
            else:
                text = "未知 / 未提供" if item is None or item == [] or item == {} else str(item)
                parts.append(f"{indent}- **{label}**：{text.replace(chr(10), chr(10) + indent + '  ')}\n")
        return "".join(parts)
    if isinstance(value, list):
        if not value:
            return indent + "- 未提供\n"
        parts = []
        for index, item in enumerate(value, 1):
            if isinstance(item, (dict, list)):
                parts.append(f"{indent}- 第 {index} 项\n" + describe(item, depth + 1))
            else:
                parts.append(f"{indent}- {str(item).replace(chr(10), chr(10) + indent + '  ')}\n")
        return "".join(parts)
    if isinstance(value, str) and "\n" in value:
        return render_value(value)
    return ("未知 / 未提供" if value is None else str(value)) + "\n"


def render(data):
    title = data["title"].replace("\n", " ").replace("\r", " ")
    parts = [f"# {title}\n", f"实验 ID：{data['id']}\n\n状态：{data['status']}\n"]
    sections = [("execution", "执行时间"), ("purpose", "实验目的"), ("model", "模型"),
                ("environment", "机器与软件环境"), ("deployment", "部署与核心配置"),
                ("benchmark", "压测细节与结果"), ("accuracy", "精度评测细节与结果"),
                ("tests", "测试细节与结果"), ("outcome", "结果与结论"), ("pitfalls", "遇到的问题"),
                ("evidence", "事实依据"), ("artifacts", "日志与附件"),
                ("missing_information", "缺失信息与冲突"), ("related_records", "关联实验"), ("tags", "标签")]
    for key, label in sections:
        if key in {"accuracy", "tests"} and key not in data:
            continue
        parts.extend([f"\n## {label}\n", describe(data.get(key))])
    return "\n".join(parts)


def load_records(root):
    records = []
    # Read the former layout too, without silently moving existing archives.
    paths = set(root.glob("*/record.json")) | set((root / "experiments").glob("*/*/*/record.json"))
    for path in sorted(paths):
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        validate(data)
        if data.get("id") != path.parent.name:
            raise ValueError(f"id does not match directory: {path}")
        records.append((path, data))
    return records


def model_directory_name(data, override=None):
    value = override or data["model"].get("name") or data["model"].get("path") or "unknown-model"
    # Model IDs and paths commonly include a namespace: use their final component.
    value = str(value).strip().replace("\\", "/").rstrip("/").split("/")[-1]
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "-", value)
    value = re.sub(r"\s+", "-", value).strip(" .-")[:80].rstrip(" .")
    return value or "unknown-model"


def cell(value):
    return str(value if value is not None else "未知").replace("|", "\\|").replace("\n", " ").replace("\r", " ").replace("[", "\\[").replace("]", "\\]").replace("<", "&lt;")


def rebuild(root):
    records = load_records(root)  # Validate all before changing generated files.
    lines = ["# 实验索引\n", "由 experiment-record 自动生成。执行时间未知的实验单列为未知，不使用归档时间替代。\n",
             "| 执行时间 | 时区 | 实验 | 模型 | 状态 | 结果 |", "|---|---|---|---|---|---|"]
    for path, data in sorted(records, key=lambda item: (item[1]["execution"].get("started_at") or "", item[1]["id"]), reverse=True):
        write(path.parent / "README.md", render(data))
        relative = quote((path.parent / "README.md").relative_to(root).as_posix(), safe="/")
        values = [cell(data["execution"].get("started_at")), cell(data["execution"].get("timezone")),
                  f"[{cell(data['title'])}]({relative})", cell(data["model"].get("name")),
                  cell(data["status"]), cell(data["outcome"].get("summary"))]
        lines.append("| " + " | ".join(values) + " |")
    write(root / "INDEX.md", "\n".join(lines) + "\n")
    return len(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("D:/experiment"))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("template")
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("add")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--model-name", "--slug", dest="model_name", help="Optional short model name for the folder")
    sub.add_parser("rebuild")
    p = sub.add_parser("list")
    p.add_argument("--from", dest="start")
    p.add_argument("--to", dest="end")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "template":
        if args.output.exists():
            raise ValueError("template output already exists")
        write(args.output, json.dumps(template(), ensure_ascii=False, indent=2) + "\n")
    elif args.command == "add":
        data = json.loads(args.input.read_text(encoding="utf-8-sig"))
        validate(data)
        load_records(root)
        now = datetime.now().astimezone()
        started = data["execution"].get("started_at")
        date = datetime.strptime(started, "%Y-%m-%d %H:%M") if started else now
        prefix = date.strftime("%Y%m%d%H%M") if started else "undated_" + date.strftime("%Y%m%d%H%M")
        base = f"{prefix}_{model_directory_name(data, args.model_name)}"
        root.mkdir(parents=True, exist_ok=True)
        number = 1
        while True:
            record_id = base if number == 1 else f"{base}_{number:02d}"
            folder = root / record_id
            try:
                folder.mkdir(exist_ok=False)
                break
            except FileExistsError:
                number += 1
        data.update(id=record_id, created_at=now.isoformat(timespec="minutes"))
        write(folder / "record.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        (folder / "evidence").mkdir()
        rebuild(root)
        print(folder)
    elif args.command == "rebuild":
        print(f"Indexed {rebuild(root)} experiments")
    else:
        for value in (args.start, args.end):
            if value:
                datetime.strptime(value, "%Y-%m-%d")
        if args.start and args.end and args.start > args.end:
            raise ValueError("--from must precede --to")
        selected, unknown = [], []
        for path, data in load_records(root):
            date = data["execution"].get("started_at")
            item = {"id": data["id"], "title": data["title"], "started_at": date, "path": str(path)}
            if not date:
                unknown.append(item)
            elif (not args.start or date[:10] >= args.start) and (not args.end or date[:10] <= args.end):
                selected.append(item)
        print(json.dumps({"records": selected, "unknown_execution_time": unknown}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
