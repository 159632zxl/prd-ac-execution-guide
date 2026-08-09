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
