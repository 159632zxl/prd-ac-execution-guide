from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "SKILL.md"
TEMPLATE = REPO_ROOT / "references" / "prd_template.md"
EXAMPLE = REPO_ROOT / "references" / "example_prd_filled.md"
README = REPO_ROOT / "README.md"

READINESS_FIELDS = (
    "AI Readiness",
    "No new design decisions required",
    "Known files / directories",
    "Expected outputs",
    "Validation commands",
    "Blocking ambiguities",
    "Human confirmation",
    "High-risk confirmation",
    "Validation evidence",
)

READINESS_CHECKS = (
    "Goal",
    "Non-goals",
    "Truth source",
    "Boundaries",
    "Files",
    "Contracts",
    "Existing reuse targets",
    "Confirmation gates",
    "Tasks",
    "Tests",
    "Expected result",
    "Design load",
)

CANONICAL_GLOBAL_RULES = (
    ("G-01", "禁止绕过事实真源", "Do not bypass the truth source."),
    ("G-02", "禁止无证据更新长期状态", "Do not update persistent state without evidence."),
    ("G-03", "禁止先做增强层再补核心闭环", "Do not build enhancements before completing the core loop."),
    ("G-04", "禁止覆盖用户已有文件且无说明", "Do not overwrite existing user files without explicit disclosure."),
    ("G-05", "禁止未查询即猜测接口、路径、schema 或命令", "Do not guess interfaces, paths, schemas, or commands without checking."),
    ("G-06", "禁止未确认即臆想业务规则或用户意图", "Do not invent business rules or user intent without confirmation."),
    ("G-07", "禁止未获批准进行 scope expansion 或高风险操作", "Do not expand scope or perform high-risk operations without approval."),
    ("G-08", "禁止无 Validation evidence 宣称完成", "Do not claim completion without validation evidence."),
)


def section(text: str, heading: str) -> str:
    match = re.search(
        rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)",
        text,
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError(f"Missing section: {heading}")
    return match.group(1)


def canonical_global_rules(text: str) -> tuple[tuple[str, str, str], ...]:
    rows = re.findall(
        r"(?m)^\|\s*(G-0[1-8])\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*FAIL\s*\|$",
        text,
    )
    return tuple((ac_id, chinese, english) for ac_id, chinese, english in rows)


class SkillDocumentContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_overview_selects_a_tier_before_writing(self) -> None:
        overview = section(self.text, "Overview")

        self.assertIn("Document Tiers", overview)
        self.assertRegex(overview, r"定级|select.*tier")

    def test_terminology_locks_four_bilingual_terms(self) -> None:
        terminology = section(self.text, "Terminology")

        for term in ("Validation evidence", "handoff", "readiness gate", "truth source"):
            with self.subTest(term=term):
                self.assertIn(term, terminology)

    def test_document_tiers_precede_required_shape(self) -> None:
        tiers_index = self.text.index("## Document Tiers")
        shape_index = self.text.index("## Required Shape")

        self.assertLess(tiers_index, shape_index)
        tiers = section(self.text, "Document Tiers")
        for tier in ("S", "M", "L"):
            with self.subTest(tier=tier):
                self.assertRegex(tiers, rf"(?m)^\| {tier} \|")
        self.assertIn("risk", tiers.lower())
        self.assertIn("Document Tier: S | M | L", self.text)

    def test_ac_references_do_not_depend_on_chapter_number(self) -> None:
        self.assertNotRegex(self.text, r"第\s*12\s*章|§12(?:\.|\b)")
        for reference in ("§AC.0", "§AC.P0", "§AC.M1"):
            with self.subTest(reference=reference):
                self.assertIn(reference, self.text)

    def test_acceptance_heading_documents_number_and_parenthesis_compatibility(self) -> None:
        acceptance_rules = section(self.text, "Acceptance Criteria Rules")

        for concept in (
            "optional section number",
            "full-width or ASCII parentheses",
            "English equivalent",
        ):
            with self.subTest(concept=concept):
                self.assertIn(concept, acceptance_rules)

    def test_executor_statement_has_five_process_rules(self) -> None:
        executor = section(self.text, "AI Executor Statement")
        numbered_rules = re.findall(r"(?m)^\d+\. ", executor)

        self.assertEqual(5, len(numbered_rules))
        self.assertIn("G-*", executor)
        self.assertIn("AC编号 | PASS/FAIL/WARN | 说明", executor)
        self.assertIn("honest blocking", executor)

    def test_attitude_is_single_source_for_checkable_forbidden_items(self) -> None:
        self.assertEqual(1, self.text.count("## Execution Attitude"))
        global_items = section(self.text, "Global Forbidden Items")

        self.assertRegex(global_items, r"Execution Attitude.*可检查|checkable.*Execution Attitude")
        boundary = section(self.text, "Boundary Policy")
        self.assertRegex(boundary, r"Never.*G-\*")

    def test_style_guidance_is_merged_without_losing_subsections(self) -> None:
        self.assertIn("## Style Rules & Common Mistakes", self.text)
        self.assertNotRegex(self.text, r"(?m)^## (?:Style Rules|Common Mistakes)$")
        merged = section(self.text, "Style Rules & Common Mistakes")

        self.assertIn("### Style Rules", merged)
        self.assertIn("### Common Mistakes", merged)
        self.assertIn("executable", merged)

    def test_resources_include_filled_example(self) -> None:
        resources = section(self.text, "Resources")

        self.assertIn("references/prd_template.md", resources)
        self.assertIn("references/example_prd_filled.md", resources)
        self.assertIn("scripts/check_prd_ac.py", resources)

    def test_skill_is_compact_enough_to_scan(self) -> None:
        self.assertLessEqual(len(self.text.splitlines()), 340)


class ReferenceDocumentContractTests(unittest.TestCase):
    def test_canonical_global_rules_align_across_documents(self) -> None:
        documents = {
            "skill": SKILL.read_text(encoding="utf-8"),
            "template": TEMPLATE.read_text(encoding="utf-8"),
            "example": EXAMPLE.read_text(encoding="utf-8"),
        }

        for name, text in documents.items():
            with self.subTest(document=name):
                self.assertEqual(CANONICAL_GLOBAL_RULES, canonical_global_rules(text))

    def test_template_is_l_tier_and_uses_stable_ac_references(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("L-tier full template", text)
        self.assertIn("Document Tier: L", text)
        self.assertNotRegex(text, r"第\s*12\s*章|§12(?:\.|\b)")
        for reference in ("§AC.0", "§AC.P0", "§AC.M1"):
            with self.subTest(reference=reference):
                self.assertIn(reference, text)

        level_two_headings = re.findall(r"(?m)^##(?!#)\s+(.+?)\s*$", text)
        self.assertIn("Acceptance Criteria", level_two_headings[-1])

    def test_filled_example_covers_m_tier_execution_flow(self) -> None:
        self.assertTrue(EXAMPLE.is_file(), "Missing filled example")
        text = EXAMPLE.read_text(encoding="utf-8")

        self.assertIn("示例：M 级项目", text)
        self.assertIn("Document Tier: M", text)

        for field in (
            "AI Readiness: ready",
            "No new design decisions required: yes",
            "Spec status: approved",
            "Implementation allowed: yes",
            "Approved by:",
            "Approval date:",
        ):
            with self.subTest(field=field):
                self.assertIn(field, text)

        for milestone in ("P0", "M1", "M2"):
            with self.subTest(milestone=milestone):
                self.assertRegex(text, rf"(?m)^## .*\b{milestone}\b")
                self.assertRegex(text, rf"(?m)^\| {milestone}-DONE(?:-\d+)? \|")

        for category in (
            "happy",
            "edge",
            "error",
            "non-functional",
            "data-integrity",
            "safety",
        ):
            with self.subTest(category=category):
                self.assertRegex(text, rf"(?m)^\| [^|]+ \| {re.escape(category)} \|")

        self.assertIn("Task -> AC", text)
        self.assertIn("阶段报告", text)
        self.assertIn("handoff", text.lower())

    def test_readiness_fields_and_checks_are_aligned(self) -> None:
        documents = {
            "skill": section(SKILL.read_text(encoding="utf-8"), "AI Readiness Gate"),
            "template": section(
                TEMPLATE.read_text(encoding="utf-8"),
                "0.1 AI Readiness Gate",
            ),
            "example": section(
                EXAMPLE.read_text(encoding="utf-8"),
                "0 AI Readiness 与 Approval Gate",
            ),
        }

        for name, text in documents.items():
            with self.subTest(document=name, contract="fields"):
                last_position = -1
                for field in READINESS_FIELDS:
                    position = text.find(f"{field}:")
                    self.assertGreater(position, last_position, field)
                    last_position = position

            with self.subTest(document=name, contract="checks"):
                last_position = -1
                for check in READINESS_CHECKS:
                    match = re.search(rf"(?m)^\| {re.escape(check)} \|", text)
                    self.assertIsNotNone(match, check)
                    position = match.start()
                    self.assertGreater(position, last_position, check)
                    last_position = position

    def test_filled_example_defines_list_output_and_safe_smoke_contract(self) -> None:
        text = EXAMPLE.read_text(encoding="utf-8")

        for contract in (
            "DATE | CATEGORY | AMOUNT (CNY) | NOTE",
            "-----|----------|--------------|-----",
            "12.34 CNY",
            "整数分除以 100",
            "固定两位小数",
            "tempfile.TemporaryDirectory()",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, text)
        self.assertRegex(text, r"(?i)finally")
        self.assertNotIn("python ledger.py list --file data/ledger.jsonl", text)


class ReadmeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = README.read_text(encoding="utf-8")

    def test_readme_lists_template_example_and_checker(self) -> None:
        for path in (
            "references/prd_template.md",
            "references/example_prd_filled.md",
            "scripts/check_prd_ac.py",
        ):
            with self.subTest(path=path):
                self.assertIn(path, self.text)

    def test_readme_explains_document_tiers(self) -> None:
        self.assertIn("Document Tiers", self.text)
        for tier in ("S", "M", "L"):
            with self.subTest(tier=tier):
                self.assertRegex(self.text, rf"`{tier}`")

    def test_readme_uses_final_chapter_instead_of_chapter_number(self) -> None:
        self.assertNotRegex(self.text, r"第\s*12\s*章|§12(?:\.|\b)|→\s*12\.")
        self.assertRegex(self.text, r"final chapter|最后一章")

    def test_readme_describes_new_checker_guards(self) -> None:
        for concept in ("verification method", "Task", "DONE", "G-*", "placeholder"):
            with self.subTest(concept=concept):
                self.assertIn(concept, self.text)

    def test_readme_defines_checker_review_boundary(self) -> None:
        for concept in (
            "structural completeness",
            "cross-reference integrity",
            "gate relationships",
            "does not replace human review",
            "AC semantics",
            "business correctness",
            "risk decisions",
        ):
            with self.subTest(concept=concept):
                self.assertIn(concept, self.text)

    def test_readme_documents_canonical_global_id_migration(self) -> None:
        for concept in (
            "Breaking change",
            "G-01` through `G-08",
            "G-09",
            "Task -> AC",
            "documents without `Document Tier`",
        ):
            with self.subTest(concept=concept):
                self.assertIn(concept, self.text)

    def test_readme_documents_template_failure_and_heading_compatibility(self) -> None:
        for concept in (
            "blank L-tier template",
            "expected to fail",
            "optional section number",
            "full-width or ASCII parentheses",
        ):
            with self.subTest(concept=concept):
                self.assertIn(concept, self.text)


if __name__ == "__main__":
    unittest.main()
