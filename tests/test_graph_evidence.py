from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.check_graph_evidence import _reject_duplicate_pairs, main, validate_document


def _add_test_network(document: dict) -> None:
    """Attach a minimal happy/error test network to the fixture graph."""

    graph_type = document["graph_type"]
    status = "planned" if graph_type == "target" else "observed"
    source_anchor = None if graph_type == "target" else {"path": "tests/test_items.py", "start_line": 1, "end_line": 5}
    test_nodes = [
        ("test:tests/test_items.py:test_write_read_chain", "test_write_read_chain"),
        ("test:tests/test_items.py:test_write_error", "test_write_error"),
    ]
    for node_id, symbol in test_nodes:
        document["nodes"].append(
            {
                "node_id": node_id,
                "kind": "test",
                "status": status,
                "path": "tests/test_items.py",
                "qualified_symbol": symbol,
                "source_anchor": source_anchor,
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "confidence": 1.0,
                "coverage": "complete",
                "freshness": "current",
                "verification_evidence": ["test index query"] if graph_type != "target" else [],
                "requirement_refs": ["REQ-01"] if graph_type == "target" else [],
                "entrypoint": True,
            }
        )

    code_nodes = [node["node_id"] for node in document["nodes"][:3]]
    for node in document["nodes"][:3]:
        node["test_refs"] = [test_nodes[0][0], test_nodes[1][0]]
    edge_specs = [
        ("validates:test:happy->fn:writer", test_nodes[0][0], code_nodes[0]),
        ("validates:test:happy->table:items", test_nodes[0][0], code_nodes[1]),
        ("validates:test:happy->fn:reader", test_nodes[0][0], code_nodes[2]),
        ("validates:test:error->fn:writer", test_nodes[1][0], code_nodes[0]),
    ]
    for edge_id, from_node, to_node in edge_specs:
        document["edges"].append(
            {
                "edge_id": edge_id,
                "kind": "validates",
                "from": from_node,
                "to": to_node,
                "status": status,
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "source_anchor": source_anchor,
                "confidence": 1.0,
                "coverage": "complete",
                "freshness": "current",
                "verification_evidence": ["test execution"] if graph_type != "target" else [],
                "requirement_refs": ["REQ-01"] if graph_type == "target" else [],
            }
        )
    document["test_chains"] = [
        {
            "chain_id": "TC-L1-items-write-read",
            "level": "L1",
            "status": "verified" if graph_type == "observed" else status,
            "entrypoint_node_id": test_nodes[0][0],
            "test_node_refs": [test_nodes[0][0], test_nodes[1][0]],
            "node_refs": code_nodes,
            "edge_refs": [
                "writes:fn:src/writer.py:write_item->table:items",
                "reads:table:items->fn:src/reader.py:read_items",
                "validates:test:happy->fn:writer",
                "validates:test:happy->table:items",
                "validates:test:happy->fn:reader",
                "validates:test:error->fn:writer",
            ],
            "requirement_refs": ["REQ-01"],
            "ac_refs": ["M1-DONE-01"],
            "required_roles": {
                "producer": [code_nodes[0]],
                "contract": [code_nodes[1]],
                "consumer": [code_nodes[2]],
                "error_path": [test_nodes[1][0]],
            },
            "error_path_refs": [test_nodes[1][0]],
            "expected_output": "reader returns the item written by the producer",
            "command": "python -m pytest tests/test_items.py -k write_read_chain",
            "evidence_kind": "runtime" if graph_type == "observed" else "static",
            "static_evidence": ["graph query links the test to producer, contract, and consumer"],
            "runtime_evidence": ["test report is green", "reader query returns the written item"] if graph_type == "observed" else [],
            "verification_evidence": ["happy path and error path test evidence"] if graph_type != "target" else [],
            "uncovered_edge_refs": [],
            "test_scope": "targeted",
        },
        {
            "chain_id": "TC-L0-items-graph",
            "level": "L0",
            "status": "verified" if graph_type == "observed" else status,
            "entrypoint_node_id": test_nodes[0][0],
            "test_node_refs": [test_nodes[0][0]],
            "node_refs": code_nodes,
            "edge_refs": [
                "writes:fn:src/writer.py:write_item->table:items",
                "reads:table:items->fn:src/reader.py:read_items",
                "validates:test:happy->fn:writer",
                "validates:test:happy->table:items",
                "validates:test:happy->fn:reader",
            ],
            "requirement_refs": ["REQ-01"],
            "ac_refs": ["M1-DONE-01"],
            "required_roles": {
                "producer": [code_nodes[0]],
                "contract": [code_nodes[1]],
                "consumer": [code_nodes[2]],
                "error_path": [],
            },
            "error_path_refs": [],
            "expected_output": "graph resolves the minimum write-read topology",
            "command": "python scripts/check_graph_evidence.py graph-snapshot.json",
            "evidence_kind": "static",
            "static_evidence": ["node and edge endpoint query"],
            "runtime_evidence": [],
            "verification_evidence": ["static graph gate"] if graph_type != "target" else [],
            "uncovered_edge_refs": [],
            "test_scope": "targeted",
        }
    ]


def valid_snapshot(graph_type: str = "observed") -> dict:
    document = {
        "schema_version": "1.1",
        "artifact_type": "graph_diff" if graph_type == "change" else "graph_snapshot",
        "graph_type": graph_type,
        "repository": {"root": ".", "git_sha": "a" * 40},
        "provider": {
            "name": "code-review-graph",
            "version": "1.0.0",
            "command": "code-review-graph index .",
            "generated_at": "2026-08-07T12:00:00Z",
            "capabilities": ["definitions and relationship extraction"],
            "limitations": [],
        },
        "coverage": {
            "scope": "repository",
            "status": "complete",
            "paths": ["src", "db", "tests", "design.md"],
            "excluded_paths": [],
        },
        "source_coverage": [
            {
                "source_section_id": "DESIGN-01",
                "status": "covered",
                "requirement_refs": ["REQ-01"],
                "ears_refs": ["EARS-01"],
                "target_node_refs": ["fn:src/writer.py:write_item", "table:items", "fn:src/reader.py:read_items"],
                "target_edge_refs": ["writes:fn:src/writer.py:write_item->table:items", "reads:table:items->fn:src/reader.py:read_items"],
                "ac_refs": ["M1-DONE-01"],
                "owner_task": "M1-T01",
                "source_anchor": {"path": "design.md", "start_line": 10, "end_line": 12},
            }
        ],
        "audit_coverage": {
            "status": "complete",
            "reviewers": ["independent-auditor"],
            "independent_verification": ["repository query and runtime check"],
            "limitations": [],
        },
        "nodes": [
            {
                "node_id": "fn:src/writer.py:write_item",
                "kind": "function",
                "status": "planned" if graph_type == "target" else "observed",
                "path": "src/writer.py",
                "qualified_symbol": "write_item",
                "source_anchor": {"path": "src/writer.py", "start_line": 1, "end_line": 5}
                if graph_type != "target"
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
                "status": "planned" if graph_type == "target" else "observed",
                "path": "db/schema.sql",
                "qualified_symbol": "items",
                "source_anchor": {"path": "db/schema.sql", "start_line": 1, "end_line": 4}
                if graph_type != "target"
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
                "status": "planned" if graph_type == "target" else "observed",
                "path": "src/reader.py",
                "qualified_symbol": "read_items",
                "source_anchor": {"path": "src/reader.py", "start_line": 1, "end_line": 5}
                if graph_type != "target"
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
                "status": "planned" if graph_type == "target" else "observed",
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "source_anchor": {"path": "src/writer.py", "start_line": 3, "end_line": 3}
                if graph_type != "target"
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
                "status": "planned" if graph_type == "target" else "observed",
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "source_anchor": {"path": "src/reader.py", "start_line": 3, "end_line": 3}
                if graph_type != "target"
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
                "storage_kind": "sql_table",
                "foreign_key_check": "PRAGMA foreign_key_check;",
                "foreign_key_check_result": ["zero foreign-key violation rows"],
                "writers": ["fn:src/writer.py:write_item"],
                "readers": ["fn:src/reader.py:read_items"],
                "state_values": ["active", "archived"],
                "state_semantics": {"active": "available for normal retrieval", "archived": "retained historical record"},
                "state_producers": {"active": ["fn:src/writer.py:write_item"], "archived": ["fn:src/writer.py:write_item"]},
                "state_consumers": {"active": ["fn:src/reader.py:read_items"], "archived": ["fn:src/reader.py:read_items"]},
                "enum_values": ["active", "archived"],
                "schema_enum_values": ["active", "archived"],
                "enum_semantics": {"active": "available for normal retrieval", "archived": "retained historical record"},
                "enum_producers": {"active": ["fn:src/writer.py:write_item"], "archived": ["fn:src/writer.py:write_item"]},
                "enum_consumers": {"active": ["fn:src/reader.py:read_items"], "archived": ["fn:src/reader.py:read_items"]},
                "expected_runtime_state": "non-empty",
                "runtime_evidence": ["SELECT COUNT(*) FROM items > 0", "reader query returns item"],
                "status": "verified" if graph_type == "observed" else ("planned" if graph_type == "target" else "observed"),
                "verification_evidence": ["insert and reader visibility checks"],
                "implementation_state": "implemented",
            }
        ],
    }
    _add_test_network(document)
    return document


class GraphEvidenceTests(unittest.TestCase):

    def test_change_diff_references_must_match_current_graph(self) -> None:
        document = valid_snapshot("change")
        document["baseline_sha"] = "b" * 40
        document["current_sha"] = "a" * 40
        document["diff"] = {
            "added_nodes": ["fn:ghost:missing"],
            "removed_nodes": ["fn:src/writer.py:write_item"],
            "changed_nodes": ["fn:ghost:changed"],
            "added_edges": ["edge:ghost:added"],
            "removed_edges": ["writes:fn:src/writer.py:write_item->table:items"],
            "changed_edges": ["edge:ghost:changed"],
            "added_contracts": [],
            "removed_contracts": [],
            "changed_contracts": [],
            "unresolved": ["edge:ghost:unresolved"],
            "impact": ["diff query"],
            "verification_evidence": ["diff query"],
        }
        errors = validate_document(document)
        self.assertTrue(any("diff" in error and "unknown" in error for error in errors))

    def test_change_diff_removed_references_must_not_remain_in_current_graph(self) -> None:
        document = valid_snapshot("change")
        document["baseline_sha"] = "b" * 40
        document["current_sha"] = "a" * 40
        document["diff"] = {
            "added_nodes": [],
            "removed_nodes": ["fn:src/writer.py:write_item"],
            "changed_nodes": [],
            "added_edges": [],
            "removed_edges": ["writes:fn:src/writer.py:write_item->table:items"],
            "changed_edges": [],
            "added_contracts": [],
            "removed_contracts": [],
            "changed_contracts": [],
            "unresolved": [],
            "impact": ["diff query"],
            "verification_evidence": ["diff query"],
        }
        errors = validate_document(document)
        self.assertTrue(any("removed_nodes" in error and "current graph" in error for error in errors))
        self.assertTrue(any("removed_edges" in error and "current graph" in error for error in errors))

    def test_change_diff_must_declare_a_change(self) -> None:
        document = valid_snapshot("change")
        document["baseline_sha"] = "b" * 40
        document["current_sha"] = "a" * 40
        document["diff"] = {
            "added_nodes": [],
            "removed_nodes": [],
            "changed_nodes": [],
            "added_edges": [],
            "removed_edges": [],
            "changed_edges": [],
            "added_contracts": [],
            "removed_contracts": [],
            "changed_contracts": [],
            "unresolved": [],
            "impact": ["no changes"],
            "verification_evidence": ["diff query"],
        }
        errors = validate_document(document)
        self.assertTrue(any("requires at least one" in error for error in errors))

    def test_change_diff_unresolved_references_must_match_current_graph(self) -> None:
        document = valid_snapshot("change")
        document["baseline_sha"] = "b" * 40
        document["current_sha"] = "a" * 40
        document["diff"] = {
            "added_nodes": [document["nodes"][0]["node_id"]],
            "removed_nodes": [],
            "changed_nodes": [],
            "added_edges": [],
            "removed_edges": [],
            "changed_edges": [],
            "added_contracts": [],
            "removed_contracts": [],
            "changed_contracts": [],
            "unresolved": ["edge:ghost:unresolved"],
            "impact": ["diff query"],
            "verification_evidence": ["diff query"],
        }
        errors = validate_document(document)
        self.assertTrue(any("unresolved" in error and "unknown" in error for error in errors))

    def test_contracts_must_be_non_empty(self) -> None:
        document = valid_snapshot()
        document["contracts"] = []
        errors = validate_document(document)
        self.assertTrue(any("contracts must be a non-empty list" in error for error in errors))

    def test_complete_audit_requires_reviewers(self) -> None:
        document = valid_snapshot()
        document["audit_coverage"]["reviewers"] = []
        errors = validate_document(document)
        self.assertTrue(any("complete requires reviewers" in error for error in errors))

    def test_evidence_placeholders_are_rejected(self) -> None:
        for field in ("runtime_evidence", "verification_evidence"):
            document = valid_snapshot()
            document["contracts"][0][field] = ["TODO"]
            errors = validate_document(document)
            self.assertTrue(any("placeholder" in error for error in errors), field)

    def test_evidence_placeholder_variants_are_rejected(self) -> None:
        for placeholder in ("TODO", "TBD", "待定", "<...>", "<…>"):
            document = valid_snapshot()
            document["contracts"][0]["runtime_evidence"] = [placeholder]
            errors = validate_document(document)
            self.assertTrue(any("placeholder" in error for error in errors), placeholder)

    def test_node_and_edge_verification_evidence_reject_placeholders(self) -> None:
        for collection in ("nodes", "edges"):
            document = valid_snapshot()
            document[collection][0]["verification_evidence"] = ["TODO"]
            errors = validate_document(document)
            self.assertTrue(any("placeholder" in error for error in errors), collection)

    def test_factual_object_statuses_require_verification_evidence(self) -> None:
        for collection in ("nodes", "edges", "contracts"):
            for status in ("observed", "changed", "implemented", "verified"):
                with self.subTest(collection=collection, status=status):
                    document = valid_snapshot()
                    document[collection][0]["status"] = status
                    document[collection][0]["verification_evidence"] = []
                    errors = validate_document(document)
                    self.assertTrue(
                        any(
                            f"{collection}[0]" in error
                            and "requires verification_evidence" in error
                            for error in errors
                        ),
                        errors,
                    )

    def test_state_and_enum_maps_reject_undeclared_keys(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["state_semantics"]["ghost"] = "undocumented"
        contract["state_producers"]["ghost"] = contract["state_producers"]["active"]
        contract["state_consumers"]["ghost"] = contract["state_consumers"]["active"]
        contract["enum_semantics"]["ghost"] = "undocumented"
        contract["enum_producers"]["ghost"] = contract["enum_producers"]["active"]
        contract["enum_consumers"]["ghost"] = contract["enum_consumers"]["active"]
        errors = validate_document(document)
        self.assertTrue(any("unknown state" in error for error in errors))
        self.assertTrue(any("unknown enum" in error for error in errors))

    def test_deferred_state_milestones_reject_undeclared_keys(self) -> None:
        document = valid_snapshot()
        document["contracts"][0]["state_deferred_milestones"] = {"ghost": "M9"}
        errors = validate_document(document)
        self.assertTrue(any("unknown state key" in error for error in errors))

    def test_terminal_states_reject_undeclared_values(self) -> None:
        document = valid_snapshot()
        document["contracts"][0]["terminal_states"] = ["ghost"]
        errors = validate_document(document)
        self.assertTrue(any("terminal state" in error for error in errors))

    def test_map_only_rejects_implementation_test_chain_status(self) -> None:
        document = valid_snapshot()
        document["test_chains"][0]["status"] = "planned"
        errors = validate_document(document, map_only=True)
        self.assertTrue(any("map-only status" in error for error in errors))

    def test_map_only_allows_explicitly_deferred_test_chain(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][0]
        chain["status"] = "deferred"
        chain["deferred_reason"] = "External runtime is unavailable"
        chain["deferred_milestone"] = "M2"
        self.assertEqual(validate_document(document, map_only=True), [])

    def test_map_only_allows_observed_test_chain(self) -> None:
        document = valid_snapshot()
        document["test_chains"][0]["status"] = "observed"
        self.assertEqual(validate_document(document, map_only=True), [])

    def test_blocked_and_unresolved_nodes_require_recovery_fields(self) -> None:
        for status, fields in (
            ("blocked", {"blocked_reason": "provider unavailable", "next_query": "run provider"}),
            ("unresolved", {"unresolved_reason": "dynamic dispatch", "next_query": "run trace"}),
        ):
            document = valid_snapshot()
            node = document["nodes"][0]
            node["status"] = status
            errors = validate_document(document)
            self.assertTrue(any("recovery" in error or status in error for error in errors), status)
            node.update(fields)
            # A verified contract cannot remain verified while one of its
            # writer/reader/storage dependencies is blocked or unresolved.
            document["contracts"][0].update(status=status, **fields)
            for chain in document["test_chains"]:
                chain.update(status=status, **fields)
            self.assertEqual(validate_document(document), [], status)

    def test_blocked_and_unresolved_contracts_require_recovery_fields(self) -> None:
        for status, fields in (
            ("blocked", {"blocked_reason": "writer not approved", "next_query": "confirm owner"}),
            ("unresolved", {"unresolved_reason": "consumer is dynamic", "next_query": "trace consumer"}),
        ):
            document = valid_snapshot()
            contract = document["contracts"][0]
            contract["status"] = status
            errors = validate_document(document)
            self.assertTrue(any("recovery" in error or status in error for error in errors), status)
            contract.update(fields)
            for chain in document["test_chains"]:
                chain.update(status=status, **fields)
            self.assertEqual(validate_document(document), [], status)

    def test_change_diff_unresolved_refs_must_point_to_unresolved_items(self) -> None:
        document = valid_snapshot("change")
        document["baseline_sha"] = "b" * 40
        document["current_sha"] = "a" * 40
        document["diff"] = {
            "added_nodes": [document["nodes"][0]["node_id"]],
            "removed_nodes": [],
            "changed_nodes": [],
            "added_edges": [],
            "removed_edges": [],
            "changed_edges": [],
            "added_contracts": [],
            "removed_contracts": [],
            "changed_contracts": [],
            "unresolved": [document["nodes"][0]["node_id"]],
            "impact": ["diff query"],
            "verification_evidence": ["diff query"],
        }
        errors = validate_document(document)
        self.assertTrue(any("unresolved" in error and "status" in error for error in errors))

    def test_change_graph_evidence_sha_must_match_current_sha(self) -> None:
        document = valid_snapshot("change")
        document["baseline_sha"] = "b" * 40
        document["current_sha"] = "c" * 40
        document["diff"] = {
            "added_nodes": [document["nodes"][0]["node_id"]],
            "removed_nodes": [],
            "changed_nodes": [],
            "added_edges": [],
            "removed_edges": [],
            "changed_edges": [],
            "added_contracts": [],
            "removed_contracts": [],
            "changed_contracts": [],
            "unresolved": [],
            "impact": ["diff query"],
            "verification_evidence": ["diff query"],
        }
        errors = validate_document(document)
        self.assertTrue(any("current_sha" in error and "git_sha" in error for error in errors))

    def test_change_graph_requires_distinct_shas_and_nonempty_impact(self) -> None:
        document = valid_snapshot("change")
        document["baseline_sha"] = "a" * 40
        document["current_sha"] = "a" * 40
        document["diff"] = {
            "added_nodes": [document["nodes"][0]["node_id"]],
            "removed_nodes": [],
            "changed_nodes": [],
            "added_edges": [],
            "removed_edges": [],
            "changed_edges": [],
            "added_contracts": [],
            "removed_contracts": [],
            "changed_contracts": [],
            "unresolved": [],
            "impact": [],
            "verification_evidence": ["diff query"],
        }
        errors = validate_document(document)
        self.assertTrue(any("baseline_sha" in error and "current_sha" in error for error in errors))
        self.assertTrue(any("impact" in error and "non-empty" in error for error in errors))

    def test_change_diff_reference_lists_reject_duplicates(self) -> None:
        document = valid_snapshot("change")
        document["baseline_sha"] = "b" * 40
        document["current_sha"] = "a" * 40
        node_id = document["nodes"][0]["node_id"]
        document["diff"] = {
            "added_nodes": [node_id, node_id],
            "removed_nodes": [],
            "changed_nodes": [],
            "added_edges": [],
            "removed_edges": [],
            "changed_edges": [],
            "added_contracts": [],
            "removed_contracts": [],
            "changed_contracts": [],
            "unresolved": [],
            "impact": ["fn:src/reader.py:read_items"],
            "verification_evidence": ["diff query"],
        }
        errors = validate_document(document)
        self.assertTrue(any("duplicate" in error and "added_nodes" in error for error in errors))

    def test_non_change_graph_cannot_include_change_only_fields(self) -> None:
        diff = {
            "added_nodes": ["fn:ghost:nope"],
            "removed_nodes": [],
            "changed_nodes": [],
            "added_edges": [],
            "removed_edges": [],
            "changed_edges": [],
            "added_contracts": [],
            "removed_contracts": [],
            "changed_contracts": [],
            "unresolved": [],
            "impact": ["diff query"],
            "verification_evidence": ["diff query"],
        }
        for graph_type in ("observed", "target"):
            for field, value in (
                ("baseline_sha", "b" * 40),
                ("current_sha", "a" * 40),
                ("diff", diff),
            ):
                with self.subTest(graph_type=graph_type, field=field):
                    document = valid_snapshot(graph_type)
                    document[field] = value
                    errors = validate_document(document)
                    self.assertTrue(any(field in error and "change" in error for error in errors), errors)

    def test_deferred_source_anchor_is_validated(self) -> None:
        document = valid_snapshot()
        section = document["source_coverage"][0]
        section["status"] = "deferred"
        section["explicit_reason"] = "later"
        section["source_anchor"] = {"path": "", "start_line": 0, "end_line": 0, "extra": "bad"}
        errors = validate_document(document)
        self.assertTrue(any("source_anchor" in error for error in errors))

    def test_non_finite_strategy_parameters_are_rejected(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            document = valid_snapshot()
            contract = document["contracts"][0]
            contract.update(
                {
                    "strategy_name": "example",
                    "strategy_status": "ready",
                    "strategy_parameters": value,
                    "strategy_trigger": "trigger",
                    "strategy_target": "items",
                    "strategy_entrypoint": "run",
                }
            )
            errors = validate_document(document)
            self.assertTrue(any("finite" in error for error in errors), repr(value))

    def test_nested_strategy_parameters_reject_non_finite_numbers(self) -> None:
        for parameters in ({"decay": float("nan")}, [float("inf")]):
            document = valid_snapshot()
            document["contracts"][0].update(
                {
                    "strategy_name": "example",
                    "strategy_status": "ready",
                    "strategy_parameters": parameters,
                    "strategy_trigger": "trigger",
                    "strategy_target": "items",
                    "strategy_entrypoint": "run",
                }
            )
            errors = validate_document(document)
            self.assertTrue(any("finite" in error for error in errors), repr(parameters))

    @staticmethod
    def _iter_paths(value: object, path: tuple[object, ...] = ()):
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = path + (key,)
                yield child_path, child
                yield from GraphEvidenceTests._iter_paths(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                child_path = path + (index,)
                yield child_path, child
                yield from GraphEvidenceTests._iter_paths(child, child_path)

    @staticmethod
    def _set_path(document: dict, path: tuple[object, ...], value: object) -> None:
        target = document
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value

    @staticmethod
    def _wrong_type(value: object) -> object | None:
        if isinstance(value, bool):
            return "not-a-boolean"
        if isinstance(value, str):
            return []
        if isinstance(value, list):
            return {}
        if isinstance(value, dict):
            return []
        if type(value) in (int, float):
            return []
        return None

    def test_all_field_type_mutations_are_safe_and_fail_closed(self) -> None:
        hostile_values = [None, True, 0, 1.5, "", "invalid", [], {}, [1], {"x": 1}]
        for graph_type in ("observed", "target", "change"):
            document = valid_snapshot(graph_type)
            if graph_type == "change":
                document.update(
                    {
                        "baseline_sha": "b" * 40,
                        "current_sha": "a" * 40,
                        "diff": {
                            "added_nodes": ["fn:src/writer.py:write_item"],
                            "removed_nodes": [],
                            "changed_nodes": [],
                            "added_edges": [],
                            "removed_edges": [],
                            "changed_edges": [],
                            "added_contracts": [],
                            "removed_contracts": [],
                            "changed_contracts": [],
                            "unresolved": [],
                            "impact": ["diff impact query"],
                            "verification_evidence": ["diff query"],
                        },
                    }
                )
            self.assertEqual(validate_document(document), [])
            for path, original in list(self._iter_paths(document)):
                for hostile in hostile_values:
                    mutated = copy.deepcopy(document)
                    self._set_path(mutated, path, hostile)
                    with self.subTest(graph_type=graph_type, path=path, hostile=hostile):
                        try:
                            errors = validate_document(mutated)
                        except Exception as exc:  # pragma: no cover - assertion carries the regression detail
                            self.fail(f"validator raised {type(exc).__name__}: {exc}")
                        self.assertIsInstance(errors, list)
                wrong = self._wrong_type(original)
                if wrong is not None:
                    mutated = copy.deepcopy(document)
                    self._set_path(mutated, path, wrong)
                    with self.subTest(graph_type=graph_type, path=path, wrong=wrong):
                        self.assertTrue(validate_document(mutated))
    def test_valid_observed_snapshot_passes(self) -> None:
        self.assertEqual(validate_document(valid_snapshot()), [])

    def test_valid_target_snapshot_passes(self) -> None:
        self.assertEqual(validate_document(valid_snapshot("target")), [])

    def test_target_graph_requires_l0_and_l1_chains(self) -> None:
        document = valid_snapshot("target")
        document["test_chains"] = [document["test_chains"][0]]
        errors = validate_document(document)
        self.assertTrue(any("L0" in error for error in errors))

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

    def test_graph_requires_test_chains(self) -> None:
        document = valid_snapshot()
        document.pop("test_chains")
        errors = validate_document(document)
        self.assertTrue(any("test_chains" in error for error in errors))

    def test_expected_runtime_state_is_required_and_enum_checked(self) -> None:
        for value in ("nonempty", "non_empty", "Non-Empty", "non-empty ", "whatever", "", None):
            document = valid_snapshot()
            document["contracts"][0]["expected_runtime_state"] = value
            document["contracts"][0]["runtime_evidence"] = []
            errors = validate_document(document)
            self.assertTrue(any("expected_runtime_state" in error for error in errors), value)

        document = valid_snapshot()
        document["contracts"][0].pop("expected_runtime_state")
        errors = validate_document(document)
        self.assertTrue(any("expected_runtime_state" in error for error in errors))

    def test_failure_mode_enum_is_checked_before_degraded_gate(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["failure_mode"] = "degraded_with_warning"
        contract.pop("observability_evidence", None)
        contract.pop("distinguishes_failure_from_empty", None)
        errors = validate_document(document)
        self.assertTrue(any("failure_mode" in error for error in errors))

    def test_target_anchor_field_is_required_but_planned_anchor_may_be_null(self) -> None:
        document = valid_snapshot("target")
        document["edges"][0].pop("source_anchor")
        errors = validate_document(document)
        self.assertTrue(any("source_anchor" in error for error in errors))

        document = valid_snapshot("target")
        document["edges"][0]["source_anchor"] = None
        self.assertEqual(validate_document(document), [])

        for graph_type, status in (("target", "implemented"), ("change", "changed")):
            document = valid_snapshot(graph_type)
            if graph_type == "change":
                document["baseline_sha"] = "b" * 40
                document["current_sha"] = "a" * 40
                document["diff"] = {
                    "added_nodes": [],
                    "removed_nodes": [],
                    "changed_nodes": [],
                    "added_edges": [],
                    "removed_edges": [],
                    "changed_edges": [],
                    "added_contracts": [],
                    "removed_contracts": [],
                    "changed_contracts": [],
                    "unresolved": [],
                    "impact": ["diff impact query"],
                    "verification_evidence": ["diff query"],
                }
            document["nodes"][0]["status"] = status
            document["nodes"][0]["source_anchor"] = None
            errors = validate_document(document)
            self.assertTrue(any("source_anchor" in error for error in errors), graph_type)

    def test_target_contract_verification_evidence_field_is_required(self) -> None:
        document = valid_snapshot("target")
        document["contracts"][0].pop("verification_evidence")
        errors = validate_document(document)
        self.assertTrue(any("verification_evidence" in error for error in errors))

    def test_malicious_types_report_errors_without_crashing(self) -> None:
        mutations = [
            ("graph_type list", lambda d: d.__setitem__("graph_type", [])),
            ("node status list", lambda d: d["nodes"][0].__setitem__("status", [])),
            ("edge kind list", lambda d: d["edges"][0].__setitem__("kind", [])),
            ("non-dict edge", lambda d: d["edges"].append(123)),
            ("source coverage refs integer", lambda d: d["source_coverage"][0].__setitem__("target_node_refs", 123)),
            ("terminal states integer", lambda d: d["contracts"][0].__setitem__("terminal_states", 123)),
            ("state producer integer", lambda d: d["contracts"][0]["state_producers"].__setitem__("active", 123)),
            ("state value list", lambda d: d["contracts"][0].__setitem__("state_values", [["active"]])),
            ("enum value list", lambda d: d["contracts"][0].__setitem__("enum_values", [["active"]])),
            ("nullable unique column list", lambda d: d["contracts"][0].__setitem__("nullable_unique_columns", [["active"]])),
            ("test node refs integer", lambda d: d["test_chains"][0].__setitem__("test_node_refs", 123)),
            ("test chain status list", lambda d: d["test_chains"][0].__setitem__("status", [])),
            ("test chain entrypoint list", lambda d: d["test_chains"][0].__setitem__("entrypoint_node_id", [])),
        ]
        for label, mutation in mutations:
            document = valid_snapshot()
            mutation(document)
            try:
                errors = validate_document(document)
            except Exception as exc:  # pragma: no cover - failure message is the assertion
                self.fail(f"{label} raised {type(exc).__name__}: {exc}")
            self.assertTrue(errors, label)

    def test_unhashable_ids_refs_and_enums_report_errors_without_crashing(self) -> None:
        mutations = [
            ("node id list", lambda d: d["nodes"][0].__setitem__("node_id", [])),
            ("edge id dict", lambda d: d["edges"][0].__setitem__("edge_id", {})),
            ("edge endpoint list", lambda d: d["edges"][0].__setitem__("from", [])),
            ("contract storage id dict", lambda d: d["contracts"][0].__setitem__("storage_node_id", {})),
            ("writer ref list", lambda d: d["contracts"][0]["writers"].__setitem__(0, [])),
            ("reader ref dict", lambda d: d["contracts"][0]["readers"].__setitem__(0, {})),
            ("state producer ref list", lambda d: d["contracts"][0]["state_producers"]["active"].__setitem__(0, [])),
            ("enum consumer ref dict", lambda d: d["contracts"][0]["enum_consumers"]["active"].__setitem__(0, {})),
            ("required role scalar", lambda d: d["test_chains"][0]["required_roles"].__setitem__("producer", 1)),
            ("required role ref list", lambda d: d["test_chains"][0]["required_roles"]["producer"].__setitem__(0, [])),
            ("uncovered ref list", lambda d: d["test_chains"][0]["uncovered_edge_refs"].append([])),
            ("evidence kind list", lambda d: d["test_chains"][0].__setitem__("evidence_kind", [])),
            ("test scope dict", lambda d: d["test_chains"][0].__setitem__("test_scope", {})),
            ("top-level coverage scope list", lambda d: d["coverage"].__setitem__("scope", [])),
            ("top-level coverage status dict", lambda d: d["coverage"].__setitem__("status", {})),
            ("failure mode null", lambda d: d["contracts"][0].__setitem__("failure_mode", None)),
        ]
        for label, mutation in mutations:
            document = valid_snapshot()
            mutation(document)
            try:
                errors = validate_document(document)
            except Exception as exc:  # pragma: no cover - failure message is the assertion
                self.fail(f"{label} raised {type(exc).__name__}: {exc}")
            self.assertTrue(errors, label)

    def test_node_anchor_matches_schema_optional_field_and_observed_evidence_rule(self) -> None:
        document = valid_snapshot("target")
        document["nodes"][0].pop("source_anchor")
        self.assertEqual(validate_document(document), [])

        document = valid_snapshot("observed")
        document["nodes"][0].pop("source_anchor")
        errors = validate_document(document)
        self.assertTrue(any("source_anchor" in error for error in errors))

    def test_evidence_arrays_require_nonempty_strings(self) -> None:
        mutations = [
            ("contract runtime_evidence", lambda d: d["contracts"][0].__setitem__("runtime_evidence", [[]])),
            ("contract verification_evidence", lambda d: d["contracts"][0].__setitem__("verification_evidence", [{}])),
            ("test runtime_evidence", lambda d: d["test_chains"][0].__setitem__("runtime_evidence", [""])),
            ("test verification_evidence", lambda d: d["test_chains"][0].__setitem__("verification_evidence", [{}])),
            ("audit independent_verification", lambda d: d["audit_coverage"].__setitem__("independent_verification", [[]])),
        ]
        for label, mutation in mutations:
            document = valid_snapshot()
            mutation(document)
            errors = validate_document(document)
            self.assertTrue(any(label.split()[-1] in error for error in errors), label)

        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["failure_mode"] = "degraded-with-warning"
        contract["observability_evidence"] = [{}]
        contract["distinguishes_failure_from_empty"] = True
        errors = validate_document(document)
        self.assertTrue(any("observability_evidence" in error for error in errors))

    def test_required_reference_items_and_boolean_flags_are_type_checked(self) -> None:
        mutations = [
            ("node entrypoint", lambda d: d["nodes"][3].__setitem__("entrypoint", "yes")),
            ("chain requirement ref", lambda d: d["test_chains"][0]["requirement_refs"].__setitem__(0, [])),
            ("chain AC ref", lambda d: d["test_chains"][0]["ac_refs"].__setitem__(0, {})),
        ]
        for label, mutation in mutations:
            document = valid_snapshot()
            mutation(document)
            errors = validate_document(document)
            self.assertTrue(errors, label)

        document = valid_snapshot()
        document["nodes"][0]["test_refs"] = None
        errors = validate_document(document)
        self.assertTrue(any("test_refs" in error for error in errors))

    def test_change_diff_evidence_items_are_type_checked(self) -> None:
        document = valid_snapshot("change")
        document["baseline_sha"] = "b" * 40
        document["current_sha"] = "a" * 40
        document["diff"] = {
            "added_nodes": [],
            "removed_nodes": [],
            "changed_nodes": [],
            "added_edges": [],
            "removed_edges": [],
            "changed_edges": [],
            "added_contracts": [],
            "removed_contracts": [],
            "changed_contracts": [],
            "unresolved": [],
            "impact": ["diff impact query"],
            "verification_evidence": [[]],
        }
        errors = validate_document(document)
        self.assertTrue(any("verification_evidence" in error for error in errors))

    def test_source_coverage_required_fields_apply_to_deferred_sections(self) -> None:
        document = valid_snapshot()
        section = document["source_coverage"][0]
        section["status"] = "deferred"
        section["explicit_reason"] = "Deferred to the next milestone"
        section.pop("owner_task")
        section.pop("source_anchor")
        errors = validate_document(document)
        self.assertTrue(any("owner_task" in error or "owner" in error for error in errors))
        self.assertTrue(any("source_anchor" in error for error in errors))

    def test_optional_contract_fields_are_type_checked_when_present(self) -> None:
        mutations = [
            ("writer milestone", "writer_milestone", []),
            ("reader milestone", "reader_milestone", {}),
            ("foreign key check", "foreign_key_check", []),
            ("null semantics blocking reason", "null_semantics_blocking_reason", []),
            ("duplicate query", "duplicate_query", {}),
            ("strategy blocking reason", "strategy_blocking_reason", []),
            ("observability evidence", "observability_evidence", {}),
            ("cleanup plan", "cleanup_plan", []),
        ]
        for label, field, value in mutations:
            document = valid_snapshot()
            document["contracts"][0][field] = value
            errors = validate_document(document)
            self.assertTrue(any(field in error for error in errors), label)

        document = valid_snapshot()
        document["contracts"][0]["distinguishes_failure_from_empty"] = "yes"
        errors = validate_document(document)
        self.assertTrue(any("distinguishes_failure_from_empty" in error for error in errors))

    def test_schema_declared_nested_fields_are_type_checked_when_present(self) -> None:
        mutations = [
            ("provider capabilities", lambda d: d["provider"].__setitem__("capabilities", [{}])),
            ("coverage limitations", lambda d: d["coverage"].__setitem__("limitations", [[]])),
            ("review premises", lambda d: d.__setitem__("review_findings", [{
                "finding_id": "F-01", "status": "proposed", "evidence": ["review"], "premises": [[]]
            }])),
            ("state semantics", lambda d: d["contracts"][0]["state_semantics"].__setitem__("active", [])),
            ("state deferred milestone", lambda d: d["contracts"][0].__setitem__("state_deferred_milestones", {"active": []})),
            ("strategy parameters", lambda d: d["contracts"][0].__setitem__("strategy_parameters", True)),
            ("edge next query", lambda d: d["edges"][0].__setitem__("next_query", [])),
            ("node exemption reason", lambda d: d["nodes"][0].__setitem__("test_exemption_reason", [])),
            ("empty node exemption reason", lambda d: d["nodes"][0].__setitem__("test_exemption_reason", "")),
            ("empty deferred reason", lambda d: d["test_chains"][0].__setitem__("deferred_reason", "")),
            ("empty review reason", lambda d: d.__setitem__("review_findings", [{
                "finding_id": "F-01", "status": "proposed", "evidence": ["review"], "inconclusive_reason": ""
            }])),
        ]
        for label, mutation in mutations:
            document = valid_snapshot()
            mutation(document)
            errors = validate_document(document)
            self.assertTrue(errors, label)

    def test_optional_enum_and_review_evidence_types_are_checked(self) -> None:
        mutations = [
            ("storage kind", lambda d: d["contracts"][0].__setitem__("storage_kind", None)),
            ("unique keys", lambda d: d["contracts"][0].__setitem__("unique_keys", None)),
            ("null semantics", lambda d: d["contracts"][0].__setitem__("null_semantics", None)),
            ("review independent verification", lambda d: d.__setitem__("review_findings", [{
                "finding_id": "F-01", "status": "proposed", "evidence": ["review"], "independent_verification": [[]]
            }])),
            ("unknown root field", lambda d: d.__setitem__("expected_runtime_stte", "non-empty")),
            ("unknown contract field", lambda d: d["contracts"][0].__setitem__("expected_runtime_stte", "non-empty")),
        ]
        for label, mutation in mutations:
            document = valid_snapshot()
            mutation(document)
            errors = validate_document(document)
            self.assertTrue(errors, label)

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

    def test_covered_source_section_requires_ears_anchor_and_owner(self) -> None:
        document = valid_snapshot()
        section = document["source_coverage"][0]
        section.pop("ears_refs")
        section.pop("source_anchor")
        section.pop("owner_task")
        errors = validate_document(document)
        self.assertTrue(any("ears_refs" in error for error in errors))
        self.assertTrue(any("source_anchor" in error for error in errors))
        self.assertTrue(any("owner" in error for error in errors))
        section["ears_refs"] = ["EARS-01"]
        section["source_anchor"] = {"path": "design.md", "start_line": 10, "end_line": 12}
        section["owner_task"] = "M1-T01"
        self.assertEqual(validate_document(document), [])

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

    def test_completed_contract_requires_real_writer_and_reader(self) -> None:
        document = valid_snapshot()
        storage = copy.deepcopy(document["nodes"][1])
        storage.update(
            node_id="table:milestone-only",
            path="db/milestone-only.sql",
            qualified_symbol="milestone_only",
            source_anchor={
                "path": "db/milestone-only.sql",
                "start_line": 1,
                "end_line": 4,
            },
            test_refs=[],
        )
        document["nodes"].append(storage)
        validation_edge = copy.deepcopy(document["edges"][2])
        validation_edge.update(
            edge_id="validates:test:happy->table:milestone-only",
            to=storage["node_id"],
            verification_evidence=["review points at the milestone-only contract"],
        )
        document["edges"].append(validation_edge)
        contract = copy.deepcopy(document["contracts"][0])
        contract.update(
            contract_id="milestone-only",
            storage_node_id=storage["node_id"],
            writers=[],
            readers=[],
            writer_milestone="M2",
            reader_milestone="M2",
            state_values=[],
            state_semantics={},
            state_producers={},
            state_consumers={},
            enum_values=[],
            schema_enum_values=[],
            enum_semantics={},
            enum_producers={},
            enum_consumers={},
            verification_evidence=["review record labels the contract verified"],
        )
        document["contracts"].append(contract)

        for status in ("implemented", "verified"):
            with self.subTest(status=status):
                contract["status"] = status

                errors = validate_document(document)

                self.assertTrue(
                    any(status in error and "writer" in error for error in errors),
                    errors,
                )
                self.assertTrue(
                    any(status in error and "reader" in error for error in errors),
                    errors,
                )

    def test_coverage_refs_must_exist(self) -> None:
        document = valid_snapshot()
        document["source_coverage"][0]["target_node_refs"] = ["fn:missing"]
        errors = validate_document(document)
        self.assertTrue(any("target_node_refs" in error for error in errors))

    def test_enum_values_require_semantics_producers_and_consumers(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract.pop("enum_semantics")
        errors = validate_document(document)
        self.assertTrue(any("enum_semantics" in error for error in errors))
        contract["enum_semantics"] = {"active": "available", "archived": "retained"}
        self.assertEqual(validate_document(document), [])

    def test_state_without_consumer_requires_deferred_milestone(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["state_consumers"]["archived"] = []
        errors = validate_document(document)
        self.assertTrue(any("deferred milestone" in error for error in errors))
        contract["state_deferred_milestones"] = {"archived": "M2"}
        self.assertEqual(validate_document(document), [])

    def test_enum_mismatch_fails(self) -> None:
        document = valid_snapshot()
        document["contracts"][0]["schema_enum_values"] = ["active"]
        errors = validate_document(document)
        self.assertTrue(any("enum" in error for error in errors))

    def test_nullable_unique_key_requires_null_semantics_and_duplicate_query(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["storage_kind"] = "sql_table"
        contract["unique_keys"] = ["subject_abbr", "concept_name"]
        contract["nullable_unique_columns"] = ["subject_abbr"]
        errors = validate_document(document)
        self.assertTrue(any("null_semantics" in error for error in errors))
        self.assertTrue(any("duplicate_query" in error for error in errors))
        contract["null_semantics"] = "partial_index"
        contract["duplicate_query"] = "SELECT subject_abbr, concept_name, COUNT(*) FROM concept_mastery GROUP BY subject_abbr, concept_name HAVING COUNT(*) > 1"
        contract["duplicate_query_result"] = ["zero duplicate groups"]
        contract["foreign_key_check"] = "PRAGMA foreign_key_check"
        self.assertEqual(validate_document(document), [])

    def test_sql_contract_requires_foreign_key_check(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["storage_kind"] = "sql_table"
        contract.pop("foreign_key_check", None)
        errors = validate_document(document)
        self.assertTrue(any("foreign_key_check" in error for error in errors))

    def test_contract_requires_storage_kind_to_select_integrity_gate(self) -> None:
        document = valid_snapshot()
        document["contracts"][0].pop("storage_kind", None)
        errors = validate_document(document)
        self.assertTrue(any("storage_kind" in error for error in errors), errors)

    def test_strategy_requires_parameters_or_blocked_status(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["strategy_name"] = "exponential"
        errors = validate_document(document)
        self.assertTrue(any("strategy" in error for error in errors))
        contract["strategy_status"] = "blocked"
        contract["strategy_blocking_reason"] = "half-life not approved"
        self.assertEqual(validate_document(document), [])

    def test_zero_is_a_concrete_strategy_parameter(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract.update(
            {
                "strategy_name": "zero-threshold",
                "strategy_status": "ready",
                "strategy_parameters": 0,
                "strategy_trigger": "on write",
                "strategy_target": "items",
                "strategy_entrypoint": "write_item",
            }
        )
        self.assertEqual(validate_document(document), [])

        for empty_parameters in ("", [], {}):
            with self.subTest(empty_parameters=empty_parameters):
                contract["strategy_parameters"] = empty_parameters
                errors = validate_document(document)
                self.assertTrue(
                    any("strategy requires strategy_parameters" in error for error in errors),
                    errors,
                )

    def test_degraded_failure_requires_observable_distinction(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["failure_mode"] = "degraded-with-warning"
        errors = validate_document(document)
        self.assertTrue(any("observability" in error for error in errors))
        self.assertTrue(any("distinguish" in error for error in errors))
        contract["observability_evidence"] = ["retrieval_warnings field"]
        contract["distinguishes_failure_from_empty"] = True
        self.assertEqual(validate_document(document), [])

    def test_corrupted_data_requires_cleanup_plan(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["implementation_state"] = "data-corrupted"
        errors = validate_document(document)
        self.assertTrue(any("data_audit_evidence" in error for error in errors))
        self.assertTrue(any("cleanup_plan" in error for error in errors))
        contract["data_audit_evidence"] = ["duplicate query returned 32 rows"]
        contract["cleanup_plan"] = "M0-T02 migration"
        self.assertEqual(validate_document(document), [])

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

    def test_rejected_review_finding_requires_premise_verification(self) -> None:
        document = valid_snapshot()
        document["review_findings"] = [
            {
                "finding_id": "F-02",
                "status": "rejected",
                "evidence": ["reviewer report"],
                "premises": ["duplicate rows are impossible"],
            }
        ]
        errors = validate_document(document)
        self.assertTrue(any("premise_verification" in error for error in errors))
        document["review_findings"][0]["premise_verification"] = ["production query found duplicate rows"]
        self.assertEqual(validate_document(document), [])

    def test_inconclusive_review_finding_requires_reason(self) -> None:
        document = valid_snapshot()
        document["review_findings"] = [
            {
                "finding_id": "F-03",
                "status": "inconclusive",
                "evidence": ["429 rate limit"],
            }
        ]
        errors = validate_document(document)
        self.assertTrue(any("inconclusive_reason" in error for error in errors))
        document["review_findings"][0]["inconclusive_reason"] = "rate limit prevented complete verification"
        self.assertEqual(validate_document(document), [])

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
        document["nodes"][0]["status"] = "changed"
        document["nodes"][0]["source_anchor"] = {
            "path": "src/writer.py",
            "start_line": 1,
            "end_line": 5,
        }
        document["diff"] = {
            "added_nodes": [],
            "removed_nodes": [],
            "changed_nodes": ["fn:src/writer.py:write_item"],
            "added_edges": [],
            "removed_edges": [],
            "changed_edges": [],
            "added_contracts": [],
            "removed_contracts": [],
            "changed_contracts": [],
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

    def test_l1_chain_requires_consumer_and_error_path(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][0]
        chain["required_roles"]["consumer"] = []
        chain["error_path_refs"] = []
        errors = validate_document(document)
        self.assertTrue(any("consumer" in error for error in errors))
        self.assertTrue(any("error_path" in error for error in errors))

    def test_verified_runtime_chain_requires_runtime_evidence(self) -> None:
        document = valid_snapshot()
        document["test_chains"][0]["runtime_evidence"] = []
        errors = validate_document(document)
        self.assertTrue(any("runtime_evidence" in error for error in errors))

    def test_verified_l1_chain_rejects_static_only_evidence(self) -> None:
        document = valid_snapshot()
        document["test_chains"][0]["evidence_kind"] = "static"
        errors = validate_document(document)
        self.assertTrue(any("runtime evidence kind" in error for error in errors))

    def test_l1_chain_requires_validation_edges_for_roles(self) -> None:
        document = valid_snapshot()
        document["test_chains"][0]["edge_refs"].remove("validates:test:happy->table:items")
        errors = validate_document(document)
        self.assertTrue(any("validates" in error for error in errors))

    def test_chain_closes_each_declared_contract_independently(self) -> None:
        document = valid_snapshot()
        replacements = {
            "fn:src/writer.py:write_item": "fn:src/log_writer.py:write_log",
            "table:items": "table:logs",
            "fn:src/reader.py:read_items": "fn:src/log_reader.py:read_logs",
            "src/writer.py": "src/log_writer.py",
            "src/reader.py": "src/log_reader.py",
            "db/schema.sql": "db/logs.sql",
            "write_item": "write_log",
            "read_items": "read_logs",
            "items-write-read": "logs-write-read",
        }

        def replace_graph_strings(value: object) -> object:
            if isinstance(value, str):
                for old, new in replacements.items():
                    value = value.replace(old, new)
                return value
            if isinstance(value, list):
                return [replace_graph_strings(item) for item in value]
            if isinstance(value, dict):
                return {
                    replace_graph_strings(key): replace_graph_strings(item)
                    for key, item in value.items()
                }
            return value

        new_nodes = [
            replace_graph_strings(copy.deepcopy(node))
            for node in document["nodes"][:3]
        ]
        new_edges = [
            replace_graph_strings(copy.deepcopy(edge))
            for edge in document["edges"][:2]
        ]
        new_contract = replace_graph_strings(copy.deepcopy(document["contracts"][0]))
        assert all(isinstance(node, dict) for node in new_nodes)
        assert all(isinstance(edge, dict) for edge in new_edges)
        assert isinstance(new_contract, dict)
        new_nodes[1]["qualified_symbol"] = "logs"
        document["nodes"].extend(new_nodes)
        document["edges"].extend(new_edges)
        document["contracts"].append(new_contract)

        validation_edge = copy.deepcopy(document["edges"][2])
        validation_edge.update(
            edge_id="validates:test:happy->table:logs",
            to="table:logs",
            verification_evidence=["test validates the secondary storage node"],
        )
        document["edges"].append(validation_edge)
        chain = document["test_chains"][0]
        chain["node_refs"].append("table:logs")
        chain["edge_refs"].append(validation_edge["edge_id"])
        chain["required_roles"]["contract"].append("table:logs")

        errors = validate_document(document)

        self.assertTrue(
            any("declared contract" in error and "producer" in error for error in errors),
            errors,
        )
        self.assertTrue(
            any("declared contract" in error and "consumer" in error for error in errors),
            errors,
        )

    def test_implemented_node_requires_test_reference_or_explicit_exemption(self) -> None:
        document = valid_snapshot()
        node = document["nodes"][0]
        node["status"] = "implemented"
        node["test_refs"] = []
        errors = validate_document(document)
        self.assertTrue(any("test" in error for error in errors))
        node["test_exemption_reason"] = "N/A: generated schema-only node; covered by contract test"
        self.assertEqual(validate_document(document), [])

    def test_deferred_l3_chain_requires_reason_and_milestone(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][0]
        chain["level"] = "L3"
        chain["status"] = "deferred"
        errors = validate_document(document)
        self.assertTrue(any("deferred" in error for error in errors))
        chain["deferred_reason"] = "External adapter is not available in the MVP environment"
        chain["deferred_milestone"] = "M3"
        self.assertEqual(validate_document(document), [])

    def test_verified_chain_with_unresolved_edge_requires_expanded_scope(self) -> None:
        document = valid_snapshot()
        document["edges"].append(
            {
                "edge_id": "dynamic:writer->dispatcher",
                "kind": "dynamic",
                "from": document["nodes"][0]["node_id"],
                "to": document["nodes"][2]["node_id"],
                "status": "unresolved",
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "source_anchor": None,
                "confidence": 0.2,
                "coverage": "partial",
                "freshness": "current",
                "verification_evidence": [],
                "requirement_refs": [],
                "unresolved_reason": "framework dispatch is dynamic",
                "next_query": "run runtime trace with dispatcher instrumentation",
            }
        )
        for chain in document["test_chains"]:
            chain["uncovered_edge_refs"] = ["dynamic:writer->dispatcher"]
        errors = validate_document(document)
        self.assertTrue(any("expanded" in error or "unresolved" in error for error in errors))
        for chain in document["test_chains"]:
            chain["test_scope"] = "expanded"
        self.assertEqual(validate_document(document), [])

    def test_schema_file_is_valid_json(self) -> None:
        schema_path = Path(__file__).parents[1] / "references" / "graph-evidence.schema.json"
        schema = json.loads(
            schema_path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
        )
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_schema_rejects_empty_contracts_and_empty_change_diff(self) -> None:
        schema_path = Path(__file__).parents[1] / "references" / "graph-evidence.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertIn("storage_kind", schema["$defs"]["contract"]["required"])
        for field in ("source_coverage", "nodes", "edges", "contracts", "test_chains"):
            self.assertEqual(schema["properties"][field]["minItems"], 1, field)

        change_rule = next(
            condition
            for condition in schema["allOf"]
            if condition.get("if", {}).get("properties", {}).get("graph_type", {}).get("const") == "change"
            and "anyOf" in condition.get("then", {}).get("properties", {}).get("diff", {})
        )
        change_conditions = change_rule["then"]["properties"]["diff"]["anyOf"]
        self.assertEqual(
            {condition["required"][0] for condition in change_conditions},
            {
                "added_nodes", "removed_nodes", "changed_nodes",
                "added_edges", "removed_edges", "changed_edges",
                "added_contracts", "removed_contracts", "changed_contracts",
            },
        )
        for condition in change_conditions:
            self.assertEqual(condition["properties"][condition["required"][0]]["minItems"], 1)

        diff_properties = schema["$defs"]["diff"]["properties"]
        self.assertEqual(diff_properties["impact"]["minItems"], 1)
        for field in (
            "added_nodes", "removed_nodes", "changed_nodes",
            "added_edges", "removed_edges", "changed_edges",
            "added_contracts", "removed_contracts", "changed_contracts",
        ):
            self.assertTrue(diff_properties[field]["uniqueItems"], field)

    def test_schema_failure_mode_matches_validator_enum(self) -> None:
        schema_path = Path(__file__).parents[1] / "references" / "graph-evidence.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        failure_mode = schema["$defs"]["contract"]["properties"]["failure_mode"]
        self.assertEqual(failure_mode, {"enum": ["normal", "degraded-with-warning"]})


if __name__ == "__main__":
    unittest.main()
