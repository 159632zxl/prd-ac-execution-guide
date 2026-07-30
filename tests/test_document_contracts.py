from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "SKILL.md"


def section(text: str, heading: str) -> str:
    match = re.search(
        rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)",
        text,
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError(f"Missing section: {heading}")
    return match.group(1)


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


if __name__ == "__main__":
    unittest.main()
