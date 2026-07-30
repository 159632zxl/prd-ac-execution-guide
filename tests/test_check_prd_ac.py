from __future__ import annotations

import re
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
| G-01 | Do not bypass the truth source | FAIL |
| G-02 | Do not update persistent state without evidence | FAIL |
| G-03 | Do not build enhancements before completing the core loop | FAIL |
| G-04 | Do not overwrite existing user files without explicit disclosure | FAIL |
| G-05 | Do not guess interfaces, paths, schemas, or commands without checking | FAIL |
| G-06 | Do not invent business rules or user intent without confirmation | FAIL |
| G-07 | Do not expand scope or perform high-risk operations without approval | FAIL |
| G-08 | Do not claim completion without validation evidence | FAIL |

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


def with_l_requirements(document: str) -> str:
    document = with_m_requirements(document)
    l_tier_sections = """
## Architecture Constitution

Truth source: `data/ledger.jsonl`
Ownership boundaries: the CLI validates input and appends ledger entries.
Data integrity rules: existing entries remain immutable.

## Boundary Policy

| Always | Ask First | Never |
|--------|-----------|-------|
| Run validation commands | Change the truth-source schema | Rewrite existing entries |

Workflow Variant: requirements-first
Spec Maintenance Mode: spec-anchored
Execution Mode: batch

Proposal -> Requirements -> Design -> Tasks -> Implementation -> Acceptance
"""
    document = document.replace("## Tasks", l_tier_sections + "\n## Tasks")
    document = document.replace(
        "| P0-T01 | P0-DONE | `ledger.py` | `python -m unittest` |",
        "| P0-T01 | P0-DONE | `ledger.py` | `python -m unittest` |\n"
        "| M1-T01 | M1-DONE | `ledger.py` | `python -m unittest` |",
    )
    document = document.replace(
        "## Acceptance Criteria",
        """## M1 Foundation

Implement the validated append-only write path.

## Stage report

Write the completed stage report to `reports/M1.md`.

## Acceptance Criteria""",
    )
    document = document.replace(
        "| P0-ERR-01 | error | Invalid amounts are rejected | Run the invalid-amount test and inspect the error | FAIL |",
        """| P0-ERR-01 | error | Invalid amounts are rejected | Run the invalid-amount test and inspect the error | FAIL |

### §AC.M1 M1 acceptance

| AC | Category | Requirement | Verification Method | Severity |
|----|----------|-------------|---------------------|----------|
| M1-DONE | happy | Append-only write path is complete | Run python -m unittest and confirm exit code 0 | FAIL |""",
    )
    return document


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
        self.assertEqual("PASS", result.stdout.strip())

    def test_narrative_ellipses_do_not_count_as_placeholders(self) -> None:
        ellipses = "\n".join(
            f"Narrative note {index}: continue... and pause… before the next step."
            for index in range(11)
        )
        document = build_document().replace("## Tasks", ellipses + "\n\n## Tasks")

        result = self.run_checker(document)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("PASS", result.stdout.strip())

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

    def test_mapping_heading_does_not_create_a_milestone(self) -> None:
        document = build_document().replace(
            "## Acceptance Criteria",
            "## 7.5 旧计划 M9 阶段映射说明\n\nM9 maps to M2.\n\n## Acceptance Criteria",
        )

        result = self.run_checker(document)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("Missing DONE AC for milestone M9", result.stdout)

    def test_numbered_and_bilingual_acceptance_headings_are_accepted(self) -> None:
        headings = (
            "## 12 验收标准总览（Acceptance Criteria）",
            "## 12. 验收标准总览(Acceptance Criteria)",
            "## 12.1 Acceptance Criteria",
        )

        for heading in headings:
            with self.subTest(heading=heading):
                document = build_document().replace("## Acceptance Criteria", heading)
                result = self.run_checker(document)

                self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_heading_that_only_mentions_acceptance_criteria_is_rejected(self) -> None:
        document = build_document().replace(
            "## Acceptance Criteria",
            "## Notes about Acceptance Criteria",
        )

        self.assert_fails_with(document, "Missing final Acceptance Criteria section")

    def test_duplicate_global_id_fails(self) -> None:
        document = build_document().replace(
            "| G-02 | Do not update persistent state without evidence | FAIL |",
            "| G-01 | Do not update persistent state without evidence | FAIL |",
        )

        self.assert_fails_with(document, "Duplicate global AC ID: G-01")

    def test_malformed_global_id_fails(self) -> None:
        document = build_document().replace(
            "| G-02 | Do not update persistent state without evidence | FAIL |",
            "| G-2 | Do not update persistent state without evidence | FAIL |",
        )

        self.assert_fails_with(document, "Malformed global AC ID: G-2")

    def test_global_id_gap_is_warning(self) -> None:
        document = (
            build_document()
            .replace("Document Tier: S\n", "")
            .replace("| G-02 | Do not update persistent state without evidence | FAIL |\n", "")
        )

        result = self.run_checker(document)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("WARN", result.stdout)
        self.assertIn("Global AC ID gap", result.stdout)

    def test_tiered_document_requires_canonical_global_ids(self) -> None:
        document = build_document()
        for number in range(3, 9):
            document = re.sub(rf"(?m)^\| G-{number:02d} \|.*\n", "", document)

        self.assert_fails_with(
            document,
            "Missing canonical global AC IDs: G-03, G-04, G-05, G-06, G-07, G-08",
        )

    def test_more_than_ten_placeholders_is_warning(self) -> None:
        placeholders = "\n".join(f"Draft note {index}: TODO" for index in range(11))
        document = build_document().replace("## Tasks", placeholders + "\n\n## Tasks")

        result = self.run_checker(document)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("WARN", result.stdout)
        self.assertIn("11 placeholder", result.stdout)

    def test_table_ellipses_count_as_placeholders(self) -> None:
        rows = "\n".join("| ... |" if index % 2 else "| … |" for index in range(11))
        notes_table = f"| Draft note |\n|---|\n{rows}"
        document = build_document().replace("## Tasks", notes_table + "\n\n## Tasks")

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

    def test_complete_l_tier_document_passes(self) -> None:
        result = self.run_checker(with_l_requirements(build_document("L")))

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_l_tier_requires_architecture_and_full_flow(self) -> None:
        document = with_m_requirements(build_document("L"))

        result = self.run_checker(document)

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("Architecture Constitution", result.stdout)
        self.assertIn("Boundary Policy", result.stdout)
        self.assertIn("stage report", result.stdout)

    def test_repository_m_example_passes_without_warnings(self) -> None:
        example = REPO_ROOT / "references" / "example_prd_filled.md"
        result = subprocess.run(
            [sys.executable, str(CHECKER), str(example)],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("PASS", result.stdout.strip())

    def test_repository_l_template_fails_on_placeholder_verification_methods(self) -> None:
        template = REPO_ROOT / "references" / "prd_template.md"
        result = subprocess.run(
            [sys.executable, str(CHECKER), str(template)],
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("placeholder verification method", result.stdout)


if __name__ == "__main__":
    unittest.main()
