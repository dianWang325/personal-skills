"""History, literal search and read-only integrity checks for local archives."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re


LEDGERS = ("attempts", "lessons", "reuse_feedback")


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def content_state(data):
    return {k: v for k, v in data.items() if k not in {"revision_history", "updated_at"}}


def validate_extensions(data):
    retrieval = data.get("retrieval", {})
    if not isinstance(retrieval, dict):
        raise ValueError("retrieval must be an object")
    for key in ("symptoms", "error_keywords", "features", "fixes", "keywords"):
        if key in retrieval and (not isinstance(retrieval[key], list) or
                                 any(not isinstance(x, str) for x in retrieval[key])):
            raise ValueError(f"retrieval.{key} must be an array of strings")
    for name in (*LEDGERS, "revision_history"):
        values = data.get(name, [])
        if not isinstance(values, list):
            raise ValueError(f"{name} must be an array")
        seen = set()
        for item in values:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
                raise ValueError(f"{name} entries require a non-empty id")
            if item["id"] in seen:
                raise ValueError(f"duplicate {name} id: {item['id']}")
            if name in LEDGERS and item.get("supersedes") is not None and item["supersedes"] not in seen:
                raise ValueError(f"{name}.supersedes must refer to an earlier entry in the same ledger")
            seen.add(item["id"])
            if name in LEDGERS and not isinstance(item.get("evidence_refs"), list):
                raise ValueError(f"{name} entries require evidence_refs (may be empty if unknown)")
            if name == "attempts":
                if item.get("assessment") not in {"supported", "refuted", "inconclusive", "out_of_scope"}:
                    raise ValueError("invalid attempt assessment")
                for key in ("action", "result"):
                    if not isinstance(item.get(key), str) or not item[key].strip():
                        raise ValueError(f"attempt requires {key}")
            if name == "lessons":
                if not isinstance(item.get("claim"), str) or not item["claim"].strip():
                    raise ValueError("lesson requires a claim")
                if item.get("status") not in {"hypothesis", "observed", "validated", "refuted", "superseded"}:
                    raise ValueError("invalid lesson status")
                if not isinstance(item.get("conditions"), dict):
                    raise ValueError("lesson requires conditions (unknown values may be null)")
                if item["status"] == "validated" and not item["evidence_refs"]:
                    raise ValueError("validated lesson requires evidence_refs")
            if name == "reuse_feedback":
                ref = item.get("lesson_ref")
                if not isinstance(ref, dict) or any(not isinstance(ref.get(k), str) or not ref[k]
                                                    for k in ("record_id", "lesson_id", "lesson_sha256")):
                    raise ValueError("feedback requires record_id, lesson_id and lesson_sha256")
                if not re.fullmatch(r"[0-9a-f]{64}", ref["lesson_sha256"]):
                    raise ValueError("invalid lesson_sha256")
                if item.get("outcome") not in {"effective", "ineffective", "limited", "inconclusive"}:
                    raise ValueError("invalid feedback outcome")
                if item["outcome"] != "inconclusive" and not item["evidence_refs"]:
                    raise ValueError("feedback outcome requires evidence_refs")


def revised_record(old, new, reason):
    """Preserve earlier ledger entries and record reversible top-level changes."""
    if not reason.strip():
        raise ValueError("update requires a reason")
    for key in ("id", "created_at"):
        if new.get(key) != old.get(key):
            raise ValueError(f"update cannot change {key}")
    if new.get("revision_history", []) != old.get("revision_history", []):
        raise ValueError("revision_history is managed by update; preserve existing history")
    for key in LEDGERS:
        previous, proposed = old.get(key, []), new.get(key, [])
        if not isinstance(proposed, list) or proposed[:len(previous)] != previous:
            raise ValueError(f"{key} is append-only; append a correction with supersedes instead")
    before, after = content_state(old), content_state(new)
    changes = []
    for key in sorted(before.keys() | after.keys()):
        if key in before and key in after and before[key] == after[key]:
            continue
        changes.append({"field": key, "before_present": key in before, "before": before.get(key),
                        "after_present": key in after, "after": after.get(key)})
    if not changes:
        raise ValueError("no content changes to record")
    result = deepcopy(new)
    history = deepcopy(old.get("revision_history", []))
    now = datetime.now().astimezone().isoformat(timespec="minutes")
    number = len(history) + 1
    used = {item["id"] for item in history}
    while f"revision-{number:04d}" in used:
        number += 1
    history.append({"id": f"revision-{number:04d}", "recorded_at": now, "reason": reason,
                    "before_sha256": digest(before), "after_sha256": digest(after), "changes": changes})
    result.update(revision_history=history, updated_at=now)
    return result


def history_problems(data):
    """Replay history backwards; hashes detect drift but do not certify truth."""
    problems = []
    state = deepcopy(content_state(data))
    for event in reversed(data.get("revision_history", [])):
        label = event.get("id", "unknown")
        if digest(state) != event.get("after_sha256"):
            problems.append(f"{label}: current/after content hash mismatch")
        changes = event.get("changes")
        if not isinstance(changes, list) or not changes:
            problems.append(f"{label}: missing changes")
            continue
        fields = set()
        for change in changes:
            if not isinstance(change, dict) or not isinstance(change.get("field"), str):
                problems.append(f"{label}: invalid change")
                continue
            key = change["field"]
            if key in fields or key in {"revision_history", "updated_at"}:
                problems.append(f"{label}: duplicate or reserved field {key}")
            fields.add(key)
            if (key in state) != change.get("after_present") or state.get(key) != change.get("after"):
                problems.append(f"{label}: changed field {key} does not match")
            if change.get("before_present"):
                state[key] = change.get("before")
            else:
                state.pop(key, None)
        if digest(state) != event.get("before_sha256"):
            problems.append(f"{label}: previous content hash mismatch")
    return problems


def walk(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk(item, f"{prefix}.{key}" if prefix else key)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from walk(item, f"{prefix}[{i}]")
    elif value is not None:
        yield prefix, str(value)


def search_records(records, query="", model=None, tag=None, status=None, feature=None,
                   start=None, end=None, include_history=False):
    terms = query.casefold().split()
    results, unknown_dates = [], []
    for path, data in records:
        if model and model.casefold() not in json.dumps(data.get("model", {}), ensure_ascii=False).casefold():
            continue
        if tag and tag.casefold() not in [str(x).casefold() for x in data.get("tags", [])]:
            continue
        if status and status != data.get("status"):
            continue
        if feature and not any(feature.casefold() in f.get("name", "").casefold() for f in data.get("runtime_features", [])):
            continue
        current = {k: v for k, v in data.items() if include_history or k != "revision_history"}
        leaves = list(walk(current))
        matches = [(field, text) for field, text in leaves
                   if any(term in text.casefold() for term in terms)]
        if terms and not all(any(term in text.casefold() for _, text in matches) for term in terms):
            continue
        item = {"id": data["id"], "title": data["title"], "started_at": data["execution"].get("started_at"),
                "status": data["status"], "path": str(path), "match_count": len(matches),
                "matches": [{"field": f, "snippet": t[:240]} for f, t in matches[:20]]}
        date = item["started_at"]
        if (start or end) and not date:
            unknown_dates.append(item)
        elif (not start or date[:10] >= start) and (not end or date[:10] <= end):
            results.append(item)
    results.sort(key=lambda x: (x["started_at"] or "", x["id"]), reverse=True)
    return {"records": results, "unknown_execution_time": unknown_dates,
            "search_type": "literal AND (case-insensitive); matches are not factual validation"}


def file_hash(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def local_path(folder, value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("expected a non-empty relative path with forward slashes")
    if Path(value).is_absolute() or PureWindowsPath(value).is_absolute() or PureWindowsPath(value).drive:
        raise ValueError("absolute/drive paths belong in external_path")
    path = (folder / value).resolve()
    if not path.is_relative_to(folder.resolve()):
        raise ValueError("path escapes the experiment directory")
    return path


def verify_archive(root, paths, validate, record_id=None):
    report = {"errors": [], "warnings": [], "records_checked": 0, "files_hashed": 0}
    records = {}
    selected = []
    def issue(level, path, code, message):
        report[level].append({"record": str(path), "code": code, "message": message})
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            validate(data)
            if data.get("id") != path.parent.name:
                raise ValueError("id does not match directory")
            if data["id"] in records:
                raise ValueError("duplicate record id")
            records[data["id"]] = data
            if not record_id or data["id"] == record_id:
                selected.append((path, data))
        except (ValueError, OSError, TypeError, KeyError) as error:
            if not record_id or path.parent.name == record_id:
                issue("errors", path, "invalid_record", str(error))
    if record_id and not selected:
        issue("errors", root, "record_not_found", record_id)
    for path, data in selected:
        report["records_checked"] += 1
        artifacts = {}
        external_refs = set()
        for artifact in data.get("artifacts", []):
            if not isinstance(artifact, dict):
                issue("errors", path, "invalid_artifact", "artifact must be an object")
                continue
            relative = artifact.get("path")
            if not relative:
                if artifact.get("external_path"):
                    issue("warnings", path, "external_unverified", str(artifact["external_path"]))
                    if isinstance(artifact["external_path"], str):
                        external_refs.add(artifact["external_path"])
                else:
                    issue("warnings", path, "artifact_without_path", str(artifact.get("kind")))
                continue
            if not isinstance(relative, str):
                issue("errors", path, "invalid_artifact_path", "path must be a string")
                continue
            if relative in artifacts:
                issue("errors", path, "duplicate_artifact", str(relative))
            if isinstance(relative, str):
                artifacts[relative] = artifact
            try:
                target = local_path(path.parent, relative)
                if not target.is_file():
                    issue("errors", path, "missing_file", str(relative))
                    continue
                expected = artifact.get("sha256")
                if not isinstance(expected, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", expected):
                    issue("warnings", path, "missing_or_invalid_hash", str(relative))
                    continue
                actual = file_hash(target)
                report["files_hashed"] += 1
                if actual != expected.lower():
                    issue("errors", path, "hash_mismatch", str(relative))
            except (ValueError, OSError) as error:
                issue("errors", path, "invalid_artifact_path", f"{relative}: {error}")
        # Inspect references at any nesting depth, including per-run references.
        for field, reference in walk({k: v for k, v in data.items() if k != "revision_history"}):
            if not re.search(r"(?:^|\.)(?:script_refs|artifact_refs|service_config_refs|benchmark_config_refs|log_refs)\[\d+\]$", field):
                continue
            if reference in artifacts or reference in external_refs:
                continue
            try:
                target = local_path(path.parent, reference)
                if target.is_dir() and ".artifact_refs[" in field:
                    children = [child for child in target.rglob("*") if child.is_file()]
                    if not children:
                        issue("warnings", path, "empty_reference_directory", f"{field}: {reference}")
                    for child in children:
                        relative = child.relative_to(path.parent).as_posix()
                        local_path(path.parent, relative)  # Reject symlink escapes inside directory refs.
                        if relative not in artifacts:
                            issue("warnings", path, "directory_file_unregistered", f"{field}: {relative}")
                    continue
                code = "unregistered_reference" if target.is_file() else "missing_reference"
                issue("errors", path, code, f"{field}: {reference}")
            except (ValueError, OSError) as error:
                issue("errors", path, "invalid_reference", f"{field}: {error}")
        for problem in history_problems(data):
            issue("errors", path, "revision_integrity", problem)
        benchmark = data.get("benchmark", {})
        if benchmark.get("performed") is True:
            if not benchmark.get("runs"):
                issue("warnings", path, "benchmark_runs_missing", "no per-run configuration/log mapping")
            for number, run in enumerate(benchmark.get("runs", []), 1):
                if not isinstance(run, dict):
                    issue("errors", path, "invalid_benchmark_run", str(number))
                    continue
                label = run.get("run_id", run.get("id", str(number)))
                if not run.get("run_id"):
                    issue("warnings", path, "benchmark_run_id_missing", str(label))
                if not run.get("service_instance"):
                    issue("warnings", path, "benchmark_service_instance_missing", str(label))
                for field in ("service_config_refs", "benchmark_config_refs", "log_refs"):
                    refs = run.get(field)
                    if not isinstance(refs, list) or not refs:
                        issue("warnings", path, "benchmark_mapping_missing", f"{label}: {field}")
                    elif any(not isinstance(ref, str) for ref in refs):
                        issue("errors", path, "invalid_benchmark_mapping", f"{label}: {field}")
                if run.get("log_completeness") != "complete":
                    issue("warnings", path, "benchmark_log_incomplete", f"{label}: full log not confirmed")
                else:
                    if not run.get("log_refs"):
                        issue("errors", path, "benchmark_log_claim_unsubstantiated", str(label))
                    for ref in run.get("log_refs", []):
                        artifact = artifacts.get(ref) if isinstance(ref, str) else None
                        if artifact is None or artifact.get("content_scope") != "full":
                            issue("errors", path, "benchmark_log_claim_unsubstantiated", f"{label}: {ref}")
        for linked_id in data.get("related_records", []):
            if isinstance(linked_id, str) and linked_id not in records:
                issue("warnings", path, "related_record_unavailable", linked_id)
        for feedback in data.get("reuse_feedback", []):
            ref = feedback["lesson_ref"]
            origin = records.get(ref["record_id"])
            lesson = next((x for x in origin.get("lessons", []) if x["id"] == ref["lesson_id"]), None) if origin else None
            if lesson is None:
                issue("errors", path, "lesson_reference_missing", f"{ref['record_id']}#{ref['lesson_id']}")
            elif digest(lesson) != ref["lesson_sha256"]:
                issue("errors", path, "lesson_revision_mismatch", f"{ref['record_id']}#{ref['lesson_id']}")
    report["verification_status"] = "failed" if report["errors"] else "incomplete" if report["warnings"] else "passed"
    report["scope"] = "Local structure, registered attachments, references and revision consistency only; not experiment correctness or success"
    return report
