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
EXPECTED_RUNTIME_STATES = {"non-empty", "intentionally empty", "not applicable"}
FAILURE_MODES = {"normal", "degraded-with-warning"}
STRATEGY_STATUSES = {"ready", "blocked"}
SOURCE_COVERAGE_STATUSES = {"covered", "deferred", "not-applicable"}
REVIEW_STATUSES = {"proposed", "verified", "rejected", "inconclusive"}
AUDIT_STATUSES = {"complete", "partial", "inconclusive"}
COVERAGE_SCOPES = {"local", "module", "repository", "system"}
EDGE_KINDS = {"calls", "imports", "reads", "writes", "publishes", "subscribes", "validates", "routes", "returns", "dynamic"}
ARTIFACT_TYPES = {"graph_snapshot", "graph_diff"}


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_PATTERN.fullmatch(value))


def _is_number(value: Any) -> bool:
    return type(value) in (int, float)


def _as_list(value: Any) -> list[Any] | None:
    return value if isinstance(value, list) else None


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_items(value: Any) -> list[str]:
    return [item for item in _safe_list(value) if _is_nonempty_string(item)]


def _validate_enum(value: Any, allowed: set[str], label: str, field: str, errors: list[str]) -> bool:
    if not isinstance(value, str) or value not in allowed:
        errors.append(f"{label} {field} is invalid")
        return False
    return True


def _validate_string_list(value: Any, label: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    valid: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"{label}[{index}] must be a string")
            continue
        if not item.strip():
            errors.append(f"{label}[{index}] must be non-empty")
            continue
        valid.append(item)
    return valid


def _validate_evidence(value: Any, label: str, errors: list[str]) -> list[str]:
    return _validate_string_list(value, label, errors)


def _validate_optional_string(
    item: dict[str, Any], field: str, label: str, errors: list[str], nonempty: bool = False
) -> None:
    if field not in item:
        return
    value = item.get(field)
    if not isinstance(value, str):
        errors.append(f"{label} {field} must be a string")
    elif nonempty and not value.strip():
        errors.append(f"{label} {field} must be non-empty")


def _validate_string_map(value: Any, label: str, errors: list[str]) -> dict[str, str]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    valid: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            errors.append(f"{label} keys must be non-empty strings")
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{label}.{key} must be a non-empty string")
        elif isinstance(key, str):
            valid[key] = item
    return valid


def _validate_string_list_map(value: Any, label: str, errors: list[str]) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    valid: dict[str, list[str]] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            errors.append(f"{label} keys must be non-empty strings")
            continue
        valid[key] = _validate_string_list(item, f"{label}.{key}", errors)
    return valid


def _reject_unknown_fields(item: dict[str, Any], allowed: set[str], label: str, errors: list[str]) -> None:
    for field in item:
        if field not in allowed:
            errors.append(f"{label} unknown field: {field}")


def _validate_diff(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return
    _reject_unknown_fields(
        value,
        {"added_nodes", "removed_nodes", "changed_nodes", "added_edges", "removed_edges", "changed_edges", "unresolved", "impact", "verification_evidence"},
        label,
        errors,
    )
    diff_fields = ("added_nodes", "removed_nodes", "changed_nodes", "added_edges", "removed_edges", "changed_edges", "unresolved", "impact", "verification_evidence")
    for field in diff_fields:
        if not isinstance(value.get(field), list):
            errors.append(f"{label}.{field} must be a list")
        else:
            _validate_string_list(value[field], f"{label}.{field}", errors)
    evidence = _validate_evidence(value.get("verification_evidence"), f"{label}.verification_evidence", errors)
    if not evidence:
        errors.append(f"{label} requires verification_evidence")


def _validate_source_anchor(anchor: Any, label: str, errors: list[str]) -> None:
    if not isinstance(anchor, dict):
        errors.append(f"{label} source_anchor must be an object")
        return
    _reject_unknown_fields(anchor, {"path", "start_line", "end_line"}, f"{label} source_anchor", errors)
    if not _is_nonempty_string(anchor.get("path")):
        errors.append(f"{label} source_anchor.path must be non-empty")
    if type(anchor.get("start_line")) is not int or anchor["start_line"] < 1:
        errors.append(f"{label} source_anchor.start_line is invalid")
    if type(anchor.get("end_line")) is not int or anchor["end_line"] < 1:
        errors.append(f"{label} source_anchor.end_line is invalid")
    if type(anchor.get("start_line")) is int and type(anchor.get("end_line")) is int:
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
    _validate_enum(item.get("coverage"), COVERAGE_STATUSES, label, "coverage", errors)
    _validate_enum(item.get("freshness"), FRESHNESS, label, "freshness", errors)
    if not isinstance(item.get("verification_evidence"), list):
        errors.append(f"{label} verification_evidence must be a list")
    else:
        _validate_string_list(item["verification_evidence"], f"{label} verification_evidence", errors)
    if not isinstance(item.get("requirement_refs"), list):
        errors.append(f"{label} requirement_refs must be a list")
    else:
        _validate_string_list(item["requirement_refs"], f"{label} requirement_refs", errors)
    if "entrypoint" in item and not isinstance(item.get("entrypoint"), bool):
        errors.append(f"{label} entrypoint must be a boolean")
    status_valid = _validate_enum(item.get("status"), STATUSES, label, "status", errors)
    if status_valid and item.get("status") == "verified" and not item.get("verification_evidence"):
        errors.append(f"{label} verified requires verification_evidence")
    if graph_type == "target" and status_valid and item.get("status") == "planned" and not item.get("requirement_refs"):
        errors.append(f"{label} planned target requires requirement_refs")


def _validate_anchor(
    item: dict[str, Any],
    label: str,
    errors: list[str],
    field_required: bool = False,
) -> None:
    status = item.get("status")
    requires_real_anchor = isinstance(status, str) and status not in {"planned", "blocked", "unresolved"}
    if "source_anchor" not in item:
        if field_required or requires_real_anchor:
            errors.append(f"{label} missing source_anchor")
        return
    anchor = item.get("source_anchor")
    if requires_real_anchor and anchor is None:
        errors.append(f"{label} status {status} requires source_anchor")
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
        _reject_unknown_fields(
            section,
            {"source_section_id", "status", "requirement_refs", "ears_refs", "target_node_refs", "target_edge_refs", "ac_refs", "owner_task", "explicit_reason", "source_anchor"},
            label,
            errors,
        )
        section_id = section.get("source_section_id")
        if not _is_nonempty_string(section_id):
            errors.append(f"{label} source_section_id must be non-empty")
        elif section_id in ids:
            errors.append(f"duplicate source_section_id: {section_id}")
        else:
            ids.add(section_id)
        for field in ("owner_task", "source_anchor"):
            if field not in section:
                errors.append(f"{label} missing {field}")
        if "owner_task" in section and not _is_nonempty_string(section.get("owner_task")):
            errors.append(f"{label} owner_task must be non-empty")
        if "source_anchor" in section and section.get("source_anchor") is not None and not isinstance(section.get("source_anchor"), dict):
            errors.append(f"{label} source_anchor must be an object or null")
        status = section.get("status")
        status_valid = _validate_enum(status, SOURCE_COVERAGE_STATUSES, label, "status", errors)
        requirement_refs = _validate_string_list(section.get("requirement_refs"), f"{label} requirement_refs", errors)
        ears_refs = _validate_string_list(section.get("ears_refs"), f"{label} ears_refs", errors)
        target_node_refs = _validate_string_list(section.get("target_node_refs"), f"{label} target_node_refs", errors)
        target_edge_refs = _validate_string_list(section.get("target_edge_refs"), f"{label} target_edge_refs", errors)
        ac_refs = _validate_string_list(section.get("ac_refs"), f"{label} ac_refs", errors)
        if status_valid and status == "covered" and not requirement_refs:
            errors.append(f"{label} covered requires requirement_refs")
        if status_valid and status == "covered" and not ears_refs:
            errors.append(f"{label} covered requires ears_refs")
        if status_valid and status == "covered" and not target_node_refs:
            errors.append(f"{label} covered requires target_node_refs")
        if status_valid and status == "covered" and not target_edge_refs:
            errors.append(f"{label} covered requires target_edge_refs")
        if status_valid and status == "covered" and not ac_refs:
            errors.append(f"{label} covered requires ac_refs")
        if status_valid and status == "covered":
            if not _is_nonempty_string(section.get("owner_task")):
                errors.append(f"{label} covered requires owner task")
            if section.get("source_anchor") is None:
                errors.append(f"{label} covered requires source_anchor")
            else:
                _validate_source_anchor(section.get("source_anchor"), label, errors)
        if status_valid and status in {"deferred", "not-applicable"} and not _is_nonempty_string(section.get("explicit_reason")):
            errors.append(f"{label} {status} requires explicit_reason")
        _validate_optional_string(section, "explicit_reason", label, errors)


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
        _reject_unknown_fields(
            finding,
            {"finding_id", "status", "evidence", "independent_verification", "premises", "premise_verification", "inconclusive_reason"},
            label,
            errors,
        )
        finding_id = finding.get("finding_id")
        if not _is_nonempty_string(finding_id):
            errors.append(f"{label} finding_id must be non-empty")
        elif finding_id in finding_ids:
            errors.append(f"duplicate finding_id: {finding_id}")
        else:
            finding_ids.add(finding_id)
        status = finding.get("status")
        status_valid = _validate_enum(status, REVIEW_STATUSES, label, "status", errors)
        evidence = finding.get("evidence")
        evidence_items = _validate_evidence(evidence, f"{label} evidence", errors)
        if not evidence_items:
            errors.append(f"{label} requires evidence")
        independent_items: list[str] = []
        if "independent_verification" in finding:
            independent_items = _validate_evidence(
                finding.get("independent_verification"), f"{label} independent_verification", errors
            )
        if status_valid and status == "verified":
            if not independent_items:
                errors.append(f"{label} verified requires independent_verification")
        premises = finding.get("premises", [])
        premises_items = _validate_string_list(premises, f"{label} premises", errors)
        premise_items: list[str] = []
        if "premise_verification" in finding:
            premise_items = _validate_evidence(
                finding.get("premise_verification"), f"{label} premise_verification", errors
            )
        if status_valid and status == "rejected" and premises_items:
            if not premise_items:
                errors.append(f"{label} rejected premises require premise_verification")
        if status_valid and status == "inconclusive" and not _is_nonempty_string(finding.get("inconclusive_reason")):
            errors.append(f"{label} inconclusive requires inconclusive_reason")
        for field in ("inconclusive_reason",):
            _validate_optional_string(finding, field, label, errors, nonempty=True)


def _validate_audit_coverage(document: dict[str, Any], errors: list[str]) -> None:
    audit = document.get("audit_coverage")
    if not isinstance(audit, dict):
        errors.append("audit_coverage must be an object")
        return
    _reject_unknown_fields(audit, {"status", "reviewers", "independent_verification", "limitations"}, "audit_coverage", errors)
    audit_status_valid = _validate_enum(audit.get("status"), AUDIT_STATUSES, "audit_coverage", "status", errors)
    reviewers = _validate_string_list(audit.get("reviewers"), "audit_coverage.reviewers", errors)
    independent_verification = _validate_evidence(
        audit.get("independent_verification"), "audit_coverage.independent_verification", errors
    )
    limitations = _validate_string_list(audit.get("limitations"), "audit_coverage.limitations", errors)
    if audit_status_valid and audit.get("status") == "complete" and not independent_verification:
        errors.append("audit_coverage complete requires independent_verification")
    if audit_status_valid and audit.get("status") in {"partial", "inconclusive"} and not limitations:
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
    edge_pairs = {
        (edge.get("kind"), edge.get("from"), edge.get("to"))
        for edge in edges
        if isinstance(edge.get("kind"), str)
        and isinstance(edge.get("from"), str)
        and isinstance(edge.get("to"), str)
    }
    for index, contract in enumerate(contracts):
        label = f"contracts[{index}]"
        if not isinstance(contract, dict):
            errors.append(f"{label} must be an object")
            continue
        _reject_unknown_fields(
            contract,
            {
                "contract_id", "storage_node_id", "storage_kind", "writers", "readers", "writer_milestone", "reader_milestone",
                "foreign_key_check", "unique_keys", "nullable_unique_columns", "null_semantics", "null_semantics_blocking_reason",
                "duplicate_query", "strategy_name", "strategy_status", "strategy_parameters", "strategy_trigger", "strategy_target",
                "strategy_entrypoint", "strategy_blocking_reason", "state_values", "state_semantics", "state_producers",
                "state_consumers", "state_deferred_milestones", "terminal_states", "enum_semantics", "enum_producers",
                "enum_consumers", "enum_values", "schema_enum_values", "expected_runtime_state", "intentional_empty_reason",
                "intentional_empty_milestone", "runtime_evidence", "status", "verification_evidence", "failure_mode",
                "observability_evidence", "distinguishes_failure_from_empty", "implementation_state", "data_audit_evidence", "cleanup_plan",
            },
            label,
            errors,
        )
        contract_id = contract.get("contract_id")
        if not _is_nonempty_string(contract_id):
            errors.append(f"{label} contract_id must be non-empty")
        elif contract_id in contract_ids:
            errors.append(f"duplicate contract_id: {contract_id}")
        else:
            contract_ids.add(contract_id)
        storage = contract.get("storage_node_id")
        storage_valid = _is_nonempty_string(storage)
        if not storage_valid or storage not in node_ids:
            errors.append(f"{label} storage_node_id does not reference a node")
        writers = contract.get("writers")
        readers = contract.get("readers")
        if not isinstance(writers, list):
            errors.append(f"{label} writers must be a list")
            writers = []
        else:
            writers = _validate_string_list(writers, f"{label} writers", errors)
        if not isinstance(readers, list):
            errors.append(f"{label} readers must be a list")
            readers = []
        else:
            readers = _validate_string_list(readers, f"{label} readers", errors)
        if not isinstance(contract.get("writers"), list) or not isinstance(contract.get("readers"), list):
            errors.append(f"{label} writers and readers must be lists")
        if not writers and not _is_nonempty_string(contract.get("writer_milestone")):
            errors.append(f"{label} requires a writer or writer_milestone")
        if not readers and not _is_nonempty_string(contract.get("reader_milestone")):
            errors.append(f"{label} requires a reader or reader_milestone")
        for writer in writers:
            if writer not in node_ids:
                errors.append(f"{label} writer does not reference a node: {writer}")
            elif storage_valid and ("writes", writer, storage) not in edge_pairs:
                errors.append(f"{label} writer lacks writes edge: {writer} -> {storage}")
        for reader in readers:
            if reader not in node_ids:
                errors.append(f"{label} reader does not reference a node: {reader}")
            elif storage_valid and ("reads", storage, reader) not in edge_pairs:
                errors.append(f"{label} reader lacks reads edge: {storage} -> {reader}")

        state_values = contract.get("state_values")
        state_semantics = contract.get("state_semantics")
        state_producers = contract.get("state_producers")
        state_consumers = contract.get("state_consumers")
        state_deferred_milestones = contract.get("state_deferred_milestones", {})
        terminal_states_list = _validate_string_list(contract.get("terminal_states", []), f"{label} terminal_states", errors)
        terminal_states = set(terminal_states_list)
        if not isinstance(state_values, list) or not isinstance(state_semantics, dict) or not isinstance(state_producers, dict) or not isinstance(state_consumers, dict):
            errors.append(f"{label} state_values, state_semantics, state_producers, and state_consumers are required")
        else:
            if not isinstance(state_deferred_milestones, dict):
                errors.append(f"{label} state_deferred_milestones must be an object")
                state_deferred_milestones = {}
            for state in _validate_string_list(state_values, f"{label} state_values", errors):
                if not _is_nonempty_string(state_semantics.get(state)):
                    errors.append(f"{label} state has no semantic description: {state}")
                producers = state_producers.get(state, [])
                if not isinstance(producers, list):
                    errors.append(f"{label} state producer list is invalid: {state}")
                    producers = []
                else:
                    producers = _validate_string_list(producers, f"{label} state_producers.{state}", errors)
                if not producers and state not in terminal_states:
                    errors.append(f"{label} state has no producer or terminal declaration: {state}")
                for producer in producers:
                    if producer not in node_ids:
                        errors.append(f"{label} state producer does not reference a node: {producer}")
                consumers = state_consumers.get(state, [])
                if not isinstance(consumers, list):
                    errors.append(f"{label} state consumer list is invalid: {state}")
                    consumers = []
                else:
                    consumers = _validate_string_list(consumers, f"{label} state_consumers.{state}", errors)
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
        elif not all(isinstance(value, str) for value in enum_values + schema_values):
            errors.append(f"{label} enum values must be strings")
        elif set(enum_values) != set(schema_values):
            errors.append(f"{label} enum_values and schema_enum_values differ")
        enum_semantics = contract.get("enum_semantics")
        enum_producers = contract.get("enum_producers")
        enum_consumers = contract.get("enum_consumers")
        if not isinstance(enum_semantics, dict) or not isinstance(enum_producers, dict) or not isinstance(enum_consumers, dict):
            errors.append(f"{label} enum_semantics, enum_producers, and enum_consumers are required")
        elif isinstance(enum_values, list):
            for value in _validate_string_list(enum_values, f"{label} enum_values", errors):
                if not _is_nonempty_string(enum_semantics.get(value)):
                    errors.append(f"{label} enum value has no semantic description: {value}")
                producers = enum_producers.get(value, [])
                if not isinstance(producers, list):
                    errors.append(f"{label} enum producer list is invalid: {value}")
                    producers = []
                else:
                    producers = _validate_string_list(producers, f"{label} enum_producers.{value}", errors)
                if not producers:
                    errors.append(f"{label} enum value has no producer: {value}")
                for producer in producers:
                    if producer not in node_ids:
                        errors.append(f"{label} enum producer does not reference a node: {producer}")
                consumers = enum_consumers.get(value, [])
                if not isinstance(consumers, list):
                    errors.append(f"{label} enum consumer list is invalid: {value}")
                    consumers = []
                else:
                    consumers = _validate_string_list(consumers, f"{label} enum_consumers.{value}", errors)
                if not consumers:
                    errors.append(f"{label} enum value has no consumer: {value}")
                for consumer in consumers:
                    if consumer not in node_ids:
                        errors.append(f"{label} enum consumer does not reference a node: {consumer}")

        expected = contract.get("expected_runtime_state")
        expected_valid = _validate_enum(expected, EXPECTED_RUNTIME_STATES, label, "expected_runtime_state", errors)
        runtime_evidence = contract.get("runtime_evidence")
        runtime_evidence_items = _validate_evidence(runtime_evidence, f"{label} runtime_evidence", errors)
        if expected_valid and expected == "non-empty" and not runtime_evidence_items:
            errors.append(f"{label} non-empty requires runtime_evidence")
        elif expected_valid and expected == "intentionally empty":
            if not _is_nonempty_string(contract.get("intentional_empty_reason")):
                errors.append(f"{label} intentionally empty requires a reason")
            if not _is_nonempty_string(contract.get("intentional_empty_milestone")):
                errors.append(f"{label} intentionally empty requires a milestone")
        contract_status_valid = _validate_enum(contract.get("status"), STATUSES, label, "status", errors)
        if map_only and contract_status_valid and contract.get("status") not in {"observed", "verified", "blocked", "unresolved"}:
            errors.append(f"{label} map-only status must be observed, verified, blocked, or unresolved")
        if "verification_evidence" not in contract:
            errors.append(f"{label} missing verification_evidence")
        else:
            verification_evidence_items = _validate_evidence(
                contract.get("verification_evidence"), f"{label} verification_evidence", errors
            )
            if contract_status_valid and contract.get("status") == "verified" and not verification_evidence_items:
                errors.append(f"{label} verified requires verification_evidence")

        storage_kind = contract.get("storage_kind")
        if "storage_kind" in contract:
            if not _validate_enum(storage_kind, STORAGE_KINDS, label, "storage_kind", errors):
                storage_kind = None
        for field in (
            "writer_milestone", "reader_milestone", "foreign_key_check", "null_semantics_blocking_reason",
            "duplicate_query", "strategy_name", "strategy_trigger", "strategy_target", "strategy_entrypoint",
            "strategy_blocking_reason", "intentional_empty_reason", "intentional_empty_milestone", "cleanup_plan",
        ):
            _validate_optional_string(contract, field, label, errors)
        if "distinguishes_failure_from_empty" in contract and not isinstance(contract.get("distinguishes_failure_from_empty"), bool):
            errors.append(f"{label} distinguishes_failure_from_empty must be a boolean")
        if storage_kind == "sql_table":
            foreign_key_check = contract.get("foreign_key_check")
            if not _is_nonempty_string(foreign_key_check) or "pragma foreign_key_check" not in foreign_key_check.lower():
                errors.append(f"{label} sql_table requires foreign_key_check PRAGMA")

        unique_keys = contract.get("unique_keys")
        nullable_columns = contract.get("nullable_unique_columns", [])
        if "unique_keys" in contract and not isinstance(unique_keys, list):
            errors.append(f"{label} unique_keys must be a list")
        elif isinstance(unique_keys, list):
            unique_keys = _validate_string_list(unique_keys, f"{label} unique_keys", errors)
        if not isinstance(nullable_columns, list):
            errors.append(f"{label} nullable_unique_columns must be a list")
            nullable_columns = []
        else:
            nullable_columns = _validate_string_list(nullable_columns, f"{label} nullable_unique_columns", errors)
        if nullable_columns:
            if not isinstance(unique_keys, list) or not set(nullable_columns).issubset(set(unique_keys)):
                errors.append(f"{label} nullable_unique_columns must be included in unique_keys")
            null_semantics_valid = _validate_enum(contract.get("null_semantics"), NULL_SEMANTICS, label, "null_semantics", errors)
            if not null_semantics_valid:
                errors.append(f"{label} nullable unique keys require null_semantics")
            elif contract.get("null_semantics") == "blocked" and not _is_nonempty_string(contract.get("null_semantics_blocking_reason")):
                errors.append(f"{label} blocked null_semantics requires a blocking reason")
            if not _is_nonempty_string(contract.get("duplicate_query")):
                errors.append(f"{label} nullable unique keys require duplicate_query")
        elif "null_semantics" in contract:
            _validate_enum(contract.get("null_semantics"), NULL_SEMANTICS, label, "null_semantics", errors)

        strategy_name = contract.get("strategy_name")
        if strategy_name is not None:
            strategy_status = contract.get("strategy_status")
            strategy_status_valid = _validate_enum(strategy_status, STRATEGY_STATUSES, label, "strategy_status", errors)
            if strategy_status_valid and strategy_status == "blocked":
                if not _is_nonempty_string(contract.get("strategy_blocking_reason")):
                    errors.append(f"{label} blocked strategy requires strategy_blocking_reason")
            else:
                for field in ("strategy_parameters", "strategy_trigger", "strategy_target", "strategy_entrypoint"):
                    value = contract.get(field)
                    if not value or (isinstance(value, str) and not value.strip()):
                        errors.append(f"{label} strategy requires {field}")
        if "strategy_status" in contract:
            _validate_enum(contract.get("strategy_status"), STRATEGY_STATUSES, label, "strategy_status", errors)
        if "strategy_parameters" in contract:
            parameters = contract.get("strategy_parameters")
            if not isinstance(parameters, (dict, list, str, int, float)) or isinstance(parameters, bool):
                errors.append(f"{label} strategy_parameters has invalid type")
        for field, value in (("state_semantics", contract.get("state_semantics")), ("enum_semantics", contract.get("enum_semantics"))):
            if isinstance(value, dict):
                _validate_string_map(value, f"{label} {field}", errors)
        for field, value in (
            ("state_producers", contract.get("state_producers")),
            ("state_consumers", contract.get("state_consumers")),
            ("state_deferred_milestones", contract.get("state_deferred_milestones")),
            ("enum_producers", contract.get("enum_producers")),
            ("enum_consumers", contract.get("enum_consumers")),
        ):
            if isinstance(value, dict):
                if field == "state_deferred_milestones":
                    _validate_string_map(value, f"{label} {field}", errors)
                else:
                    _validate_string_list_map(value, f"{label} {field}", errors)

        failure_mode = contract.get("failure_mode")
        failure_mode_valid = "failure_mode" not in contract or _validate_enum(failure_mode, FAILURE_MODES, label, "failure_mode", errors)
        observability_evidence: list[str] = []
        if "observability_evidence" in contract:
            observability_evidence = _validate_evidence(
                contract.get("observability_evidence"), f"{label} observability_evidence", errors
            )
        if failure_mode_valid and failure_mode == "degraded-with-warning":
            if not observability_evidence:
                errors.append(f"{label} degraded-with-warning requires observability evidence")
            if contract.get("distinguishes_failure_from_empty") is not True:
                errors.append(f"{label} degraded-with-warning must distinguish failure from empty")

        implementation_state = contract.get("implementation_state")
        implementation_state_valid = _validate_enum(implementation_state, IMPLEMENTATION_STATES, label, "implementation_state", errors)
        data_audit_evidence: list[str] = []
        if "data_audit_evidence" in contract:
            data_audit_evidence = _validate_evidence(
                contract.get("data_audit_evidence"), f"{label} data_audit_evidence", errors
            )
        if implementation_state_valid and implementation_state == "data-corrupted":
            if not data_audit_evidence:
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

    node_by_id = {
        node["node_id"]: node
        for node in nodes
        if isinstance(node, dict) and _is_nonempty_string(node.get("node_id"))
    }
    edge_by_id = {
        edge["edge_id"]: edge
        for edge in edges
        if isinstance(edge, dict) and _is_nonempty_string(edge.get("edge_id"))
    }
    chain_ids: set[str] = set()
    observed_levels: set[str] = set()
    for index, chain in enumerate(chains):
        label = f"test_chains[{index}]"
        if not isinstance(chain, dict):
            errors.append(f"{label} must be an object")
            continue
        _reject_unknown_fields(
            chain,
            {
                "chain_id", "level", "status", "entrypoint_node_id", "test_node_refs", "node_refs", "edge_refs", "requirement_refs",
                "ac_refs", "required_roles", "error_path_refs", "expected_output", "command", "evidence_kind", "static_evidence",
                "runtime_evidence", "verification_evidence", "uncovered_edge_refs", "test_scope", "deferred_reason", "deferred_milestone",
                "blocked_reason", "next_query",
            },
            label,
            errors,
        )

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
        level_valid = _validate_enum(level, TEST_LEVELS, label, "level", errors)
        status_valid = _validate_enum(status, TEST_STATUSES, label, "status", errors)
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
        if isinstance(chain.get("requirement_refs"), list):
            _validate_string_list(chain["requirement_refs"], f"{label} requirement_refs", errors)
        if isinstance(chain.get("ac_refs"), list):
            _validate_string_list(chain["ac_refs"], f"{label} ac_refs", errors)

        test_node_refs = _validate_string_list(chain.get("test_node_refs"), f"{label} test_node_refs", errors) if isinstance(chain.get("test_node_refs"), list) else []
        node_refs = _validate_string_list(chain.get("node_refs"), f"{label} node_refs", errors) if isinstance(chain.get("node_refs"), list) else []
        edge_refs = _validate_string_list(chain.get("edge_refs"), f"{label} edge_refs", errors) if isinstance(chain.get("edge_refs"), list) else []
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
        if not _is_nonempty_string(entrypoint) or entrypoint not in test_node_refs:
            errors.append(f"{label} entrypoint must be listed in test_node_refs")
        elif not node_by_id.get(entrypoint, {}).get("entrypoint"):
            errors.append(f"{label} entrypoint test node must be marked entrypoint")

        roles = chain.get("required_roles")
        if not isinstance(roles, dict):
            errors.append(f"{label} required_roles must be an object")
            roles = {}
        else:
            _reject_unknown_fields(roles, {"producer", "contract", "consumer", "error_path"}, f"{label} required_roles", errors)
        for role in ("producer", "contract", "consumer", "error_path"):
            if not isinstance(roles.get(role), list):
                errors.append(f"{label} required_roles.{role} must be a list")
        for role in ("producer", "contract", "consumer"):
            role_refs = _validate_string_list(roles.get(role), f"{label} required_roles.{role}", errors) if isinstance(roles.get(role), list) else []
            if level_valid and level != "L0" and not role_refs:
                errors.append(f"{label} {role} is required for {level}")
            for ref in role_refs:
                if ref not in node_refs:
                    errors.append(f"{label} {role} ref is not in node_refs: {ref}")
        error_path_refs = _validate_string_list(chain.get("error_path_refs"), f"{label} error_path_refs", errors) if isinstance(chain.get("error_path_refs"), list) else []
        error_role_refs = _validate_string_list(roles.get("error_path"), f"{label} required_roles.error_path", errors) if isinstance(roles.get("error_path"), list) else []
        if level_valid and level != "L0" and not error_path_refs:
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
            for ref in _string_items(roles.get(role))
        }
        for ref in required_code_refs:
            if not any(edge.get("to") == ref for edge in validation_edges):
                errors.append(f"{label} missing validates edge for role node: {ref}")

        producers = _string_items(roles.get("producer"))
        contracts = _string_items(roles.get("contract"))
        consumers = _string_items(roles.get("consumer"))
        if level_valid and level != "L0":
            if not any(
                edge.get("from") in producers
                and edge.get("to") in contracts
                and isinstance(edge.get("kind"), str)
                and edge.get("kind") in PRODUCER_EDGE_KINDS
                for edge in chain_edges
            ):
                errors.append(f"{label} has no producer-to-contract edge")
            if not any(
                edge.get("from") in contracts
                and edge.get("to") in consumers
                and isinstance(edge.get("kind"), str)
                and edge.get("kind") in CONSUMER_EDGE_KINDS
                for edge in chain_edges
            ):
                errors.append(f"{label} has no contract-to-consumer edge")

        evidence_kind = chain.get("evidence_kind")
        static_evidence = chain.get("static_evidence")
        runtime_evidence = chain.get("runtime_evidence")
        verification_evidence = chain.get("verification_evidence")
        evidence_kind_valid = _validate_enum(evidence_kind, {"static", "runtime", "mixed"}, label, "evidence_kind", errors)
        static_evidence_items = _validate_evidence(static_evidence, f"{label} static_evidence", errors)
        runtime_evidence_items = _validate_evidence(runtime_evidence, f"{label} runtime_evidence", errors)
        verification_evidence_items = _validate_evidence(
            verification_evidence, f"{label} verification_evidence", errors
        )
        if status_valid and status == "verified":
            if not verification_evidence_items:
                errors.append(f"{label} verified requires verification_evidence")
            if level == "L0":
                if evidence_kind_valid and evidence_kind != "static":
                    errors.append(f"{label} L0 verified must use static evidence")
                if not static_evidence_items:
                    errors.append(f"{label} L0 verified requires static_evidence")
                if runtime_evidence_items:
                    errors.append(f"{label} L0 must not claim runtime_evidence")
            else:
                if evidence_kind_valid and evidence_kind not in {"runtime", "mixed"}:
                    errors.append(f"{label} {level} verified requires runtime evidence kind")
                if not runtime_evidence_items:
                    errors.append(f"{label} verified requires runtime_evidence")
        if status_valid and status == "deferred":
            if not _is_nonempty_string(chain.get("deferred_reason")):
                errors.append(f"{label} deferred requires deferred_reason")
            if not _is_nonempty_string(chain.get("deferred_milestone")):
                errors.append(f"{label} deferred requires deferred_milestone")
        if status_valid and status == "blocked" and not _is_nonempty_string(chain.get("blocked_reason")):
            errors.append(f"{label} blocked requires blocked_reason")
        if status_valid and status == "unresolved" and not _is_nonempty_string(chain.get("next_query")):
            errors.append(f"{label} unresolved requires next_query")
        for field in ("deferred_reason", "deferred_milestone", "blocked_reason", "next_query"):
            _validate_optional_string(chain, field, label, errors, nonempty=True)

        test_scope = chain.get("test_scope")
        test_scope_valid = _validate_enum(test_scope, TEST_SCOPES, label, "test_scope", errors)
        uncovered = _validate_string_list(chain.get("uncovered_edge_refs"), f"{label} uncovered_edge_refs", errors) if isinstance(chain.get("uncovered_edge_refs"), list) else []
        for ref in uncovered:
            edge = edge_by_id.get(ref)
            if edge is None:
                errors.append(f"{label} uncovered_edge_refs references unknown edge: {ref}")
            elif edge.get("status") != "unresolved":
                errors.append(f"{label} uncovered edge must remain unresolved: {ref}")
        if status_valid and status == "verified" and uncovered and test_scope_valid and test_scope not in {"full", "expanded"}:
            errors.append(f"{label} unresolved edges require expanded or full test scope")

    if isinstance(document.get("graph_type"), str) and document.get("graph_type") in {"target", "change"}:
        for required_level in ("L0", "L1"):
            if required_level not in observed_levels:
                errors.append(f"target/change graph requires a {required_level} test chain")

    for node in nodes:
        if not isinstance(node, dict):
            continue
        test_refs = node.get("test_refs", [])
        if "test_refs" in node and not isinstance(test_refs, list):
            errors.append(f"node {node.get('node_id')} test_refs must be a list")
            continue
        for ref in _validate_string_list(test_refs, f"node {node.get('node_id')} test_refs", errors) if isinstance(test_refs, list) else []:
            test_node = node_by_id.get(ref)
            if test_node is None or test_node.get("kind") != "test":
                errors.append(f"node {node.get('node_id')} test_refs references non-test node: {ref}")
        if isinstance(node.get("status"), str) and node.get("status") in {"changed", "implemented", "verified"} and not test_refs:
            if not _is_nonempty_string(node.get("test_exemption_reason")):
                errors.append(f"node {node.get('node_id')} requires test_refs or test_exemption_reason")


def validate_document(document: Any, map_only: bool = False) -> list[str]:
    """Return all validation errors for one normalized graph snapshot."""

    errors: list[str] = []
    if not isinstance(document, dict):
        return ["document must be a JSON object"]
    _reject_unknown_fields(
        document,
        {"schema_version", "artifact_type", "graph_type", "repository", "provider", "coverage", "source_coverage", "audit_coverage", "baseline_sha", "current_sha", "diff", "nodes", "edges", "contracts", "test_chains", "review_findings"},
        "document",
        errors,
    )
    for field in ("schema_version", "artifact_type", "graph_type", "repository", "provider", "coverage", "source_coverage", "audit_coverage", "nodes", "edges", "contracts", "test_chains"):
        if field not in document:
            errors.append(f"missing top-level field: {field}")
    if document.get("schema_version") != "1.1":
        errors.append("schema_version must be 1.1")
    graph_type = document.get("graph_type")
    graph_type_valid = _validate_enum(graph_type, GRAPH_TYPES, "document", "graph_type", errors)
    artifact_type = document.get("artifact_type")
    artifact_type_valid = _validate_enum(artifact_type, ARTIFACT_TYPES, "document", "artifact_type", errors)
    expected_artifact = "graph_diff" if graph_type == "change" else "graph_snapshot"
    if graph_type_valid and artifact_type_valid and artifact_type != expected_artifact:
        errors.append(f"{graph_type} graph requires artifact_type {expected_artifact}")
    if map_only:
        if graph_type_valid and graph_type != "observed":
            errors.append("map-only requires graph_type observed")
        if any(field in document for field in ("baseline_sha", "current_sha", "diff")):
            errors.append("map-only cannot include Change Graph baseline or diff fields")
    for field in ("baseline_sha", "current_sha"):
        if field in document and not _is_sha(document.get(field)):
            errors.append(f"{field} is invalid")

    repository = document.get("repository")
    if not isinstance(repository, dict):
        errors.append("repository must be an object")
    else:
        _reject_unknown_fields(repository, {"root", "git_sha"}, "repository", errors)
        if not _is_nonempty_string(repository.get("root")):
            errors.append("repository.root must be non-empty")
        if not _is_sha(repository.get("git_sha")):
            errors.append("repository.git_sha is invalid")
    provider = document.get("provider")
    if not isinstance(provider, dict):
        errors.append("provider must be an object")
    else:
        _reject_unknown_fields(provider, {"name", "version", "command", "generated_at", "capabilities", "limitations"}, "provider", errors)
        for field in ("name", "version", "command", "generated_at"):
            if not _is_nonempty_string(provider.get(field)):
                errors.append(f"provider.{field} must be non-empty")
        for field in ("capabilities", "limitations"):
            if field in provider:
                _validate_string_list(provider.get(field), f"provider.{field}", errors)
    coverage = document.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
    else:
        _reject_unknown_fields(coverage, {"scope", "status", "paths", "excluded_paths", "limitations"}, "coverage", errors)
        _validate_enum(coverage.get("scope"), COVERAGE_SCOPES, "coverage", "scope", errors)
        coverage_status_valid = _validate_enum(coverage.get("status"), COVERAGE_STATUSES, "coverage", "status", errors)
        for field in ("paths", "excluded_paths"):
            if not isinstance(coverage.get(field), list):
                errors.append(f"coverage.{field} must be a list")
            else:
                _validate_string_list(coverage[field], f"coverage.{field}", errors)
        if "limitations" in coverage:
            _validate_string_list(coverage.get("limitations"), "coverage.limitations", errors)
        if map_only and coverage_status_valid and coverage.get("status") == "unknown":
            errors.append("map-only coverage.status cannot be unknown")

    _validate_source_coverage(document, errors)
    _validate_audit_coverage(document, errors)
    _validate_reviews(document, errors)
    if graph_type_valid and graph_type == "change":
        if not _is_sha(document.get("baseline_sha")):
            errors.append("change graph requires a valid baseline_sha")
        if not _is_sha(document.get("current_sha")):
            errors.append("change graph requires a valid current_sha")
        diff = document.get("diff")
        if not isinstance(diff, dict):
            errors.append("change graph requires a diff object")
        else:
            _validate_diff(diff, "change graph diff", errors)
    elif "diff" in document:
        _validate_diff(document.get("diff"), "diff", errors)

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
        _reject_unknown_fields(node, {"node_id", "kind", "status", "path", "qualified_symbol", "source_anchor", "provider", "git_sha", "confidence", "coverage", "freshness", "verification_evidence", "requirement_refs", "entrypoint", "test_refs", "test_exemption_reason"}, label, errors)
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
        if not _is_number(confidence) or not 0 <= confidence <= 1:
            errors.append(f"{label} confidence must be between 0 and 1")
        _validate_common(node, label, errors, graph_type if graph_type_valid else "observed")
        _validate_anchor(node, label, errors, field_required=False)
        if map_only and isinstance(node.get("status"), str) and node.get("status") not in {"observed", "verified", "blocked", "unresolved"}:
            errors.append(f"{label} map-only status must be observed, verified, blocked, or unresolved")
        _validate_optional_string(node, "test_exemption_reason", label, errors, nonempty=True)

    edge_ids: set[str] = set()
    for index, edge in enumerate(edges):
        label = f"edges[{index}]"
        if not isinstance(edge, dict):
            errors.append(f"{label} must be an object")
            continue
        _reject_unknown_fields(edge, {"edge_id", "kind", "from", "to", "status", "provider", "git_sha", "source_anchor", "confidence", "coverage", "freshness", "verification_evidence", "requirement_refs", "unresolved_reason", "next_query"}, label, errors)
        edge_id = edge.get("edge_id")
        if not _is_nonempty_string(edge_id):
            errors.append(f"{label} edge_id must be non-empty")
        elif edge_id in edge_ids:
            errors.append(f"duplicate edge_id: {edge_id}")
        else:
            edge_ids.add(edge_id)
        _validate_enum(edge.get("kind"), EDGE_KINDS, label, "kind", errors)
        from_id = edge.get("from")
        to_id = edge.get("to")
        if not _is_nonempty_string(from_id) or not _is_nonempty_string(to_id) or from_id not in node_ids or to_id not in node_ids:
            errors.append(f"{label} endpoint does not reference an existing node")
        confidence = edge.get("confidence")
        if not _is_number(confidence) or not 0 <= confidence <= 1:
            errors.append(f"{label} confidence must be between 0 and 1")
        _validate_common(edge, label, errors, graph_type if graph_type_valid else "observed")
        _validate_anchor(edge, label, errors, field_required=True)
        if map_only and isinstance(edge.get("status"), str) and edge.get("status") not in {"observed", "verified", "blocked", "unresolved"}:
            errors.append(f"{label} map-only status must be observed, verified, blocked, or unresolved")
        if edge.get("kind") == "dynamic" and edge.get("status") != "unresolved":
            errors.append(f"{label} dynamic edge must remain unresolved")
        if edge.get("status") == "unresolved":
            if not _is_nonempty_string(edge.get("unresolved_reason")):
                errors.append(f"{label} unresolved requires unresolved_reason")
            if not _is_nonempty_string(edge.get("next_query")):
                errors.append(f"{label} unresolved requires next_query")
        _validate_optional_string(edge, "unresolved_reason", label, errors)
        _validate_optional_string(edge, "next_query", label, errors)

    for index, section in enumerate(_safe_list(document.get("source_coverage"))):
        if not isinstance(section, dict):
            continue
        label = f"source_coverage[{index}]"
        for ref in _string_items(section.get("target_node_refs")):
            if ref not in node_ids:
                errors.append(f"{label} target_node_refs references unknown node: {ref}")
        for ref in _string_items(section.get("target_edge_refs")):
            if ref not in edge_ids:
                errors.append(f"{label} target_edge_refs references unknown edge: {ref}")

    incident_nodes = {
        endpoint
        for edge in edges
        if isinstance(edge, dict)
        for endpoint in (edge.get("from"), edge.get("to"))
        if _is_nonempty_string(endpoint)
    }
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if isinstance(node.get("status"), str) and node.get("status") in {"removed", "blocked", "unresolved"}:
            continue
        node_id = node.get("node_id")
        if _is_nonempty_string(node_id) and node_id not in incident_nodes and not node.get("entrypoint") and not node.get("test_refs"):
            errors.append(f"orphan node: {node.get('node_id')}")

    _validate_test_chains(document, errors, [node for node in nodes if isinstance(node, dict)], [edge for edge in edges if isinstance(edge, dict)])
    _validate_contracts(document, errors, node_ids, [edge for edge in edges if isinstance(edge, dict)], map_only=map_only)
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
