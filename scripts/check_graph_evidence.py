#!/usr/bin/env python3
"""Validate normalized PRD code-graph evidence without third-party packages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


STATUSES = {
    "planned",
    "observed",
    "changed",
    "implemented",
    "verified",
    "blocked",
    "unresolved",
    "removed",
}
GRAPH_TYPES = {"observed", "target", "change"}
COVERAGE_STATUSES = {"complete", "partial", "unknown"}
FRESHNESS = {"current", "stale", "unknown"}
SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{7,64}$")
NULL_SEMANTICS = {"sentinel", "partial_index", "coalesce_expression_index", "blocked"}
IMPLEMENTATION_STATES = {"unimplemented", "implemented-but-broken", "data-corrupted", "implemented"}
STORAGE_KINDS = {"sql_table", "sql_field", "cache", "event", "interface", "file", "other"}
TEST_LEVELS = {"L0", "L1", "L2", "L3", "L4"}
TEST_STATUSES = {"planned", "implemented", "verified", "blocked", "unresolved", "deferred"}
TEST_SCOPES = {"targeted", "full", "expanded"}
PRODUCER_EDGE_KINDS = {"calls", "writes", "publishes", "returns", "routes"}
CONSUMER_EDGE_KINDS = {"calls", "reads", "subscribes", "returns", "routes"}


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_PATTERN.fullmatch(value))


def _as_list(value: Any) -> list[Any] | None:
    return value if isinstance(value, list) else None


def _validate_source_anchor(anchor: Any, label: str, errors: list[str]) -> None:
    if not isinstance(anchor, dict):
        errors.append(f"{label} source_anchor must be an object")
        return
    if not _is_nonempty_string(anchor.get("path")):
        errors.append(f"{label} source_anchor.path must be non-empty")
    if not isinstance(anchor.get("start_line"), int) or anchor["start_line"] < 1:
        errors.append(f"{label} source_anchor.start_line is invalid")
    if not isinstance(anchor.get("end_line"), int) or anchor["end_line"] < 1:
        errors.append(f"{label} source_anchor.end_line is invalid")
    if isinstance(anchor.get("start_line"), int) and isinstance(anchor.get("end_line"), int):
        if anchor["end_line"] < anchor["start_line"]:
            errors.append(f"{label} source_anchor end_line precedes start_line")


def _validate_common(item: dict[str, Any], label: str, errors: list[str], graph_type: str) -> None:
    for field in ("provider", "git_sha", "coverage", "freshness", "verification_evidence", "requirement_refs"):
        if field not in item:
            errors.append(f"{label} missing {field}")
    if not _is_nonempty_string(item.get("provider")):
        errors.append(f"{label} provider must be non-empty")
    if not _is_sha(item.get("git_sha")):
        errors.append(f"{label} git_sha is invalid")
    if item.get("coverage") not in COVERAGE_STATUSES:
        errors.append(f"{label} coverage is invalid")
    if item.get("freshness") not in FRESHNESS:
        errors.append(f"{label} freshness is invalid")
    if not isinstance(item.get("verification_evidence"), list):
        errors.append(f"{label} verification_evidence must be a list")
    if not isinstance(item.get("requirement_refs"), list):
        errors.append(f"{label} requirement_refs must be a list")
    if item.get("status") not in STATUSES:
        errors.append(f"{label} status is invalid")
    if item.get("status") == "verified" and not item.get("verification_evidence"):
        errors.append(f"{label} verified requires verification_evidence")
    if graph_type == "target" and item.get("status") == "planned" and not item.get("requirement_refs"):
        errors.append(f"{label} planned target requires requirement_refs")


def _validate_anchor(item: dict[str, Any], label: str, errors: list[str], graph_type: str) -> None:
    anchor = item.get("source_anchor")
    if graph_type == "observed" and item.get("status") not in {"planned", "blocked", "unresolved"} and anchor is None:
        errors.append(f"{label} observed evidence requires source_anchor")
    if anchor is None:
        return
    _validate_source_anchor(anchor, label, errors)


def _validate_source_coverage(document: dict[str, Any], errors: list[str]) -> None:
    sections = _as_list(document.get("source_coverage"))
    if sections is None or not sections:
        errors.append("source_coverage must be a non-empty list")
        return
    ids: set[str] = set()
    for index, section in enumerate(sections):
        label = f"source_coverage[{index}]"
        if not isinstance(section, dict):
            errors.append(f"{label} must be an object")
            continue
        section_id = section.get("source_section_id")
        if not _is_nonempty_string(section_id):
            errors.append(f"{label} source_section_id must be non-empty")
        elif section_id in ids:
            errors.append(f"duplicate source_section_id: {section_id}")
        else:
            ids.add(section_id)
        status = section.get("status")
        if status not in {"covered", "deferred", "not-applicable"}:
            errors.append(f"{label} status is invalid")
        if not isinstance(section.get("requirement_refs"), list):
            errors.append(f"{label} requirement_refs must be a list")
        if not isinstance(section.get("ears_refs"), list):
            errors.append(f"{label} ears_refs must be a list")
        if not isinstance(section.get("target_node_refs"), list):
            errors.append(f"{label} target_node_refs must be a list")
        if not isinstance(section.get("target_edge_refs"), list):
            errors.append(f"{label} target_edge_refs must be a list")
        if not isinstance(section.get("ac_refs"), list):
            errors.append(f"{label} ac_refs must be a list")
        if status == "covered" and not section.get("requirement_refs"):
            errors.append(f"{label} covered requires requirement_refs")
        if status == "covered" and not section.get("ears_refs"):
            errors.append(f"{label} covered requires ears_refs")
        if status == "covered" and not section.get("target_node_refs"):
            errors.append(f"{label} covered requires target_node_refs")
        if status == "covered" and not section.get("target_edge_refs"):
            errors.append(f"{label} covered requires target_edge_refs")
        if status == "covered" and not section.get("ac_refs"):
            errors.append(f"{label} covered requires ac_refs")
        if status == "covered":
            if not _is_nonempty_string(section.get("owner_task")):
                errors.append(f"{label} covered requires owner task")
            if section.get("source_anchor") is None:
                errors.append(f"{label} covered requires source_anchor")
            else:
                _validate_source_anchor(section.get("source_anchor"), label, errors)
        if status in {"deferred", "not-applicable"} and not _is_nonempty_string(section.get("explicit_reason")):
            errors.append(f"{label} {status} requires explicit_reason")


def _validate_reviews(document: dict[str, Any], errors: list[str]) -> None:
    findings = document.get("review_findings", [])
    if not isinstance(findings, list):
        errors.append("review_findings must be a list")
        return
    finding_ids: set[str] = set()
    for index, finding in enumerate(findings):
        label = f"review_findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{label} must be an object")
            continue
        finding_id = finding.get("finding_id")
        if not _is_nonempty_string(finding_id):
            errors.append(f"{label} finding_id must be non-empty")
        elif finding_id in finding_ids:
            errors.append(f"duplicate finding_id: {finding_id}")
        else:
            finding_ids.add(finding_id)
        status = finding.get("status")
        if status not in {"proposed", "verified", "rejected", "inconclusive"}:
            errors.append(f"{label} status is invalid")
        evidence = finding.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{label} requires evidence")
        if status == "verified":
            independent = finding.get("independent_verification")
            if not isinstance(independent, list) or not independent:
                errors.append(f"{label} verified requires independent_verification")
        premises = finding.get("premises", [])
        if not isinstance(premises, list):
            errors.append(f"{label} premises must be a list")
        elif status == "rejected" and premises:
            premise_verification = finding.get("premise_verification")
            if not isinstance(premise_verification, list) or not premise_verification:
                errors.append(f"{label} rejected premises require premise_verification")
        if status == "inconclusive" and not _is_nonempty_string(finding.get("inconclusive_reason")):
            errors.append(f"{label} inconclusive requires inconclusive_reason")


def _validate_audit_coverage(document: dict[str, Any], errors: list[str]) -> None:
    audit = document.get("audit_coverage")
    if not isinstance(audit, dict):
        errors.append("audit_coverage must be an object")
        return
    if audit.get("status") not in {"complete", "partial", "inconclusive"}:
        errors.append("audit_coverage.status is invalid")
    for field in ("reviewers", "independent_verification", "limitations"):
        if not isinstance(audit.get(field), list):
            errors.append(f"audit_coverage.{field} must be a list")
    if audit.get("status") == "complete" and not audit.get("independent_verification"):
        errors.append("audit_coverage complete requires independent_verification")
    if audit.get("status") in {"partial", "inconclusive"} and not audit.get("limitations"):
        errors.append("audit_coverage partial or inconclusive requires limitations")


def _validate_contracts(
    document: dict[str, Any],
    errors: list[str],
    node_ids: set[str],
    edges: list[dict[str, Any]],
    map_only: bool = False,
) -> None:
    contracts = _as_list(document.get("contracts"))
    if contracts is None:
        errors.append("contracts must be a list")
        return
    contract_ids: set[str] = set()
    edge_pairs = {(edge.get("kind"), edge.get("from"), edge.get("to")) for edge in edges}
    for index, contract in enumerate(contracts):
        label = f"contracts[{index}]"
        if not isinstance(contract, dict):
            errors.append(f"{label} must be an object")
            continue
        contract_id = contract.get("contract_id")
        if not _is_nonempty_string(contract_id):
            errors.append(f"{label} contract_id must be non-empty")
        elif contract_id in contract_ids:
            errors.append(f"duplicate contract_id: {contract_id}")
        else:
            contract_ids.add(contract_id)
        storage = contract.get("storage_node_id")
        if storage not in node_ids:
            errors.append(f"{label} storage_node_id does not reference a node")
        writers = contract.get("writers")
        readers = contract.get("readers")
        if not isinstance(writers, list) or not isinstance(readers, list):
            errors.append(f"{label} writers and readers must be lists")
            continue
        if not writers and not _is_nonempty_string(contract.get("writer_milestone")):
            errors.append(f"{label} requires a writer or writer_milestone")
        if not readers and not _is_nonempty_string(contract.get("reader_milestone")):
            errors.append(f"{label} requires a reader or reader_milestone")
        for writer in writers:
            if writer not in node_ids:
                errors.append(f"{label} writer does not reference a node: {writer}")
            elif ("writes", writer, storage) not in edge_pairs:
                errors.append(f"{label} writer lacks writes edge: {writer} -> {storage}")
        for reader in readers:
            if reader not in node_ids:
                errors.append(f"{label} reader does not reference a node: {reader}")
            elif ("reads", storage, reader) not in edge_pairs:
                errors.append(f"{label} reader lacks reads edge: {storage} -> {reader}")

        state_values = contract.get("state_values")
        state_semantics = contract.get("state_semantics")
        state_producers = contract.get("state_producers")
        state_consumers = contract.get("state_consumers")
        state_deferred_milestones = contract.get("state_deferred_milestones", {})
        terminal_states = set(contract.get("terminal_states", []))
        if not isinstance(state_values, list) or not isinstance(state_semantics, dict) or not isinstance(state_producers, dict) or not isinstance(state_consumers, dict):
            errors.append(f"{label} state_values, state_semantics, state_producers, and state_consumers are required")
        else:
            if not isinstance(state_deferred_milestones, dict):
                errors.append(f"{label} state_deferred_milestones must be an object")
                state_deferred_milestones = {}
            for state in state_values:
                if not _is_nonempty_string(state_semantics.get(state)):
                    errors.append(f"{label} state has no semantic description: {state}")
                producers = state_producers.get(state, [])
                if not producers and state not in terminal_states:
                    errors.append(f"{label} state has no producer or terminal declaration: {state}")
                for producer in producers:
                    if producer not in node_ids:
                        errors.append(f"{label} state producer does not reference a node: {producer}")
                consumers = state_consumers.get(state, [])
                if not consumers and state not in terminal_states:
                    if not _is_nonempty_string(state_deferred_milestones.get(state)):
                        errors.append(f"{label} state has no consumer, terminal, or deferred milestone: {state}")
                for consumer in consumers:
                    if consumer not in node_ids:
                        errors.append(f"{label} state consumer does not reference a node: {consumer}")

        enum_values = contract.get("enum_values")
        schema_values = contract.get("schema_enum_values")
        if not isinstance(enum_values, list) or not isinstance(schema_values, list):
            errors.append(f"{label} enum_values and schema_enum_values are required")
        elif set(enum_values) != set(schema_values):
            errors.append(f"{label} enum_values and schema_enum_values differ")
        enum_semantics = contract.get("enum_semantics")
        enum_producers = contract.get("enum_producers")
        enum_consumers = contract.get("enum_consumers")
        if not isinstance(enum_semantics, dict) or not isinstance(enum_producers, dict) or not isinstance(enum_consumers, dict):
            errors.append(f"{label} enum_semantics, enum_producers, and enum_consumers are required")
        elif isinstance(enum_values, list):
            for value in enum_values:
                if not _is_nonempty_string(enum_semantics.get(value)):
                    errors.append(f"{label} enum value has no semantic description: {value}")
                producers = enum_producers.get(value, [])
                if not isinstance(producers, list) or not producers:
                    errors.append(f"{label} enum value has no producer: {value}")
                for producer in producers:
                    if producer not in node_ids:
                        errors.append(f"{label} enum producer does not reference a node: {producer}")
                consumers = enum_consumers.get(value, [])
                if not isinstance(consumers, list) or not consumers:
                    errors.append(f"{label} enum value has no consumer: {value}")
                for consumer in consumers:
                    if consumer not in node_ids:
                        errors.append(f"{label} enum consumer does not reference a node: {consumer}")

        expected = contract.get("expected_runtime_state")
        runtime_evidence = contract.get("runtime_evidence")
        if not isinstance(runtime_evidence, list):
            errors.append(f"{label} runtime_evidence must be a list")
        elif expected == "non-empty" and not runtime_evidence:
            errors.append(f"{label} non-empty requires runtime_evidence")
        elif expected == "intentionally empty":
            if not _is_nonempty_string(contract.get("intentional_empty_reason")):
                errors.append(f"{label} intentionally empty requires a reason")
            if not _is_nonempty_string(contract.get("intentional_empty_milestone")):
                errors.append(f"{label} intentionally empty requires a milestone")
        if contract.get("status") not in STATUSES:
            errors.append(f"{label} status is invalid")
        if map_only and contract.get("status") not in {"observed", "verified", "blocked", "unresolved"}:
            errors.append(f"{label} map-only status must be observed, verified, blocked, or unresolved")
        if contract.get("status") == "verified" and not contract.get("verification_evidence"):
            errors.append(f"{label} verified requires verification_evidence")

        storage_kind = contract.get("storage_kind")
        if storage_kind is not None and storage_kind not in STORAGE_KINDS:
            errors.append(f"{label} storage_kind is invalid")
        if storage_kind == "sql_table":
            foreign_key_check = contract.get("foreign_key_check")
            if not _is_nonempty_string(foreign_key_check) or "pragma foreign_key_check" not in foreign_key_check.lower():
                errors.append(f"{label} sql_table requires foreign_key_check PRAGMA")

        unique_keys = contract.get("unique_keys")
        nullable_columns = contract.get("nullable_unique_columns", [])
        if unique_keys is not None and not isinstance(unique_keys, list):
            errors.append(f"{label} unique_keys must be a list")
        if not isinstance(nullable_columns, list):
            errors.append(f"{label} nullable_unique_columns must be a list")
        elif nullable_columns:
            if not isinstance(unique_keys, list) or not set(nullable_columns).issubset(set(unique_keys)):
                errors.append(f"{label} nullable_unique_columns must be included in unique_keys")
            if contract.get("null_semantics") not in NULL_SEMANTICS:
                errors.append(f"{label} nullable unique keys require null_semantics")
            elif contract.get("null_semantics") == "blocked" and not _is_nonempty_string(contract.get("null_semantics_blocking_reason")):
                errors.append(f"{label} blocked null_semantics requires a blocking reason")
            if not _is_nonempty_string(contract.get("duplicate_query")):
                errors.append(f"{label} nullable unique keys require duplicate_query")

        strategy_name = contract.get("strategy_name")
        if strategy_name is not None:
            strategy_status = contract.get("strategy_status")
            if strategy_status == "blocked":
                if not _is_nonempty_string(contract.get("strategy_blocking_reason")):
                    errors.append(f"{label} blocked strategy requires strategy_blocking_reason")
            else:
                for field in ("strategy_parameters", "strategy_trigger", "strategy_target", "strategy_entrypoint"):
                    value = contract.get(field)
                    if not value or (isinstance(value, str) and not value.strip()):
                        errors.append(f"{label} strategy requires {field}")

        if contract.get("failure_mode") == "degraded-with-warning":
            if not isinstance(contract.get("observability_evidence"), list) or not contract.get("observability_evidence"):
                errors.append(f"{label} degraded-with-warning requires observability evidence")
            if contract.get("distinguishes_failure_from_empty") is not True:
                errors.append(f"{label} degraded-with-warning must distinguish failure from empty")

        implementation_state = contract.get("implementation_state")
        if implementation_state not in IMPLEMENTATION_STATES:
            errors.append(f"{label} implementation_state is invalid")
        elif implementation_state == "data-corrupted":
            if not isinstance(contract.get("data_audit_evidence"), list) or not contract.get("data_audit_evidence"):
                errors.append(f"{label} data-corrupted requires data_audit_evidence")
            if not _is_nonempty_string(contract.get("cleanup_plan")):
                errors.append(f"{label} data-corrupted requires cleanup_plan")


def _validate_test_chains(
    document: dict[str, Any],
    errors: list[str],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> None:
    """Require testable vertical chains instead of disconnected test prose."""

    chains = document.get("test_chains")
    if not isinstance(chains, list) or not chains:
        errors.append("test_chains must be a non-empty list")
        return

    node_by_id = {node.get("node_id"): node for node in nodes if isinstance(node, dict)}
    edge_by_id = {edge.get("edge_id"): edge for edge in edges if isinstance(edge, dict)}
    chain_ids: set[str] = set()
    observed_levels: set[str] = set()
    for index, chain in enumerate(chains):
        label = f"test_chains[{index}]"
        if not isinstance(chain, dict):
            errors.append(f"{label} must be an object")
            continue

        chain_id = chain.get("chain_id")
        if not _is_nonempty_string(chain_id):
            errors.append(f"{label} chain_id must be non-empty")
        elif chain_id in chain_ids:
            errors.append(f"duplicate chain_id: {chain_id}")
        else:
            chain_ids.add(chain_id)

        level = chain.get("level")
        status = chain.get("status")
        if isinstance(level, str):
            observed_levels.add(level)
        if level not in TEST_LEVELS:
            errors.append(f"{label} level is invalid")
        if status not in TEST_STATUSES:
            errors.append(f"{label} status is invalid")
        if not _is_nonempty_string(chain.get("expected_output")):
            errors.append(f"{label} expected_output must be non-empty")
        if not _is_nonempty_string(chain.get("command")):
            errors.append(f"{label} command must be non-empty")
        for field in ("test_node_refs", "node_refs", "edge_refs", "requirement_refs", "ac_refs", "error_path_refs", "uncovered_edge_refs"):
            if not isinstance(chain.get(field), list):
                errors.append(f"{label} {field} must be a list")
        if not chain.get("requirement_refs"):
            errors.append(f"{label} requires requirement_refs")
        if not chain.get("ac_refs"):
            errors.append(f"{label} requires ac_refs")

        test_node_refs = chain.get("test_node_refs", [])
        node_refs = chain.get("node_refs", [])
        edge_refs = chain.get("edge_refs", [])
        for ref in test_node_refs:
            node = node_by_id.get(ref)
            if node is None:
                errors.append(f"{label} test_node_refs references unknown node: {ref}")
            elif node.get("kind") != "test":
                errors.append(f"{label} test_node_refs must reference test nodes: {ref}")
        for ref in node_refs:
            if ref not in node_by_id:
                errors.append(f"{label} node_refs references unknown node: {ref}")
        for ref in edge_refs:
            if ref not in edge_by_id:
                errors.append(f"{label} edge_refs references unknown edge: {ref}")

        entrypoint = chain.get("entrypoint_node_id")
        if entrypoint not in test_node_refs:
            errors.append(f"{label} entrypoint must be listed in test_node_refs")
        elif not node_by_id.get(entrypoint, {}).get("entrypoint"):
            errors.append(f"{label} entrypoint test node must be marked entrypoint")

        roles = chain.get("required_roles")
        if not isinstance(roles, dict):
            errors.append(f"{label} required_roles must be an object")
            roles = {}
        for role in ("producer", "contract", "consumer", "error_path"):
            if not isinstance(roles.get(role), list):
                errors.append(f"{label} required_roles.{role} must be a list")
        for role in ("producer", "contract", "consumer"):
            role_refs = roles.get(role, [])
            if level != "L0" and not role_refs:
                errors.append(f"{label} {role} is required for {level}")
            for ref in role_refs:
                if ref not in node_refs:
                    errors.append(f"{label} {role} ref is not in node_refs: {ref}")
        error_path_refs = chain.get("error_path_refs", [])
        error_role_refs = roles.get("error_path", [])
        if level != "L0" and not error_path_refs:
            errors.append(f"{label} error_path is required for {level}")
        for ref in error_role_refs:
            if ref not in error_path_refs:
                errors.append(f"{label} required_roles.error_path ref is not in error_path_refs: {ref}")
        for ref in error_path_refs:
            if ref not in node_by_id and ref not in edge_by_id:
                errors.append(f"{label} error_path_refs references unknown node or edge: {ref}")

        chain_edges = [edge_by_id[ref] for ref in edge_refs if ref in edge_by_id]
        validation_edges = [
            edge for edge in chain_edges
            if edge.get("kind") == "validates" and edge.get("from") in test_node_refs
        ]
        required_code_refs = {
            ref
            for role in ("producer", "contract", "consumer")
            for ref in roles.get(role, [])
        }
        for ref in required_code_refs:
            if not any(edge.get("to") == ref for edge in validation_edges):
                errors.append(f"{label} missing validates edge for role node: {ref}")

        producers = roles.get("producer", [])
        contracts = roles.get("contract", [])
        consumers = roles.get("consumer", [])
        if level != "L0":
            if not any(
                edge.get("from") in producers
                and edge.get("to") in contracts
                and edge.get("kind") in PRODUCER_EDGE_KINDS
                for edge in chain_edges
            ):
                errors.append(f"{label} has no producer-to-contract edge")
            if not any(
                edge.get("from") in contracts
                and edge.get("to") in consumers
                and edge.get("kind") in CONSUMER_EDGE_KINDS
                for edge in chain_edges
            ):
                errors.append(f"{label} has no contract-to-consumer edge")

        evidence_kind = chain.get("evidence_kind")
        static_evidence = chain.get("static_evidence")
        runtime_evidence = chain.get("runtime_evidence")
        verification_evidence = chain.get("verification_evidence")
        if evidence_kind not in {"static", "runtime", "mixed"}:
            errors.append(f"{label} evidence_kind is invalid")
        for field, value in (
            ("static_evidence", static_evidence),
            ("runtime_evidence", runtime_evidence),
            ("verification_evidence", verification_evidence),
        ):
            if not isinstance(value, list):
                errors.append(f"{label} {field} must be a list")
        if status == "verified":
            if not isinstance(verification_evidence, list) or not verification_evidence:
                errors.append(f"{label} verified requires verification_evidence")
            if level == "L0":
                if evidence_kind != "static":
                    errors.append(f"{label} L0 verified must use static evidence")
                if not isinstance(static_evidence, list) or not static_evidence:
                    errors.append(f"{label} L0 verified requires static_evidence")
                if runtime_evidence:
                    errors.append(f"{label} L0 must not claim runtime_evidence")
            else:
                if evidence_kind not in {"runtime", "mixed"}:
                    errors.append(f"{label} {level} verified requires runtime evidence kind")
                if not isinstance(runtime_evidence, list) or not runtime_evidence:
                    errors.append(f"{label} verified requires runtime_evidence")
        if status == "deferred":
            if not _is_nonempty_string(chain.get("deferred_reason")):
                errors.append(f"{label} deferred requires deferred_reason")
            if not _is_nonempty_string(chain.get("deferred_milestone")):
                errors.append(f"{label} deferred requires deferred_milestone")
        if status == "blocked" and not _is_nonempty_string(chain.get("blocked_reason")):
            errors.append(f"{label} blocked requires blocked_reason")
        if status == "unresolved" and not _is_nonempty_string(chain.get("next_query")):
            errors.append(f"{label} unresolved requires next_query")

        test_scope = chain.get("test_scope")
        if test_scope not in TEST_SCOPES:
            errors.append(f"{label} test_scope is invalid")
        uncovered = chain.get("uncovered_edge_refs", [])
        for ref in uncovered:
            edge = edge_by_id.get(ref)
            if edge is None:
                errors.append(f"{label} uncovered_edge_refs references unknown edge: {ref}")
            elif edge.get("status") != "unresolved":
                errors.append(f"{label} uncovered edge must remain unresolved: {ref}")
        if status == "verified" and uncovered and test_scope not in {"full", "expanded"}:
            errors.append(f"{label} unresolved edges require expanded or full test scope")

    if document.get("graph_type") in {"target", "change"}:
        for required_level in ("L0", "L1"):
            if required_level not in observed_levels:
                errors.append(f"target/change graph requires a {required_level} test chain")

    for node in nodes:
        if not isinstance(node, dict):
            continue
        test_refs = node.get("test_refs", [])
        if test_refs is not None and not isinstance(test_refs, list):
            errors.append(f"node {node.get('node_id')} test_refs must be a list")
            continue
        for ref in test_refs or []:
            test_node = node_by_id.get(ref)
            if test_node is None or test_node.get("kind") != "test":
                errors.append(f"node {node.get('node_id')} test_refs references non-test node: {ref}")
        if node.get("status") in {"changed", "implemented", "verified"} and not test_refs:
            if not _is_nonempty_string(node.get("test_exemption_reason")):
                errors.append(f"node {node.get('node_id')} requires test_refs or test_exemption_reason")


def validate_document(document: Any, map_only: bool = False) -> list[str]:
    """Return all validation errors for one normalized graph snapshot."""

    errors: list[str] = []
    if not isinstance(document, dict):
        return ["document must be a JSON object"]
    for field in ("schema_version", "artifact_type", "graph_type", "repository", "provider", "coverage", "source_coverage", "audit_coverage", "nodes", "edges", "contracts", "test_chains"):
        if field not in document:
            errors.append(f"missing top-level field: {field}")
    if document.get("schema_version") != "1.1":
        errors.append("schema_version must be 1.1")
    graph_type = document.get("graph_type")
    if graph_type not in GRAPH_TYPES:
        errors.append("graph_type must be observed, target, or change")
    artifact_type = document.get("artifact_type")
    expected_artifact = "graph_diff" if graph_type == "change" else "graph_snapshot"
    if artifact_type != expected_artifact:
        errors.append(f"{graph_type} graph requires artifact_type {expected_artifact}")
    if map_only:
        if graph_type != "observed":
            errors.append("map-only requires graph_type observed")
        if any(field in document for field in ("baseline_sha", "current_sha", "diff")):
            errors.append("map-only cannot include Change Graph baseline or diff fields")

    repository = document.get("repository")
    if not isinstance(repository, dict):
        errors.append("repository must be an object")
    else:
        if not _is_nonempty_string(repository.get("root")):
            errors.append("repository.root must be non-empty")
        if not _is_sha(repository.get("git_sha")):
            errors.append("repository.git_sha is invalid")
    provider = document.get("provider")
    if not isinstance(provider, dict):
        errors.append("provider must be an object")
    else:
        for field in ("name", "version", "command", "generated_at"):
            if not _is_nonempty_string(provider.get(field)):
                errors.append(f"provider.{field} must be non-empty")
    coverage = document.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
    else:
        if coverage.get("scope") not in {"local", "module", "repository", "system"}:
            errors.append("coverage.scope is invalid")
        if coverage.get("status") not in COVERAGE_STATUSES:
            errors.append("coverage.status is invalid")
        for field in ("paths", "excluded_paths"):
            if not isinstance(coverage.get(field), list):
                errors.append(f"coverage.{field} must be a list")
        if map_only and coverage.get("status") == "unknown":
            errors.append("map-only coverage.status cannot be unknown")

    _validate_source_coverage(document, errors)
    _validate_audit_coverage(document, errors)
    _validate_reviews(document, errors)
    if graph_type == "change":
        if not _is_sha(document.get("baseline_sha")):
            errors.append("change graph requires a valid baseline_sha")
        if not _is_sha(document.get("current_sha")):
            errors.append("change graph requires a valid current_sha")
        diff = document.get("diff")
        if not isinstance(diff, dict):
            errors.append("change graph requires a diff object")
        else:
            diff_fields = ("added_nodes", "removed_nodes", "changed_nodes", "added_edges", "removed_edges", "changed_edges", "unresolved", "impact", "verification_evidence")
            for field in diff_fields:
                if not isinstance(diff.get(field), list):
                    errors.append(f"change graph diff.{field} must be a list")
            if isinstance(diff.get("verification_evidence"), list) and not diff["verification_evidence"]:
                errors.append("change graph diff requires verification_evidence")

    nodes = _as_list(document.get("nodes"))
    edges = _as_list(document.get("edges"))
    if nodes is None:
        errors.append("nodes must be a list")
        nodes = []
    if edges is None:
        errors.append("edges must be a list")
        edges = []

    node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        label = f"nodes[{index}]"
        if not isinstance(node, dict):
            errors.append(f"{label} must be an object")
            continue
        node_id = node.get("node_id")
        if not _is_nonempty_string(node_id):
            errors.append(f"{label} node_id must be non-empty")
        elif node_id in node_ids:
            errors.append(f"duplicate node_id: {node_id}")
        else:
            node_ids.add(node_id)
        for field in ("kind", "path", "qualified_symbol"):
            if not _is_nonempty_string(node.get(field)):
                errors.append(f"{label} {field} must be non-empty")
        confidence = node.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            errors.append(f"{label} confidence must be between 0 and 1")
        _validate_common(node, label, errors, graph_type)
        _validate_anchor(node, label, errors, graph_type)
        if map_only and node.get("status") not in {"observed", "verified", "blocked", "unresolved"}:
            errors.append(f"{label} map-only status must be observed, verified, blocked, or unresolved")

    edge_ids: set[str] = set()
    for index, edge in enumerate(edges):
        label = f"edges[{index}]"
        if not isinstance(edge, dict):
            errors.append(f"{label} must be an object")
            continue
        edge_id = edge.get("edge_id")
        if not _is_nonempty_string(edge_id):
            errors.append(f"{label} edge_id must be non-empty")
        elif edge_id in edge_ids:
            errors.append(f"duplicate edge_id: {edge_id}")
        else:
            edge_ids.add(edge_id)
        if edge.get("kind") not in {"calls", "imports", "reads", "writes", "publishes", "subscribes", "validates", "routes", "returns", "dynamic"}:
            errors.append(f"{label} kind is invalid")
        if edge.get("from") not in node_ids or edge.get("to") not in node_ids:
            errors.append(f"{label} endpoint does not reference an existing node")
        confidence = edge.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            errors.append(f"{label} confidence must be between 0 and 1")
        _validate_common(edge, label, errors, graph_type)
        _validate_anchor(edge, label, errors, graph_type)
        if map_only and edge.get("status") not in {"observed", "verified", "blocked", "unresolved"}:
            errors.append(f"{label} map-only status must be observed, verified, blocked, or unresolved")
        if edge.get("kind") == "dynamic" and edge.get("status") != "unresolved":
            errors.append(f"{label} dynamic edge must remain unresolved")
        if edge.get("status") == "unresolved":
            if not _is_nonempty_string(edge.get("unresolved_reason")):
                errors.append(f"{label} unresolved requires unresolved_reason")
            if not _is_nonempty_string(edge.get("next_query")):
                errors.append(f"{label} unresolved requires next_query")

    for index, section in enumerate(document.get("source_coverage", [])):
        if not isinstance(section, dict):
            continue
        label = f"source_coverage[{index}]"
        for ref in section.get("target_node_refs", []):
            if ref not in node_ids:
                errors.append(f"{label} target_node_refs references unknown node: {ref}")
        for ref in section.get("target_edge_refs", []):
            if ref not in edge_ids:
                errors.append(f"{label} target_edge_refs references unknown edge: {ref}")

    incident_nodes = {endpoint for edge in edges for endpoint in (edge.get("from"), edge.get("to"))}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("status") in {"removed", "blocked", "unresolved"}:
            continue
        if node.get("node_id") not in incident_nodes and not node.get("entrypoint") and not node.get("test_refs"):
            errors.append(f"orphan node: {node.get('node_id')}")

    _validate_test_chains(document, errors, [node for node in nodes if isinstance(node, dict)], [edge for edge in edges if isinstance(edge, dict)])
    _validate_contracts(document, errors, node_ids, edges, map_only=map_only)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="graph snapshot JSON file")
    parser.add_argument("--map-only", action="store_true", help="require an observed-only, no-change code map")
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL\n- cannot read JSON: {exc}")
        return 1
    errors = validate_document(document, map_only=args.map_only)
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
