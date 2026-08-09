from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_graph_evidence import valid_snapshot


ROOT = Path(__file__).parents[1]


class CliErrorHandlingTests(unittest.TestCase):
    def run_script(self, script: str, path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_graph_checker_reports_fail_for_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_bytes(b"\xff")
            result = self.run_script("check_graph_evidence.py", path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_graph_checker_rejects_non_standard_json_constants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nan.json"
            path.write_text('{"confidence": NaN}', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "check_graph_evidence.py"), str(path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot read JSON", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_prd_checker_reports_fail_for_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.md"
            result = self.run_script("check_prd_ac.py", path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_prd_checker_reports_fail_for_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.md"
            path.write_bytes(b"\xff")
            result = self.run_script("check_prd_ac.py", path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FAIL", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_graph_checker_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version":"1.1","schema_version":"1.1"}', encoding="utf-8")
            result = self.run_script("check_graph_evidence.py", path)
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate JSON key", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_graph_checker_handles_deep_strategy_parameters_without_traceback(self) -> None:
        document = valid_snapshot()
        document["contracts"][0].update(
            strategy_name="exponential",
            strategy_status="ready",
            strategy_parameters="__DEEP_PARAMETERS__",
            strategy_trigger="item is reviewed",
            strategy_target="items.next_review",
            strategy_entrypoint="src/writer.py:write_item",
        )
        payload = json.dumps(document)
        nested = '{"nested":' * 850 + "1.0" + "}" * 850
        payload = payload.replace('"__DEEP_PARAMETERS__"', nested)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deep.json"
            path.write_text(payload, encoding="utf-8")
            result = self.run_script("check_graph_evidence.py", path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
