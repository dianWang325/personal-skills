"""Behavior checks using temporary archives only. Run: python -m unittest discover -s scripts."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import archive_tools as tools
import records


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="experiment-record-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = records.template()
        self.data.update(id="202610212030_Model", title="CPP 回退实验", created_at="2026-10-21T20:30+08:00")
        self.data["execution"]["started_at"] = "2026-10-21 20:30"
        self.data["model"]["name"] = "Model"
        self.folder = self.root / self.data["id"]
        self.folder.mkdir()
        self.path = self.folder / "record.json"
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")

    def cli(self, *args, code=0):
        result = subprocess.run([sys.executable, str(Path(records.__file__)), "--root", str(self.root), *args],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, code, result.stderr or result.stdout)
        return result.stdout

    def test_update_keeps_previous_conclusions_and_rejects_history_rewrite(self):
        self.data["outcome"]["summary"] = "old conclusion"
        self.save()
        edited = deepcopy(self.data)
        edited["outcome"]["summary"] = "new conclusion"
        candidate = self.root / "candidate.json"
        candidate.write_text(json.dumps(edited), encoding="utf-8")
        self.cli("update", "--record", self.data["id"], "--input", str(candidate), "--reason", "new evidence")
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["outcome"]["summary"], "new conclusion")
        self.assertIn("old conclusion", json.dumps(saved["revision_history"]))
        self.assertFalse(tools.history_problems(saved))
        self.assertIn("old conclusion", (self.folder / "README.md").read_text(encoding="utf-8"))
        saved["outcome"]["summary"] = "tampered"
        self.assertTrue(tools.history_problems(saved))
        altered = deepcopy(saved)
        altered["revision_history"] = []
        with self.assertRaises(ValueError):
            tools.revised_record(saved, altered, "erase history")

    def test_append_only_attempts_and_lesson_conditions(self):
        self.data["attempts"] = [{"id":"a1", "action":"try sync", "result":"no improvement",
                                  "assessment":"inconclusive", "evidence_refs":[]}]
        new = deepcopy(self.data)
        new["attempts"] = []
        with self.assertRaises(ValueError):
            tools.revised_record(self.data, new, "remove failure")
        new["attempts"] = deepcopy(self.data["attempts"]) + [{"id":"a2", "action":"isolate case",
            "result":"previous success was contaminated", "assessment":"refuted", "supersedes":"a1", "evidence_refs":[]}]
        revised = tools.revised_record(self.data, new, "new control result")
        records.validate(revised)
        self.assertFalse(tools.history_problems(revised))
        revised["lessons"] = [{"id":"l1", "claim":"scoped finding", "status":"validated", "evidence_refs":[]}]
        with self.assertRaises(ValueError):
            records.validate(revised)

    def test_search_problem_filters_dates_and_history(self):
        self.data["tags"] = ["regression"]
        self.data["retrieval"]["error_keywords"] = ["unsupported-shape"]
        self.data["runtime_features"] = [{"name":"CPP", "observed_status":"unknown", "events":[],
                                          "evidence_refs":[], "run_refs":[]}]
        self.save()
        found = json.loads(self.cli("search", "--query", "cpp unsupported-shape", "--model", "model", "--tag", "regression"))
        self.assertEqual(len(found["records"]), 1)
        self.assertTrue(any("error_keywords" in x["field"] for x in found["records"][0]["matches"]))
        self.assertFalse(json.loads(self.cli("search", "--query", "cpp absent"))["records"])
        old = deepcopy(self.data)
        self.data["retrieval"]["error_keywords"] = ["replacement"]
        self.data = tools.revised_record(old, self.data, "correct keyword")
        self.save()
        self.assertFalse(json.loads(self.cli("search", "--query", "unsupported-shape"))["records"])
        self.assertTrue(json.loads(self.cli("search", "--query", "unsupported-shape", "--include-history"))["records"])
        self.assertFalse(json.loads(self.cli("search", "--from", "2026-10-22"))["records"])

    def test_verify_attachment_reference_hash_and_path_escape(self):
        evidence = self.folder / "evidence"
        evidence.mkdir()
        script = evidence / "start.sh"
        script.write_bytes(b"echo fixture\n")
        self.data["artifacts"] = [{"kind":"service_script", "path":"evidence/start.sh", "sha256":tools.file_hash(script)}]
        self.data["deployment"]["script_refs"] = ["evidence/start.sh"]
        self.save()
        before = self.path.read_bytes()
        self.assertEqual(json.loads(self.cli("verify"))["verification_status"], "passed")
        self.assertEqual(before, self.path.read_bytes())
        script.write_bytes(b"changed\n")
        result = json.loads(self.cli("verify", code=1))
        self.assertTrue(any(x["code"] == "hash_mismatch" for x in result["errors"]))
        self.data["artifacts"][0]["path"] = "../outside.sh"
        self.save()
        result = json.loads(self.cli("verify", code=1))
        self.assertTrue(any(x["code"] == "invalid_artifact_path" for x in result["errors"]))
        self.data["artifacts"] = []
        self.save()
        result = json.loads(self.cli("verify", code=1))
        self.assertTrue(any(x["code"] == "unregistered_reference" for x in result["errors"]))

    def test_external_files_are_unverified_not_passed(self):
        self.data["artifacts"] = [{"external_path":"/remote/large.jsonl"}]
        self.save()
        result = json.loads(self.cli("verify", code=2))
        self.assertEqual(result["verification_status"], "incomplete")
        self.assertFalse(result["errors"])

    def test_report_directory_reference_accepts_registered_hashed_files(self):
        output = self.folder/"evidence/results/round1"
        output.mkdir(parents=True)
        result = output/"metrics.json"
        result.write_bytes(b'{"requests":1}')
        self.data["artifacts"] = [{"path":"evidence/results/round1/metrics.json", "sha256":tools.file_hash(result)}]
        self.data["tests"]["artifact_refs"] = ["evidence/results/round1"]
        self.save()
        self.assertEqual(json.loads(self.cli("verify"))["verification_status"], "passed")
        (output/"unregistered.txt").write_text("new file", encoding="utf-8")
        report = json.loads(self.cli("verify", code=2))
        self.assertTrue(any(x["code"] == "directory_file_unregistered" for x in report["warnings"]))

    def test_benchmark_full_log_binding_and_readable_links(self):
        evidence = self.folder / "evidence"
        evidence.mkdir()
        payloads = {"service.json":b'{"tp":8}', "bench.json":b'{"concurrency":4}',
                    "bench.log":b"first line\r\n" + b"measurement\r\n" * 10000 + b"final report\r\n"}
        for name, payload in payloads.items():
            file = evidence/name
            file.write_bytes(payload)
            self.data["artifacts"].append({"path":"evidence/"+name, "sha256":tools.file_hash(file),
                                           "content_scope":"full"})
        self.data["benchmark"]["performed"] = True
        self.data["benchmark"]["runs"] = [{"run_id":"r1", "service_instance":{"id":"service-1"},
            "service_config_refs":["evidence/service.json"], "benchmark_config_refs":["evidence/bench.json"],
            "log_refs":["evidence/bench.log"], "log_completeness":"complete"}]
        self.save()
        self.cli("rebuild")
        result = json.loads(self.cli("verify"))
        self.assertEqual(result["verification_status"], "passed")
        self.assertEqual(result["files_hashed"], 3)
        text = (self.folder/"README.md").read_text(encoding="utf-8")
        self.assertIn("服务配置 → 压测配置 → 压测日志", text)
        self.assertIn("[evidence/bench.log](evidence/bench.log)", text)
        self.assertEqual((evidence/"bench.log").read_bytes(), payloads["bench.log"])
        self.data["artifacts"][-1]["content_scope"] = "excerpt"
        self.save()
        result = json.loads(self.cli("verify", code=1))
        self.assertTrue(any(x["code"] == "benchmark_log_claim_unsubstantiated" for x in result["errors"]))

    def test_missing_benchmark_mapping_is_explicitly_incomplete(self):
        self.data["benchmark"].update(performed=True, runs=[{"run_id":"r1"}])
        self.save()
        result = json.loads(self.cli("verify", code=2))
        self.assertEqual(result["verification_status"], "incomplete")
        self.assertTrue(any(x["code"] == "benchmark_mapping_missing" for x in result["warnings"]))

    def test_feedback_is_bound_to_exact_lesson_content(self):
        lesson = {"id":"l1", "claim":"scoped finding", "status":"observed", "conditions":{"model":"Model"}, "evidence_refs":[]}
        self.data["lessons"] = [lesson]
        self.data["reuse_feedback"] = [{"id":"f1", "lesson_ref":{"record_id":self.data["id"], "lesson_id":"l1",
            "lesson_sha256":tools.digest(lesson)}, "outcome":"inconclusive", "evidence_refs":[]}]
        self.save()
        self.assertEqual(json.loads(self.cli("verify"))["verification_status"], "passed")
        ref = json.loads(self.cli("lesson-digest", "--record", self.data["id"], "--lesson", "l1"))
        self.assertEqual(ref["lesson_sha256"], tools.digest(lesson))
        self.data["lessons"][0]["claim"] = "rewritten claim"
        self.save()
        result = json.loads(self.cli("verify", code=1))
        self.assertTrue(any(x["code"] == "lesson_revision_mismatch" for x in result["errors"]))

    def test_legacy_and_flat_naming_collision(self):
        for key in ("revision_history", "attempts", "lessons", "reuse_feedback", "retrieval"):
            self.data.pop(key)
        records.validate(self.data)
        self.save()
        self.assertEqual(json.loads(self.cli("verify"))["verification_status"], "passed")
        source = self.root / "source.json"
        data = records.template()
        data["title"] = "flat record"
        data["execution"]["started_at"] = "2026-10-21 20:30"
        data["model"]["name"] = "org/Model"
        source.write_text(json.dumps(data), encoding="utf-8")
        created = Path(self.cli("add", "--input", str(source)).strip())
        self.assertEqual(created.parent, self.root)
        self.assertEqual(created.name, "202610212030_Model_02")

    def test_invalid_record_does_not_hide_other_verification_results(self):
        bad = self.root / "broken"
        bad.mkdir()
        (bad / "record.json").write_text("{", encoding="utf-8")
        result = json.loads(self.cli("verify", code=1))
        self.assertEqual(result["records_checked"], 1)
        self.assertTrue(any(x["code"] == "invalid_record" for x in result["errors"]))


if __name__ == "__main__":
    unittest.main()
