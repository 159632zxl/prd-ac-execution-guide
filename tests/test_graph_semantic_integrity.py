from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.check_graph_evidence import validate_document
from tests.test_graph_evidence import valid_snapshot


def change_snapshot() -> dict:
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
        "unresolved": [],
        "impact": ["diff impact query"],
        "verification_evidence": ["git diff and dependency query"],
    }
    return document


def unresolved_dynamic_edge(document: dict) -> dict:
    return {
        "edge_id": "dynamic:writer->reader",
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
        "next_query": "run a dispatcher runtime trace",
    }


class GraphSemanticIntegrityTests(unittest.TestCase):
    def test_identifiers_and_references_reject_boundary_whitespace(self) -> None:
        identifier_mutations = (
            ("source section", lambda d: d["source_coverage"][0].__setitem__("source_section_id", " DESIGN-01 ")),
            ("node", lambda d: d["nodes"][0].__setitem__("node_id", " fn:src/writer.py:write_item ")),
            ("edge", lambda d: d["edges"][0].__setitem__("edge_id", " writes:writer->items ")),
            ("contract", lambda d: d["contracts"][0].__setitem__("contract_id", " items-write-read ")),
            ("chain", lambda d: d["test_chains"][0].__setitem__("chain_id", " TC-L1-items-write-read ")),
        )
        for label, mutate in identifier_mutations:
            with self.subTest(identifier=label):
                document = valid_snapshot()
                mutate(document)
                errors = validate_document(document)
                self.assertTrue(
                    any("leading or trailing whitespace" in error for error in errors),
                    errors,
                )

        document = valid_snapshot()
        document["review_findings"] = [
            {
                "finding_id": " FIND-01 ",
                "status": "proposed",
                "evidence": ["source query"],
            }
        ]
        self.assertTrue(
            any(
                "leading or trailing whitespace" in error
                for error in validate_document(document)
            )
        )

        reference_mutations = (
            ("edge endpoint", lambda d: d["edges"][0].__setitem__("from", " fn:src/writer.py:write_item ")),
            ("storage ref", lambda d: d["contracts"][0].__setitem__("storage_node_id", " table:items ")),
            ("entrypoint ref", lambda d: d["test_chains"][0].__setitem__("entrypoint_node_id", " test:tests/test_items.py:test_write_read_chain ")),
            ("reference list", lambda d: d["source_coverage"][0].__setitem__("requirement_refs", [" REQ-01 "])),
        )
        for label, mutate in reference_mutations:
            with self.subTest(reference=label):
                document = valid_snapshot()
                mutate(document)
                errors = validate_document(document)
                self.assertTrue(
                    any("leading or trailing whitespace" in error for error in errors),
                    errors,
                )

    def test_schema_reuses_canonical_identifier_definition(self) -> None:
        schema_path = Path(__file__).parents[1] / "references" / "graph-evidence.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        identifier = schema["$defs"].get("identifier")
        self.assertIsNotNone(identifier)
        assert identifier is not None
        self.assertIn("pattern", identifier)
        for definition_name, field in (
            ("sourceCoverage", "source_section_id"),
            ("node", "node_id"),
            ("edge", "edge_id"),
            ("contract", "contract_id"),
            ("testChain", "chain_id"),
            ("reviewFinding", "finding_id"),
        ):
            self.assertEqual(
                schema["$defs"][definition_name]["properties"][field].get("$ref"),
                "#/$defs/identifier",
                f"{definition_name}.{field}",
            )

    def test_schema_encodes_machine_expressible_integrity_rules(self) -> None:
        schema_path = Path(__file__).parents[1] / "references" / "graph-evidence.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        self.assertIn("check_graph_evidence.py", schema.get("$comment", ""))
        self.assertEqual(schema["properties"]["coverage"]["properties"]["paths"].get("minItems"), 1)
        self.assertNotIn("removed", schema["$defs"]["status"]["enum"])
        self.assertIn("unresolved_reason", schema["$defs"]["testChain"]["properties"])

        def required_for_status(definition: dict, status: str) -> set[str]:
            for condition in definition.get("allOf", []):
                status_schema = condition.get("if", {}).get("properties", {}).get("status", {})
                if status_schema.get("const") == status:
                    return set(condition.get("then", {}).get("required", []))
            return set()

        for definition_name in ("node", "edge", "contract", "testChain"):
            definition = schema["$defs"][definition_name]
            self.assertEqual(
                required_for_status(definition, "blocked"),
                {"blocked_reason", "next_query"},
                definition_name,
            )
            self.assertEqual(
                required_for_status(definition, "unresolved"),
                {"unresolved_reason", "next_query"},
                definition_name,
            )

        diff_evidence = schema["$defs"]["diff"]["properties"]["verification_evidence"]
        self.assertEqual(diff_evidence["minItems"], 1)

        contract = schema["$defs"]["contract"]
        for field in ("writers", "state_values", "enum_values", "schema_enum_values"):
            self.assertTrue(contract["properties"][field].get("uniqueItems"), field)
        for field in ("requirement_refs", "target_node_refs", "target_edge_refs", "ac_refs"):
            self.assertTrue(schema["$defs"]["sourceCoverage"]["properties"][field].get("uniqueItems"), field)

        strategy_fields = (
            "strategy_status",
            "strategy_parameters",
            "strategy_trigger",
            "strategy_target",
            "strategy_entrypoint",
            "strategy_blocking_reason",
        )
        dependencies = contract.get("dependentRequired", {})
        for field in strategy_fields:
            self.assertIn("strategy_name", dependencies.get(field, []), field)
        self.assertIn("strategy_status", dependencies.get("strategy_name", []))

        parameter_schema = contract["properties"]["strategy_parameters"]
        self.assertEqual(parameter_schema, {"$ref": "#/$defs/strategyParameters"})

        self.assertTrue(
            any(
                condition.get("if", {}).get("properties", {}).get("unique_keys", {}).get("minItems") == 1
                and "duplicate_query" in condition.get("then", {}).get("required", [])
                for condition in contract.get("allOf", [])
            ),
            "non-empty unique_keys must require duplicate_query",
        )

        observed_rule = next(
            (
                condition
                for condition in schema.get("allOf", [])
                if condition.get("if", {}).get("properties", {}).get("graph_type", {}).get("const") == "observed"
            ),
            None,
        )
        self.assertIsNotNone(observed_rule)
        for collection in ("nodes", "edges", "contracts"):
            status_rule = observed_rule["then"]["properties"][collection]["items"]["properties"]["status"]
            self.assertEqual(set(status_rule["not"]["enum"]), {"planned", "changed"}, collection)

        non_change_rule = next(
            condition
            for condition in schema.get("allOf", [])
            if set(condition.get("if", {}).get("properties", {}).get("graph_type", {}).get("enum", []))
            == {"observed", "target"}
        )
        not_schema = non_change_rule["then"]["not"]
        forbidden_conditions = not_schema.get("anyOf", [not_schema])
        self.assertEqual(
            {condition["required"][0] for condition in forbidden_conditions},
            {"baseline_sha", "current_sha", "diff"},
        )

        target_rule = next(
            (
                condition
                for condition in schema.get("allOf", [])
                if condition.get("if", {}).get("properties", {}).get("graph_type", {}).get("const") == "target"
            ),
            None,
        )
        self.assertIsNotNone(target_rule)
        for collection in ("nodes", "edges"):
            item_rule = target_rule["then"]["properties"][collection]["items"]  # type: ignore[index]
            planned_rule = next(
                condition
                for condition in item_rule["allOf"]
                if condition.get("if", {}).get("properties", {}).get("status", {}).get("const") == "planned"
            )
            self.assertEqual(planned_rule["then"]["properties"]["requirement_refs"].get("minItems"), 1)

    def test_schema_encodes_status_dependent_evidence_rules(self) -> None:
        schema_path = Path(__file__).parents[1] / "references" / "graph-evidence.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        def status_condition(definition: dict, status: str) -> dict:
            for condition in definition.get("allOf", []):
                status_schema = condition.get("if", {}).get("properties", {}).get("status", {})
                if status_schema.get("const") == status:
                    return condition.get("then", {})
            self.fail(f"missing {status} condition")

        audit = schema["$defs"]["auditCoverage"]
        complete_audit = status_condition(audit, "complete")
        self.assertEqual(complete_audit["properties"]["reviewers"].get("minItems"), 1)
        self.assertEqual(complete_audit["properties"]["independent_verification"].get("minItems"), 1)
        root_audit_rules = [
            condition
            for condition in schema.get("allOf", [])
            if "audit_coverage" in condition.get("if", {}).get("properties", {})
        ]
        self.assertEqual(root_audit_rules, [], "audit rules belong in $defs.auditCoverage")

        source_coverage = schema["$defs"]["sourceCoverage"]
        covered = status_condition(source_coverage, "covered")
        for field in ("requirement_refs", "ears_refs", "target_node_refs", "target_edge_refs", "ac_refs"):
            self.assertEqual(covered["properties"][field].get("minItems"), 1, field)

        for definition_name in ("node", "edge", "contract", "testChain"):
            verified = status_condition(schema["$defs"][definition_name], "verified")
            self.assertEqual(verified["properties"]["verification_evidence"].get("minItems"), 1, definition_name)

        factual_statuses = {"observed", "changed", "implemented"}
        for definition_name in ("node", "edge", "contract"):
            factual = next(
                (
                    condition["then"]
                    for condition in schema["$defs"][definition_name].get("allOf", [])
                    if set(
                        condition.get("if", {})
                        .get("properties", {})
                        .get("status", {})
                        .get("enum", [])
                    )
                    == factual_statuses
                ),
                None,
            )
            self.assertIsNotNone(factual, definition_name)
            assert factual is not None
            self.assertEqual(
                factual["properties"]["verification_evidence"].get("minItems"),
                1,
                definition_name,
            )

        review = schema["$defs"]["reviewFinding"]
        self.assertEqual(review["properties"]["evidence"].get("minItems"), 1)
        verified_review = status_condition(review, "verified")
        self.assertEqual(verified_review["properties"]["independent_verification"].get("minItems"), 1)

        coverage = schema["properties"]["coverage"]
        incomplete_condition = next(
            condition
            for condition in coverage.get("allOf", [])
            if set(condition.get("if", {}).get("properties", {}).get("status", {}).get("enum", []))
            == {"partial", "unknown"}
        )
        self.assertEqual(incomplete_condition["then"]["properties"]["limitations"].get("minItems"), 1)

        test_chain = schema["$defs"]["testChain"]["properties"]
        self.assertIn("observed", test_chain["status"]["enum"])
        self.assertEqual(test_chain["requirement_refs"].get("minItems"), 1)
        self.assertEqual(test_chain["ac_refs"].get("minItems"), 1)
        for field in ("test_node_refs", "node_refs", "edge_refs"):
            self.assertEqual(test_chain[field].get("minItems"), 1, field)
        for role in ("producer", "contract", "consumer"):
            self.assertEqual(
                test_chain["required_roles"]["properties"][role].get("minItems"),
                1,
                role,
            )
        self.assertTrue(schema["$defs"]["diff"]["properties"]["unresolved"].get("uniqueItems"))

    def test_schema_recursively_constrains_strategy_parameters(self) -> None:
        schema_path = Path(__file__).parents[1] / "references" / "graph-evidence.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        parameter_schema = schema["$defs"]["contract"]["properties"]["strategy_parameters"]
        self.assertEqual(parameter_schema, {"$ref": "#/$defs/strategyParameters"})

        root_variants = schema["$defs"]["strategyParameters"]["oneOf"]
        self.assertEqual(
            {variant.get("$ref") for variant in root_variants if "$ref" in variant},
            {"#/$defs/strategyParameterObject", "#/$defs/strategyParameterArray"},
        )
        self.assertEqual(
            {variant.get("type") for variant in root_variants if "type" in variant},
            {"string", "number"},
        )

        nested_variants = schema["$defs"]["strategyParameterValue"]["oneOf"]
        self.assertIn({"type": "boolean"}, nested_variants)
        parameter_object = schema["$defs"]["strategyParameterObject"]
        self.assertEqual(parameter_object["minProperties"], 1)
        self.assertEqual(
            parameter_object["additionalProperties"],
            {"$ref": "#/$defs/strategyParameterValue"},
        )
        parameter_array = schema["$defs"]["strategyParameterArray"]
        self.assertEqual(parameter_array["minItems"], 1)
        self.assertEqual(
            parameter_array["items"],
            {"$ref": "#/$defs/strategyParameterValue"},
        )

    def test_provider_requires_declared_capabilities_and_limitations(self) -> None:
        for field in ("capabilities", "limitations"):
            with self.subTest(field=field):
                document = valid_snapshot()
                document["provider"].update(
                    capabilities=["definitions and relationship extraction"],
                    limitations=[],
                )
                document["provider"].pop(field)

                errors = validate_document(document)

                self.assertTrue(any(f"provider.{field}" in error for error in errors), errors)

        document = valid_snapshot()
        document["provider"].update(capabilities=[], limitations=[])
        errors = validate_document(document)
        self.assertTrue(any("provider.capabilities" in error and "non-empty" in error for error in errors), errors)

        schema_path = Path(__file__).parents[1] / "references" / "graph-evidence.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        provider = schema["$defs"]["provider"]
        self.assertTrue({"capabilities", "limitations"}.issubset(provider["required"]))
        self.assertEqual(provider["properties"]["capabilities"].get("minItems"), 1)

        document = valid_snapshot()
        document["provider"]["generated_at"] = "not-a-timestamp"
        errors = validate_document(document)
        self.assertTrue(any("provider.generated_at" in error and "RFC3339" in error for error in errors), errors)

        self.assertEqual(provider["properties"]["generated_at"].get("format"), "date-time")

    def test_observed_and_change_graphs_reject_planned_current_objects(self) -> None:
        observed = valid_snapshot()
        observed["test_chains"][0]["status"] = "planned"
        observed_errors = validate_document(observed)
        self.assertTrue(
            any("observed graph" in error and "planned" in error for error in observed_errors),
            observed_errors,
        )

        for collection in ("nodes", "edges", "contracts", "test_chains"):
            with self.subTest(collection=collection):
                change = change_snapshot()
                change[collection][0]["status"] = "planned"
                change_errors = validate_document(change)
                label = f"{collection}[0]"
                self.assertTrue(
                    any(label in error and "change graph" in error and "planned" in error for error in change_errors),
                    change_errors,
                )

    def test_factual_test_chains_require_evidence_matching_declared_kind(self) -> None:
        for status in ("observed", "implemented"):
            with self.subTest(status=status):
                document = valid_snapshot()
                chain = document["test_chains"][0]
                chain.update(
                    status=status,
                    evidence_kind="static",
                    static_evidence=[],
                    runtime_evidence=[],
                    verification_evidence=[],
                )

                errors = validate_document(document)

                self.assertTrue(any(f"{status} requires verification_evidence" in error for error in errors), errors)
                self.assertTrue(any("static evidence kind requires static_evidence" in error for error in errors), errors)

        document = valid_snapshot()
        chain = document["test_chains"][0]
        chain.update(evidence_kind="mixed", static_evidence=[])
        errors = validate_document(document)
        self.assertTrue(any("mixed evidence kind requires static_evidence" in error for error in errors), errors)

    def test_state_and_enum_roles_stay_inside_contract_closure(self) -> None:
        mutations = (
            ("state producer", lambda c: c["state_producers"].__setitem__("active", ["fn:src/reader.py:read_items"])),
            ("state consumer", lambda c: c["state_consumers"].__setitem__("active", ["fn:src/writer.py:write_item"])),
            ("enum producer", lambda c: c["enum_producers"].__setitem__("active", ["fn:src/reader.py:read_items"])),
            ("enum consumer", lambda c: c["enum_consumers"].__setitem__("active", ["fn:src/writer.py:write_item"])),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                document = valid_snapshot()
                mutate(document["contracts"][0])

                errors = validate_document(document)

                self.assertTrue(any(f"{label} is outside contract closure" in error for error in errors), errors)

    def test_rejected_review_requires_explicit_premise_verification(self) -> None:
        document = valid_snapshot()
        document["review_findings"] = [
            {
                "finding_id": "F-REJECTED",
                "status": "rejected",
                "evidence": ["reviewer report"],
            }
        ]
        errors = validate_document(document)
        self.assertTrue(any("rejected requires premises" in error for error in errors), errors)

        document["review_findings"][0]["premises"] = ["duplicate rows are impossible"]
        errors = validate_document(document)
        self.assertTrue(any("premise_verification" in error for error in errors), errors)

        document["review_findings"][0]["premise_verification"] = ["independent query disproved the premise"]
        self.assertEqual(validate_document(document), [])

    def test_implementation_state_cannot_claim_unimplemented_as_implemented(self) -> None:
        for status in ("implemented", "verified"):
            with self.subTest(status=status):
                document = valid_snapshot()
                document["contracts"][0]["status"] = status
                document["contracts"][0]["implementation_state"] = "unimplemented"
                errors = validate_document(document)
                self.assertTrue(any("implementation_state" in error and "unimplemented" in error for error in errors), errors)

    def test_current_graph_objects_cannot_use_removed_status(self) -> None:
        for collection in ("nodes", "edges", "contracts"):
            with self.subTest(collection=collection):
                document = valid_snapshot()
                document[collection][0]["status"] = "removed"
                errors = validate_document(document)
                self.assertTrue(
                    any("removed" in error and "diff.removed" in error for error in errors),
                    errors,
                )

    def test_repository_sha_must_match_snapshot_and_change_current_sha(self) -> None:
        snapshot = valid_snapshot()
        snapshot["repository"]["git_sha"] = "b" * 40
        snapshot_errors = validate_document(snapshot)
        self.assertTrue(any("repository.git_sha" in error for error in snapshot_errors), snapshot_errors)

        change = change_snapshot()
        change["repository"]["git_sha"] = "c" * 40
        change_errors = validate_document(change)
        self.assertTrue(any("repository.git_sha" in error and "current_sha" in error for error in change_errors), change_errors)

    def test_node_and_edge_ids_cannot_collide(self) -> None:
        document = valid_snapshot()
        document["edges"][0]["edge_id"] = document["nodes"][0]["node_id"]
        errors = validate_document(document)
        self.assertTrue(any("both a node and an edge" in error for error in errors), errors)

    def test_change_diff_categories_are_disjoint(self) -> None:
        document = change_snapshot()
        node_id = document["nodes"][0]["node_id"]
        document["diff"]["changed_nodes"] = [node_id]
        errors = validate_document(document)
        self.assertTrue(any("multiple node change categories" in error for error in errors), errors)

    def test_change_diff_lists_all_unresolved_current_objects(self) -> None:
        document = change_snapshot()
        document["edges"].append(unresolved_dynamic_edge(document))
        errors = validate_document(document)
        self.assertTrue(any("diff.unresolved omits" in error for error in errors), errors)

    def test_blocked_and_unresolved_chains_require_reason_and_recovery(self) -> None:
        blocked = valid_snapshot()
        blocked_chain = blocked["test_chains"][0]
        blocked_chain["status"] = "blocked"
        blocked_chain["blocked_reason"] = "runtime environment is unavailable"
        blocked_errors = validate_document(blocked)
        self.assertTrue(any("blocked requires next_query" in error for error in blocked_errors), blocked_errors)

        unresolved = valid_snapshot()
        unresolved_chain = unresolved["test_chains"][0]
        unresolved_chain["status"] = "unresolved"
        unresolved_chain["next_query"] = "run the integration trace"
        unresolved_errors = validate_document(unresolved)
        self.assertTrue(any("unresolved requires unresolved_reason" in error for error in unresolved_errors), unresolved_errors)

    def test_non_l0_chain_requires_a_declared_error_role(self) -> None:
        document = valid_snapshot()
        document["test_chains"][0]["required_roles"]["error_path"] = []
        errors = validate_document(document)
        self.assertTrue(any("error_path role is required" in error for error in errors), errors)

    def test_error_path_refs_must_belong_to_the_chain(self) -> None:
        document = valid_snapshot()
        unrelated = {
            **document["nodes"][0],
            "node_id": "fn:src/unrelated.py:unrelated",
            "path": "src/unrelated.py",
            "qualified_symbol": "unrelated",
            "source_anchor": {"path": "src/unrelated.py", "start_line": 1, "end_line": 1},
            "entrypoint": True,
            "test_refs": [],
        }
        document["nodes"].append(unrelated)
        chain = document["test_chains"][0]
        chain["required_roles"]["error_path"] = [unrelated["node_id"]]
        chain["error_path_refs"] = [unrelated["node_id"]]
        errors = validate_document(document)
        self.assertTrue(any("error_path_refs is not part of the chain" in error for error in errors), errors)

    def test_error_path_role_cannot_be_satisfied_by_a_normal_edge(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][0]
        error_test = "test:tests/test_items.py:test_write_error"
        error_validation = "validates:test:error->fn:writer"
        normal_edge = "writes:fn:src/writer.py:write_item->table:items"
        chain["test_node_refs"] = [ref for ref in chain["test_node_refs"] if ref != error_test]
        chain["edge_refs"] = [ref for ref in chain["edge_refs"] if ref != error_validation]
        chain["required_roles"]["error_path"] = [normal_edge]
        chain["error_path_refs"] = [normal_edge]

        errors = validate_document(document)

        self.assertTrue(any("error_path role must reference a declared node" in error for error in errors), errors)

    def test_verified_chain_discloses_relevant_unresolved_edges(self) -> None:
        document = valid_snapshot()
        document["edges"].append(unresolved_dynamic_edge(document))
        errors = validate_document(document)
        self.assertTrue(any("omits relevant unresolved edge" in error for error in errors), errors)

    def test_terminal_states_still_require_a_producer(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["terminal_states"] = ["archived"]
        contract["state_producers"]["archived"] = []
        errors = validate_document(document)
        self.assertTrue(any("state has no producer" in error for error in errors), errors)

    def test_evidence_rejects_sentinels_and_invisible_controls(self) -> None:
        invalid_values = (
            ".",
            "-",
            "?",
            "N/A",
            "none",
            "无",
            "见上",
            "no evidence",
            "not run",
            "not verified",
            "no independent verification",
            "no evidence available",
            "not run because environment is unavailable",
            "无证据",
            "未验证",
            "x",
            "\u200b ok",
            "\x08 ok",
            "\x1b[31m",
            "<command>",
            "ＴＯＤＯ",
            "ＴＢＤ",
            "Ｎ／Ａ",
            "ＮＯＮＥ",
            "ok",
            "PASS",
            "done",
            "works",
            "verified",
            "success",
            "正常",
            "通过",
            "完成",
            "已验证",
        )
        for value in invalid_values:
            with self.subTest(value=value):
                document = valid_snapshot()
                document["contracts"][0]["runtime_evidence"] = [value]
                errors = validate_document(document)
                self.assertTrue(any("evidence" in error or "placeholder" in error for error in errors), errors)

    def test_negative_attestations_cannot_satisfy_evidence_fields(self) -> None:
        node_document = valid_snapshot()
        node_document["nodes"][0]["verification_evidence"] = ["no evidence"]
        self.assertTrue(
            any("verification_evidence" in error for error in validate_document(node_document))
        )

        chain_document = valid_snapshot()
        chain_document["test_chains"][0]["runtime_evidence"] = ["not run"]
        chain_document["test_chains"][0]["verification_evidence"] = ["not verified"]
        self.assertTrue(
            any("runtime_evidence" in error for error in validate_document(chain_document))
        )

        review_document = valid_snapshot()
        review_document["review_findings"] = [
            {
                "finding_id": "FIND-01",
                "status": "verified",
                "evidence": ["review source query"],
                "independent_verification": ["no independent verification"],
            }
        ]
        self.assertTrue(
            any("independent_verification" in error for error in validate_document(review_document))
        )

    def test_evidence_rejects_boundary_whitespace(self) -> None:
        document = valid_snapshot()
        document["nodes"][0]["verification_evidence"] = [" evidence with boundary whitespace "]

        errors = validate_document(document)

        self.assertTrue(
            any("verification_evidence" in error and "whitespace" in error for error in errors),
            errors,
        )

    def test_verified_review_requires_distinct_independent_evidence(self) -> None:
        document = valid_snapshot()
        document["review_findings"] = [
            {
                "finding_id": "FIND-01",
                "status": "verified",
                "evidence": ["same reviewer report"],
                "independent_verification": ["same reviewer report"],
            }
        ]

        errors = validate_document(document)

        self.assertTrue(
            any("independent_verification" in error and "distinct" in error for error in errors),
            errors,
        )

    def test_verified_review_rejects_unicode_equivalent_independent_evidence(self) -> None:
        equivalent_pairs = (
            ("graph query", "Ｇｒａｐｈ　ｑｕｅｒｙ"),
            ("caf\u00e9 query", "cafe\u0301 query"),
            ("graph query", "graph\u00a0query"),
        )
        for evidence, independent_verification in equivalent_pairs:
            with self.subTest(independent_verification=independent_verification):
                document = valid_snapshot()
                document["review_findings"] = [
                    {
                        "finding_id": "FIND-UNICODE",
                        "status": "verified",
                        "evidence": [evidence],
                        "independent_verification": [independent_verification],
                    }
                ]

                errors = validate_document(document)

                self.assertTrue(
                    any(
                        "independent_verification" in error and "distinct" in error
                        for error in errors
                    ),
                    errors,
                )

    def test_incomplete_audit_cannot_support_a_rejected_absence_finding(self) -> None:
        document = valid_snapshot()
        document["audit_coverage"].update(
            status="inconclusive",
            limitations=["audit rate limit prevented full coverage"],
        )
        document["review_findings"] = [
            {
                "finding_id": "F-ABSENCE",
                "status": "rejected",
                "evidence": ["candidate missing consumer"],
                "premises": ["missing-consumer"],
                "premise_verification": ["audited subset search found no missing consumer"],
            }
        ]

        errors = validate_document(document)

        self.assertTrue(
            any("inconclusive" in error and "rejected" in error for error in errors),
            errors,
        )

    def test_contract_io_roles_reject_storage_kind_nodes_as_code(self) -> None:
        document = valid_snapshot()
        document["nodes"][0]["kind"] = "table"

        errors = validate_document(document)

        self.assertTrue(
            any("writer" in error and "storage" in error for error in errors),
            errors,
        )

    def test_verified_contract_cannot_depend_on_blocked_or_unresolved_io(self) -> None:
        for dependency in ("writer_edge", "reader_edge", "writer_node", "reader_node", "storage_node"):
            with self.subTest(dependency=dependency):
                document = valid_snapshot()
                # Keep the chain status observational so this test isolates contract closure.
                for chain in document["test_chains"]:
                    chain.update(
                        status="observed",
                        evidence_kind="runtime",
                        runtime_evidence=["observed runtime result"],
                        verification_evidence=["observed chain result"],
                    )
                document["contracts"][0]["status"] = "verified"
                if dependency == "writer_edge":
                    item = document["edges"][0]
                elif dependency == "reader_edge":
                    item = document["edges"][1]
                elif dependency == "writer_node":
                    item = document["nodes"][0]
                elif dependency == "reader_node":
                    item = document["nodes"][2]
                else:
                    item = document["nodes"][1]
                item.update(
                    status="blocked",
                    blocked_reason="dependency is blocked",
                    next_query="query dependency",
                )

                errors = validate_document(document)

                self.assertTrue(
                    any("verified contract" in error and "blocked" in error for error in errors),
                    errors,
                )

    def test_contract_io_roles_must_reference_code_nodes(self) -> None:
        document = valid_snapshot()
        test_node_id = "test:fake-writer"
        document["nodes"].append(
            {
                **document["nodes"][0],
                "node_id": test_node_id,
                "kind": "test",
                "path": "tests/test_items.py",
                "qualified_symbol": "fake_writer",
                "source_anchor": {"path": "tests/test_items.py", "start_line": 1, "end_line": 1},
                "entrypoint": True,
            }
        )
        document["edges"].append(
            {
                **document["edges"][0],
                "edge_id": f"writes:{test_node_id}->table:items",
                "from": test_node_id,
                "to": "table:items",
                "source_anchor": {"path": "tests/test_items.py", "start_line": 1, "end_line": 1},
            }
        )
        document["contracts"][0]["writers"].append(test_node_id)

        errors = validate_document(document)

        self.assertTrue(any("writer must reference code nodes" in error for error in errors), errors)

    def test_storage_kind_must_match_a_known_storage_node_kind(self) -> None:
        document = valid_snapshot()
        document["nodes"][1]["kind"] = "mystery"

        errors = validate_document(document)

        self.assertTrue(any("storage_kind" in error and "storage node kind" in error for error in errors), errors)

    def test_graph_entity_ids_cannot_collide_across_collections(self) -> None:
        for collection in ("contracts", "test_chains"):
            with self.subTest(collection=collection):
                document = valid_snapshot()
                field = "contract_id" if collection == "contracts" else "chain_id"
                document[collection][0][field] = document["nodes"][0]["node_id"]

                errors = validate_document(document)

                self.assertTrue(any("identifier collision" in error for error in errors), errors)

    def test_coverage_requires_paths_and_incomplete_status_limitations(self) -> None:
        empty_paths = valid_snapshot()
        empty_paths["coverage"]["paths"] = []
        path_errors = validate_document(empty_paths)
        self.assertTrue(any("coverage.paths must be non-empty" in error for error in path_errors), path_errors)

        partial = valid_snapshot()
        partial["coverage"]["status"] = "partial"
        partial["coverage"]["limitations"] = []
        partial_errors = validate_document(partial)
        self.assertTrue(any("partial or unknown requires limitations" in error for error in partial_errors), partial_errors)

    def test_coverage_paths_are_normalized_unique_and_disjoint(self) -> None:
        duplicate = valid_snapshot()
        duplicate["coverage"]["paths"] = ["src", "src/"]
        duplicate_errors = validate_document(duplicate)
        self.assertTrue(any("duplicate paths" in error for error in duplicate_errors), duplicate_errors)

        overlap = valid_snapshot()
        overlap["coverage"]["excluded_paths"] = ["./src/"]
        overlap_errors = validate_document(overlap)
        self.assertTrue(any("both included and excluded" in error for error in overlap_errors), overlap_errors)

    def test_coverage_paths_bound_graph_and_source_evidence(self) -> None:
        outside_scope = valid_snapshot()
        outside_scope["coverage"]["paths"] = ["src"]
        scope_errors = validate_document(outside_scope)
        self.assertTrue(any("outside coverage.paths" in error for error in scope_errors), scope_errors)

        excluded = valid_snapshot()
        excluded["coverage"]["excluded_paths"] = ["tests"]
        excluded_errors = validate_document(excluded)
        self.assertTrue(any("inside coverage.excluded_paths" in error for error in excluded_errors), excluded_errors)

        edge_anchor = valid_snapshot()
        edge_anchor["edges"][0]["source_anchor"]["path"] = "other/outside.py"
        edge_errors = validate_document(edge_anchor)
        self.assertTrue(any("edges[0] source_anchor.path" in error and "coverage.paths" in error for error in edge_errors), edge_errors)

        source_anchor = valid_snapshot()
        source_anchor["source_coverage"][0]["source_anchor"]["path"] = "other/design.md"
        source_errors = validate_document(source_anchor)
        self.assertTrue(any("source_coverage[0] source_anchor.path" in error and "coverage.paths" in error for error in source_errors), source_errors)

    def test_source_coverage_refs_must_link_to_declared_targets_and_chains(self) -> None:
        unknown_requirement = valid_snapshot("target")
        unknown_requirement["source_coverage"][0]["requirement_refs"] = ["REQ-UNKNOWN"]
        requirement_errors = validate_document(unknown_requirement)
        self.assertTrue(any("source_coverage[0] requirement_refs" in error and "linked" in error for error in requirement_errors), requirement_errors)

        unknown_ac = valid_snapshot("target")
        unknown_ac["source_coverage"][0]["ac_refs"] = ["M999-DONE-01"]
        ac_errors = validate_document(unknown_ac)
        self.assertTrue(any("source_coverage[0] ac_refs" in error and "linked" in error for error in ac_errors), ac_errors)

        unrelated_requirement = valid_snapshot("target")
        section = unrelated_requirement["source_coverage"][0]
        section["target_node_refs"] = ["fn:src/writer.py:write_item"]
        section["target_edge_refs"] = ["writes:fn:src/writer.py:write_item->table:items"]
        section["requirement_refs"] = ["REQ-OTHER"]
        unrelated_requirement["nodes"][2]["requirement_refs"] = ["REQ-OTHER"]
        unrelated_errors = validate_document(unrelated_requirement)
        self.assertTrue(any("source_coverage[0] requirement_refs" in error and "linked" in error for error in unrelated_errors), unrelated_errors)

        unrelated_ac = valid_snapshot("target")
        unrelated_ac["nodes"].append(
            {
                "node_id": "fn:src/unrelated.py:unrelated",
                "kind": "function",
                "status": "planned",
                "path": "src/unrelated.py",
                "qualified_symbol": "unrelated",
                "source_anchor": None,
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "confidence": 1.0,
                "coverage": "complete",
                "freshness": "current",
                "verification_evidence": [],
                "requirement_refs": ["REQ-UNRELATED"],
                "entrypoint": True,
            }
        )
        unrelated_ac["edges"].append(
            {
                "edge_id": "calls:fn:src/unrelated.py:unrelated->fn:src/unrelated.py:unrelated",
                "kind": "calls",
                "from": "fn:src/unrelated.py:unrelated",
                "to": "fn:src/unrelated.py:unrelated",
                "status": "planned",
                "provider": "code-review-graph",
                "git_sha": "a" * 40,
                "source_anchor": None,
                "confidence": 1.0,
                "coverage": "complete",
                "freshness": "current",
                "verification_evidence": [],
                "requirement_refs": ["REQ-UNRELATED"],
            }
        )
        section = unrelated_ac["source_coverage"][0]
        section["target_node_refs"] = ["fn:src/unrelated.py:unrelated"]
        section["target_edge_refs"] = [
            "calls:fn:src/unrelated.py:unrelated->fn:src/unrelated.py:unrelated"
        ]
        section["requirement_refs"] = ["REQ-UNRELATED"]
        unrelated_ac_errors = validate_document(unrelated_ac)
        self.assertTrue(any("source_coverage[0] ac_refs" in error and "linked" in error for error in unrelated_ac_errors), unrelated_ac_errors)

    def test_graph_requirement_and_ac_refs_must_be_declared_by_source_coverage(self) -> None:
        mutations = (
            (
                "node requirement",
                lambda document: document["nodes"][0]["requirement_refs"].append("REQ-FAKE"),
                "nodes[0].requirement_refs references requirement not declared by source_coverage: REQ-FAKE",
            ),
            (
                "edge requirement",
                lambda document: document["edges"][0]["requirement_refs"].append("REQ-FAKE"),
                "edges[0].requirement_refs references requirement not declared by source_coverage: REQ-FAKE",
            ),
            (
                "test-chain requirement",
                lambda document: document["test_chains"][0]["requirement_refs"].append("REQ-FAKE"),
                "test_chains[0].requirement_refs references requirement not declared by source_coverage: REQ-FAKE",
            ),
            (
                "test-chain AC",
                lambda document: document["test_chains"][0]["ac_refs"].append("M9-DONE-FAKE"),
                "test_chains[0].ac_refs references AC not declared by source_coverage: M9-DONE-FAKE",
            ),
        )

        for label, mutate, expected in mutations:
            with self.subTest(label=label):
                document = valid_snapshot("target")
                mutate(document)

                errors = validate_document(document)

                self.assertIn(expected, errors)

    def test_source_coverage_edge_refs_include_both_endpoint_nodes(self) -> None:
        document = valid_snapshot()
        section = document["source_coverage"][0]
        section["target_node_refs"].remove("fn:src/reader.py:read_items")
        errors = validate_document(document)
        self.assertTrue(
            any(
                "target_edge_refs endpoint is missing from target_node_refs" in error
                and "fn:src/reader.py:read_items" in error
                for error in errors
            ),
            errors,
        )

    def test_duplicate_semantic_values_and_references_are_rejected(self) -> None:
        mutations = (
            ("state_values", lambda d: d["contracts"][0].__setitem__("state_values", ["active", "active"])),
            (
                "enum_values",
                lambda d: d["contracts"][0].update(
                    enum_values=["active", "active"],
                    schema_enum_values=["active", "active"],
                ),
            ),
            (
                "writers",
                lambda d: d["contracts"][0].__setitem__(
                    "writers",
                    [d["nodes"][0]["node_id"], d["nodes"][0]["node_id"]],
                ),
            ),
            (
                "source refs",
                lambda d: d["source_coverage"][0].__setitem__(
                    "target_node_refs",
                    [d["nodes"][0]["node_id"], d["nodes"][0]["node_id"]],
                ),
            ),
        )
        for label, mutation in mutations:
            with self.subTest(label=label):
                document = valid_snapshot()
                mutation(document)
                errors = validate_document(document)
                self.assertTrue(any("duplicate" in error for error in errors), errors)

    def test_strategy_fields_require_a_nonempty_strategy_name(self) -> None:
        for fields in (
            {"strategy_status": "ready"},
            {"strategy_parameters": {"rate": 0.5}},
            {"strategy_name": "", "strategy_status": "blocked", "strategy_blocking_reason": "not approved"},
        ):
            with self.subTest(fields=fields):
                document = valid_snapshot()
                document["contracts"][0].update(fields)
                errors = validate_document(document)
                self.assertTrue(any("strategy_name" in error for error in errors), errors)

    def test_recovery_ownership_and_reviewer_fields_reject_placeholders(self) -> None:
        mutations = (
            lambda d: d["nodes"][0].update(status="blocked", blocked_reason="TODO", next_query="TODO"),
            lambda d: d["source_coverage"][0].update(owner_task="<owner>"),
            lambda d: d["audit_coverage"].update(reviewers=["TBD"]),
            lambda d: d["coverage"].update(status="partial", limitations=["待定"]),
        )
        for mutation in mutations:
            document = valid_snapshot()
            mutation(document)
            errors = validate_document(document)
            self.assertTrue(any("placeholder" in error or "requires" in error for error in errors), errors)

    def test_observed_graph_rejects_planned_and_changed_object_statuses(self) -> None:
        for collection in ("nodes", "edges", "contracts"):
            for status in ("planned", "changed"):
                with self.subTest(collection=collection, status=status):
                    document = valid_snapshot()
                    document[collection][0]["status"] = status
                    errors = validate_document(document)
                    self.assertTrue(any("observed graph" in error.lower() for error in errors), errors)

    def test_node_source_anchor_path_matches_node_path(self) -> None:
        document = valid_snapshot()
        document["nodes"][0]["source_anchor"]["path"] = "src/ghost.py"
        errors = validate_document(document)
        self.assertTrue(any("source_anchor.path must match node path" in error for error in errors), errors)

    def test_sql_unique_keys_require_duplicate_query(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["storage_kind"] = "sql_table"
        contract["unique_keys"] = ["id"]
        contract["foreign_key_check"] = "PRAGMA foreign_key_check"
        errors = validate_document(document)
        self.assertTrue(any("unique keys require duplicate_query" in error for error in errors), errors)

    def test_sql_integrity_commands_require_separate_result_evidence(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract.update(
            {
                "storage_kind": "sql_table",
                "foreign_key_check": "PRAGMA foreign_key_check;",
                "foreign_key_check_result": ["zero foreign-key violation rows"],
            }
        )
        self.assertEqual(validate_document(document), [])

        contract["foreign_key_check"] = "Do not run PRAGMA foreign_key_check."
        errors = validate_document(document)
        self.assertTrue(any("executable PRAGMA foreign_key_check" in error for error in errors), errors)

        contract["foreign_key_check"] = "PRAGMA main.foreign_key_check(items);"
        contract["foreign_key_check_result"] = []
        errors = validate_document(document)
        self.assertTrue(any("foreign_key_check_result" in error and "non-empty" in error for error in errors), errors)

        contract["foreign_key_check_result"] = ["zero foreign-key violation rows"]
        contract["unique_keys"] = ["id"]
        contract["duplicate_query"] = (
            "SELECT id, COUNT(*) FROM items GROUP BY id HAVING COUNT(*) > 1;"
        )
        contract["duplicate_query_result"] = ["zero duplicate groups"]
        self.assertEqual(validate_document(document), [])

        contract["duplicate_query"] = "Do not run the duplicate SELECT."
        errors = validate_document(document)
        self.assertTrue(any("executable SELECT or WITH query" in error for error in errors), errors)

        contract["duplicate_query"] = (
            "SELECT id, COUNT(*) FROM items GROUP BY id HAVING COUNT(*) > 1;"
        )
        contract["duplicate_query_result"] = []
        errors = validate_document(document)
        self.assertTrue(any("duplicate_query_result" in error and "non-empty" in error for error in errors), errors)

    def test_duplicate_query_rejects_multiple_statements(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["unique_keys"] = ["id"]
        contract["duplicate_query"] = "SELECT id FROM items; DROP TABLE items;"
        contract["duplicate_query_result"] = ["zero duplicate groups"]

        errors = validate_document(document)

        self.assertTrue(any("single" in error or "duplicate_query" in error for error in errors), errors)

    def test_storage_kind_must_match_an_unambiguous_storage_node_kind(self) -> None:
        document = valid_snapshot()
        document["contracts"][0]["storage_kind"] = "other"
        errors = validate_document(document)
        self.assertTrue(any("storage_kind does not match" in error for error in errors), errors)

    def test_schema_requires_sql_integrity_result_evidence(self) -> None:
        schema_path = Path(__file__).parents[1] / "references" / "graph-evidence.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        contract = schema["$defs"]["contract"]

        for field in ("foreign_key_check_result", "duplicate_query_result"):
            self.assertEqual(
                contract["properties"].get(field, {}).get("$ref"),
                "#/$defs/evidence",
                field,
            )

        sql_rule = next(
            rule
            for rule in contract["allOf"]
            if rule.get("if", {}).get("properties", {}).get("storage_kind", {}).get("const")
            == "sql_table"
        )
        self.assertEqual(
            set(sql_rule["then"]["required"]),
            {"foreign_key_check", "foreign_key_check_result"},
        )

        unique_rule = next(
            rule
            for rule in contract["allOf"]
            if rule.get("if", {}).get("properties", {}).get("unique_keys", {}).get("minItems")
            == 1
        )
        self.assertEqual(
            set(unique_rule["then"]["required"]),
            {"duplicate_query", "duplicate_query_result"},
        )

    def test_placeholder_text_cannot_satisfy_provenance_semantics_or_actions(self) -> None:
        mutations = (
            ("repository root", lambda d: d["repository"].__setitem__("root", "<root>")),
            ("provider command", lambda d: d["provider"].__setitem__("command", "<command>")),
            ("coverage path", lambda d: d["coverage"].__setitem__("paths", ["TODO"])),
            ("source section", lambda d: d["source_coverage"][0].__setitem__("source_section_id", "TBD")),
            (
                "node path",
                lambda d: (
                    d["nodes"][0].__setitem__("path", "<path>"),
                    d["nodes"][0]["source_anchor"].__setitem__("path", "<path>"),
                ),
            ),
            ("node symbol", lambda d: d["nodes"][0].__setitem__("qualified_symbol", "TODO")),
            ("state semantics", lambda d: d["contracts"][0]["state_semantics"].__setitem__("active", "TODO")),
            ("test command", lambda d: d["test_chains"][0].__setitem__("command", "TODO")),
            ("expected output", lambda d: d["test_chains"][0].__setitem__("expected_output", "TBD")),
        )
        for label, mutation in mutations:
            with self.subTest(label=label):
                document = valid_snapshot()
                mutation(document)
                errors = validate_document(document)
                self.assertTrue(any("placeholder" in error for error in errors), errors)

        deferred_state = valid_snapshot()
        deferred_state["contracts"][0]["state_consumers"]["archived"] = []
        deferred_state["contracts"][0]["state_deferred_milestones"] = {"archived": "TODO"}
        deferred_errors = validate_document(deferred_state)
        self.assertTrue(any("placeholder" in error for error in deferred_errors), deferred_errors)

        change = change_snapshot()
        change["diff"]["impact"] = ["TODO"]
        change_errors = validate_document(change)
        self.assertTrue(any("placeholder" in error for error in change_errors), change_errors)

    def test_nested_strategy_parameters_reject_placeholders_without_recursion(self) -> None:
        document = valid_snapshot()
        contract = document["contracts"][0]
        contract.update(
            strategy_name="exponential",
            strategy_status="ready",
            strategy_parameters={"rate": {"value": "TODO"}},
            strategy_trigger="item is reviewed",
            strategy_target="items.next_review",
            strategy_entrypoint="src/writer.py:write_item",
        )
        errors = validate_document(document)
        self.assertTrue(any("strategy_parameters" in error and "placeholder" in error for error in errors), errors)

        deep_parameters: object = 1.0
        for _ in range(1200):
            deep_parameters = {"nested": deep_parameters}
        contract["strategy_parameters"] = deep_parameters
        deep_errors = validate_document(document)
        self.assertEqual(deep_errors, [])

    def test_ready_strategy_parameters_reject_nested_empty_values(self) -> None:
        invalid_parameters = (
            {"rate": None},
            {"rate": ""},
            {"rate": []},
            {"rate": {}},
            {"rate": {"value": None}},
            [None],
            [[]],
            [{"rate": ""}],
        )
        for parameters in invalid_parameters:
            with self.subTest(parameters=parameters):
                document = valid_snapshot()
                document["contracts"][0].update(
                    strategy_name="exponential",
                    strategy_status="ready",
                    strategy_parameters=parameters,
                    strategy_trigger="item is reviewed",
                    strategy_target="items.next_review",
                    strategy_entrypoint="src/writer.py:write_item",
                )

                errors = validate_document(document)

                self.assertTrue(any("strategy_parameters" in error for error in errors), errors)

    def test_strategy_parameters_reject_boundary_whitespace_recursively(self) -> None:
        invalid_parameters = (
            " padded ",
            {"rate": " 0.9 "},
            {" rate ": 0.9},
            [{"nested": "value "}],
        )
        for parameters in invalid_parameters:
            with self.subTest(parameters=parameters):
                document = valid_snapshot()
                document["contracts"][0].update(
                    strategy_name="exponential",
                    strategy_status="ready",
                    strategy_parameters=parameters,
                    strategy_trigger="item is reviewed",
                    strategy_target="items.next_review",
                    strategy_entrypoint="src/writer.py:write_item",
                )

                errors = validate_document(document)

                self.assertTrue(any("strategy_parameters" in error for error in errors), errors)

    def test_nested_boolean_strategy_parameter_is_concrete(self) -> None:
        document = valid_snapshot()
        document["contracts"][0].update(
            strategy_name="exponential",
            strategy_status="ready",
            strategy_parameters={"jitter": False, "limits": [0, 3]},
            strategy_trigger="item is reviewed",
            strategy_target="items.next_review",
            strategy_entrypoint="src/writer.py:write_item",
        )

        self.assertEqual(validate_document(document), [])

    def test_test_chain_entrypoint_must_connect_to_a_validation_edge(self) -> None:
        document = valid_snapshot()
        detached = {
            **document["nodes"][3],
            "node_id": "test:tests/test_items.py:test_detached_entrypoint",
            "qualified_symbol": "test_detached_entrypoint",
        }
        document["nodes"].append(detached)
        chain = document["test_chains"][0]
        chain["entrypoint_node_id"] = detached["node_id"]
        chain["test_node_refs"].append(detached["node_id"])
        errors = validate_document(document)
        self.assertTrue(any("entrypoint" in error and "validates edge" in error for error in errors), errors)

    def test_test_chain_edges_must_stay_inside_declared_chain_nodes(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][0]
        outside = {
            **document["nodes"][0],
            "node_id": "fn:src/outside.py:outside",
            "path": "src/outside.py",
            "qualified_symbol": "outside",
            "source_anchor": {"path": "src/outside.py", "start_line": 1, "end_line": 2},
        }
        document["nodes"].append(outside)
        edge = {
            **document["edges"][-1],
            "edge_id": "validates:test:happy->fn:outside",
            "from": chain["entrypoint_node_id"],
            "to": outside["node_id"],
        }
        document["edges"].append(edge)
        chain["edge_refs"].append(edge["edge_id"])

        errors = validate_document(document)
        self.assertTrue(any("edge endpoint is outside the declared chain" in error for error in errors), errors)

    def test_test_chain_entrypoint_must_reach_all_required_role_nodes(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][0]
        happy, error = chain["test_node_refs"]
        unrelated = {
            **document["nodes"][0],
            "node_id": "fn:src/unrelated.py:unrelated",
            "path": "src/unrelated.py",
            "qualified_symbol": "unrelated",
            "source_anchor": {"path": "src/unrelated.py", "start_line": 1, "end_line": 2},
        }
        document["nodes"].append(unrelated)
        chain["node_refs"].append(unrelated["node_id"])

        prototype = next(
            edge
            for edge in document["edges"]
            if edge["edge_id"] == "validates:test:error->fn:writer"
        )
        for edge_id, target in (
            ("validates:test:error->table:items", "table:items"),
            ("validates:test:error->fn:reader", "fn:src/reader.py:read_items"),
            ("validates:test:happy->fn:unrelated", unrelated["node_id"]),
        ):
            edge = {**prototype, "edge_id": edge_id, "to": target}
            if edge_id == "validates:test:happy->fn:unrelated":
                edge["from"] = happy
            else:
                edge["from"] = error
            document["edges"].append(edge)
            chain["edge_refs"].append(edge_id)
        chain["edge_refs"] = [
            ref
            for ref in chain["edge_refs"]
            if ref
            not in {
                "validates:test:happy->fn:writer",
                "validates:test:happy->table:items",
                "validates:test:happy->fn:reader",
            }
        ]

        errors = validate_document(document)
        self.assertTrue(any("entrypoint cannot reach required role node" in error for error in errors), errors)

    def test_verified_chain_cannot_rely_on_planned_role_nodes(self) -> None:
        document = valid_snapshot("target")
        chain = document["test_chains"][0]
        chain.update(
            status="verified",
            evidence_kind="runtime",
            runtime_evidence=["runtime output"],
            verification_evidence=["verified runtime output"],
        )

        errors = validate_document(document)

        self.assertTrue(
            any("verified" in error and "planned" in error for error in errors),
            errors,
        )

    def test_verified_chain_cannot_rely_on_blocked_or_unresolved_role_nodes(self) -> None:
        for status, recovery in (
            ("blocked", {"blocked_reason": "dependency is unavailable", "next_query": "run the dependency check"}),
            ("unresolved", {"unresolved_reason": "dispatch is unresolved", "next_query": "run the dispatch trace"}),
        ):
            with self.subTest(status=status):
                document = valid_snapshot()
                document["nodes"][0].update(status=status, **recovery)

                errors = validate_document(document)

                self.assertTrue(
                    any("verified" in error and status in error for error in errors),
                    errors,
                )

    def test_verified_chain_cannot_rely_on_blocked_or_unresolved_contracts(self) -> None:
        for status, recovery in (
            ("blocked", {"blocked_reason": "contract is unavailable", "next_query": "inspect the contract"}),
            ("unresolved", {"unresolved_reason": "contract is unresolved", "next_query": "trace the contract"}),
        ):
            with self.subTest(status=status):
                document = valid_snapshot()
                document["contracts"][0].update(status=status, **recovery)

                errors = validate_document(document)

                self.assertTrue(
                    any("verified chain" in error and status in error for error in errors),
                    errors,
                )

    def test_verified_chain_cannot_rely_on_blocked_or_planned_edges(self) -> None:
        document = valid_snapshot()
        document["edges"][0].update(
            status="blocked",
            blocked_reason="producer edge is unavailable",
            next_query="trace the producer edge",
        )

        errors = validate_document(document)

        self.assertTrue(
            any("verified chain" in error and "blocked edge" in error for error in errors),
            errors,
        )

    def test_test_chain_roles_cannot_reference_test_nodes(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][0]
        happy, error = chain["test_node_refs"]
        contract = document["nodes"][1]["node_id"]
        consumer = document["nodes"][2]["node_id"]
        chain["node_refs"].append(happy)
        chain["required_roles"]["producer"] = [happy]

        prototype = document["edges"][0]
        validation_self_edge = {
            **prototype,
            "edge_id": "validates:test:happy->test:happy",
            "kind": "validates",
            "from": happy,
            "to": happy,
            "source_anchor": {"path": "tests/test_items.py", "start_line": 1, "end_line": 1},
            "verification_evidence": ["validation edge query"],
        }
        producer_edge = {
            **prototype,
            "edge_id": "writes:test:happy->table:items",
            "kind": "writes",
            "from": happy,
            "to": contract,
            "source_anchor": {"path": "tests/test_items.py", "start_line": 1, "end_line": 1},
            "verification_evidence": ["producer edge query"],
        }
        document["edges"].extend([validation_self_edge, producer_edge])
        chain["edge_refs"].extend([validation_self_edge["edge_id"], producer_edge["edge_id"]])

        errors = validate_document(document)

        self.assertTrue(any("test nodes" in error for error in errors), errors)

    def test_test_chain_contract_role_must_be_distinct_from_producer_and_consumer(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][0]
        happy, error = chain["test_node_refs"]
        writer = document["nodes"][0]["node_id"]
        chain["node_refs"] = [writer]
        chain["required_roles"] = {
            "producer": [writer],
            "contract": [writer],
            "consumer": [writer],
            "error_path": [error],
        }
        chain["error_path_refs"] = [error]

        prototype = document["edges"][0]
        self_edge = {
            **prototype,
            "edge_id": "calls:writer->writer",
            "kind": "calls",
            "from": writer,
            "to": writer,
            "source_anchor": {"path": "src/writer.py", "start_line": 1, "end_line": 1},
            "verification_evidence": ["role edge query"],
        }
        document["edges"].append(self_edge)
        chain["edge_refs"] = [
            "validates:test:happy->fn:writer",
            "validates:test:error->fn:writer",
            self_edge["edge_id"],
        ]

        errors = validate_document(document)

        self.assertTrue(any("distinct" in error or "overlap" in error for error in errors), errors)

    def test_test_chain_contract_role_must_reference_declared_contract_storage(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][0]
        writer, table, reader = [node["node_id"] for node in document["nodes"][:3]]
        error = chain["test_node_refs"][1]
        chain["required_roles"] = {
            "producer": [writer],
            "contract": [reader],
            "consumer": [table],
            "error_path": [error],
        }
        chain["node_refs"] = [writer, reader, table]

        prototype = document["edges"][0]
        role_edges = [
            {
                **prototype,
                "edge_id": "calls:writer->reader",
                "kind": "calls",
                "from": writer,
                "to": reader,
                "source_anchor": {"path": "src/writer.py", "start_line": 1, "end_line": 1},
                "verification_evidence": ["role edge query"],
            },
            {
                **prototype,
                "edge_id": "calls:reader->table",
                "kind": "calls",
                "from": reader,
                "to": table,
                "source_anchor": {"path": "src/reader.py", "start_line": 1, "end_line": 1},
                "verification_evidence": ["role edge query"],
            },
        ]
        document["edges"].extend(role_edges)
        chain["edge_refs"].extend(edge["edge_id"] for edge in role_edges)

        errors = validate_document(document)

        self.assertTrue(any("declared contract" in error for error in errors), errors)

    def test_test_chain_producer_and_consumer_must_match_contract_closure(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][0]
        writer, table, reader = [node["node_id"] for node in document["nodes"][:3]]
        error = chain["test_node_refs"][1]
        chain["required_roles"] = {
            "producer": [reader],
            "contract": [table],
            "consumer": [writer],
            "error_path": [error],
        }
        chain["node_refs"] = [writer, table, reader]

        prototype = document["edges"][0]
        role_edges = [
            {
                **prototype,
                "edge_id": "calls:reader->table",
                "kind": "calls",
                "from": reader,
                "to": table,
                "source_anchor": {"path": "src/reader.py", "start_line": 1, "end_line": 1},
                "verification_evidence": ["role edge query"],
            },
            {
                **prototype,
                "edge_id": "calls:table->writer",
                "kind": "calls",
                "from": table,
                "to": writer,
                "source_anchor": {"path": "db/schema.sql", "start_line": 1, "end_line": 1},
                "verification_evidence": ["role edge query"],
            },
        ]
        document["edges"].extend(role_edges)
        chain["edge_refs"].extend(edge["edge_id"] for edge in role_edges)

        errors = validate_document(document)

        self.assertTrue(any("contract closure" in error for error in errors), errors)

    def test_test_chain_must_include_contract_io_edges(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][0]
        writer, storage, reader = [node["node_id"] for node in document["nodes"][:3]]
        prototype = document["edges"][0]
        fake_role_edges = [
            {
                **prototype,
                "edge_id": "calls:writer->storage",
                "kind": "calls",
                "from": writer,
                "to": storage,
                "source_anchor": {"path": "src/writer.py", "start_line": 1, "end_line": 1},
                "verification_evidence": ["call edge query"],
            },
            {
                **prototype,
                "edge_id": "calls:storage->reader",
                "kind": "calls",
                "from": storage,
                "to": reader,
                "source_anchor": {"path": "src/reader.py", "start_line": 1, "end_line": 1},
                "verification_evidence": ["call edge query"],
            },
        ]
        document["edges"].extend(fake_role_edges)
        chain["edge_refs"] = [
            edge_id for edge_id in chain["edge_refs"] if edge_id.startswith("validates:")
        ] + [edge["edge_id"] for edge in fake_role_edges]

        errors = validate_document(document)

        self.assertTrue(
            any("contract writer edge" in error or "contract reader edge" in error for error in errors),
            errors,
        )

    def test_error_path_test_must_validate_a_code_role(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][0]
        error = chain["required_roles"]["error_path"][0]
        chain["edge_refs"] = [
            ref for ref in chain["edge_refs"] if ref != "validates:test:error->fn:writer"
        ]

        prototype = document["edges"][0]
        self_edge = {
            **prototype,
            "edge_id": "validates:test:error->test:error",
            "kind": "validates",
            "from": error,
            "to": error,
            "source_anchor": {"path": "tests/test_items.py", "start_line": 1, "end_line": 1},
            "verification_evidence": ["error path edge query"],
        }
        document["edges"].append(self_edge)
        chain["edge_refs"].append(self_edge["edge_id"])

        errors = validate_document(document)

        self.assertTrue(any("error-path test node" in error for error in errors), errors)

    def test_l0_chain_requires_static_producer_contract_consumer_topology(self) -> None:
        document = valid_snapshot()
        chain = document["test_chains"][1]
        chain["node_refs"] = []
        chain["edge_refs"] = ["validates:test:happy->fn:writer"]
        chain["required_roles"] = {
            "producer": [],
            "contract": [],
            "consumer": [],
            "error_path": [],
        }
        errors = validate_document(document)
        for role in ("producer", "contract", "consumer"):
            self.assertTrue(any(f"{role} is required for L0" in error for error in errors), errors)

        document = valid_snapshot()
        chain = document["test_chains"][1]
        chain["edge_refs"] = [
            "validates:test:happy->fn:writer",
            "validates:test:happy->table:items",
            "validates:test:happy->fn:reader",
        ]
        errors = validate_document(document)
        self.assertTrue(any("no producer-to-contract edge" in error for error in errors), errors)
        self.assertTrue(any("no contract-to-consumer edge" in error for error in errors), errors)

    def test_identifier_lists_reject_explicit_placeholders(self) -> None:
        document = change_snapshot()
        document["diff"]["added_nodes"] = []
        document["diff"]["removed_nodes"] = ["TODO"]
        cases = [("removed node", document)]

        document = change_snapshot()
        document["diff"]["added_nodes"] = []
        document["diff"]["removed_edges"] = ["TBD"]
        cases.append(("removed edge", document))

        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["state_values"] = ["TODO"]
        contract["state_semantics"] = {"TODO": "future state"}
        contract["state_producers"] = {"TODO": [document["nodes"][0]["node_id"]]}
        contract["state_consumers"] = {"TODO": [document["nodes"][2]["node_id"]]}
        cases.append(("state value", document))

        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["enum_values"] = ["TODO"]
        contract["schema_enum_values"] = ["TODO"]
        contract["enum_semantics"] = {"TODO": "future enum value"}
        contract["enum_producers"] = {"TODO": [document["nodes"][0]["node_id"]]}
        contract["enum_consumers"] = {"TODO": [document["nodes"][2]["node_id"]]}
        cases.append(("enum value", document))

        document = valid_snapshot()
        contract = document["contracts"][0]
        contract["unique_keys"] = ["TODO"]
        contract["duplicate_query"] = "SELECT id, COUNT(*) FROM items GROUP BY id HAVING COUNT(*) > 1"
        cases.append(("unique key", document))

        for label, document in cases:
            with self.subTest(label=label):
                errors = validate_document(document)
                self.assertTrue(any("placeholder" in error for error in errors), errors)

    def test_graph_paths_must_be_repository_relative(self) -> None:
        for path in ("../outside.py", "src/../../outside.py", "/outside.py", "C:/outside.py", r"C:\outside.py", r"\\server\share\outside.py"):
            with self.subTest(path=path):
                document = valid_snapshot()
                document["nodes"][0]["path"] = path
                document["nodes"][0]["source_anchor"]["path"] = path
                errors = validate_document(document)
                self.assertTrue(any("repository-relative" in error for error in errors), errors)

        source = valid_snapshot()
        source["source_coverage"][0]["source_anchor"]["path"] = "C:/outside/design.md"
        source_errors = validate_document(source)
        self.assertTrue(any("repository-relative" in error for error in source_errors), source_errors)

    def test_change_diff_lists_all_changed_current_objects(self) -> None:
        document = change_snapshot()
        changed_node = document["nodes"][1]
        changed_node["status"] = "changed"
        document["diff"]["changed_nodes"] = []
        errors = validate_document(document)
        self.assertTrue(any("changed_nodes omits changed node" in error for error in errors), errors)

    def test_change_diff_lists_all_changed_contracts(self) -> None:
        document = change_snapshot()
        changed_contract = document["contracts"][0]
        changed_contract["status"] = "changed"

        errors = validate_document(document)

        self.assertTrue(
            any("changed_contracts omits changed contract" in error for error in errors),
            errors,
        )

    def test_change_diff_changed_refs_require_changed_state(self) -> None:
        document = change_snapshot()
        document["diff"]["added_nodes"] = []
        document["diff"]["changed_nodes"] = [document["nodes"][0]["node_id"]]

        errors = validate_document(document)

        self.assertTrue(
            any("changed_nodes" in error and "status" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
