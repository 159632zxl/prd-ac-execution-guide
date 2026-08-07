from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class CodeMapWorkflowTests(unittest.TestCase):
    def test_skill_declares_standalone_code_map_workflow(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "Code Map Only Workflow",
            "Map Completeness Gate",
            "Implementation allowed: no",
            "No source modifications",
            "code-map-only",
            "observed-only",
        ):
            self.assertIn(phrase, text)

    def test_templates_declare_code_map_only_outputs(self) -> None:
        for name in ("references/change_packet_template.md", "references/prd_template.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("Code Map Only", text)
            self.assertIn("Map Completeness Gate", text)
            self.assertIn("No source modifications", text)
            self.assertIn("graph-snapshot.json", text)


if __name__ == "__main__":
    unittest.main()
