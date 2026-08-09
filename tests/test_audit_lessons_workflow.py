from __future__ import annotations

import unittest
from pathlib import Path
import re


ROOT = Path(__file__).parents[1]


class AuditLessonsWorkflowTests(unittest.TestCase):
    def test_skill_preserves_mainline_authoring_contracts(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for heading in (
            "## Terminology",
            "## Document Tiers",
            "## Required Shape",
            "## Style Rules & Common Mistakes",
        ):
            self.assertIn(heading, text)
        self.assertLess(text.index("## Document Tiers"), text.index("## Required Shape"))
        self.assertLessEqual(len(text.splitlines()), 340)
        self.assertNotRegex(text, r"第\s*12\s*章|§12(?:\.|\b)")
        for reference in ("§AC.0", "§AC.P0", "§AC.M1"):
            self.assertIn(reference, text)
        canonical_rows = re.findall(
            r"(?m)^\|\s*(G-0[1-8])\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*FAIL\s*\|$",
            text,
        )
        self.assertEqual([row[0] for row in canonical_rows], [f"G-{number:02d}" for number in range(1, 9)])

    def test_prd_template_preserves_mainline_tier_and_stable_ac_contracts(self) -> None:
        text = (ROOT / "references/prd_template.md").read_text(encoding="utf-8")
        self.assertIn("L-tier full template", text)
        self.assertIn("Document Tier: L", text)
        self.assertIn("After an optional section number,", text)
        self.assertNotRegex(text, r"第\s*12\s*章|§12(?:\.|\b)")
        for reference in ("§AC.0", "§AC.P0", "§AC.M1"):
            self.assertIn(reference, text)
        canonical_rows = re.findall(
            r"(?m)^\|\s*(G-0[1-8])\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*FAIL\s*\|$",
            text,
        )
        self.assertEqual([row[0] for row in canonical_rows], [f"G-{number:02d}" for number in range(1, 9)])

    def test_skill_mentions_audit_hardening_rules(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "NULL semantics",
            "PRAGMA foreign_key_check",
            "strategy parameters",
            "degraded-with-warning",
            "data-corrupted",
            "premise verification",
            "audit coverage",
            "owner task",
        ):
            self.assertIn(phrase, text)

    def test_templates_expose_audit_hardening_fields(self) -> None:
        for name in ("references/change_packet_template.md", "references/prd_template.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for phrase in (
                "NULL semantics",
                "PRAGMA foreign_key_check",
                "strategy parameters",
                "degraded-with-warning",
                "data-corrupted",
                "premise verification",
                "audit coverage",
                "owner task",
            ):
                self.assertIn(phrase, text)

    def test_skill_and_templates_expose_test_chain_gate(self) -> None:
        for name in ("SKILL.md", "references/change_packet_template.md", "references/prd_template.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            for phrase in (
                "Test Chain Gate",
                "L0",
                "L1",
                "runtime evidence",
                "producer",
                "consumer",
                "error path",
            ):
                self.assertIn(phrase, text)

    def test_skill_and_templates_expose_graph_semantic_integrity_rules(self) -> None:
        for name in ("SKILL.md", "references/change_packet_template.md", "references/prd_template.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            normalized = " ".join(text.split())
            for phrase in (
                "current collections must not retain `removed`",
                "`diff.removed_*` IDs must be absent from the current graph",
                "matching diff list",
                "meaningful `reason` and `next_query`",
                "repository-relative paths",
                "outgoing `validates` edge",
                "`edge_refs` endpoints must stay inside the chain's declared",
                "entrypoint must reach every producer, contract, and consumer role",
            ):
                self.assertIn(phrase, normalized, f"{name} is missing {phrase!r}")

    def test_skill_and_templates_expose_new_evidence_integrity_contracts(self) -> None:
        for name in ("SKILL.md", "references/change_packet_template.md", "references/prd_template.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            normalized = " ".join(text.split())
            for phrase in (
                "canonical identifiers",
                "leading or trailing whitespace",
                "downstream `requirement_refs` and Test Chain `ac_refs`",
                "declared by `source_coverage`",
                "observed`, `changed`, `implemented`, or `verified",
                "non-empty `verification_evidence`",
                "both endpoints in `target_node_refs`",
                "`foreign_key_check_result`",
                "`duplicate_query_result`",
            ):
                self.assertIn(phrase, normalized, f"{name} is missing {phrase!r}")

    def test_skill_and_templates_expose_current_graph_provider_and_role_closure(self) -> None:
        for name in ("SKILL.md", "references/change_packet_template.md", "references/prd_template.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            normalized = " ".join(text.split())
            for phrase in (
                "provider capabilities and limitations",
                "Observed and Change Graph current collections must not use `planned`",
                "factual test chain",
                "mixed evidence requires both static and runtime evidence",
                "state and enum producers must be contract writers",
                "state and enum consumers must be contract readers",
            ):
                self.assertIn(phrase, normalized, f"{name} is missing {phrase!r}")


if __name__ == "__main__":
    unittest.main()
