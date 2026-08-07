from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.check_graph_evidence import main, validate_document


def valid_snapshot(graph_type: str = "observed") -> dict:
    return {
        "schema_version": "1.0",
        "artifact_type": "graph_diff" if graph_type == "change" else "graph_snapshot",
        "graph_type": graph_type,
        "repository": {"root": ".", "git_sha": "a" * 40},
        "provider": {
            "name": "code-review-graph",
            "version": "1.0.0",
            "command": "code-review-graph index .",
            "generated_at": "2026-08-07T12:00:00Z",
        },
        "coverage": {
            "scope": "repository",
            "status": "complete",
            "paths": ["src"],
            "excluded_paths": [],
        },
        "source_coverage": [
            {
                "source_section_id": "DESIGN-01",
                "status": "covered",
                "requirement_refs": ["REQ-01"],
                "ac_refs": ["M1-DONE-01"],
            }
        ],
        "nodes": [
            {
                "node_id": "fn:src/writer.py:write_item",
                "kind": "function",
                "status": "observed" if graph_type == "observed" else "planned",
                "path": "src/writer.py",
                "qualified_symbol": "write_item",
                "source_anchor": {"path": "src/writer.py", "start_line": 1, "end_line": 5}
                if graph_type == "observed"
                else None,
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "confidence": 1.0,
                "coverage": "complete",
                "freshness": "current",
                "verification_evidence": ["graph query: fn:src/writer.py:write_item"],
                "requirement_refs": ["REQ-01"] if graph_type == "target" else [],
            },
            {
                "node_id": "table:items",
                "kind": "table",
                "status": "observed" if graph_type == "observed" else "planned",
                "path": "db/schema.sql",
                "qualified_symbol": "items",
                "source_anchor": {"path": "db/schema.sql", "start_line": 1, "end_line": 4}
                if graph_type == "observed"
                else None,
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "confidence": 1.0,
                "coverage": "complete",
                "freshness": "current",
                "verification_evidence": ["schema query: items"],
                "requirement_refs": ["REQ-01"] if graph_type == "target" else [],
            },
            {
                "node_id": "fn:src/reader.py:read_items",
                "kind": "function",
                "status": "observed" if graph_type == "observed" else "planned",
                "path": "src/reader.py",
                "qualified_symbol": "read_items",
                "source_anchor": {"path": "src/reader.py", "start_line": 1, "end_line": 5}
                if graph_type == "observed"
                else None,
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "confidence": 1.0,
                "coverage": "complete",
                "freshness": "current",
                "verification_evidence": ["graph query: fn:src/reader.py:read_items"],
                "requirement_refs": ["REQ-01"] if graph_type == "target" else [],
            },
        ],
        "edges": [
            {
                "edge_id": "writes:fn:src/writer.py:write_item->table:items",
                "kind": "writes",
                "from": "fn:src/writer.py:write_item",
                "to": "table:items",
                "status": "observed" if graph_type == "observed" else "planned",
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "source_anchor": {"path": "src/writer.py", "start_line": 3, "end_line": 3}
                if graph_type == "observed"
                else None,
                "confidence": 1.0,
                "coverage": "complete",
                "freshness": "current",
                "verification_evidence": ["runtime insert count > 0"],
                "requirement_refs": ["REQ-01"] if graph_type == "target" else [],
            },
            {
                "edge_id": "reads:table:items->fn:src/reader.py:read_items",
                "kind": "reads",
                "from": "table:items",
                "to": "fn:src/reader.py:read_items",
                "status": "observed" if graph_type == "observed" else "planned",
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "source_anchor": {"path": "src/reader.py", "start_line": 3, "end_line": 3}
                if graph_type == "observed"
                else None,
                "confidence": 1.0,
                "coverage": "complete",
                "freshness": "current",
                "verification_evidence": ["reader visibility query returns item"],
                "requirement_refs": ["REQ-01"] if graph_type == "target" else [],
            },
        ],
        "contracts": [
            {
                "contract_id": "items-write-read",
                "storage_node_id": "table:items",
                "writers": ["fn:src/writer.py:write_item"],
                "readers": ["fn:src/reader.py:read_items"],
                "state_values": ["active", "archived"],
                "state_semantics": {"active": "available for normal retrieval", "archived": "retained historical record"},
                "state_producers": {"active": ["fn:src/writer.py:write_item"], "archived": ["fn:src/writer.py:write_item"]},
                "state_consumers": {"active": ["fn:src/reader.py:read_items"], "archived": ["fn:src/reader.py:read_items"]},
                "enum_values": ["active", "archived"],
                "schema_enum_values": ["active", "archived"],
                "expected_runtime_state": "non-empty",
                "runtime_evidence": ["SELECT COUNT(*) FROM items > 0", "reader query returns item"],
                "status": "verified" if graph_type == "observed" else "planned",
                "verification_evidence": ["insert and reader visibility checks"],
            }
        ],
    }


class GraphEvidenceTests(unittest.TestCase):
    def test_valid_observed_snapshot_passes(self) -> None:
        self.assertEqual(validate_document(valid_snapshot()), [])

    def test_valid_target_snapshot_passes(self) -> None:
        self.assertEqual(validate_document(valid_snapshot("target")), [])

    def test_map_only_accepts_observed_snapshot(self) -> None:
        self.assertEqual(validate_document(valid_snapshot(), map_only=True), [])

    def test_map_only_rejects_target_graph(self) -> None:
        errors = validate_document(valid_snapshot("target"), map_only=True)
        self.assertTrue(any("map-only" in error for error in errors))

    def test_map_only_rejects_implementation_status(self) -> None:
        document = valid_snapshot()
        document["nodes"][0]["status"] = "implemented"
        errors = validate_document(document, map_only=True)
        self.assertTrue(any("status" in error for error in errors))

    def test_map_only_rejects_planned_contract(self) -> None:
        document = valid_snapshot()
        document["contracts"][0]["status"] = "planned"
        errors = validate_document(document, map_only=True)
        self.assertTrue(any("map-only status" in error for error in errors))

    def test_target_snapshot_requires_requirement_refs(self) -> None:
        document = valid_snapshot("target")
        document["nodes"][0]["requirement_refs"] = []
        errors = validate_document(document)
        self.assertTrue(any("requirement_refs" in error for error in errors))

    def test_covered_source_section_requires_ac_refs(self) -> None:
        document = valid_snapshot()
        document["source_coverage"][0]["ac_refs"] = []
        errors = validate_document(document)
        self.assertTrue(any("covered requires ac_refs" in error for error in errors))

    def test_unknown_edge_endpoint_fails(self) -> None:
        document = valid_snapshot()
        document["edges"][0]["to"] = "table:missing"
        errors = validate_document(document)
        self.assertTrue(any("endpoint" in error for error in errors))

    def test_verified_without_evidence_fails(self) -> None:
        document = valid_snapshot()
        document["nodes"][0]["status"] = "verified"
        document["nodes"][0]["verification_evidence"] = []
        errors = validate_document(document)
        self.assertTrue(any("verification_evidence" in error for error in errors))

    def test_reader_without_writer_fails(self) -> None:
        document = valid_snapshot()
        document["contracts"][0]["writers"] = []
        errors = validate_document(document)
        self.assertTrue(any("writer" in error for error in errors))

    def test_enum_mismatch_fails(self) -> None:
        document = valid_snapshot()
        document["contracts"][0]["schema_enum_values"] = ["active"]
        errors = validate_document(document)
        self.assertTrue(any("enum" in error for error in errors))

    def test_state_requires_semantics_and_producer(self) -> None:
        document = valid_snapshot()
        document["contracts"][0]["state_semantics"].pop("active")
        errors = validate_document(document)
        self.assertTrue(any("semantic description" in error for error in errors))

    def test_verified_review_finding_requires_independent_evidence(self) -> None:
        document = valid_snapshot()
        document["review_findings"] = [
            {
                "finding_id": "F-01",
                "status": "verified",
                "evidence": ["reviewer report"],
            }
        ]
        errors = validate_document(document)
        self.assertTrue(any("independent_verification" in error for error in errors))

    def test_intentionally_empty_requires_reason_and_milestone(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["expected_runtime_state"] = "intentionally empty"
        errors = validate_document(document)
        self.assertTrue(any("intentionally empty" in error for error in errors))
        contract["intentional_empty_reason"] = "writer lands in M2"
        contract["intentional_empty_milestone"] = "M2"
        self.assertEqual(validate_document(document), [])

    def test_change_graph_requires_baseline_and_current_sha(self) -> None:
        document = valid_snapshot("change")
        errors = validate_document(document)
        self.assertTrue(any("baseline_sha" in error for error in errors))
        document["baseline_sha"] = "b" * 40
        document["current_sha"] = "a" * 40
        document["diff"] = {
            "added_nodes": [],
            "removed_nodes": [],
            "changed_nodes": ["fn:src/writer.py:write_item"],
            "added_edges": [],
            "removed_edges": [],
            "changed_edges": [],
            "unresolved": [],
            "impact": ["fn:src/reader.py:read_items"],
            "verification_evidence": ["diff impact query"],
        }
        self.assertEqual(validate_document(document), [])

    def test_change_graph_requires_diff_sets(self) -> None:
        document = valid_snapshot("change")
        document["baseline_sha"] = "b" * 40
        document["current_sha"] = "a" * 40
        errors = validate_document(document)
        self.assertTrue(any("diff object" in error for error in errors))

    def test_cli_reads_json_and_returns_nonzero_for_invalid_document(self) -> None:
        document = valid_snapshot()
        document["edges"][0]["from"] = "fn:missing"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                result = main([str(path)])
            self.assertEqual(result, 1)
            self.assertIn("FAIL", output.getvalue())

    def test_cli_map_only_accepts_observed_snapshot(self) -> None:
        document = valid_snapshot()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "observed.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                result = main(["--map-only", str(path)])
            self.assertEqual(result, 0)
            self.assertIn("PASS", output.getvalue())

    def test_dynamic_edge_must_remain_unresolved(self) -> None:
        document = valid_snapshot()
        document["edges"][0]["kind"] = "dynamic"
        document["edges"][0]["status"] = "observed"
        errors = validate_document(document)
        self.assertTrue(any("dynamic edge" in error for error in errors))

    def test_orphan_node_fails_without_entrypoint_or_test(self) -> None:
        document = valid_snapshot()
        document["nodes"].append(
            {
                "node_id": "fn:src/orphan.py:unused",
                "kind": "function",
                "status": "observed",
                "path": "src/orphan.py",
                "qualified_symbol": "unused",
                "source_anchor": {"path": "src/orphan.py", "start_line": 1, "end_line": 1},
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "confidence": 1.0,
                "coverage": "complete",
                "freshness": "current",
                "verification_evidence": ["graph query"],
                "requirement_refs": [],
            }
        )
        errors = validate_document(document)
        self.assertTrue(any("orphan node" in error for error in errors))

    def test_schema_file_is_valid_json(self) -> None:
        schema_path = Path(__file__).parents[1] / "references" / "graph-evidence.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
