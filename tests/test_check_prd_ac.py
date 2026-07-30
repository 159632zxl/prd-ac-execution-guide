from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "scripts" / "check_prd_ac.py"


def build_document(tier: str = "S") -> str:
    return f"""# Ledger CLI PRD

```text
Spec status: approved
Document Tier: {tier}
Implementation allowed: yes
```

## Goal

Store one validated ledger entry from the command line.

## Non-goals

No synchronization, GUI, or multi-user support.

## Boundary and truth source

Truth source: `data/ledger.jsonl`.
The CLI owns local validation and append-only writes.

## Tasks

| Task | Implements AC | Output | Validation |
|------|---------------|--------|------------|
| P0-T01 | P0-DONE | `ledger.py` | `python -m unittest` |

## P0 Current-state review

Confirm the target path and command contract.

## Acceptance Criteria

### §AC.0 Global forbidden items

| AC | Forbidden item | Severity |
|----|----------------|----------|
| G-01 | Do not overwrite the truth source | FAIL |
| G-02 | Do not claim completion without evidence | FAIL |

### §AC.P0 P0 acceptance

| AC | Category | Requirement | Verification Method | Severity |
|----|----------|-------------|---------------------|----------|
| P0-DONE | happy | Command contract is documented | Run python -m unittest and confirm exit code 0 | FAIL |
| P0-ERR-01 | error | Invalid amounts are rejected | Run the invalid-amount test and inspect the error | FAIL |
"""


def with_m_requirements(document: str) -> str:
    addition = """
## AI Readiness Gate

AI Readiness: ready
No new design decisions required: yes
Known files / directories: `ledger.py`, `tests/`
Expected outputs: working CLI and test evidence
Validation commands: `python -m unittest`
Blocking ambiguities: none

## Approval Gate

Approved by: product owner
Approval date: 2026-07-30
Implementation allowed: yes

## Interfaces and boundaries

producer -> consumer: CLI -> JSONL store
input: validated command arguments
output: one JSON line
writes: `data/ledger.jsonl`
forbidden: rewriting existing entries
validation: unit and CLI tests

## Handoff and recovery

Current stage: P0
Passed AC: none
Failed AC: none
Current blockers: none
Next command: `python -m unittest`
Recovery entry: repository root
Do not repeat: no non-repeatable steps
Related reports: `reports/P0.md`
"""
    return document.replace("## Tasks", addition + "\n## Tasks")


class CheckerTests(unittest.TestCase):
    def run_checker(self, document: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "prd.md"
            path.write_text(document, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(CHECKER), str(path)],
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
            )

    def assert_fails_with(self, document: str, message: str) -> None:
        result = self.run_checker(document)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn(message, result.stdout)

    def test_language_neutral_s_document_passes(self) -> None:
        result = self.run_checker(build_document())

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_missing_document_tier_is_backward_compatible_warning(self) -> None:
        document = build_document().replace("Document Tier: S\n", "")

        result = self.run_checker(document)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("WARN", result.stdout)
        self.assertIn("Document Tier", result.stdout)

    def test_invalid_document_tier_fails(self) -> None:
        self.assert_fails_with(
            build_document("XL"),
            "Invalid Document Tier",
        )

    def test_empty_verification_method_fails(self) -> None:
        document = build_document().replace(
            "| P0-DONE | happy | Command contract is documented | Run python -m unittest and confirm exit code 0 | FAIL |",
            "| P0-DONE | happy | Command contract is documented | | FAIL |",
        )

        self.assert_fails_with(document, "verification method")

    def test_placeholder_verification_method_fails(self) -> None:
        document = build_document().replace(
            "Run python -m unittest and confirm exit code 0",
            "...",
        )

        self.assert_fails_with(document, "verification method")

    def test_invalid_ac_category_fails(self) -> None:
        document = build_document().replace(
            "| P0-ERR-01 | error |",
            "| P0-ERR-01 | unknown |",
        )

        self.assert_fails_with(document, "Invalid AC category")

    def test_invalid_ac_severity_fails(self) -> None:
        document = build_document().replace(
            "| P0-ERR-01 | error | Invalid amounts are rejected | Run the invalid-amount test and inspect the error | FAIL |",
            "| P0-ERR-01 | error | Invalid amounts are rejected | Run the invalid-amount test and inspect the error | INFO |",
        )

        self.assert_fails_with(document, "Invalid AC severity")

    def test_dangling_task_ac_reference_fails(self) -> None:
        document = build_document().replace(
            "| P0-T01 | P0-DONE |",
            "| P0-T01 | P0-DONE, M9-ERR-01 |",
        )

        self.assert_fails_with(document, "Undefined AC reference: M9-ERR-01")

    def test_each_milestone_requires_done_ac(self) -> None:
        document = build_document().replace(
            "## Acceptance Criteria",
            "## M1 Foundation\n\nCreate the initial module.\n\n## Acceptance Criteria",
        )

        self.assert_fails_with(document, "Missing DONE AC for milestone M1")

    def test_duplicate_global_id_fails(self) -> None:
        document = build_document().replace(
            "| G-02 | Do not claim completion without evidence | FAIL |",
            "| G-01 | Do not claim completion without evidence | FAIL |",
        )

        self.assert_fails_with(document, "Duplicate global AC ID: G-01")

    def test_malformed_global_id_fails(self) -> None:
        document = build_document().replace(
            "| G-02 | Do not claim completion without evidence | FAIL |",
            "| G-2 | Do not claim completion without evidence | FAIL |",
        )

        self.assert_fails_with(document, "Malformed global AC ID: G-2")

    def test_global_id_gap_is_warning(self) -> None:
        document = build_document().replace(
            "| G-02 | Do not claim completion without evidence | FAIL |",
            "| G-03 | Do not claim completion without evidence | FAIL |",
        )

        result = self.run_checker(document)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("WARN", result.stdout)
        self.assertIn("Global AC ID gap", result.stdout)

    def test_more_than_ten_placeholders_is_warning(self) -> None:
        placeholders = "\n".join(f"Draft note {index}: TODO" for index in range(11))
        document = build_document().replace("## Tasks", placeholders + "\n\n## Tasks")

        result = self.run_checker(document)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("WARN", result.stdout)
        self.assertIn("11 placeholder", result.stdout)

    def test_m_tier_requires_readiness_approval_interfaces_and_handoff(self) -> None:
        result = self.run_checker(build_document("M"))

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        for requirement in ("AI Readiness", "Approval", "interface", "Handoff"):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, result.stdout)

    def test_complete_m_tier_document_passes(self) -> None:
        result = self.run_checker(with_m_requirements(build_document("M")))

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_l_tier_requires_architecture_and_full_flow(self) -> None:
        document = with_m_requirements(build_document("L"))

        result = self.run_checker(document)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("Architecture Constitution", result.stdout)
        self.assertIn("Boundary Policy", result.stdout)
        self.assertIn("stage report", result.stdout)


if __name__ == "__main__":
    unittest.main()
