from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class AuditLessonsWorkflowTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
