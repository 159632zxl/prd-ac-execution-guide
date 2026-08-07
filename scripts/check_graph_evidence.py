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


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_PATTERN.fullmatch(value))


def _as_list(value: Any) -> list[Any] | None:
    return value if isinstance(value, list) else None


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
    if not isinstance(anchor, dict):
        errors.append(f"{label} source_anchor must be an object or null")
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
        if not isinstance(section.get("ac_refs"), list):
            errors.append(f"{label} ac_refs must be a list")
        if status == "covered" and not section.get("requirement_refs"):
            errors.append(f"{label} covered requires requirement_refs")
        if status == "covered" and not section.get("ac_refs"):
            errors.append(f"{label} covered requires ac_refs")
        if status in {"deferred", "not-applicable"} and not _is_nonempty_string(section.get("explicit_reason")):
            errors.append(f"{label} {status} requires explicit_reason")


def _validate_reviews(document: dict[str, Any], errors: list[str]) -> None:
    findings = document.get("review_findings", [])
    if not isinstance(findings, list):
        errors.append("review_findings must be a list")
        return
    for index, finding in enumerate(findings):
        label = f"review_findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{label} must be an object")
            continue
        if not _is_nonempty_string(finding.get("finding_id")):
            errors.append(f"{label} finding_id must be non-empty")
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
        terminal_states = set(contract.get("terminal_states", []))
        if not isinstance(state_values, list) or not isinstance(state_semantics, dict) or not isinstance(state_producers, dict) or not isinstance(state_consumers, dict):
            errors.append(f"{label} state_values, state_semantics, state_producers, and state_consumers are required")
        else:
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
                    errors.append(f"{label} state has no consumer or terminal declaration: {state}")
                for consumer in consumers:
                    if consumer not in node_ids:
                        errors.append(f"{label} state consumer does not reference a node: {consumer}")

        enum_values = contract.get("enum_values")
        schema_values = contract.get("schema_enum_values")
        if not isinstance(enum_values, list) or not isinstance(schema_values, list):
            errors.append(f"{label} enum_values and schema_enum_values are required")
        elif set(enum_values) != set(schema_values):
            errors.append(f"{label} enum_values and schema_enum_values differ")

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


def validate_document(document: Any, map_only: bool = False) -> list[str]:
    """Return all validation errors for one normalized graph snapshot."""

    errors: list[str] = []
    if not isinstance(document, dict):
        return ["document must be a JSON object"]
    for field in ("schema_version", "artifact_type", "graph_type", "repository", "provider", "coverage", "nodes", "edges", "contracts"):
        if field not in document:
            errors.append(f"missing top-level field: {field}")
    if document.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
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

    incident_nodes = {endpoint for edge in edges for endpoint in (edge.get("from"), edge.get("to"))}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("status") in {"removed", "blocked", "unresolved"}:
            continue
        if node.get("node_id") not in incident_nodes and not node.get("entrypoint") and not node.get("test_refs"):
            errors.append(f"orphan node: {node.get('node_id')}")

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
