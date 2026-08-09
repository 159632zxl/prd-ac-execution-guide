from __future__ import annotations

import subprocess
import re
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


def valid_minimal_prd(*, milestone_heading: str = "## M1 Work", done_id: str = "M1-DONE-01") -> str:
    return f"""# PRD

## Goal

Store one validated item.

## Non-goals

No synchronization.

## Boundary and truth source

Truth source: local file. Boundary: this repository.

{milestone_heading}

Implement the bounded write/read slice.

## Tasks

| Task | Implements AC |
|---|---|
| M1-T01 | {done_id} |

## Acceptance Criteria

### Global forbidden items

| AC | Forbidden item | Severity |
|---|---|---|
| G-01 | Do not claim completion without test evidence | FAIL |

### Milestone acceptance

| AC | Category | Requirement | Verification Method | Severity |
|---|---|---|---|---|
| {done_id} | happy | The write/read slice is observable | Run the focused test | FAIL |
"""


def valid_m_tier_prd() -> str:
    document = valid_minimal_prd()
    canonical_rules = (
        "Do not bypass the truth source.",
        "Do not update persistent state without evidence.",
        "Do not build enhancements before completing the core loop.",
        "Do not overwrite existing user files without explicit disclosure.",
        "Do not guess interfaces, paths, schema, or commands without checking.",
        "Do not invent business rules or user intent without confirmation.",
        "Do not expand scope or perform high-risk operations without approval.",
        "Do not claim completion without validation evidence.",
    )
    global_rows = "\n".join(
        f"| G-{number:02d} | {rule} | FAIL |"
        for number, rule in enumerate(canonical_rules, start=1)
    )
    document = document.replace(
        "| G-01 | Do not claim completion without test evidence | FAIL |",
        global_rows,
    )
    document = document.replace(
        "## Acceptance Criteria",
        "## Interface and contract\n\nProducer to consumer.\n\n"
        "## Handoff and recovery\n\nNext command is recorded.\n\n"
        "## Acceptance Criteria",
    )
    return (
        "Document Tier: M\n"
        "AI Readiness: ready\n"
        "No new design decisions required: yes\n"
        "Validation commands: python -m unittest\n"
        "Blocking ambiguities: none\n"
        "Spec status: approved\n"
        "Approved by: product-owner\n"
        "Approval date: 2026-08-09\n"
        "Implementation allowed: yes\n\n"
        + document
    )


class MainCheckerContractTests(unittest.TestCase):
    def test_valid_minimal_fixture_passes_base_checks(self) -> None:
        from scripts.check_prd_ac import check_document

        failures, _ = check_document(valid_minimal_prd())
        self.assertEqual(failures, [])

    def test_gfm_tables_without_outer_pipes_are_accepted(self) -> None:
        from scripts.check_prd_ac import check_document

        document = "\n".join(
            line.strip()[1:-1].strip()
            if line.strip().startswith("|") and line.strip().endswith("|")
            else line
            for line in valid_minimal_prd().splitlines()
        )

        failures, _ = check_document(document)

        self.assertEqual(failures, [])

    def test_canonical_g05_matches_repository_wording(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_m_tier_prd().replace(
            "interfaces, paths, schema, or commands",
            "interfaces, paths, schemas, or commands",
        )

        failures, _ = check_document(document)

        self.assertEqual(failures, [])

    def test_goal_and_non_goals_may_be_nested_before_acceptance(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd().replace(
            "## Goal\n\nStore one validated item.\n\n"
            "## Non-goals\n\nNo synchronization.\n\n",
            "## Overview\n\n"
            "### Goal\n\nStore one validated item.\n\n"
            "### Non-goals\n\nNo synchronization.\n\n",
        )

        failures, _ = check_document(document)

        self.assertEqual(failures, [])

    def test_main_checker_rejects_placeholders_without_traceback(self) -> None:
        document = """# PRD

## Acceptance Criteria

| AC | Category | Requirement | Verification Method | Severity |
|---|---|---|---|---|
| P0-DONE | happy | A real requirement | TODO | FAIL |
| G-01 | safety | A real prohibition | Run the test | FAIL |
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prd.md"
            path.write_text(document, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "check_prd_ac.py"), str(path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("placeholder", result.stdout.lower())
        self.assertNotIn("Traceback", result.stderr)

    def test_main_checker_rejects_empty_task_and_acceptance_tables(self) -> None:
        document = """# PRD

## Goal

Store one validated item.

## Non-goals

No synchronization.

## Boundary and truth source

Truth source: local file.

## Tasks

| Task | Implements AC |
|---|---|

## Acceptance Criteria

### Global forbidden items

| AC | Forbidden item | Severity |
|---|---|---|

### P0 acceptance

| AC | Category | Requirement | Verification Method | Severity |
|---|---|---|---|---|
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.md"
            path.write_text(document, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "check_prd_ac.py"), str(path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must contain at least one row", result.stdout)

    def test_global_forbidden_item_must_be_real_content(self) -> None:
        from scripts.check_prd_ac import check_document

        for value in ("", "<forbidden-action>"):
            with self.subTest(value=value):
                document = valid_minimal_prd().replace(
                    "Do not claim completion without test evidence",
                    value,
                )
                failures, _ = check_document(document)
                self.assertTrue(any("forbidden item" in failure.lower() for failure in failures), failures)

    def test_task_and_requirement_cells_reject_placeholders(self) -> None:
        from scripts.check_prd_ac import check_document

        empty_task = valid_minimal_prd().replace("| M1-T01 | M1-DONE-01 |", "|  | M1-DONE-01 |")
        task_failures, _ = check_document(empty_task)
        self.assertTrue(any("empty task" in failure.lower() for failure in task_failures), task_failures)

        placeholder_requirement = valid_minimal_prd().replace(
            "The write/read slice is observable",
            "<requirement>",
        )
        requirement_failures, _ = check_document(placeholder_requirement)
        self.assertTrue(any("placeholder requirement" in failure.lower() for failure in requirement_failures), requirement_failures)

    def test_fenced_examples_cannot_satisfy_required_fields(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd().replace(
            "## Boundary and truth source\n\nTruth source: local file. Boundary: this repository.",
            "## Context\n\n```text\nTruth source: fake\nBoundary: fake\n```",
        )
        failures, _ = check_document(document)
        self.assertIn("Missing truth source", failures)
        self.assertIn("Missing system boundary", failures)

    def test_designated_metadata_fences_remain_backward_compatible(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_m_tier_prd()
        metadata = """```text
Spec status: approved
Document Tier: M
Approved by: product-owner
Approval date: 2026-08-09
Implementation allowed: yes
```"""
        readiness = """## AI Readiness Gate

```text
AI Readiness: ready
No new design decisions required: yes
Validation commands: python -m unittest
Blocking ambiguities: none
```"""
        for line in (
            "Document Tier: M",
            "AI Readiness: ready",
            "No new design decisions required: yes",
            "Validation commands: python -m unittest",
            "Blocking ambiguities: none",
            "Spec status: approved",
            "Approved by: product-owner",
            "Approval date: 2026-08-09",
            "Implementation allowed: yes",
        ):
            document = document.replace(line + "\n", "", 1)
        document = metadata + "\n\n" + document.replace("## Interface and contract", readiness + "\n\n## Interface and contract")

        failures, warnings = check_document(document)

        self.assertEqual(failures, [])
        self.assertFalse(any("Missing Document Tier" in warning for warning in warnings), warnings)

    def test_unscoped_fenced_example_cannot_select_a_document_tier(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd().replace(
            "## Tasks",
            "## Example\n\n```text\nDocument Tier: M\n```\n\n## Tasks",
        )
        failures, warnings = check_document(document)

        self.assertEqual(failures, [])
        self.assertTrue(any("Missing Document Tier" in warning for warning in warnings), warnings)

    def test_document_tier_declaration_cannot_be_obfuscated_into_legacy_mode(self) -> None:
        from scripts.check_prd_ac import check_document

        base = valid_minimal_prd()
        declarations = (
            "Document Tier:",
            "\ufeffDocument Tier: M",
            "Document \u200bTier: M",
            "Document T\u034fier: M",
            "Document T\ufe0fier: M",
            "Document T&#105;er: M",
            "Document Tier&#58; M",
            "Document **Tier**: M",
            "<strong>Document Tier</strong>: M",
            "[Document Tier](https://example.test/tier): M",
            "`Document Tier`: M",
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration):
                failures, warnings = check_document(f"{declaration}\n{base}")

                self.assertTrue(failures, (declaration, failures, warnings))
                self.assertFalse(
                    any("Missing Document Tier" in warning for warning in warnings),
                    (declaration, failures, warnings),
                )

    def test_fenced_manifest_tier_cannot_be_obfuscated_into_legacy_mode(self) -> None:
        from scripts.check_prd_ac import check_document
        from tests.test_check_prd_ac import build_document

        document = build_document("M")
        declarations = (
            "Document T\u034fier: M",
            "Document **Tier**: M",
            "Document T&#105;er: M",
            "Document Tier&#58; M",
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration):
                failures, warnings = check_document(
                    document.replace("Document Tier: M", declaration)
                )

                self.assertTrue(failures, (declaration, failures, warnings))
                self.assertFalse(
                    any("Missing Document Tier" in warning for warning in warnings),
                    (declaration, failures, warnings),
                )

    def test_empty_required_metadata_values_are_not_concrete(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_m_tier_prd()
        mutations = (
            (
                "Validation commands: python -m unittest",
                "Validation commands:",
                "M tier requires AI Readiness fields: Validation commands",
            ),
            (
                "Approved by: product-owner",
                "Approved by:",
                "M tier requires Approval fields: Approved by",
            ),
        )
        for old, new, expected in mutations:
            with self.subTest(field=new):
                failures, _ = check_document(document.replace(old, new))

                self.assertIn(expected, failures)

    def test_reference_definitions_cannot_supply_required_metadata(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_m_tier_prd()
        mutations = (
            ("Document Tier", "M", "M", "Invalid Document Tier"),
            (
                "AI Readiness",
                "ready",
                "ready",
                "M tier requires AI Readiness fields: AI Readiness",
            ),
            (
                "No new design decisions required",
                "yes",
                "yes",
                "M tier requires AI Readiness fields: No new design decisions required",
            ),
            (
                "Validation commands",
                "python -m unittest",
                "python",
                "M tier requires AI Readiness fields: Validation commands",
            ),
            (
                "Blocking ambiguities",
                "none",
                "none",
                "M tier requires AI Readiness fields: Blocking ambiguities",
            ),
            (
                "Spec status",
                "approved",
                "approved",
                "M tier requires Approval fields: Spec status",
            ),
            (
                "Approved by",
                "product-owner",
                "product-owner",
                "M tier requires Approval fields: Approved by",
            ),
            (
                "Approval date",
                "2026-08-09",
                "2026-08-09",
                "M tier requires Approval fields: Approval date",
            ),
            (
                "Implementation allowed",
                "yes",
                "yes",
                "M tier requires Approval fields: Implementation allowed",
            ),
        )
        for field, original, destination, expected in mutations:
            with self.subTest(field=field):
                hidden = document.replace(
                    f"{field}: {original}",
                    f"[{field}]: {destination}",
                )
                failures, warnings = check_document(hidden)

                self.assertTrue(any(expected in failure for failure in failures), failures)
                self.assertFalse(
                    any("Missing Document Tier" in warning for warning in warnings),
                    warnings,
                )

    def test_reference_like_visible_metadata_is_not_a_reference_definition(self) -> None:
        from scripts.check_prd_ac import check_document, field_values

        document = valid_m_tier_prd()
        declarations = (
            "[Document Tier] : M",
            "[Document Tier]&#58; M",
            "Document  Tier: M",
            "Document\tTier: M",
            "Document&#9;Tier: M",
            "1. Document Tier: M",
            "> - Document Tier: M",
            "\ufeff[Document Tier]: M",
            "\u200b[Document Tier]: M",
            "\u2060[Document Tier]: M",
            "\u034f[Document Tier]: M",
        )
        for declaration in declarations:
            with self.subTest(declaration=ascii(declaration)):
                visible = document.replace(
                    "Document Tier: M",
                    declaration,
                )

                self.assertEqual(field_values([declaration], "Document Tier"), ["M"])
                failures, warnings = check_document(visible)

                self.assertEqual(failures, [])
                self.assertFalse(
                    any("Missing Document Tier" in warning for warning in warnings),
                    warnings,
                )

    def test_reference_definition_label_whitespace_is_render_normalized(self) -> None:
        from scripts.check_prd_ac import check_document, field_values

        document = valid_m_tier_prd()
        for label in ("Document  Tier", "Document\tTier", "Document&#9;Tier"):
            with self.subTest(label=ascii(label)):
                declaration = f"[{label}]: M"

                self.assertEqual(field_values([declaration], "Document Tier"), [""])
                failures, warnings = check_document(
                    document.replace("Document Tier: M", declaration)
                )

                self.assertTrue(
                    any("Invalid Document Tier" in failure for failure in failures),
                    failures,
                )
                self.assertFalse(
                    any("Missing Document Tier" in warning for warning in warnings),
                    warnings,
                )

    def test_backslash_cannot_escape_reference_destination_whitespace(self) -> None:
        from scripts.check_prd_ac import check_document, field_values

        declaration = r"[Document Tier]: M\ value"

        self.assertEqual(
            field_values([declaration], "Document Tier"),
            [r"M\ value"],
        )
        failures, warnings = check_document(
            valid_m_tier_prd().replace("Document Tier: M", declaration)
        )

        self.assertTrue(
            any(r"Invalid Document Tier: M\ value" in failure for failure in failures),
            failures,
        )
        self.assertFalse(
            any("Missing Document Tier" in warning for warning in warnings),
            warnings,
        )

    def test_reference_continuations_do_not_cross_into_deeper_blockquotes(self) -> None:
        from scripts.check_prd_ac import check_document, mask_inline_metadata

        visible_variants = (
            ("> [ref]:\n>> /visible", "> [ref]:\n>> /visible"),
            ('> [ref]: /hidden\n>> "visible title"', '\n>> "visible title"'),
        )
        for content, expected_mask in visible_variants:
            with self.subTest(content=content):
                self.assertEqual(mask_inline_metadata(content), expected_mask)
                document = valid_m_tier_prd().replace(
                    "## Interface and contract\n\nProducer to consumer.\n\n",
                    f"## Interface and contract\n\n{content}\n\n",
                )

                failures, _ = check_document(document)

                self.assertNotIn("M tier requires interfaces and boundaries", failures)

        for hidden in (
            "> [ref]:\n> /hidden",
            '> [ref]: /hidden\n> "hidden title"',
        ):
            with self.subTest(hidden=hidden):
                self.assertEqual(mask_inline_metadata(hidden), "\n")

    def test_inline_reference_title_does_not_hide_following_visible_line(self) -> None:
        from scripts.check_prd_ac import check_document, mask_inline_metadata

        variants = (
            ('[ref]: /hidden "inline title"\n"visible second"', '\n"visible second"'),
            (
                '[ref]:\n /hidden "inline title"\n"visible second"',
                '\n\n"visible second"',
            ),
        )
        for content, expected_mask in variants:
            with self.subTest(content=content):
                self.assertEqual(mask_inline_metadata(content), expected_mask)
                document = valid_m_tier_prd().replace(
                    "## Interface and contract\n\nProducer to consumer.\n\n",
                    f"## Interface and contract\n\n{content}\n\n",
                )

                failures, _ = check_document(document)

                self.assertNotIn("M tier requires interfaces and boundaries", failures)

    def test_multiline_reference_definition_cannot_supply_document_tier(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_m_tier_prd().replace(
            "Document Tier: M",
            "[Document\n Tier]: M",
        )

        failures, warnings = check_document(document)

        self.assertTrue(
            any("Invalid Document Tier" in failure for failure in failures),
            failures,
        )
        self.assertFalse(
            any("Missing Document Tier" in warning for warning in warnings),
            warnings,
        )

    def test_unterminated_multiline_reference_scan_remains_linear(self) -> None:
        from time import perf_counter

        from scripts.check_prd_ac import reference_definition_spans

        lines = ["[unterminated", *(["continuation"] * 5000)]

        started = perf_counter()
        spans = reference_definition_spans(lines)
        elapsed = perf_counter() - started

        self.assertEqual(spans, [])
        self.assertLess(elapsed, 1.5, f"reference scan took {elapsed:.3f}s")

    def test_html_comments_cannot_satisfy_required_fields_or_tables(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd().replace(
            "## Boundary and truth source\n\nTruth source: local file. Boundary: this repository.",
            "<!--\n## Boundary and truth source\nTruth source: fake. Boundary: fake.\n-->",
        )
        failures, _ = check_document(document)
        self.assertIn("Missing truth source", failures)
        self.assertIn("Missing system boundary", failures)

    def test_indented_code_cannot_satisfy_required_fields(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd().replace(
            "## Boundary and truth source\n\nTruth source: local file. Boundary: this repository.",
            "## Context\n\n    Truth source: fake\n    Boundary: fake",
        )
        failures, _ = check_document(document)
        self.assertIn("Missing truth source", failures)
        self.assertIn("Missing system boundary", failures)

    def test_inline_code_and_link_metadata_cannot_satisfy_required_fields(self) -> None:
        from scripts.check_prd_ac import check_document

        replacements = (
            "## Context\n\n`Truth source: fake. Boundary: fake.`",
            '## Context\n\n[context](https://example.test "Truth source: fake. Boundary: fake.")',
            '## Context\n\n<span title="Truth source: fake. Boundary: fake.">context</span>',
        )
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                document = valid_minimal_prd().replace(
                    "## Boundary and truth source\n\nTruth source: local file. Boundary: this repository.",
                    replacement,
                )
                failures, _ = check_document(document)
                self.assertIn("Missing truth source", failures)
                self.assertIn("Missing system boundary", failures)

    def test_reference_link_definitions_cannot_satisfy_required_fields(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd().replace(
            "## Boundary and truth source\n\nTruth source: local file. Boundary: this repository.",
            "## Context\n\n[context][meta]\n\n"
            '[meta]: https://example.test/path "Truth source: fake. Boundary: fake."',
        )
        failures, _ = check_document(document)
        self.assertIn("Missing truth source", failures)
        self.assertIn("Missing system boundary", failures)

    def test_acceptance_mentions_cannot_replace_truth_source_and_boundary_declarations(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd().replace(
            "## Boundary and truth source\n\nTruth source: local file. Boundary: this repository.",
            "## Context\n\nNo declarations here.",
        ).replace(
            "Do not claim completion without test evidence",
            "Do not guess the truth source or boundary",
        )
        failures, _ = check_document(document)
        self.assertIn("Missing truth source", failures)
        self.assertIn("Missing system boundary", failures)

    def test_nonvisible_table_metadata_cannot_satisfy_required_cells(self) -> None:
        from scripts.check_prd_ac import check_document

        base = valid_minimal_prd()
        mutations = (
            (
                "forbidden item",
                base.replace(
                    "Do not claim completion without test evidence",
                    '<em title="Do not claim completion without test evidence"></em>',
                ),
                "forbidden item",
            ),
            (
                "requirement",
                base.replace(
                    "The write/read slice is observable",
                    '<strong title="The write/read slice is observable"></strong>',
                ),
                "requirement",
            ),
            (
                "verification",
                base.replace(
                    "Run the focused test",
                    "[](https://example.test/run-the-focused-test)",
                ),
                "verification method",
            ),
            (
                "task",
                base.replace(
                    "M1-T01 | M1-DONE-01",
                    '<code title="M1-T01"></code> | M1-DONE-01',
                ),
                "empty task",
            ),
            (
                "AC mapping",
                base.replace(
                    "M1-T01 | M1-DONE-01",
                    "M1-T01 | [details](https://example.test/M1-DONE-01)",
                ),
                "no AC reference",
            ),
        )
        for label, document, expected in mutations:
            with self.subTest(label=label):
                failures, _ = check_document(document)
                self.assertTrue(any(expected.lower() in failure.lower() for failure in failures), failures)

    def test_m_tier_fields_require_visible_nonplaceholder_values(self) -> None:
        from scripts.check_prd_ac import check_document

        valid = valid_m_tier_prd()
        valid_failures, _ = check_document(valid)
        self.assertEqual(valid_failures, [])

        values = {
            "AI Readiness": "ready",
            "No new design decisions required": "yes",
            "Validation commands": "python -m unittest",
            "Blocking ambiguities": "none",
            "Spec status": "approved",
            "Approved by": "product-owner",
            "Approval date": "2026-08-09",
            "Implementation allowed": "yes",
        }
        for field, value in values.items():
            with self.subTest(field=field):
                document = valid.replace(f"{field}: {value}", f"{field}: TODO")
                failures, _ = check_document(document)
                self.assertTrue(any(field in failure for failure in failures), failures)

    def test_tier_metadata_values_follow_declared_enums(self) -> None:
        from scripts.check_prd_ac import check_document

        m_document = valid_m_tier_prd()
        m_fields = {
            "AI Readiness": "ready",
            "No new design decisions required": "yes",
            "Spec status": "approved",
            "Implementation allowed": "yes",
        }
        for field, valid_value in m_fields.items():
            with self.subTest(field=field):
                document = m_document.replace(
                    f"{field}: {valid_value}",
                    f"{field}: maybe",
                )
                failures, _ = check_document(document)
                self.assertTrue(any(f"Invalid {field}" in failure for failure in failures), failures)

        l_document = m_document.replace("Document Tier: M", "Document Tier: L").replace(
            "AI Readiness: ready",
            "Workflow Variant: requirements-first\n"
            "Spec Maintenance Mode: spec-first\n"
            "Execution Mode: batch\n"
            "AI Readiness: ready",
        )
        l_fields = {
            "Workflow Variant": "requirements-first",
            "Spec Maintenance Mode": "spec-first",
            "Execution Mode": "batch",
        }
        for field, valid_value in l_fields.items():
            with self.subTest(field=field):
                document = l_document.replace(
                    f"{field}: {valid_value}",
                    f"{field}: maybe",
                )
                failures, _ = check_document(document)
                self.assertTrue(any(f"Invalid {field}" in failure for failure in failures), failures)

    def test_conflicting_metadata_declarations_fail(self) -> None:
        from scripts.check_prd_ac import check_document

        valid = valid_m_tier_prd()
        mutations = (
            ("Document Tier", "Document Tier: S\n" + valid),
            ("Spec status", "Spec status: draft\n" + valid),
            ("Implementation allowed", "Implementation allowed: no\n" + valid),
            ("AI Readiness", "AI Readiness: not-ready\n" + valid),
        )
        for field, document in mutations:
            with self.subTest(field=field):
                failures, _ = check_document(document)
                self.assertTrue(
                    any(f"Conflicting {field} declarations" in failure for failure in failures),
                    failures,
                )

        repeated = "Spec status: approved\nImplementation allowed: yes\n" + valid
        failures, _ = check_document(repeated)
        self.assertEqual(failures, [])

    def test_metadata_cross_field_contradictions_fail(self) -> None:
        from scripts.check_prd_ac import check_document

        valid = valid_m_tier_prd()
        mutations = (
            (
                "draft implementation",
                valid.replace("Spec status: approved", "Spec status: draft"),
                "Implementation allowed: yes requires Spec status: approved",
            ),
            (
                "superseded implementation",
                valid.replace("Spec status: approved", "Spec status: superseded"),
                "Implementation allowed: yes requires Spec status: approved",
            ),
            (
                "ready with design decisions",
                valid.replace(
                    "No new design decisions required: yes",
                    "No new design decisions required: no",
                ),
                "AI Readiness: ready requires No new design decisions required: yes",
            ),
            (
                "not-ready implementation",
                valid.replace("AI Readiness: ready", "AI Readiness: not-ready"),
                "Implementation allowed: yes requires AI Readiness: ready",
            ),
        )
        for label, document, expected in mutations:
            with self.subTest(label=label):
                failures, _ = check_document(document)
                self.assertIn(expected, failures)

    def test_s_tier_validates_declared_metadata(self) -> None:
        from scripts.check_prd_ac import check_document

        valid = valid_m_tier_prd().replace("Document Tier: M", "Document Tier: S")
        for field, current in (
            ("Spec status", "approved"),
            ("Implementation allowed", "yes"),
        ):
            with self.subTest(invalid=field):
                document = valid.replace(f"{field}: {current}", f"{field}: maybe")
                failures, _ = check_document(document)
                self.assertTrue(any(f"Invalid {field}" in failure for failure in failures), failures)

            with self.subTest(missing=field):
                document = valid.replace(f"{field}: {current}\n", "")
                failures, _ = check_document(document)
                self.assertTrue(any("S tier requires metadata fields" in failure for failure in failures), failures)

        document = valid.replace(
            "AI Readiness: ready",
            "Workflow Variant: maybe\nAI Readiness: ready",
        )
        failures, _ = check_document(document)
        self.assertTrue(any("Invalid Workflow Variant" in failure for failure in failures), failures)

    def test_acceptance_criteria_authority_must_be_unique(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_m_tier_prd().replace(
            "## Acceptance Criteria",
            "## Acceptance Criteria\n\nInterim authority.\n\n## Acceptance Criteria",
        )
        failures, _ = check_document(document)
        self.assertTrue(
            any("exactly one Acceptance Criteria" in failure for failure in failures),
            failures,
        )

    def test_raw_html_blocks_cannot_satisfy_prd_structure(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd()
        for tag in (
            "script",
            "style",
            "pre",
            "textarea",
            "template",
            "xmp",
            "iframe",
            "noembed",
            "noframes",
            "title",
        ):
            with self.subTest(tag=tag):
                failures, _ = check_document(f'<{tag} data-test="hidden">\n{document}\n</{tag}>')
                self.assertIn("Missing goal section", failures)

        plaintext_failures, _ = check_document(f"<plaintext>\n{document}")
        self.assertIn("Missing goal section", plaintext_failures)

        ignored_close_failures, _ = check_document(
            f"<plaintext>\nignored closing tag</plaintext>\n{document}"
        )
        self.assertIn("Missing goal section", ignored_close_failures)

    def test_multiline_raw_html_opener_cannot_supply_acceptance_authority(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd().replace(
            "## Acceptance Criteria",
            "<script\n type=text/plain>\n## Acceptance Criteria",
        )
        failures, _ = check_document(document + "\n</script>")

        self.assertIn("Missing final Acceptance Criteria section", failures)

    def test_incomplete_raw_tag_after_visible_text_remains_literal(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd().replace(
            "Store one validated item.",
            "Store one validated item. This sentence discusses <script as a literal token.",
        )
        failures, _ = check_document(document)

        self.assertEqual(failures, [])

    def test_invalid_incomplete_raw_tag_prefix_remains_visible_text(self) -> None:
        from scripts.check_prd_ac import check_document, rendered_section_boundaries

        for literal in (
            "<script/",
            "<script=",
            "<script!",
            "<div/",
            "</div/",
            "</script/",
        ):
            with self.subTest(literal=literal):
                failures, _ = check_document(f"{literal}\n{valid_minimal_prd()}")

                self.assertEqual(failures, [])
                self.assertEqual(
                    rendered_section_boundaries([literal, "## visible"]),
                    [(1, 2)],
                )

    def test_unterminated_raw_html_after_visible_prefix_cannot_satisfy_structure(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd()
        for tag in (
            "script",
            "style",
            "pre",
            "textarea",
            "template",
            "xmp",
            "listing",
            "iframe",
            "noembed",
            "noframes",
            "title",
            "plaintext",
        ):
            with self.subTest(tag=tag):
                failures, _ = check_document(
                    f'visible prefix <{tag} data-test="hidden">\n{document}'
                )

                self.assertIn("Missing goal section", failures)

    def test_literal_raw_html_tag_names_remain_visible_text(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd()
        prefixes = (
            "Literal `<plaintext>` tag.",
            "Literal ``<plaintext>`` tag.",
            r"Literal \<plaintext> tag.",
            '<span title="<plaintext>">Literal tag name.</span>',
            "    <plaintext>",
            "```<plaintext>\nignored fenced content\n```",
        )
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                failures, _ = check_document(f"{prefix}\n{document}")

                self.assertEqual(failures, [])

    def test_hidden_html_cannot_satisfy_prd_structure(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_m_tier_prd()
        wrappers = (
            '<div hidden>\n{document}\n</div>',
            '<div style="display: none">\n{document}\n</div>',
            '<section style="visibility: hidden">\n{document}\n</section>',
        )
        for wrapper in wrappers:
            with self.subTest(wrapper=wrapper):
                failures, _ = check_document(wrapper.format(document=document))
                self.assertIn("Missing goal section", failures)

    def test_hidden_html_variants_cannot_satisfy_prd_structure(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_m_tier_prd()
        wrappers = (
            "<div style=display:none>\n{document}\n</div>",
            '<div style="visibility:collapse">\n{document}\n</div>',
            "<div style=opacity:0>\n{document}\n</div>",
            '<div style="display:/**/none!important">\n{document}\n</div>',
            '<div style="display:none/**/!important">\n{document}\n</div>',
            '<div style="visibility:hidden !IMPORTANT">\n{document}\n</div>',
            '<div style="opacity:0!important">\n{document}\n</div>',
            '<div style="display&#58;none">\n{document}\n</div>',
            '<div style="d\\69 splay:n\\6f ne">\n{document}\n</div>',
            '<div aria-hidden="true">\n{document}\n</div>',
            '<div aria-hidden="tr&#117;e">\n{document}\n</div>',
            "<div hidden>\n{document}",
            "<details>\n<summary>Archived example</summary>\n{document}\n</details>",
            "<dialog>\n{document}\n</dialog>",
        )
        for wrapper in wrappers:
            with self.subTest(wrapper=wrapper):
                failures, _ = check_document(wrapper.format(document=document))
                self.assertIn("Missing goal section", failures)

        visible_wrappers = (
            '<div aria-hidden="false">\n{document}\n</div>',
            "<details open>\n{document}\n</details>",
            "<dialog open>\n{document}\n</dialog>",
        )
        for wrapper in visible_wrappers:
            with self.subTest(visible_wrapper=wrapper):
                failures, _ = check_document(wrapper.format(document=document))
                self.assertNotIn("Missing goal section", failures)

    def test_m_l_metadata_must_precede_first_level_two_section(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_m_tier_prd()
        metadata = "\n".join(
            line
            for line in document.splitlines()
            if re.match(
                r"^(?:Document Tier|AI Readiness|No new design decisions required|"
                r"Validation commands|Blocking ambiguities|Spec status|Approved by|"
                r"Approval date|Implementation allowed):",
                line,
            )
        )
        stripped = re.sub(
            r"^(?:Document Tier|AI Readiness|No new design decisions required|"
            r"Validation commands|Blocking ambiguities|Spec status|Approved by|"
            r"Approval date|Implementation allowed):[^\n]*\n",
            "",
            document,
            flags=re.MULTILINE,
        )
        moved = stripped + "\n\n" + metadata + "\n"

        failures, _ = check_document(moved)
        self.assertTrue(
            any("metadata" in failure.lower() for failure in failures), failures
        )

    def test_negated_required_headings_do_not_satisfy_m_or_l_gates(self) -> None:
        from scripts.check_prd_ac import check_document

        m_document = valid_m_tier_prd()
        for heading, expected in (
            ("## Interface and contract", "M tier requires interfaces and boundaries"),
            ("## Handoff and recovery", "M tier requires Handoff and recovery"),
        ):
            with self.subTest(heading=heading):
                mutated = m_document.replace(heading, "## No " + heading[3:].lower())
                failures, _ = check_document(mutated)
                self.assertIn(expected, failures)

    def test_render_equivalent_negated_heading_does_not_satisfy_l_gate(self) -> None:
        from scripts.check_prd_ac import check_document
        from tests.test_check_prd_ac import build_document, with_l_requirements

        document = with_l_requirements(build_document("L"))
        variants = (
            "## N&#111; Architecture Constitution",
            "## N\u200bo Architecture Constitution",
            "## N\u034fo Architecture Constitution",
            "## N\ufe0fo Architecture Constitution",
            "## \uff2e\uff4f Architecture Constitution",
            "## N**o** Architecture Constitution",
            "## [No](https://example.test/no) Architecture Constitution",
            "## [No] Architecture Constitution\n\n[No]: https://example.test/no",
            "## ![No](https://example.test/no.png) Architecture Constitution",
            "## ![No] Architecture Constitution\n\n[No]: https://example.test/no.png",
            "## `No` Architecture Constitution",
        )
        for heading in variants:
            with self.subTest(heading=heading):
                failures, _ = check_document(
                    document.replace("## Architecture Constitution", heading)
                )

                self.assertIn("L tier requires Architecture Constitution", failures)

    def test_reference_definition_does_not_populate_required_m_section(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            "[only-ref]: https://example.test/invisible",
            "[only-ref]: https://example.test/" + "x" * 1200,
            "[" + "a" * 1200 + "]: https://example.test/invisible",
            "[only\n ref]: https://example.test/invisible",
            "[only-ref]:\n https://example.test/invisible",
            '[only-ref]: https://example.test/invisible\n"title"',
            '[only-ref]: https://example.test/invisible\n    "title"',
            "> [only-ref]: https://example.test/invisible",
            '> [only-ref]: https://example.test/invisible\n> "title"',
            "- [only-ref]: https://example.test/invisible",
            '- [only-ref]: https://example.test/invisible\n  "title"',
        )
        for content in variants:
            with self.subTest(content=content):
                document = valid_m_tier_prd().replace(
                    "## Interface and contract\n\nProducer to consumer.\n\n",
                    f"## Interface and contract\n\n{content}\n\n",
                )
                failures, _ = check_document(document)

                self.assertIn("M tier requires interfaces and boundaries", failures)

    def test_incomplete_visible_reference_syntax_counts_as_section_content(self) -> None:
        from scripts.check_prd_ac import check_document

        for content in (
            "[visible-label]:",
            '[visible-label]: "some title"',
            "[visible-label]: (some title)",
            r"[visible-label]: M\ value",
            "[visible-label]:\n- visible-item",
            "[visible-label]:\n> visible-quote",
            "[visible-label]:\n1. visible-item",
            '[hidden-label]: https://example.test/hidden\n- "visible item"',
        ):
            with self.subTest(content=content):
                document = valid_m_tier_prd().replace(
                    "## Interface and contract\n\nProducer to consumer.\n\n",
                    f"## Interface and contract\n\n{content}\n\n",
                )

                failures, _ = check_document(document)

                self.assertNotIn("M tier requires interfaces and boundaries", failures)

    def test_l_tier_requires_ordered_workflow_declaration(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_m_tier_prd().replace("Document Tier: M", "Document Tier: L")
        document = document.replace(
            "AI Readiness: ready",
            "Workflow Variant: requirements-first\n"
            "Spec Maintenance Mode: spec-first\n"
            "Execution Mode: batch\n"
            "AI Readiness: ready",
        )
        document = document.replace(
            "## Interface and contract",
            "## Architecture Constitution\n\nRules.\n\n"
            "## Boundary Policy\n\nBoundaries.\n\n"
            "## P0 Foundation\n\nFoundation.\n\n"
            "## Stage report format\n\nThe report format is written to reports/M1.md.\n\n"
            "## Interface and contract",
        )
        document = document.replace(
            "## Handoff and recovery",
            "## Handoff and recovery\n\nRecovery is recorded.\n\n"
            "Proposal -> Requirements -> Design -> Tasks -> Implementation -> Acceptance",
        )
        document = document.replace(
            "| M1-DONE-01 | happy | The write/read slice is observable | Run the focused test | FAIL |",
            "| P0-DONE | happy | Foundation is accepted | Run the foundation test | FAIL |\n"
            "| M1-DONE-01 | happy | The write/read slice is observable | Run the focused test | FAIL |",
        )

        reversed_document = document.replace(
            "Proposal -> Requirements -> Design -> Tasks -> Implementation -> Acceptance",
            "Acceptance -> Implementation -> Tasks -> Design -> Requirements -> Proposal",
        )
        failures, _ = check_document(reversed_document)

        self.assertTrue(any("complete Proposal" in failure for failure in failures), failures)

    def test_acceptance_criteria_must_be_the_final_document_section(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd() + "\n\n# Appendix\n\nAdditional notes.\n"
        failures, _ = check_document(document)

        self.assertIn("Acceptance Criteria must be the final section", failures)

    def test_rendered_h1_h2_after_acceptance_invalidates_final_section(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            "   ## Appendix\n\nAdditional notes.",
            "   # Appendix\n\nAdditional notes.",
            "> ## Appendix\n> Additional notes.",
            "- ## Appendix\n\n  Additional notes.",
            "Appendix\n---\n\nAdditional notes.",
            "Appendix\n===\n\nAdditional notes.",
            "> Appendix\n> ---\n> Additional notes.",
            "- Appendix\n  ---\n\n  Additional notes.",
            "1. Appendix\n   ---\n\n   Additional notes.",
            "<h2>Appendix</h2>\n\nAdditional notes.",
            '<div><H1 class="appendix">Appendix</H1></div>\n\nAdditional notes.',
            '<h2\n class="appendix">Appendix</h2>\n\nAdditional notes.',
            "\\\\<h2>Appendix after a literal backslash</h2>",
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

                self.assertIn("Acceptance Criteria must be the final section", failures)

    def test_nonheading_markup_after_acceptance_remains_in_the_ac_section(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            "### Appendix child\n\nAdditional notes.",
            "```html\n<h2>Example</h2>\n```",
            "    ## Indented code",
            "`<h2>Inline code</h2>`",
            "``<h2>Multi-backtick inline code</h2>``",
            "[link](<h2>)",
            "![image](<h2>)",
            "[example]: <h2>",
            r"\<h2>Literal opening tag</h2>",
            '<div data-label="<h2>">Attribute text</div>',
            "<div>\n## Literal Markdown heading\nText\n</div>",
            "<div>\nLiteral Setext heading\n---\nText\n</div>",
            "> <div>\n> ## Literal quoted heading\n> Text\n> </div>",
            "- <div>\n  ## Literal list heading\n  Text\n  </div>",
            "<!-- <h2>Commented heading</h2> -->",
            "<template><h2>Hidden heading</h2></template>",
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

                self.assertEqual(failures, [])

    def test_rendered_inline_html_after_acceptance_invalidates_final_section(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            "](<h2>visible</h2>)",
            r"\[x](<h2>visible</h2>)",
            r"\`<h2>visible</h2>`",
            "[x](<h2>visible</h2>)",
            "![x](<h2>visible</h2>)",
            "<div>\n`<h2>visible</h2>`\n</div>",
            "<div>\n[link](<h2>visible</h2>)\n</div>",
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

                self.assertIn("Acceptance Criteria must be the final section", failures)

    def test_multiline_code_span_html_does_not_create_a_section(self) -> None:
        from scripts.check_prd_ac import check_document

        appendix = "`start\nx <h2>not heading</h2>\nend`"
        failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

        self.assertEqual(failures, [])

    def test_type_seven_html_tag_cannot_interrupt_a_paragraph(self) -> None:
        from scripts.check_prd_ac import check_document

        appendix = "paragraph\n<custom>\n## Appendix"
        failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

        self.assertIn("Acceptance Criteria must be the final section", failures)

    def test_reference_definition_title_does_not_create_a_section(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            '[ref]: /url\n"<h2>not heading</h2>"',
            '[ref]: /url\n"not heading"\n---',
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

                self.assertEqual(failures, [])

    def test_reference_like_text_inside_html_block_keeps_html_heading(self) -> None:
        from scripts.check_prd_ac import check_document

        appendix = "</div>\n  [ref]: <h2>"

        failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

        self.assertIn("Acceptance Criteria must be the final section", failures)

    def test_container_code_and_noninterrupting_list_are_not_sections(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            ">     ## not heading",
            "-     ## not heading",
            "paragraph\n2. ## not heading",
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

                self.assertEqual(failures, [])

    def test_list_continuation_headings_survive_the_full_mask_pipeline(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            "- Title\n    ---",
            "1. Title\n    ===",
            "- Title\n    ## visible",
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(
                    valid_minimal_prd() + "\n\n" + appendix
                )

                self.assertIn(
                    "Acceptance Criteria must be the final section",
                    failures,
                )

    def test_list_relative_indented_code_remains_non_heading(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            "- Title\n      ## not a heading",
            "> - Title\n>       ## not a heading",
            "    ## root indented code",
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(
                    valid_minimal_prd() + "\n\n" + appendix
                )

                self.assertEqual(failures, [])

    def test_list_relative_fence_masks_its_heading_literals(self) -> None:
        from scripts.check_prd_ac import (
            mask_fenced_lines,
            rendered_section_boundaries,
        )

        source = "- item\n    ```\n  ## hidden\n    ```\n## visible"
        masked = mask_fenced_lines(source, preserve_html_comments=True)

        self.assertEqual(rendered_section_boundaries(masked), [(4, 2)])

    def test_container_reordering_does_not_form_a_setext_heading(self) -> None:
        from scripts.check_prd_ac import check_document

        appendix = "> - paragraph\n  > ---"
        failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

        self.assertEqual(failures, [])

    def test_blockquote_nested_in_list_survives_the_full_mask_pipeline(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            "- > Title\n  > ---",
            "- > Title\n    > ---",
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(
                    valid_minimal_prd() + "\n\n" + appendix
                )

                self.assertIn(
                    "Acceptance Criteria must be the final section",
                    failures,
                )

    def test_list_context_survives_blank_and_masked_lines(self) -> None:
        from scripts.check_prd_ac import (
            mask_fenced_lines,
            rendered_section_boundaries,
        )

        cases = (
            ("-     T\n    ## H", [(1, 2)]),
            ("- T\n\n    ## H", [(2, 2)]),
            (
                "-   item\n        ~~~\n    ## H\n        ~~~\n## root",
                [(2, 2), (4, 2)],
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                masked = mask_fenced_lines(source, preserve_html_comments=True)

                self.assertEqual(rendered_section_boundaries(masked), expected)

    def test_heading_after_container_fence_is_not_masked(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            "> ~~~\nTitle\n---",
            "-\n  ~~~\nTitle\n---",
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

                self.assertIn("Acceptance Criteria must be the final section", failures)

    def test_container_interrupts_type_six_html_block(self) -> None:
        from scripts.check_prd_ac import check_document

        appendix = "> <div>\n## visible"

        failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

        self.assertIn("Acceptance Criteria must be the final section", failures)

    def test_setext_respects_list_and_blockquote_continuation(self) -> None:
        from scripts.check_prd_ac import check_document

        list_continuation = "- listed\n  Title\n==="
        failures, _ = check_document(valid_minimal_prd() + "\n\n" + list_continuation)
        self.assertEqual(failures, [])

        blockquote_termination = "> <!--\n-->\n  Title\n---"
        failures, _ = check_document(
            valid_minimal_prd() + "\n\n" + blockquote_termination
        )
        self.assertIn("Acceptance Criteria must be the final section", failures)

    def test_commonmark_html_blocks_mask_markdown_heading_literals(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            "<!DOCTYPE html\n## not heading\n>",
            "<?processing\n## not heading\n?>",
            "<![CDATA[\n## not heading\n]]>",
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

                self.assertEqual(failures, [])

    def test_consecutive_html_blocks_follow_their_own_termination_rules(self) -> None:
        from scripts.check_prd_ac import check_document

        appendix = (
            "<?x\n## no\n?>\n"
            "<custom>\n## no\n</custom>\n"
            ">     ## no\n"
            "   ## no\n"
            "`start\n## no\nend`\n"
            "<custom>\n## no\n</custom>\n___"
        )

        failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

        self.assertEqual(failures, [])

    def test_html_declaration_ends_before_the_following_setext_heading(self) -> None:
        from scripts.check_prd_ac import check_document

        appendix = (
            "<!DOCTYPE html\n## no\n>\n"
            "Title\n-----\n"
            "-     ## no"
        )

        failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

        self.assertIn("Acceptance Criteria must be the final section", failures)

    def test_open_type_seven_html_block_masks_following_container_text(self) -> None:
        from scripts.check_prd_ac import check_document

        appendix = (
            "<custom>\n## no\n</custom>\n"
            "> foo\nbar\n===\n"
            "foo\n<!-- ## no -->\n"
            "<!DOCTYPE html\n## no\n>\n"
            "> ## no"
        )

        failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

        self.assertEqual(failures, [])

    def test_official_commonmark_nonheadings_do_not_create_sections(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            "***\n---\n___",
            "> foo\nbar\n===",
            "-\n  foo\n-\n  ```\n  bar\n  ```\n-\n      baz",
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

                self.assertEqual(failures, [])

    def test_multiline_setext_boundary_uses_the_first_source_line(self) -> None:
        from scripts.check_prd_ac import rendered_section_boundaries

        self.assertEqual(rendered_section_boundaries(["alpha", "beta", "---"]), [(0, 2)])

    def test_setext_after_a_quoted_heading_starts_a_new_section(self) -> None:
        from scripts.check_prd_ac import rendered_section_boundaries

        lines = ["`## no`", "### child", "> ## visible", "`## no`", "---"]

        self.assertEqual(rendered_section_boundaries(lines), [(2, 2), (3, 2)])

    def test_setext_after_a_closed_quote_is_not_suppressed(self) -> None:
        from scripts.check_prd_ac import rendered_section_boundaries

        lines = [
            "<!-- ## no -->",
            "foo",
            "a",
            "b",
            "---",
            "> Title",
            "> ---",
            "Title",
            "===",
        ]

        self.assertEqual(rendered_section_boundaries(lines), [(1, 2), (5, 2), (7, 1)])

    def test_setext_headings_follow_commonmark_paragraph_and_list_rules(self) -> None:
        from scripts.check_prd_ac import rendered_section_boundaries

        cases = (
            (["- Title", "    ---"], [(0, 2)]),
            (["1. Title", "    ==="], [(0, 1)]),
            (["> - Title", ">   ---"], [(0, 2)]),
            (["===", "---"], [(0, 2)]),
            (["===", "==="], [(0, 1)]),
            (["paragraph", "    Title", "---"], [(0, 2)]),
            (["paragraph", "2. Title", "==="], [(0, 1)]),
            (["paragraph", "- Title", "   ---"], [(1, 2)]),
            (["paragraph", "", "  - Title", "    ==="], [(2, 1)]),
        )
        for lines, expected in cases:
            with self.subTest(lines=lines):
                self.assertEqual(rendered_section_boundaries(lines), expected)

    def test_multiline_inline_html_stays_inside_its_markdown_container(self) -> None:
        from scripts.check_prd_ac import rendered_section_boundaries

        cases = (
            (["> paragraph <h2", '> class="x">Title</h2>'], [(0, 2)]),
            (["- paragraph <h2", '  class="x">Title</h2>'], [(0, 2)]),
            (["> - paragraph <h2", '>   class="x">Title</h2>'], [(0, 2)]),
            (["> paragraph <h2", 'class="x">Title</h2>'], [(0, 2)]),
            (["> > paragraph <h2", '> class="x">Title</h2>'], [(0, 2)]),
            (["- paragraph <h2", 'class="x">Title</h2>'], [(0, 2)]),
            (["> - paragraph <h2", '> class="x">Title</h2>'], [(0, 2)]),
        )
        for lines, expected in cases:
            with self.subTest(lines=lines):
                self.assertEqual(rendered_section_boundaries(lines), expected)

    def test_container_blank_line_ends_type_seven_html_block(self) -> None:
        from scripts.check_prd_ac import rendered_section_boundaries

        lines = ["> <div>", ">", "> ## visible"]

        self.assertEqual(rendered_section_boundaries(lines), [(2, 2)])

    def test_html_control_block_payload_does_not_create_a_section(self) -> None:
        from scripts.check_prd_ac import rendered_section_boundaries

        variants = (
            ["<?x <h2>not a heading</h2> ?>"],
            ["<![CDATA[<h2>not a heading</h2>]]>"],
            ["<!DECLARATION <h2>not a heading</h2>>"],
        )
        for lines in variants:
            with self.subTest(lines=lines):
                self.assertEqual(rendered_section_boundaries(lines), [])

    def test_terminated_html_blocks_ignore_blank_lines_until_terminator(self) -> None:
        from scripts.check_prd_ac import rendered_section_boundaries

        variants = (
            ["<?x", "", "<h2>not a heading</h2>", "?>"],
            ["<![CDATA[", "", "<h2>not a heading</h2>", "]]>"],
            ["<!DECLARATION", "", "<h2>not a heading</h2>", ">"],
            ["<script>", "", "<h2>not a heading</h2>", "</script>"],
            ["<!--", "", "<h2>not a heading</h2>", "-->"],
        )
        for lines in variants:
            with self.subTest(lines=lines):
                self.assertEqual(rendered_section_boundaries(lines), [])

    def test_html_blocks_do_not_cross_or_invent_containers(self) -> None:
        from scripts.check_prd_ac import rendered_section_boundaries

        self.assertEqual(
            rendered_section_boundaries(
                ["<?x", "> <h2>not a heading</h2>", "?>"]
            ),
            [],
        )
        self.assertEqual(
            rendered_section_boundaries(
                ["> <?x", "<h2>visible heading</h2> ?>"]
            ),
            [(1, 2)],
        )

    def test_raw_html_heading_uses_the_block_starting_container(self) -> None:
        from scripts.check_prd_ac import rendered_section_boundaries

        variants = (
            ["<custom>", "<h2", ">Title</h2>"],
            ["> <custom>", "> <h2", "> >Title</h2>"],
            ["- <custom>", "  <h2", "  >Title</h2>"],
        )
        for lines in variants:
            with self.subTest(lines=lines):
                self.assertEqual(rendered_section_boundaries(lines), [(1, 2)])

    def test_atx_headings_respect_paragraph_and_list_container_state(self) -> None:
        from scripts.check_prd_ac import rendered_section_boundaries

        cases = (
            (["> paragraph", "> 2. ## not a heading"], []),
            (["### child", "2. ## heading"], [(1, 2)]),
            (["- paragraph", "2. ## heading"], [(1, 2)]),
            (["- paragraph", "    ## heading"], [(1, 2)]),
            (["paragraph", "2. text", "    ## not a heading"], []),
        )
        for lines, expected in cases:
            with self.subTest(lines=lines):
                self.assertEqual(rendered_section_boundaries(lines), expected)

    def test_unclosed_backtick_scan_remains_linear(self) -> None:
        from time import perf_counter

        from scripts.check_prd_ac import _blank_inline_heading_literals

        source = "x" + ("`" * 6000)

        started = perf_counter()
        masked = _blank_inline_heading_literals(source)
        elapsed = perf_counter() - started

        self.assertEqual(masked, source)
        self.assertLess(elapsed, 1.0, f"inline scan took {elapsed:.3f}s")

    def test_unclosed_reference_image_scan_remains_linear(self) -> None:
        from time import perf_counter

        from scripts.check_prd_ac import _blank_inline_heading_literals

        source = "![a][" * 4000

        started = perf_counter()
        masked = _blank_inline_heading_literals(source, {"IMAGE"})
        elapsed = perf_counter() - started

        self.assertEqual(masked, source)
        self.assertLess(elapsed, 1.0, f"reference image scan took {elapsed:.3f}s")

    def test_invalid_commonmark_inline_html_does_not_create_a_section(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            "p <h2 @> x",
            "p <h2 a=> x",
            "p <h2 / > x",
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

                self.assertEqual(failures, [])

    def test_unicode_whitespace_inline_html_creates_a_section(self) -> None:
        from scripts.check_prd_ac import check_document

        for separator in ("\u00a0", "\u2003", "\u202f"):
            with self.subTest(separator=repr(separator)):
                appendix = f"p <h2{separator}>Appendix</h2>"
                failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

                self.assertIn("Acceptance Criteria must be the final section", failures)

    def test_image_alt_html_does_not_create_a_section(self) -> None:
        from scripts.check_prd_ac import check_document

        appendix = "p ![<h2>not a heading</h2>](image.png)"
        failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

        self.assertEqual(failures, [])

    def test_resolved_reference_image_alt_html_does_not_create_a_section(self) -> None:
        from scripts.check_prd_ac import check_document

        variants = (
            "![<h2>not a heading</h2>][image]\n\n[image]: image.png",
            "![<h2>not a heading</h2>][]\n\n[<h2>not a heading</h2>]: image.png",
            "![<h2>not a heading</h2>]\n\n[<h2>not a heading</h2>]: image.png",
        )
        for appendix in variants:
            with self.subTest(appendix=appendix):
                failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

                self.assertEqual(failures, [])

        visible_variants = (
            "![<h2>visible heading</h2>][missing]",
            "![<h2>x</h2>]\n\n[x]: image.png",
            "![<h2>x</h2>][missing]\n\n[<h2>x</h2>]: image.png",
            "\\![<h2>x</h2>][image]\n\n[image]: image.png",
            "[<h2>x</h2>][image]\n\n[image]: destination",
        )
        for appendix in visible_variants:
            with self.subTest(visible_appendix=appendix):
                failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)
                self.assertIn("Acceptance Criteria must be the final section", failures)

    def test_html_tag_cannot_cross_a_commonmark_block_boundary(self) -> None:
        from scripts.check_prd_ac import check_document

        appendix = "p <h2\n> quoted text"
        failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

        self.assertEqual(failures, [])

    def test_link_destination_parenthesis_limit_controls_html_visibility(self) -> None:
        from scripts.check_prd_ac import check_document

        hidden = "[x](" + "(" * 32 + "<h2>hidden</h2>" + ")" * 32 + ")"
        visible = "[x](" + "(" * 33 + "<h2>visible</h2>" + ")" * 33 + ")"

        hidden_failures, _ = check_document(valid_minimal_prd() + "\n\n" + hidden)
        visible_failures, _ = check_document(valid_minimal_prd() + "\n\n" + visible)

        self.assertEqual(hidden_failures, [])
        self.assertIn("Acceptance Criteria must be the final section", visible_failures)

    def test_caret_reference_definition_title_does_not_create_a_section(self) -> None:
        from scripts.check_prd_ac import check_document

        appendix = '[^ref]: /url\n"<h2>not a heading</h2>"'
        failures, _ = check_document(valid_minimal_prd() + "\n\n" + appendix)

        self.assertEqual(failures, [])

    def test_code_span_backslashes_follow_commonmark_delimiter_rules(self) -> None:
        from scripts.check_prd_ac import check_document

        hidden = "p `<h2>not a heading</h2>\\` z"
        visible = "p `a\\`<h2>Appendix</h2>` z"

        hidden_failures, _ = check_document(valid_minimal_prd() + "\n\n" + hidden)
        visible_failures, _ = check_document(valid_minimal_prd() + "\n\n" + visible)

        self.assertEqual(hidden_failures, [])
        self.assertIn("Acceptance Criteria must be the final section", visible_failures)

    def test_inline_nonsemantic_html_cannot_satisfy_required_content(self) -> None:
        from scripts.check_prd_ac import check_document

        base = valid_minimal_prd()
        for tag in ("script", "style", "template"):
            with self.subTest(tag=tag):
                document = base.replace("## Goal", f"## <{tag}>Goal</{tag}>")
                failures, _ = check_document(document)
                self.assertIn("Missing goal section", failures)

        hidden_requirement = base.replace(
            "The write/read slice is observable",
            "<template>The write/read slice is observable</template>",
        )
        requirement_failures, _ = check_document(hidden_requirement)
        self.assertTrue(any("Empty AC requirement" in failure for failure in requirement_failures), requirement_failures)

        hidden_mapping = base.replace(
            "M1-T01 | M1-DONE-01",
            "M1-T01 | <script>M1-DONE-01</script>",
        )
        mapping_failures, _ = check_document(hidden_mapping)
        self.assertTrue(any("no AC reference" in failure for failure in mapping_failures), mapping_failures)

    def test_invisible_format_characters_cannot_satisfy_required_values(self) -> None:
        from scripts.check_prd_ac import check_document

        m_document = valid_m_tier_prd().replace(
            "AI Readiness: ready",
            "AI Readiness: T\u200bODO",
        )
        m_failures, _ = check_document(m_document)
        self.assertTrue(any("AI Readiness" in failure for failure in m_failures), m_failures)

        declarations = valid_minimal_prd().replace(
            "## Boundary and truth source\n\nTruth source: local file. Boundary: this repository.",
            "## Context\n\nTruth source: \u200b\nBoundary: \u200b",
        )
        declaration_failures, _ = check_document(declarations)
        self.assertIn("Missing truth source", declaration_failures)
        self.assertIn("Missing system boundary", declaration_failures)

        requirement = valid_minimal_prd().replace(
            "The write/read slice is observable",
            "T\u200bODO",
        )
        requirement_failures, _ = check_document(requirement)
        self.assertTrue(any("Placeholder requirement" in failure for failure in requirement_failures), requirement_failures)

    def test_control_characters_cannot_satisfy_required_values(self) -> None:
        from scripts.check_prd_ac import check_document

        base = valid_minimal_prd()
        mutations = (
            ("goal", base.replace("Store one validated item.", "\x08"), "Missing goal section"),
            ("non-goals", base.replace("No synchronization.", "\x1b"), "Missing non-goals section"),
            (
                "declarations",
                base.replace(
                    "Truth source: local file. Boundary: this repository.",
                    "Truth source: \x08\nBoundary: \x1b",
                ),
                "Missing truth source",
            ),
            (
                "task",
                base.replace("M1-T01 | M1-DONE-01", "\x08 | M1-DONE-01"),
                "placeholder task",
            ),
            (
                "forbidden",
                base.replace("Do not claim completion without test evidence", "\x08"),
                "forbidden item",
            ),
            (
                "requirement",
                base.replace("The write/read slice is observable", "\x08"),
                "requirement",
            ),
            (
                "verification",
                base.replace("Run the focused test", "\x1b"),
                "verification method",
            ),
        )
        for label, document, expected in mutations:
            with self.subTest(label=label):
                failures, _ = check_document(document)
                self.assertTrue(any(expected.lower() in failure.lower() for failure in failures), failures)

    def test_goal_and_non_goal_sections_require_visible_content(self) -> None:
        from scripts.check_prd_ac import check_document

        base = valid_minimal_prd()
        mutations = (
            (
                "goal",
                base.replace("## Goal\n\nStore one validated item.\n\n", "## Goal\n\n"),
                "Missing goal section",
            ),
            (
                "non-goals",
                base.replace("## Non-goals\n\nNo synchronization.\n\n", "## Non-goals\n\n"),
                "Missing non-goals section",
            ),
            (
                "placeholder goal",
                base.replace("Store one validated item.", "TODO"),
                "Missing goal section",
            ),
            (
                "goal header only",
                base.replace(
                    "Store one validated item.",
                    "| Goal | Details |\n|---|---|",
                ),
                "Missing goal section",
            ),
            (
                "goal header only without outer pipes",
                base.replace(
                    "Store one validated item.",
                    "Goal | Details\n---|---",
                ),
                "Missing goal section",
            ),
            (
                "non-goals header only",
                base.replace(
                    "No synchronization.",
                    "| Non-goal | Details |\n|---|---|",
                ),
                "Missing non-goals section",
            ),
        )
        for label, document, expected in mutations:
            with self.subTest(label=label):
                failures, _ = check_document(document)
                self.assertIn(expected, failures)

    def test_required_table_content_rejects_non_evidence_sentinels(self) -> None:
        from scripts.check_prd_ac import check_document

        base = valid_minimal_prd()
        mutations = (
            ("forbidden", base.replace("Do not claim completion without test evidence", "-"), "forbidden item"),
            ("requirement", base.replace("The write/read slice is observable", "N/A"), "requirement"),
            ("verification", base.replace("Run the focused test", "?"), "verification method"),
            ("task", base.replace("M1-T01 | M1-DONE-01", "- | M1-DONE-01"), "task"),
        )
        for label, document, expected in mutations:
            with self.subTest(label=label):
                failures, _ = check_document(document)
                self.assertTrue(any(expected in failure.lower() for failure in failures), failures)

    def test_nfkc_equivalent_placeholders_cannot_satisfy_required_content(self) -> None:
        from scripts.check_prd_ac import check_document

        base = valid_minimal_prd()
        mutations = (
            ("goal", base.replace("Store one validated item.", "ＴＯＤＯ"), "Missing goal section"),
            (
                "requirement TODO",
                base.replace("The write/read slice is observable", "ＴＯＤＯ"),
                "requirement",
            ),
            (
                "requirement N/A",
                base.replace("The write/read slice is observable", "Ｎ／Ａ"),
                "requirement",
            ),
            (
                "verification NONE",
                base.replace("Run the focused test", "ＮＯＮＥ"),
                "verification method",
            ),
        )
        for label, document, expected in mutations:
            with self.subTest(label=label):
                failures, _ = check_document(document)
                self.assertTrue(
                    any(expected.lower() in failure.lower() for failure in failures),
                    failures,
                )

    def test_l_tier_requires_a_declared_reports_directory(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_m_tier_prd().replace("Document Tier: M", "Document Tier: L")
        document = document.replace(
            "AI Readiness: ready",
            "Workflow Variant: requirements-first\n"
            "Spec Maintenance Mode: spec-first\n"
            "Execution Mode: batch\n"
            "AI Readiness: ready",
        )
        document = document.replace(
            "## Interface and contract",
            "## Architecture Constitution\n\nRules.\n\n"
            "## Boundary Policy\n\nBoundaries.\n\n"
            "## P0 Foundation\n\nFoundation.\n\n"
            "## Proposal Requirements Design Tasks Implementation\n\nFlow.\n\n"
            "## Stage report format\n\nThe report format is defined.\n\n"
            "## Interface and contract",
        )
        document = document.replace(
            "| M1-DONE-01 | happy | The write/read slice is observable | Run the focused test | FAIL |",
            "| P0-DONE | happy | Foundation is accepted | Run the foundation test | FAIL |\n"
            "| M1-DONE-01 | happy | The write/read slice is observable | Run the focused test | FAIL |",
        )

        failures, _ = check_document(document)
        self.assertIn("L tier requires stage report format and reports directory", failures)

        declared = document.replace(
            "The report format is defined.",
            "The report format is written to reports/.",
        )
        declared_failures, _ = check_document(declared)
        self.assertNotIn("L tier requires stage report format and reports directory", declared_failures)

    def test_l_tier_accepts_reports_path_in_inline_code(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_m_tier_prd().replace("Document Tier: M", "Document Tier: L")
        document = document.replace(
            "AI Readiness: ready",
            "Workflow Variant: requirements-first\n"
            "Spec Maintenance Mode: spec-first\n"
            "Execution Mode: batch\n"
            "AI Readiness: ready",
        )
        document = document.replace(
            "## Interface and contract",
            "## Architecture Constitution\n\nRules.\n\n"
            "## Boundary Policy\n\nBoundaries.\n\n"
            "## P0 Foundation\n\nFoundation.\n\n"
            "## Proposal Requirements Design Tasks Implementation\n\nFlow.\n\n"
            "## Stage report format\n\nThe report format is written to `reports/M1.md`.\n\n"
            "## Interface and contract",
        )
        document = document.replace(
            "| M1-DONE-01 | happy | The write/read slice is observable | Run the focused test | FAIL |",
            "| P0-DONE | happy | Foundation is accepted | Run the foundation test | FAIL |\n"
            "| M1-DONE-01 | happy | The write/read slice is observable | Run the focused test | FAIL |",
        )

        failures, _ = check_document(document)

        self.assertNotIn("L tier requires stage report format and reports directory", failures)

    def test_fence_closer_must_match_marker_and_opening_length(self) -> None:
        from scripts.check_prd_ac import check_document, mask_fenced_lines

        lines = mask_fenced_lines("````text\ninside\n```\nstill inside\n````\noutside")
        self.assertEqual(lines, ["", "", "", "", "", "outside"])

        hidden = "````text\n    ````\n" + valid_minimal_prd() + "\n````"
        failures, _ = check_document(hidden)
        self.assertIn("Missing goal section", failures)

    def test_level_three_milestone_heading_requires_done_ac(self) -> None:
        from scripts.check_prd_ac import check_document

        document = valid_minimal_prd(milestone_heading="### M1 Work", done_id="P0-DONE")
        failures, _ = check_document(document)
        self.assertTrue(any("Missing DONE AC for milestone M1" in failure for failure in failures), failures)


if __name__ == "__main__":
    unittest.main()
