from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "eval-braintrust"
sys.path.insert(0, str(SKILL_DIR))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


run_batch = load_module("run_batch", SKILL_DIR / "run_batch.py")
aggregate_runs = load_module("aggregate_runs", SKILL_DIR / "aggregate_runs.py")


class EvalBraintrustBatchTests(unittest.TestCase):
    def test_build_batch_id_is_stable_for_fixed_time(self):
        now = datetime(2026, 5, 19, 18, 30, tzinfo=timezone.utc)
        self.assertEqual(
            run_batch.build_batch_id("pre", "guardrails", now),
            "batch-pre-guardrails-20260519T183000Z",
        )

    def test_parse_experiment_name_prefers_results_url(self):
        log = """
        noise
        See results for https://www.braintrust.dev/app/SoFi/p/CI%20Regression%20Tests/experiments/test-cases-super-pre-batch-run-01?foo=bar
        test-cases-super-older-name
        """
        self.assertEqual(
            run_batch.parse_experiment_name_from_log(log),
            "test-cases-super-pre-batch-run-01",
        )

    def test_normalize_tag_treats_all_as_unfiltered(self):
        self.assertIsNone(run_batch.normalize_tag("all"))
        self.assertIsNone(run_batch.normalize_tag("   "))
        self.assertEqual(run_batch.normalize_tag("guardrails"), "guardrails")

    def test_build_eval_env_sets_mock_url_and_pythonpath(self):
        env = run_batch.build_eval_env(
            base_env={"PYTHONPATH": "/tmp/original"},
            experiment_name="test-cases-super-current-demo-run-01",
            tag="guardrails",
            project_root=Path("/Users/foothill/code/openai-member-agent"),
        )
        self.assertEqual(env["BRAINTRUST_EXPERIMENT_NAME"], "test-cases-super-current-demo-run-01")
        self.assertEqual(env["BRAINTRUST_TAG_FILTER"], "guardrails")
        self.assertEqual(env["MOCK_SERVICE_URL"], "http://127.0.0.1:3001")
        self.assertEqual(
            env["PYTHONPATH"],
            "/Users/foothill/code/openai-member-agent/evaluation:/tmp/original",
        )

    def test_resolve_python_bin_prefers_explicit_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            python_bin = Path(tmp) / "python3"
            python_bin.write_text("#!/bin/sh\n", encoding="utf-8")
            self.assertEqual(run_batch.resolve_python_bin(str(python_bin)), python_bin.resolve())

    def test_aggregate_manifest_computes_mean_and_pooled_accuracy(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            baseline1 = tmp_path / "baseline1.json"
            baseline2 = tmp_path / "baseline2.json"
            baseline1.write_text(
                json.dumps(
                    {
                        "records": [
                            {"group_id": "regulated-advice", "scenario_type": "block", "group_pass": True},
                            {"group_id": "regulated-advice", "scenario_type": "block", "group_pass": False},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            baseline2.write_text(
                json.dumps(
                    {
                        "records": [
                            {"group_id": "regulated-advice", "scenario_type": "block", "group_pass": True},
                            {"group_id": "regulated-advice", "scenario_type": "block", "group_pass": True},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            manifest = {
                "batch_id": "batch-pre",
                "phase": "pre",
                "provider": "super",
                "tag": "guardrails",
                "runs_requested": 2,
                "runs": [
                    {"status": "success", "baseline_path": str(baseline1), "index": 1},
                    {"status": "success", "baseline_path": str(baseline2), "index": 2},
                ],
            }

            aggregate = aggregate_runs.aggregate_manifest(manifest)
            block = aggregate["summary"]["regulated-advice"]["scenarios"]["block"]
            self.assertEqual(aggregate["runs_included"], 2)
            self.assertEqual(block["pooled_passed"], 3)
            self.assertEqual(block["pooled_total"], 4)
            self.assertEqual(block["pooled_accuracy"], 0.75)
            self.assertEqual(block["mean_accuracy"], 0.75)


if __name__ == "__main__":
    unittest.main()
