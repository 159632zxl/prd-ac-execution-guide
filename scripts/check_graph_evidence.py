#!/usr/bin/env python3
"""Validate normalized PRD code-graph evidence without third-party packages."""

from __future__ import annotations

import argparse
import json
import math
import posixpath
import re
import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from scripts.check_prd_ac import (
        contains_disallowed_control,
        contains_explicit_placeholder,
        normalize_validation_text,
    )
except ModuleNotFoundError:  # direct execution from the scripts directory
    from check_prd_ac import (
        contains_disallowed_control,
        contains_explicit_placeholder,
        normalize_validation_text,
    )


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
TEST_STATUSES = {"planned", "observed", "implemented", "verified", "blocked", "unresolved", "deferred"}
TEST_SCOPES = {"targeted", "full", "expanded"}
FACTUAL_STATUSES = {"observed", "changed", "implemented", "verified"}
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
NON_EVIDENCE_RE = re.compile(r"^(?:[.\-?]+|n/?a|none|null|nil|无|没有|见上|同上)$", re.IGNORECASE)
BARE_ATTESTATION_RE = re.compile(
    r"^(?:"
    r"ok|pass(?:ed)?|done|works?|working|verified|success(?:ful)?|succeeded|"
    r"confirmed|checked|tested|valid|正常|通过|完成|已完成|已验证|已确认|已检查|"
    r"成功|有效|可用|没问题|无问题"
    r")[.!?。！？]*$",
    re.IGNORECASE,
)
NEGATED_EVIDENCE_RE = re.compile(
    r"^(?:"
    # Evidence fields must contain an observation, not an assertion that an
    # observation was unavailable.  Keep this anchored at the beginning so a
    # legitimate result such as "query found no duplicate rows" remains valid.
    r"no\s+(?:(?:independent|runtime|static|test)\s+)?(?:evidence|verification|tests?|testing|results?)\b.*"
    r"|(?:not|never)\s+(?:run|executed|tested|verified|checked|performed)\b.*"
    r"|(?:without|missing)\s+(?:(?:independent|runtime|static|test)\s+)?(?:evidence|verification|results?)\b.*"
    r"|(?:无|没有|暂无)(?:独立|运行时|静态|测试)?(?:证据|验证|测试|结果)(?:\s|[：:]|$).*"
    r"|(?:未|尚未)(?:运行|执行|测试|验证|检查)(?:\s|[：:]|$).*"
    r")(?:[.!?。！？]*)$",
    re.IGNORECASE,
)
NEGATED_EVIDENCE_EXTENDED_RE = re.compile(
    r"^(?:"
    r"no\s+(?:(?:independent|runtime|static|test)\s+)?"
    r"(?:evidence|verification|tests?|testing|results?)"
    r"(?:\s+(?:available|provided|found|exists?|was\s+(?:available|provided|found))\b.*)?"
    r"|(?:not|never)\s+(?:run|executed|tested|verified|checked|performed)"
    r"(?:\s+(?:yet|because|due\s+to|as|since|until)\b.*)?"
    r"|(?:without|missing)\s+(?:(?:independent|runtime|static|test)\s+)?"
    r"(?:evidence|verification|results?)(?:\s+(?:available|provided|found|exists?)\b.*)?"
    r"|(?:evidence|verification|tests?|testing|results?)\s+"
    r"(?:unavailable|missing|not\s+(?:available|provided|found))\b.*"
    r"|(?:无|没有|暂无)(?:独立|运行时|静态|测试)?(?:证据|验证|测试|结果)"
    r"(?:可用|缺失|不存在|未提供|未找到)?(?:[，,：:；;。.!?].*)?"
    r"|(?:未|尚未)(?:运行|执行|测试|验证|检查)"
    r"(?:[，,：:；;。.!?].*)?"
    r")$",
    re.IGNORECASE,
)
SQLITE_FOREIGN_KEY_CHECK_RE = re.compile(
    r"^PRAGMA\s+(?:(?:[A-Za-z_][A-Za-z0-9_]*|\"[^\"\r\n]+\"|\[[^\]\r\n]+\]|`[^`\r\n]+`)\s*\.\s*)?"
    r"foreign_key_check(?:\s*\([^;\r\n]+\))?\s*;?$",
    re.IGNORECASE,
)
DUPLICATE_QUERY_RE = re.compile(
    r"^(?:SELECT|WITH)\b(?:(?!;)[\s\S])*(?:;)?$", re.IGNORECASE
)
SQL_WRITE_KEYWORD_RE = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)
RFC3339_TIMESTAMP_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)
STORAGE_KIND_BY_NODE_KIND = {
    "table": "sql_table",
    "sql_table": "sql_table",
    "sql-table": "sql_table",
    "column": "sql_field",
    "field": "sql_field",
    "sql_field": "sql_field",
    "sql-field": "sql_field",
    "cache": "cache",
    "event": "event",
    "interface": "interface",
    "file": "file",
}


def _is_storage_node_kind(value: Any) -> bool:
    """Return whether a node kind denotes a persistence/boundary object."""

    return isinstance(value, str) and value.strip().casefold() in {
        *STORAGE_KIND_BY_NODE_KIND,
        "storage",
        "database",
        "db",
    }


def _is_read_only_duplicate_query(value: Any) -> bool:
    """Conservatively validate a single read-only duplicate query."""

    if not isinstance(value, str):
        return False
    query = value.strip()
    if not query or not DUPLICATE_QUERY_RE.fullmatch(query):
        return False
    # Ignore keywords inside quoted identifiers/literals when checking for
    # obvious write statements.  Semicolons are intentionally checked on the
    # original text by DUPLICATE_QUERY_RE, so comments cannot hide a second
    # statement.
    scan = re.sub(
        r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]",
        " ",
        query,
    )
    scan = re.sub(r"--[^\r\n]*|/\*[\s\S]*?\*/", " ", scan)
    return SQL_WRITE_KEYWORD_RE.search(scan) is None


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_concrete_string(value: Any) -> bool:
    if not _is_nonempty_string(value):
        return False
    text = normalize_validation_text(value.strip())
    return not (
        contains_explicit_placeholder(text)
        or contains_disallowed_control(text)
    )


def _is_meaningful_string(value: Any) -> bool:
    if not _is_concrete_string(value):
        return False
    normalized = normalize_validation_text(value.strip())
    return not (
        NON_EVIDENCE_RE.fullmatch(normalized)
        or NEGATED_EVIDENCE_RE.fullmatch(normalized)
        or NEGATED_EVIDENCE_EXTENDED_RE.fullmatch(normalized)
    )


def _validate_concrete_string(value: Any, label: str, errors: list[str]) -> bool:
    if not _is_nonempty_string(value):
        errors.append(f"{label} must be non-empty")
        return False
    if not _is_concrete_string(value):
        errors.append(f"{label} contains a placeholder")
        return False
    if value != value.strip():
        errors.append(f"{label} must not contain leading or trailing whitespace")
        return False
    return True


def _validate_meaningful_string(value: Any, label: str, errors: list[str]) -> bool:
    if not _is_nonempty_string(value):
        errors.append(f"{label} must be non-empty")
        return False
    if not _is_meaningful_string(value):
        errors.append(f"{label} contains a placeholder")
        return False
    return True


def _validate_identifier(value: Any, label: str, errors: list[str]) -> bool:
    if not _validate_meaningful_string(value, label, errors):
        return False
    if value != value.strip():
        errors.append(f"{label} must not contain leading or trailing whitespace")
        return False
    return True


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_PATTERN.fullmatch(value))


def _is_rfc3339_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not RFC3339_TIMESTAMP_RE.fullmatch(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _is_number(value: Any) -> bool:
    return type(value) in (int, float) and (not isinstance(value, float) or math.isfinite(value))


def _iter_nested_values(value: Any) -> Iterator[Any]:
    stack = [value]
    visited: set[int] = set()
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            identity = id(current)
            if identity in visited:
                continue
            visited.add(identity)
            stack.extend(current.keys())
            stack.extend(current.values())
        elif isinstance(current, list):
            identity = id(current)
            if identity in visited:
                continue
            visited.add(identity)
            stack.extend(current)
        else:
            yield current


def _contains_non_finite_number(value: Any) -> bool:
    return any(isinstance(item, float) and not math.isfinite(item) for item in _iter_nested_values(value))


def _contains_placeholder_string(value: Any) -> bool:
    return any(
        isinstance(item, str)
        and (
            contains_explicit_placeholder(item)
            or contains_disallowed_control(item)
        )
        for item in _iter_nested_values(value)
    )


def _has_concrete_strategy_parameters(value: Any) -> bool:
    stack = [value]
    visited: set[int] = set()
    while stack:
        current = stack.pop()
        if isinstance(current, str):
            if current != current.strip() or not _is_meaningful_string(current):
                return False
        elif isinstance(current, bool):
            continue
        elif type(current) in (int, float):
            if not _is_number(current):
                return False
        elif isinstance(current, dict):
            if not current or id(current) in visited:
                return False
            visited.add(id(current))
            if any(
                not isinstance(key, str)
                or key != key.strip()
                or not _is_meaningful_string(key)
                for key in current
            ):
                return False
            stack.extend(current.values())
        elif isinstance(current, list):
            if not current or id(current) in visited:
                return False
            visited.add(id(current))
            stack.extend(current)
        else:
            return False
    return True


def _is_repository_relative_path(value: Any, *, allow_dot: bool = False) -> bool:
    if not _is_nonempty_string(value):
        return False
    normalized = value.strip().replace("\\", "/")
    if normalized == ".":
        return allow_dot
    if normalized.startswith(("/", "~/")) or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", normalized):
        return False
    return ".." not in normalized.split("/")


def _normalize_repository_path(value: str) -> str:
    return posixpath.normpath(value.strip().replace("\\", "/"))


def _path_is_within(path: str, root: str) -> bool:
    return root == "." or path == root or path.startswith(root.rstrip("/") + "/")


def _validate_path_coverage(
    value: Any,
    label: str,
    included_paths: set[str],
    excluded_paths: set[str],
    errors: list[str],
) -> None:
    if not _is_repository_relative_path(value):
        return
    normalized = _normalize_repository_path(value)
    if included_paths and not any(_path_is_within(normalized, root) for root in included_paths):
        errors.append(f"{label} is outside coverage.paths: {normalized}")
    if any(_path_is_within(normalized, root) for root in excluded_paths):
        errors.append(f"{label} is inside coverage.excluded_paths: {normalized}")


def _validate_repository_relative_path(
    value: Any,
    label: str,
    errors: list[str],
    *,
    allow_dot: bool = False,
) -> bool:
    if not _validate_concrete_string(value, label, errors):
        return False
    if not _is_repository_relative_path(value, allow_dot=allow_dot):
        errors.append(f"{label} must be a repository-relative path without traversal")
        return False
    return True


def _validate_recovery_fields(item: dict[str, Any], label: str, status: Any, errors: list[str]) -> None:
    if not isinstance(status, str):
        return
    if status == "blocked" and not _is_meaningful_string(item.get("blocked_reason")):
        errors.append(f"{label} blocked requires blocked_reason")
    if status == "unresolved" and not _is_meaningful_string(item.get("unresolved_reason")):
        errors.append(f"{label} unresolved requires unresolved_reason")
    if status in {"blocked", "unresolved"} and not _is_meaningful_string(item.get("next_query")):
        errors.append(f"{label} {status} requires next_query recovery action")


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


def _is_status(value: Any, *statuses: str) -> bool:
    """Test an arbitrary status without hashing malformed list/dict values."""
    return isinstance(value, str) and value in statuses


def _validate_string_list(value: Any, label: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    valid: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"{label}[{index}] must be a string")
            continue
        if not item.strip():
            errors.append(f"{label}[{index}] must be non-empty")
            continue
        normalized = item.strip()
        if normalized in seen:
            errors.append(f"{label}[{index}] is a duplicate value: {normalized}")
        else:
            seen.add(normalized)
        valid.append(item)
    return valid


def _validate_reference_list(value: Any, label: str, errors: list[str]) -> list[str]:
    items = _validate_string_list(value, label, errors)
    return [
        item
        for index, item in enumerate(items)
        if _validate_identifier(item, f"{label}[{index}]", errors)
    ]


def _validate_concrete_string_list(value: Any, label: str, errors: list[str]) -> list[str]:
    items = _validate_string_list(value, label, errors)
    return [
        item
        for index, item in enumerate(items)
        if _validate_concrete_string(item, f"{label}[{index}]", errors)
    ]


def _validate_evidence(value: Any, label: str, errors: list[str]) -> list[str]:
    items = _validate_string_list(value, label, errors)
    for index, item in enumerate(items):
        stripped = item.strip()
        normalized = normalize_validation_text(stripped)
        if item != stripped:
            errors.append(f"{label}[{index}] must not contain leading or trailing whitespace")
        if contains_explicit_placeholder(normalized):
            errors.append(f"{label}[{index}] contains a placeholder")
        elif contains_disallowed_control(normalized):
            errors.append(f"{label}[{index}] evidence contains a disallowed control character")
        elif len(normalized) < 2 or NON_EVIDENCE_RE.fullmatch(normalized):
            errors.append(f"{label}[{index}] is not usable evidence")
        elif BARE_ATTESTATION_RE.fullmatch(normalized):
            errors.append(f"{label}[{index}] is only a conclusion, not evidence")
        elif (
            NEGATED_EVIDENCE_RE.fullmatch(normalized)
            or NEGATED_EVIDENCE_EXTENDED_RE.fullmatch(normalized)
        ):
            errors.append(f"{label}[{index}] explicitly states that evidence is unavailable")
    return items


def _validate_optional_string(
    item: dict[str, Any],
    field: str,
    label: str,
    errors: list[str],
    nonempty: bool = False,
    meaningful: bool = False,
) -> None:
    if field not in item:
        return
    value = item.get(field)
    if not isinstance(value, str):
        errors.append(f"{label} {field} must be a string")
    elif nonempty and not value.strip():
        errors.append(f"{label} {field} must be non-empty")
    elif meaningful and not _is_meaningful_string(value):
        errors.append(f"{label} {field} contains a placeholder")


def _validate_string_map(value: Any, label: str, errors: list[str]) -> dict[str, str]:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return {}
    valid: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            errors.append(f"{label} keys must be non-empty strings")
        if not _validate_meaningful_string(item, f"{label}.{key}", errors):
            continue
        if isinstance(key, str):
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
        valid[key] = _validate_reference_list(item, f"{label}.{key}", errors)
    return valid


def _reject_unknown_fields(item: dict[str, Any], allowed: set[str], label: str, errors: list[str]) -> None:
    for field in item:
        if field not in allowed:
            errors.append(f"{label} unknown field: {field}")


def _validate_diff(
    value: Any,
    label: str,
    errors: list[str],
    node_ids: set[str] | None = None,
    edge_ids: set[str] | None = None,
    contract_ids: set[str] | None = None,
    node_statuses: dict[str, Any] | None = None,
    edge_statuses: dict[str, Any] | None = None,
    contract_statuses: dict[str, Any] | None = None,
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return
    _reject_unknown_fields(
        value,
        {
            "added_nodes", "removed_nodes", "changed_nodes",
            "added_edges", "removed_edges", "changed_edges",
            "added_contracts", "removed_contracts", "changed_contracts",
            "unresolved", "impact", "verification_evidence",
        },
        label,
        errors,
    )
    diff_fields = (
        "added_nodes", "removed_nodes", "changed_nodes",
        "added_edges", "removed_edges", "changed_edges",
        "added_contracts", "removed_contracts", "changed_contracts",
        "unresolved",
    )
    for field in diff_fields:
        if not isinstance(value.get(field), list):
            errors.append(f"{label}.{field} must be a list")
        else:
            _validate_concrete_string_list(value[field], f"{label}.{field}", errors)
    impact_items = _validate_evidence(value.get("impact"), f"{label}.impact", errors)
    if not impact_items:
        errors.append(f"{label}.impact must be non-empty")
    reference_sets: dict[str, set[str]] = {}
    for field in (
        "added_nodes", "removed_nodes", "changed_nodes",
        "added_edges", "removed_edges", "changed_edges",
        "added_contracts", "removed_contracts", "changed_contracts",
    ):
        items = _string_items(value.get(field))
        reference_sets[field] = set(items)
        if len(items) != len(set(items)):
            errors.append(f"{label}.{field} contains duplicate references")
    for kind, fields in (
        ("node", ("added_nodes", "removed_nodes", "changed_nodes")),
        ("edge", ("added_edges", "removed_edges", "changed_edges")),
        ("contract", ("added_contracts", "removed_contracts", "changed_contracts")),
    ):
        seen: set[str] = set()
        for field in fields:
            for ref in sorted(reference_sets[field] & seen):
                errors.append(f"{label} reference appears in multiple {kind} change categories: {ref}")
            seen.update(reference_sets[field])
    evidence = _validate_evidence(value.get("verification_evidence"), f"{label}.verification_evidence", errors)
    if not evidence:
        errors.append(f"{label} requires verification_evidence")
    if node_ids is not None and edge_ids is not None and contract_ids is not None:
        for field in ("added_nodes", "changed_nodes"):
            for ref in _string_items(value.get(field)):
                if ref not in node_ids:
                    errors.append(f"{label}.{field} references unknown node: {ref}")
                elif field == "changed_nodes" and node_statuses is not None and not _is_status(
                    node_statuses.get(ref), "changed", "implemented", "verified"
                ):
                    errors.append(
                        f"{label}.changed_nodes reference must have a changed/implemented/verified status: {ref}"
                    )
        for field in ("added_edges", "changed_edges"):
            for ref in _string_items(value.get(field)):
                if ref not in edge_ids:
                    errors.append(f"{label}.{field} references unknown edge: {ref}")
                elif field == "changed_edges" and edge_statuses is not None and not _is_status(
                    edge_statuses.get(ref), "changed", "implemented", "verified"
                ):
                    errors.append(
                        f"{label}.changed_edges reference must have a changed/implemented/verified status: {ref}"
                    )
        for field in ("added_contracts", "changed_contracts"):
            for ref in _string_items(value.get(field)):
                if ref not in contract_ids:
                    errors.append(f"{label}.{field} references unknown contract: {ref}")
                elif field == "changed_contracts" and contract_statuses is not None and not _is_status(
                    contract_statuses.get(ref), "changed", "implemented", "verified"
                ):
                    errors.append(
                        f"{label}.changed_contracts reference must have a changed/implemented/verified status: {ref}"
                    )
        for field in ("removed_nodes",):
            for ref in _string_items(value.get(field)):
                if ref in node_ids:
                    errors.append(f"{label}.{field} references an item still present in the current graph: {ref}")
        for field in ("removed_edges",):
            for ref in _string_items(value.get(field)):
                if ref in edge_ids:
                    errors.append(f"{label}.{field} references an item still present in the current graph: {ref}")
        for ref in _string_items(value.get("removed_contracts")):
            if ref in contract_ids:
                errors.append(
                    f"{label}.removed_contracts references an item still present in the current graph: {ref}"
                )
        unresolved_refs = set(_string_items(value.get("unresolved")))
        for ref in unresolved_refs:
            if ref not in node_ids and ref not in edge_ids and ref not in contract_ids:
                errors.append(f"{label}.unresolved references unknown node, edge, or contract: {ref}")
            elif (
                ref in node_ids
                and node_statuses is not None
                and not _is_status(node_statuses.get(ref), "unresolved")
            ) or (
                ref in edge_ids
                and edge_statuses is not None
                and not _is_status(edge_statuses.get(ref), "unresolved")
            ) or (
                ref in contract_ids
                and contract_statuses is not None
                and not _is_status(contract_statuses.get(ref), "unresolved")
            ):
                errors.append(f"{label}.unresolved reference must have unresolved status: {ref}")
        if node_statuses is not None:
            for ref, status in node_statuses.items():
                if status == "unresolved" and ref not in unresolved_refs:
                    errors.append(f"{label}.unresolved omits unresolved node: {ref}")
                if status == "changed" and ref not in reference_sets["changed_nodes"]:
                    errors.append(f"{label}.changed_nodes omits changed node: {ref}")
        if edge_statuses is not None:
            for ref, status in edge_statuses.items():
                if status == "unresolved" and ref not in unresolved_refs:
                    errors.append(f"{label}.unresolved omits unresolved edge: {ref}")
                if status == "changed" and ref not in reference_sets["changed_edges"]:
                    errors.append(f"{label}.changed_edges omits changed edge: {ref}")
        if contract_statuses is not None:
            for ref, status in contract_statuses.items():
                if status == "unresolved" and ref not in unresolved_refs:
                    errors.append(f"{label}.unresolved omits unresolved contract: {ref}")
                if status == "changed" and ref not in reference_sets["changed_contracts"]:
                    errors.append(f"{label}.changed_contracts omits changed contract: {ref}")
        if not any(
            _string_items(value.get(field))
            for field in (
                "added_nodes", "removed_nodes", "changed_nodes",
                "added_edges", "removed_edges", "changed_edges",
                "added_contracts", "removed_contracts", "changed_contracts",
            )
        ):
            errors.append(f"{label} requires at least one added, removed, or changed node/edge/contract")


def _validate_source_anchor(anchor: Any, label: str, errors: list[str]) -> None:
    if not isinstance(anchor, dict):
        errors.append(f"{label} source_anchor must be an object")
        return
    _reject_unknown_fields(anchor, {"path", "start_line", "end_line"}, f"{label} source_anchor", errors)
    _validate_repository_relative_path(anchor.get("path"), f"{label} source_anchor.path", errors)
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
    _validate_meaningful_string(item.get("provider"), f"{label} provider", errors)
    if not _is_sha(item.get("git_sha")):
        errors.append(f"{label} git_sha is invalid")
    _validate_enum(item.get("coverage"), COVERAGE_STATUSES, label, "coverage", errors)
    _validate_enum(item.get("freshness"), FRESHNESS, label, "freshness", errors)
    verification_evidence: list[str] = []
    if not isinstance(item.get("verification_evidence"), list):
        errors.append(f"{label} verification_evidence must be a list")
    else:
        verification_evidence = _validate_evidence(
            item["verification_evidence"], f"{label} verification_evidence", errors
        )
    if not isinstance(item.get("requirement_refs"), list):
        errors.append(f"{label} requirement_refs must be a list")
    else:
        _validate_reference_list(item["requirement_refs"], f"{label} requirement_refs", errors)
    if "entrypoint" in item and not isinstance(item.get("entrypoint"), bool):
        errors.append(f"{label} entrypoint must be a boolean")
    status_valid = _validate_enum(item.get("status"), STATUSES, label, "status", errors)
    if status_valid and item.get("status") in FACTUAL_STATUSES and not verification_evidence:
        errors.append(f"{label} {item.get('status')} requires verification_evidence")
    if graph_type == "observed" and status_valid and item.get("status") in {"planned", "changed"}:
        errors.append(f"{label} observed graph cannot use status {item.get('status')}")
    if graph_type == "change" and status_valid and item.get("status") == "planned":
        errors.append(f"{label} change graph cannot use status planned")
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
        if _validate_identifier(section_id, f"{label} source_section_id", errors):
            if section_id in ids:
                errors.append(f"duplicate source_section_id: {section_id}")
            else:
                ids.add(section_id)
        for field in ("owner_task", "source_anchor"):
            if field not in section:
                errors.append(f"{label} missing {field}")
        if "owner_task" in section:
            _validate_meaningful_string(section.get("owner_task"), f"{label} owner_task", errors)
        if "source_anchor" in section and section.get("source_anchor") is not None and not isinstance(section.get("source_anchor"), dict):
            errors.append(f"{label} source_anchor must be an object or null")
        elif section.get("source_anchor") is not None:
            _validate_source_anchor(section.get("source_anchor"), label, errors)
        status = section.get("status")
        status_valid = _validate_enum(status, SOURCE_COVERAGE_STATUSES, label, "status", errors)
        requirement_refs = _validate_reference_list(section.get("requirement_refs"), f"{label} requirement_refs", errors)
        ears_refs = _validate_reference_list(section.get("ears_refs"), f"{label} ears_refs", errors)
        target_node_refs = _validate_reference_list(section.get("target_node_refs"), f"{label} target_node_refs", errors)
        target_edge_refs = _validate_reference_list(section.get("target_edge_refs"), f"{label} target_edge_refs", errors)
        ac_refs = _validate_reference_list(section.get("ac_refs"), f"{label} ac_refs", errors)
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
            if not _is_meaningful_string(section.get("owner_task")):
                errors.append(f"{label} covered requires owner task")
            if section.get("source_anchor") is None:
                errors.append(f"{label} covered requires source_anchor")
            else:
                _validate_source_anchor(section.get("source_anchor"), label, errors)
        if status_valid and status in {"deferred", "not-applicable"} and not _is_meaningful_string(section.get("explicit_reason")):
            errors.append(f"{label} {status} requires explicit_reason")
        _validate_optional_string(section, "explicit_reason", label, errors, meaningful=True)


def _validate_source_coverage_links(
    document: dict[str, Any],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    errors: list[str],
) -> None:
    sections = [
        section
        for section in _safe_list(document.get("source_coverage"))
        if isinstance(section, dict)
    ]
    node_by_id = {
        node["node_id"]: node
        for node in nodes
        if _is_nonempty_string(node.get("node_id"))
    }
    edge_by_id = {
        edge["edge_id"]: edge
        for edge in edges
        if _is_nonempty_string(edge.get("edge_id"))
    }
    chains = [
        chain
        for chain in _safe_list(document.get("test_chains"))
        if isinstance(chain, dict)
    ]

    declared_requirements = {
        ref
        for section in sections
        for ref in _string_items(section.get("requirement_refs"))
    }
    declared_ac_refs = {
        ref
        for section in sections
        for ref in _string_items(section.get("ac_refs"))
    }
    for collection_label, items in (("nodes", nodes), ("edges", edges), ("test_chains", chains)):
        for index, item in enumerate(items):
            for ref in _string_items(item.get("requirement_refs")):
                if ref not in declared_requirements:
                    errors.append(
                        f"{collection_label}[{index}].requirement_refs references requirement "
                        f"not declared by source_coverage: {ref}"
                    )
    for index, chain in enumerate(chains):
        for ref in _string_items(chain.get("ac_refs")):
            if ref not in declared_ac_refs:
                errors.append(
                    f"test_chains[{index}].ac_refs references AC not declared by source_coverage: {ref}"
                )

    for index, section in enumerate(sections):
        label = f"source_coverage[{index}]"
        target_node_refs = set(_string_items(section.get("target_node_refs")))
        target_edge_refs = set(_string_items(section.get("target_edge_refs")))
        for edge_ref in sorted(target_edge_refs):
            edge = edge_by_id.get(edge_ref)
            if edge is None:
                continue
            for endpoint in (edge.get("from"), edge.get("to")):
                if isinstance(endpoint, str) and endpoint not in target_node_refs:
                    errors.append(
                        f"{label} target_edge_refs endpoint is missing from "
                        f"target_node_refs: {endpoint} (edge {edge_ref})"
                    )
        relevant_chains = []
        for chain in chains:
            chain_node_refs = set(_string_items(chain.get("node_refs"))) | set(
                _string_items(chain.get("test_node_refs"))
            )
            chain_edge_refs = set(_string_items(chain.get("edge_refs")))
            if target_node_refs & chain_node_refs or target_edge_refs & chain_edge_refs:
                relevant_chains.append(chain)

        linked_requirements = {
            requirement
            for ref in target_node_refs
            if ref in node_by_id
            for requirement in _string_items(node_by_id[ref].get("requirement_refs"))
        } | {
            requirement
            for ref in target_edge_refs
            if ref in edge_by_id
            for requirement in _string_items(edge_by_id[ref].get("requirement_refs"))
        } | {
            requirement
            for chain in relevant_chains
            for requirement in _string_items(chain.get("requirement_refs"))
        }
        linked_ac_refs = {
            ac_ref
            for chain in relevant_chains
            for ac_ref in _string_items(chain.get("ac_refs"))
        }

        for ref in _string_items(section.get("requirement_refs")):
            if ref not in linked_requirements:
                errors.append(
                    f"{label} requirement_refs is not linked to its declared targets or test chains: {ref}"
                )
        for ref in _string_items(section.get("ac_refs")):
            if ref not in linked_ac_refs:
                errors.append(
                    f"{label} ac_refs is not linked to a test chain for its declared targets: {ref}"
                )


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
        if _validate_identifier(finding_id, f"{label} finding_id", errors):
            if finding_id in finding_ids:
                errors.append(f"duplicate finding_id: {finding_id}")
            else:
                finding_ids.add(finding_id)
        status = finding.get("status")
        status_valid = _validate_enum(status, REVIEW_STATUSES, label, "status", errors)
        audit = document.get("audit_coverage")
        audit_status = audit.get("status") if isinstance(audit, dict) else None
        if (
            status_valid
            and status in {"verified", "rejected"}
            and audit_status != "complete"
        ):
            errors.append(
                f"{label} {status} requires audit_coverage.status complete; "
                f"current status is {audit_status or '<missing>'}"
            )
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
            else:
                evidence_keys = {
                    normalize_validation_text(item).strip().casefold()
                    for item in evidence_items
                }
                independent_keys = {
                    normalize_validation_text(item).strip().casefold()
                    for item in independent_items
                }
                overlap = sorted(evidence_keys & independent_keys)
                if overlap:
                    errors.append(
                        f"{label} independent_verification must be distinct from evidence: "
                        + ", ".join(overlap)
                    )
        premises = finding.get("premises", [])
        premises_items = _validate_reference_list(premises, f"{label} premises", errors)
        premise_items: list[str] = []
        if "premise_verification" in finding:
            premise_items = _validate_evidence(
                finding.get("premise_verification"), f"{label} premise_verification", errors
            )
        if status_valid and status == "rejected":
            if not premises_items:
                errors.append(f"{label} rejected requires premises")
            if not premise_items:
                errors.append(f"{label} rejected premises require premise_verification")
        if status_valid and status == "inconclusive" and not _is_meaningful_string(finding.get("inconclusive_reason")):
            errors.append(f"{label} inconclusive requires inconclusive_reason")
        for field in ("inconclusive_reason",):
            _validate_optional_string(finding, field, label, errors, nonempty=True, meaningful=True)


def _validate_audit_coverage(document: dict[str, Any], errors: list[str]) -> None:
    audit = document.get("audit_coverage")
    if not isinstance(audit, dict):
        errors.append("audit_coverage must be an object")
        return
    _reject_unknown_fields(audit, {"status", "reviewers", "independent_verification", "limitations"}, "audit_coverage", errors)
    audit_status_valid = _validate_enum(audit.get("status"), AUDIT_STATUSES, "audit_coverage", "status", errors)
    reviewers = _validate_string_list(audit.get("reviewers"), "audit_coverage.reviewers", errors)
    meaningful_reviewers = [
        reviewer
        for index, reviewer in enumerate(reviewers)
        if _validate_meaningful_string(reviewer, f"audit_coverage.reviewers[{index}]", errors)
    ]
    independent_verification = _validate_evidence(
        audit.get("independent_verification"), "audit_coverage.independent_verification", errors
    )
    limitations = _validate_string_list(audit.get("limitations"), "audit_coverage.limitations", errors)
    meaningful_limitations = [
        limitation
        for index, limitation in enumerate(limitations)
        if _validate_meaningful_string(limitation, f"audit_coverage.limitations[{index}]", errors)
    ]
    if audit_status_valid and audit.get("status") == "complete" and not independent_verification:
        errors.append("audit_coverage complete requires independent_verification")
    if audit_status_valid and audit.get("status") == "complete" and not meaningful_reviewers:
        errors.append("audit_coverage complete requires reviewers")
    if audit_status_valid and audit.get("status") in {"partial", "inconclusive"} and not meaningful_limitations:
        errors.append("audit_coverage partial or inconclusive requires limitations")


def _validate_contracts(
    document: dict[str, Any],
    errors: list[str],
    node_ids: set[str],
    node_kinds: dict[str, str],
    edges: list[dict[str, Any]],
    map_only: bool = False,
    node_statuses: dict[str, Any] | None = None,
    edge_statuses: dict[str, Any] | None = None,
) -> None:
    contracts = _as_list(document.get("contracts"))
    if contracts is None:
        errors.append("contracts must be a list")
        return
    if not contracts:
        errors.append("contracts must be a non-empty list")
    contract_ids: set[str] = set()
    edge_pairs = {
        (edge.get("kind"), edge.get("from"), edge.get("to"))
        for edge in edges
        if isinstance(edge.get("kind"), str)
        and isinstance(edge.get("from"), str)
        and isinstance(edge.get("to"), str)
    }
    edges_by_pair: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for edge in edges:
        kind = edge.get("kind")
        source = edge.get("from")
        target = edge.get("to")
        if isinstance(kind, str) and isinstance(source, str) and isinstance(target, str):
            edges_by_pair.setdefault((kind, source, target), []).append(edge)
    for index, contract in enumerate(contracts):
        label = f"contracts[{index}]"
        if not isinstance(contract, dict):
            errors.append(f"{label} must be an object")
            continue
        _reject_unknown_fields(
            contract,
            {
                "contract_id", "storage_node_id", "storage_kind", "writers", "readers", "writer_milestone", "reader_milestone",
                "foreign_key_check", "foreign_key_check_result", "unique_keys", "nullable_unique_columns", "null_semantics", "null_semantics_blocking_reason",
                "duplicate_query", "duplicate_query_result", "strategy_name", "strategy_status", "strategy_parameters", "strategy_trigger", "strategy_target",
                "strategy_entrypoint", "strategy_blocking_reason", "state_values", "state_semantics", "state_producers",
                "state_consumers", "state_deferred_milestones", "terminal_states", "enum_semantics", "enum_producers",
                "enum_consumers", "enum_values", "schema_enum_values", "expected_runtime_state", "intentional_empty_reason",
                "intentional_empty_milestone", "runtime_evidence", "status", "verification_evidence", "failure_mode",
                "observability_evidence", "distinguishes_failure_from_empty", "implementation_state", "data_audit_evidence", "cleanup_plan",
                "blocked_reason", "unresolved_reason", "next_query",
            },
            label,
            errors,
        )
        contract_id = contract.get("contract_id")
        if _validate_identifier(contract_id, f"{label} contract_id", errors):
            if contract_id in contract_ids:
                errors.append(f"duplicate contract_id: {contract_id}")
            else:
                contract_ids.add(contract_id)
        storage = contract.get("storage_node_id")
        storage_valid = _validate_identifier(storage, f"{label} storage_node_id", errors)
        if not storage_valid or not isinstance(storage, str) or storage not in node_ids:
            errors.append(f"{label} storage_node_id does not reference a node")
        writers = contract.get("writers")
        readers = contract.get("readers")
        if not isinstance(writers, list):
            errors.append(f"{label} writers must be a list")
            writers = []
        else:
            writers = _validate_reference_list(writers, f"{label} writers", errors)
        if not isinstance(readers, list):
            errors.append(f"{label} readers must be a list")
            readers = []
        else:
            readers = _validate_reference_list(readers, f"{label} readers", errors)
        if not isinstance(contract.get("writers"), list) or not isinstance(contract.get("readers"), list):
            errors.append(f"{label} writers and readers must be lists")
        if not writers and not _is_nonempty_string(contract.get("writer_milestone")):
            errors.append(f"{label} requires a writer or writer_milestone")
        if not readers and not _is_nonempty_string(contract.get("reader_milestone")):
            errors.append(f"{label} requires a reader or reader_milestone")
        for writer in writers:
            if writer not in node_ids:
                errors.append(f"{label} writer does not reference a node: {writer}")
            else:
                writer_kind = node_kinds.get(writer)
                if isinstance(writer_kind, str) and writer_kind.casefold() == "test":
                    errors.append(f"{label} writer must reference code nodes, not test nodes: {writer}")
                elif _is_storage_node_kind(writer_kind):
                    errors.append(
                        f"{label} writer must reference code nodes, not storage nodes: {writer}"
                    )
                if storage_valid and isinstance(storage, str) and ("writes", writer, storage) not in edge_pairs:
                    errors.append(f"{label} writer lacks writes edge: {writer} -> {storage}")
        for reader in readers:
            if reader not in node_ids:
                errors.append(f"{label} reader does not reference a node: {reader}")
            else:
                reader_kind = node_kinds.get(reader)
                if isinstance(reader_kind, str) and reader_kind.casefold() == "test":
                    errors.append(f"{label} reader must reference code nodes, not test nodes: {reader}")
                elif _is_storage_node_kind(reader_kind):
                    errors.append(
                        f"{label} reader must reference code nodes, not storage nodes: {reader}"
                    )
                if storage_valid and isinstance(storage, str) and ("reads", storage, reader) not in edge_pairs:
                    errors.append(f"{label} reader lacks reads edge: {storage} -> {reader}")

        state_values = contract.get("state_values")
        state_semantics = contract.get("state_semantics")
        state_producers = contract.get("state_producers")
        state_consumers = contract.get("state_consumers")
        state_deferred_milestones = contract.get("state_deferred_milestones", {})
        terminal_states_list = _validate_concrete_string_list(
            contract.get("terminal_states", []), f"{label} terminal_states", errors
        )
        terminal_states = set(terminal_states_list)
        if not isinstance(state_values, list) or not isinstance(state_semantics, dict) or not isinstance(state_producers, dict) or not isinstance(state_consumers, dict):
            errors.append(f"{label} state_values, state_semantics, state_producers, and state_consumers are required")
        else:
            declared_states = set(_string_items(state_values))
            for field in ("state_semantics", "state_producers", "state_consumers"):
                value = contract.get(field)
                unknown_states = (
                    [key for key in value if not isinstance(key, str) or key not in declared_states]
                    if isinstance(value, dict)
                    else []
                )
                for state in unknown_states:
                    errors.append(f"{label} unknown state key in {field}: {state}")
            if not isinstance(state_deferred_milestones, dict):
                errors.append(f"{label} state_deferred_milestones must be an object")
                state_deferred_milestones = {}
            else:
                for state in (
                    key
                    for key in state_deferred_milestones
                    if not isinstance(key, str) or key not in declared_states
                ):
                    errors.append(f"{label} unknown state key in state_deferred_milestones: {state}")
            for terminal_state in terminal_states:
                if terminal_state not in declared_states:
                    errors.append(f"{label} terminal state is not declared in state_values: {terminal_state}")
            for state in _validate_concrete_string_list(state_values, f"{label} state_values", errors):
                if not _is_nonempty_string(state_semantics.get(state)):
                    errors.append(f"{label} state has no semantic description: {state}")
                producers = state_producers.get(state, [])
                if not isinstance(producers, list):
                    errors.append(f"{label} state producer list is invalid: {state}")
                    producers = []
                else:
                    producers = _validate_reference_list(producers, f"{label} state_producers.{state}", errors)
                if not producers:
                    errors.append(f"{label} state has no producer: {state}")
                for producer in producers:
                    if producer not in node_ids:
                        errors.append(f"{label} state producer does not reference a node: {producer}")
                    elif producer not in writers:
                        errors.append(f"{label} state producer is outside contract closure: {producer}")
                consumers = state_consumers.get(state, [])
                if not isinstance(consumers, list):
                    errors.append(f"{label} state consumer list is invalid: {state}")
                    consumers = []
                else:
                    consumers = _validate_reference_list(consumers, f"{label} state_consumers.{state}", errors)
                if not consumers and state not in terminal_states:
                    if not _is_nonempty_string(state_deferred_milestones.get(state)):
                        errors.append(f"{label} state has no consumer, terminal, or deferred milestone: {state}")
                for consumer in consumers:
                    if consumer not in node_ids:
                        errors.append(f"{label} state consumer does not reference a node: {consumer}")
                    elif consumer not in readers:
                        errors.append(f"{label} state consumer is outside contract closure: {consumer}")

        enum_values = contract.get("enum_values")
        schema_values = contract.get("schema_enum_values")
        validated_enum_values: list[str] = []
        if not isinstance(enum_values, list) or not isinstance(schema_values, list):
            errors.append(f"{label} enum_values and schema_enum_values are required")
        elif not all(isinstance(value, str) for value in enum_values + schema_values):
            errors.append(f"{label} enum values must be strings")
        else:
            validated_enum_values = _validate_concrete_string_list(
                enum_values, f"{label} enum_values", errors
            )
            validated_schema_values = _validate_concrete_string_list(
                schema_values, f"{label} schema_enum_values", errors
            )
            if set(validated_enum_values) != set(validated_schema_values):
                errors.append(f"{label} enum_values and schema_enum_values differ")
        enum_semantics = contract.get("enum_semantics")
        enum_producers = contract.get("enum_producers")
        enum_consumers = contract.get("enum_consumers")
        if not isinstance(enum_semantics, dict) or not isinstance(enum_producers, dict) or not isinstance(enum_consumers, dict):
            errors.append(f"{label} enum_semantics, enum_producers, and enum_consumers are required")
        elif isinstance(enum_values, list):
            declared_enum_values = set(_string_items(enum_values))
            for field, value in (("enum_semantics", enum_semantics), ("enum_producers", enum_producers), ("enum_consumers", enum_consumers)):
                for enum_value in (
                    key for key in value if not isinstance(key, str) or key not in declared_enum_values
                ):
                    errors.append(f"{label} unknown enum key in {field}: {enum_value}")
            for value in validated_enum_values:
                if not _is_nonempty_string(enum_semantics.get(value)):
                    errors.append(f"{label} enum value has no semantic description: {value}")
                producers = enum_producers.get(value, [])
                if not isinstance(producers, list):
                    errors.append(f"{label} enum producer list is invalid: {value}")
                    producers = []
                else:
                    producers = _validate_reference_list(producers, f"{label} enum_producers.{value}", errors)
                if not producers:
                    errors.append(f"{label} enum value has no producer: {value}")
                for producer in producers:
                    if producer not in node_ids:
                        errors.append(f"{label} enum producer does not reference a node: {producer}")
                    elif producer not in writers:
                        errors.append(f"{label} enum producer is outside contract closure: {producer}")
                consumers = enum_consumers.get(value, [])
                if not isinstance(consumers, list):
                    errors.append(f"{label} enum consumer list is invalid: {value}")
                    consumers = []
                else:
                    consumers = _validate_reference_list(consumers, f"{label} enum_consumers.{value}", errors)
                if not consumers:
                    errors.append(f"{label} enum value has no consumer: {value}")
                for consumer in consumers:
                    if consumer not in node_ids:
                        errors.append(f"{label} enum consumer does not reference a node: {consumer}")
                    elif consumer not in readers:
                        errors.append(f"{label} enum consumer is outside contract closure: {consumer}")

        expected = contract.get("expected_runtime_state")
        expected_valid = _validate_enum(expected, EXPECTED_RUNTIME_STATES, label, "expected_runtime_state", errors)
        runtime_evidence = contract.get("runtime_evidence")
        runtime_evidence_items = _validate_evidence(runtime_evidence, f"{label} runtime_evidence", errors)
        if expected_valid and expected == "non-empty" and not runtime_evidence_items:
            errors.append(f"{label} non-empty requires runtime_evidence")
        elif expected_valid and expected == "intentionally empty":
            if not _is_meaningful_string(contract.get("intentional_empty_reason")):
                errors.append(f"{label} intentionally empty requires a reason")
            if not _is_meaningful_string(contract.get("intentional_empty_milestone")):
                errors.append(f"{label} intentionally empty requires a milestone")
        contract_status_valid = _validate_enum(contract.get("status"), STATUSES, label, "status", errors)
        if contract_status_valid and contract.get("status") == "removed":
            errors.append(f"{label} removed objects belong only in change graph diff.removed_* references")
        if contract_status_valid and contract.get("status") in {"implemented", "verified"}:
            if not writers:
                errors.append(
                    f"{label} {contract.get('status')} contract requires a real writer; "
                    "writer_milestone cannot substitute for completed closure"
                )
            if not readers:
                errors.append(
                    f"{label} {contract.get('status')} contract requires a real reader; "
                    "reader_milestone cannot substitute for completed closure"
                )
        if (
            document.get("graph_type") == "observed"
            and contract_status_valid
            and _is_status(contract.get("status"), "planned", "changed")
        ):
            errors.append(f"{label} observed graph cannot use status {contract.get('status')}")
        if (
            document.get("graph_type") == "change"
            and contract_status_valid
            and contract.get("status") == "planned"
        ):
            errors.append(f"{label} change graph cannot use status planned")
        if (
            map_only
            and contract_status_valid
            and not _is_status(contract.get("status"), "observed", "verified", "blocked", "unresolved", "deferred")
        ):
            errors.append(f"{label} map-only status is not an observed/deferred status")
        if "verification_evidence" not in contract:
            errors.append(f"{label} missing verification_evidence")
        else:
            verification_evidence_items = _validate_evidence(
                contract.get("verification_evidence"), f"{label} verification_evidence", errors
            )
            if (
                contract_status_valid
                and contract.get("status") in FACTUAL_STATUSES
                and not verification_evidence_items
            ):
                errors.append(
                    f"{label} {contract.get('status')} requires verification_evidence"
                )
        _validate_recovery_fields(contract, label, contract.get("status"), errors)

        # A verified/implemented contract cannot claim a closed, observable
        # boundary while any of its storage, writer, reader, or I/O edges are
        # blocked, unresolved, planned, or deferred.
        if contract_status_valid and contract.get("status") in {"implemented", "verified"}:
            dependency_statuses = {"blocked", "unresolved", "planned", "deferred"}
            dependency_nodes = [storage, *writers, *readers]
            for dependency in dependency_nodes:
                dependency_status = (
                    node_statuses.get(dependency)
                    if isinstance(dependency, str) and node_statuses is not None
                    else None
                )
                if _is_status(dependency_status, *dependency_statuses):
                    errors.append(
                        f"{label} {contract.get('status')} contract cannot rely on "
                        f"{dependency_status} node: {dependency}"
                    )
            for writer in writers:
                if not isinstance(writer, str) or not isinstance(storage, str):
                    continue
                for edge in edges_by_pair.get(("writes", writer, storage), []):
                    edge_id = edge.get("edge_id")
                    edge_status = (
                        edge_statuses.get(edge_id, edge.get("status"))
                        if edge_statuses is not None and isinstance(edge_id, str)
                        else edge.get("status")
                    )
                    if _is_status(edge_status, *dependency_statuses):
                        errors.append(
                            f"{label} {contract.get('status')} contract cannot rely on "
                            f"{edge_status} writer edge: {edge.get('edge_id')}"
                        )
            for reader in readers:
                if not isinstance(reader, str) or not isinstance(storage, str):
                    continue
                for edge in edges_by_pair.get(("reads", storage, reader), []):
                    edge_id = edge.get("edge_id")
                    edge_status = (
                        edge_statuses.get(edge_id, edge.get("status"))
                        if edge_statuses is not None and isinstance(edge_id, str)
                        else edge.get("status")
                    )
                    if _is_status(edge_status, *dependency_statuses):
                        errors.append(
                            f"{label} {contract.get('status')} contract cannot rely on "
                            f"{edge_status} reader edge: {edge.get('edge_id')}"
                        )

        storage_kind = contract.get("storage_kind")
        if not _validate_enum(storage_kind, STORAGE_KINDS, label, "storage_kind", errors):
            storage_kind = None
        node_kind = node_kinds.get(storage) if isinstance(storage, str) else None
        expected_storage_kind = (
            STORAGE_KIND_BY_NODE_KIND.get(node_kind.lower())
            if isinstance(node_kind, str)
            else None
        )
        if (
            expected_storage_kind is not None
            and storage_kind is not None
            and storage_kind != expected_storage_kind
        ):
            errors.append(
                f"{label} storage_kind does not match storage node kind {node_kind}: "
                f"expected {expected_storage_kind}"
            )
        elif (
            isinstance(storage_kind, str)
            and storage_kind not in {"other"}
            and expected_storage_kind is None
        ):
            errors.append(
                f"{label} storage_kind cannot be verified for unknown storage node kind: {node_kind}"
            )
        for field in (
            "writer_milestone", "reader_milestone", "foreign_key_check", "null_semantics_blocking_reason",
            "duplicate_query", "strategy_name", "strategy_trigger", "strategy_target", "strategy_entrypoint",
            "strategy_blocking_reason", "intentional_empty_reason", "intentional_empty_milestone", "cleanup_plan",
            "blocked_reason", "unresolved_reason", "next_query",
        ):
            _validate_optional_string(contract, field, label, errors, meaningful=True)
        if "distinguishes_failure_from_empty" in contract and not isinstance(contract.get("distinguishes_failure_from_empty"), bool):
            errors.append(f"{label} distinguishes_failure_from_empty must be a boolean")
        foreign_key_check_result: list[str] = []
        if "foreign_key_check_result" in contract:
            foreign_key_check_result = _validate_evidence(
                contract.get("foreign_key_check_result"),
                f"{label} foreign_key_check_result",
                errors,
            )
        if storage_kind == "sql_table":
            foreign_key_check = contract.get("foreign_key_check")
            if (
                not _is_meaningful_string(foreign_key_check)
                or not SQLITE_FOREIGN_KEY_CHECK_RE.fullmatch(foreign_key_check.strip())
            ):
                errors.append(
                    f"{label} sql_table requires an executable PRAGMA foreign_key_check statement"
                )
            if not foreign_key_check_result:
                errors.append(
                    f"{label} foreign_key_check_result must be non-empty"
                )

        unique_keys = contract.get("unique_keys")
        nullable_columns = contract.get("nullable_unique_columns", [])
        if "unique_keys" in contract and not isinstance(unique_keys, list):
            errors.append(f"{label} unique_keys must be a list")
        elif isinstance(unique_keys, list):
            unique_keys = _validate_concrete_string_list(unique_keys, f"{label} unique_keys", errors)
        duplicate_query_result: list[str] = []
        if "duplicate_query_result" in contract:
            duplicate_query_result = _validate_evidence(
                contract.get("duplicate_query_result"),
                f"{label} duplicate_query_result",
                errors,
            )
        if isinstance(unique_keys, list) and unique_keys:
            duplicate_query = contract.get("duplicate_query")
            if not _is_meaningful_string(duplicate_query):
                errors.append(f"{label} unique keys require duplicate_query")
            elif not _is_read_only_duplicate_query(duplicate_query):
                errors.append(
                    f"{label} duplicate_query must be a single read-only executable SELECT or WITH query"
                )
            if not duplicate_query_result:
                errors.append(f"{label} duplicate_query_result must be non-empty")
        if not isinstance(nullable_columns, list):
            errors.append(f"{label} nullable_unique_columns must be a list")
            nullable_columns = []
        else:
            nullable_columns = _validate_concrete_string_list(
                nullable_columns, f"{label} nullable_unique_columns", errors
            )
        if nullable_columns:
            if not isinstance(unique_keys, list) or not set(nullable_columns).issubset(set(unique_keys)):
                errors.append(f"{label} nullable_unique_columns must be included in unique_keys")
            null_semantics_valid = _validate_enum(contract.get("null_semantics"), NULL_SEMANTICS, label, "null_semantics", errors)
            if not null_semantics_valid:
                errors.append(f"{label} nullable unique keys require null_semantics")
            elif contract.get("null_semantics") == "blocked" and not _is_meaningful_string(contract.get("null_semantics_blocking_reason")):
                errors.append(f"{label} blocked null_semantics requires a blocking reason")
        elif "null_semantics" in contract:
            _validate_enum(contract.get("null_semantics"), NULL_SEMANTICS, label, "null_semantics", errors)

        strategy_name = contract.get("strategy_name")
        strategy_fields = {
            "strategy_name",
            "strategy_status",
            "strategy_parameters",
            "strategy_trigger",
            "strategy_target",
            "strategy_entrypoint",
            "strategy_blocking_reason",
        }
        if any(field in contract for field in strategy_fields):
            strategy_name_valid = _validate_meaningful_string(strategy_name, f"{label} strategy_name", errors)
            strategy_status = contract.get("strategy_status")
            strategy_status_valid = _validate_enum(strategy_status, STRATEGY_STATUSES, label, "strategy_status", errors)
            if strategy_name_valid and strategy_status_valid and strategy_status == "blocked":
                if not _is_meaningful_string(contract.get("strategy_blocking_reason")):
                    errors.append(f"{label} blocked strategy requires strategy_blocking_reason")
            elif strategy_name_valid and strategy_status_valid:
                for field in ("strategy_parameters", "strategy_trigger", "strategy_target", "strategy_entrypoint"):
                    value = contract.get(field)
                    if field == "strategy_parameters":
                        value_is_concrete = _has_concrete_strategy_parameters(value)
                    else:
                        value_is_concrete = _is_meaningful_string(value)
                    if not value_is_concrete:
                        errors.append(f"{label} strategy requires {field}")
        if "strategy_parameters" in contract:
            parameters = contract.get("strategy_parameters")
            if not isinstance(parameters, (dict, list, str, int, float)) or isinstance(parameters, bool):
                errors.append(f"{label} strategy_parameters has invalid type")
            elif _contains_non_finite_number(parameters):
                errors.append(f"{label} strategy_parameters must be finite")
            elif _contains_placeholder_string(parameters):
                errors.append(f"{label} strategy_parameters contains a placeholder")
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
            if not _is_meaningful_string(contract.get("cleanup_plan")):
                errors.append(f"{label} data-corrupted requires cleanup_plan")
        if (
            implementation_state_valid
            and implementation_state == "unimplemented"
            and _is_status(contract.get("status"), "implemented", "verified")
        ):
            errors.append(
                f"{label} status {contract.get('status')} conflicts with implementation_state unimplemented"
            )


def _validate_test_chains(
    document: dict[str, Any],
    errors: list[str],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    map_only: bool = False,
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
                "blocked_reason", "unresolved_reason", "next_query",
            },
            label,
            errors,
        )

        chain_id = chain.get("chain_id")
        if _validate_identifier(chain_id, f"{label} chain_id", errors):
            if chain_id in chain_ids:
                errors.append(f"duplicate chain_id: {chain_id}")
            else:
                chain_ids.add(chain_id)

        level = chain.get("level")
        status = chain.get("status")
        if isinstance(level, str):
            observed_levels.add(level)
        level_valid = _validate_enum(level, TEST_LEVELS, label, "level", errors)
        status_valid = _validate_enum(status, TEST_STATUSES, label, "status", errors)
        if (
            isinstance(document.get("graph_type"), str)
            and document.get("graph_type") in {"observed", "change"}
            and status_valid
            and status == "planned"
        ):
            errors.append(f"{label} {document.get('graph_type')} graph cannot use status planned")
        if map_only and status_valid and status not in {"observed", "verified", "blocked", "unresolved", "deferred"}:
            errors.append(f"{label} map-only status is not an observed/deferred status")
        _validate_meaningful_string(chain.get("expected_output"), f"{label} expected_output", errors)
        _validate_meaningful_string(chain.get("command"), f"{label} command", errors)
        for field in ("test_node_refs", "node_refs", "edge_refs", "requirement_refs", "ac_refs", "error_path_refs", "uncovered_edge_refs"):
            if not isinstance(chain.get(field), list):
                errors.append(f"{label} {field} must be a list")
        if not chain.get("requirement_refs"):
            errors.append(f"{label} requires requirement_refs")
        if not chain.get("ac_refs"):
            errors.append(f"{label} requires ac_refs")
        if isinstance(chain.get("requirement_refs"), list):
            _validate_reference_list(chain["requirement_refs"], f"{label} requirement_refs", errors)
        if isinstance(chain.get("ac_refs"), list):
            _validate_reference_list(chain["ac_refs"], f"{label} ac_refs", errors)

        test_node_refs = _validate_reference_list(chain.get("test_node_refs"), f"{label} test_node_refs", errors) if isinstance(chain.get("test_node_refs"), list) else []
        node_refs = _validate_reference_list(chain.get("node_refs"), f"{label} node_refs", errors) if isinstance(chain.get("node_refs"), list) else []
        edge_refs = _validate_reference_list(chain.get("edge_refs"), f"{label} edge_refs", errors) if isinstance(chain.get("edge_refs"), list) else []
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
        entrypoint_valid = _validate_identifier(
            entrypoint, f"{label} entrypoint_node_id", errors
        )
        if not entrypoint_valid or entrypoint not in test_node_refs:
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
            role_refs = _validate_reference_list(roles.get(role), f"{label} required_roles.{role}", errors) if isinstance(roles.get(role), list) else []
            if level_valid and not role_refs:
                errors.append(f"{label} {role} is required for {level}")
            for ref in role_refs:
                if ref not in node_refs:
                    errors.append(f"{label} {role} ref is not in node_refs: {ref}")
                else:
                    role_kind = node_by_id.get(ref, {}).get("kind")
                    if isinstance(role_kind, str) and role_kind.casefold() == "test":
                        errors.append(f"{label} {role} must reference code nodes, not test nodes: {ref}")
                    elif role in {"producer", "consumer"} and _is_storage_node_kind(role_kind):
                        errors.append(
                            f"{label} {role} must reference code nodes, not storage nodes: {ref}"
                        )
        producer_refs = set(_string_items(roles.get("producer")))
        contract_refs = set(_string_items(roles.get("contract")))
        consumer_refs = set(_string_items(roles.get("consumer")))
        role_boundary_overlap = contract_refs & (producer_refs | consumer_refs)
        for ref in sorted(role_boundary_overlap):
            errors.append(
                f"{label} contract role must be distinct from producer and consumer roles: {ref}"
            )
        declared_contract_storage_ids = {
            contract.get("storage_node_id")
            for contract in _safe_list(document.get("contracts"))
            if isinstance(contract, dict) and _is_nonempty_string(contract.get("storage_node_id"))
        }
        for ref in sorted(contract_refs - declared_contract_storage_ids):
            errors.append(
                f"{label} contract role does not reference a declared contract storage node: {ref}"
            )
        selected_contracts = [
            contract
            for contract in _safe_list(document.get("contracts"))
            if isinstance(contract, dict)
            and isinstance(contract.get("storage_node_id"), str)
            and contract.get("storage_node_id") in contract_refs
        ]
        declared_writers = {
            ref
            for contract in selected_contracts
            for ref in _string_items(contract.get("writers"))
        }
        declared_readers = {
            ref
            for contract in selected_contracts
            for ref in _string_items(contract.get("readers"))
        }
        for ref in sorted(producer_refs - declared_writers):
            errors.append(f"{label} producer is outside contract closure: {ref}")
        for ref in sorted(consumer_refs - declared_readers):
            errors.append(f"{label} consumer is outside contract closure: {ref}")
        required_role_refs = producer_refs | contract_refs | consumer_refs
        if status_valid and status == "verified":
            for ref in set(test_node_refs) | required_role_refs:
                node = node_by_id.get(ref)
                node_status = node.get("status") if isinstance(node, dict) else None
                if _is_status(node_status, "planned", "blocked", "unresolved", "deferred"):
                    errors.append(
                        f"{label} verified chain cannot rely on {node_status} node: {ref}"
                    )
            for contract in _safe_list(document.get("contracts")):
                if (
                    not isinstance(contract, dict)
                    or not isinstance(contract.get("storage_node_id"), str)
                    or contract.get("storage_node_id") not in contract_refs
                ):
                    continue
                contract_status = contract.get("status")
                if _is_status(contract_status, "planned", "blocked", "unresolved", "deferred"):
                    errors.append(
                        f"{label} verified chain cannot rely on {contract_status} contract: "
                        f"{contract.get('contract_id')}"
                    )
        error_path_refs = _validate_reference_list(chain.get("error_path_refs"), f"{label} error_path_refs", errors) if isinstance(chain.get("error_path_refs"), list) else []
        error_role_refs = _validate_reference_list(roles.get("error_path"), f"{label} required_roles.error_path", errors) if isinstance(roles.get("error_path"), list) else []
        if level_valid and level != "L0" and not error_path_refs:
            errors.append(f"{label} error_path is required for {level}")
        if level_valid and level != "L0" and not error_role_refs:
            errors.append(f"{label} error_path role is required for {level}")
        for ref in error_role_refs:
            if ref not in error_path_refs:
                errors.append(f"{label} required_roles.error_path ref is not in error_path_refs: {ref}")
            if ref not in test_node_refs and ref not in node_refs:
                errors.append(f"{label} error_path role must reference a declared node: {ref}")
        chain_ref_set = set(test_node_refs) | set(node_refs) | set(edge_refs)
        for ref in error_path_refs:
            if ref not in node_by_id and ref not in edge_by_id:
                errors.append(f"{label} error_path_refs references unknown node or edge: {ref}")
            elif ref not in chain_ref_set:
                errors.append(f"{label} error_path_refs is not part of the chain: {ref}")

        chain_edges = [edge_by_id[ref] for ref in edge_refs if ref in edge_by_id]
        chain_edge_pairs = {
            (edge.get("kind"), edge.get("from"), edge.get("to"))
            for edge in chain_edges
            if isinstance(edge.get("kind"), str)
            and isinstance(edge.get("from"), str)
            and isinstance(edge.get("to"), str)
        }
        for contract in selected_contracts:
            storage = contract.get("storage_node_id")
            if not isinstance(storage, str):
                continue
            contract_writers = set(_string_items(contract.get("writers")))
            contract_readers = set(_string_items(contract.get("readers")))
            contract_producers = producer_refs & contract_writers
            contract_consumers = consumer_refs & contract_readers
            contract_label = contract.get("contract_id") or storage
            if not contract_producers:
                errors.append(
                    f"{label} declared contract {contract_label} has no producer role"
                )
            if not contract_consumers:
                errors.append(
                    f"{label} declared contract {contract_label} has no consumer role"
                )
            for producer in sorted(contract_producers):
                if ("writes", producer, storage) not in chain_edge_pairs:
                    errors.append(
                        f"{label} omits contract writer edge from edge_refs: "
                        f"{producer} -> {storage}"
                    )
            for consumer in sorted(contract_consumers):
                if ("reads", storage, consumer) not in chain_edge_pairs:
                    errors.append(
                        f"{label} omits contract reader edge from edge_refs: "
                        f"{storage} -> {consumer}"
                    )
        declared_chain_nodes = set(test_node_refs) | set(node_refs)
        if status_valid and status == "verified":
            for edge in chain_edges:
                edge_status = edge.get("status")
                if _is_status(edge_status, "planned", "blocked", "deferred"):
                    errors.append(
                        f"{label} verified chain cannot rely on {edge_status} edge: "
                        f"{edge.get('edge_id')}"
                    )
        for edge in chain_edges:
            source = edge.get("from")
            target = edge.get("to")
            if (
                not isinstance(source, str)
                or not isinstance(target, str)
                or source not in declared_chain_nodes
                or target not in declared_chain_nodes
            ):
                errors.append(
                    f"{label} edge endpoint is outside the declared chain: {edge.get('edge_id')}"
                )
        validation_edges = [
            edge for edge in chain_edges
            if edge.get("kind") == "validates" and edge.get("from") in test_node_refs
        ]
        if _is_nonempty_string(entrypoint) and not any(edge.get("from") == entrypoint for edge in validation_edges):
            errors.append(f"{label} entrypoint has no validates edge in edge_refs")
        for ref in error_role_refs:
            if ref in test_node_refs and not any(
                edge.get("from") == ref
                and isinstance(edge.get("to"), str)
                and edge.get("to") in required_role_refs
                for edge in validation_edges
            ):
                errors.append(f"{label} error-path test node has no validates edge to a code role: {ref}")
            elif ref in node_refs and not any(edge.get("to") == ref for edge in validation_edges):
                errors.append(f"{label} error-path node has no validates edge: {ref}")
        required_code_refs = required_role_refs
        for ref in required_code_refs:
            if not any(edge.get("to") == ref for edge in validation_edges):
                errors.append(f"{label} missing validates edge for role node: {ref}")

        if _is_nonempty_string(entrypoint):
            reachable = {entrypoint}
            frontier = [entrypoint]
            adjacency: dict[str, set[str]] = {}
            for edge in chain_edges:
                source = edge.get("from")
                target = edge.get("to")
                if isinstance(source, str) and isinstance(target, str):
                    adjacency.setdefault(source, set()).add(target)
            while frontier:
                source = frontier.pop()
                for target in adjacency.get(source, set()) - reachable:
                    reachable.add(target)
                    frontier.append(target)
            for ref in sorted(required_code_refs - reachable):
                errors.append(f"{label} entrypoint cannot reach required role node: {ref}")

        producers = _string_items(roles.get("producer"))
        contracts = _string_items(roles.get("contract"))
        consumers = _string_items(roles.get("consumer"))
        if level_valid:
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
        factual_chain = status_valid and status in FACTUAL_STATUSES
        if factual_chain:
            if not verification_evidence_items:
                errors.append(f"{label} {status} requires verification_evidence")
            if evidence_kind_valid and evidence_kind == "static" and not static_evidence_items:
                errors.append(f"{label} static evidence kind requires static_evidence")
            elif evidence_kind_valid and evidence_kind == "runtime" and not runtime_evidence_items:
                errors.append(f"{label} runtime evidence kind requires runtime_evidence")
            elif evidence_kind_valid and evidence_kind == "mixed":
                if not static_evidence_items:
                    errors.append(f"{label} mixed evidence kind requires static_evidence")
                if not runtime_evidence_items:
                    errors.append(f"{label} mixed evidence kind requires runtime_evidence")
        if status_valid and status == "verified":
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
            if not _is_meaningful_string(chain.get("deferred_reason")):
                errors.append(f"{label} deferred requires deferred_reason")
            if not _is_meaningful_string(chain.get("deferred_milestone")):
                errors.append(f"{label} deferred requires deferred_milestone")
        if status_valid:
            _validate_recovery_fields(chain, label, status, errors)
        for field in ("deferred_reason", "deferred_milestone", "blocked_reason", "unresolved_reason", "next_query"):
            _validate_optional_string(chain, field, label, errors, nonempty=True, meaningful=True)

        test_scope = chain.get("test_scope")
        test_scope_valid = _validate_enum(test_scope, TEST_SCOPES, label, "test_scope", errors)
        uncovered = _validate_reference_list(chain.get("uncovered_edge_refs"), f"{label} uncovered_edge_refs", errors) if isinstance(chain.get("uncovered_edge_refs"), list) else []
        for ref in uncovered:
            edge = edge_by_id.get(ref)
            if edge is None:
                errors.append(f"{label} uncovered_edge_refs references unknown edge: {ref}")
            elif edge.get("status") != "unresolved":
                errors.append(f"{label} uncovered edge must remain unresolved: {ref}")
        if status_valid and status == "verified" and uncovered and test_scope_valid and test_scope not in {"full", "expanded"}:
            errors.append(f"{label} unresolved edges require expanded or full test scope")
        if status_valid and status == "verified":
            referenced_nodes = set(test_node_refs) | set(node_refs)
            relevant_unresolved_edges = {
                edge.get("edge_id")
                for edge in edges
                if edge.get("status") == "unresolved"
                and _is_nonempty_string(edge.get("edge_id"))
                and (
                    (isinstance(edge.get("from"), str) and edge.get("from") in referenced_nodes)
                    or (isinstance(edge.get("to"), str) and edge.get("to") in referenced_nodes)
                )
            }
            for ref in sorted(relevant_unresolved_edges - set(uncovered)):
                errors.append(f"{label} omits relevant unresolved edge from uncovered_edge_refs: {ref}")

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
        for ref in _validate_reference_list(test_refs, f"node {node.get('node_id')} test_refs", errors) if isinstance(test_refs, list) else []:
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
    if graph_type_valid and graph_type != "change":
        for field in ("baseline_sha", "current_sha", "diff"):
            if field in document:
                errors.append(f"{graph_type} graph cannot include change-only field: {field}")
    for field in ("baseline_sha", "current_sha"):
        if field in document and not _is_sha(document.get(field)):
            errors.append(f"{field} is invalid")

    repository = document.get("repository")
    repository_sha: str | None = None
    if not isinstance(repository, dict):
        errors.append("repository must be an object")
    else:
        _reject_unknown_fields(repository, {"root", "git_sha"}, "repository", errors)
        _validate_concrete_string(repository.get("root"), "repository.root", errors)
        if not _is_sha(repository.get("git_sha")):
            errors.append("repository.git_sha is invalid")
        else:
            repository_sha = repository["git_sha"]
    provider = document.get("provider")
    if not isinstance(provider, dict):
        errors.append("provider must be an object")
    else:
        _reject_unknown_fields(provider, {"name", "version", "command", "generated_at", "capabilities", "limitations"}, "provider", errors)
        for field in ("name", "version", "command", "generated_at"):
            _validate_meaningful_string(provider.get(field), f"provider.{field}", errors)
        if not _is_rfc3339_timestamp(provider.get("generated_at")):
            errors.append("provider.generated_at must be an RFC3339 date-time")
        for field in ("capabilities", "limitations"):
            if field not in provider:
                errors.append(f"provider.{field} is required")
                continue
            items = _validate_concrete_string_list(provider.get(field), f"provider.{field}", errors)
            if field == "capabilities" and not items:
                errors.append("provider.capabilities must be non-empty")
    included_coverage_paths: set[str] = set()
    excluded_coverage_paths: set[str] = set()
    coverage = document.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
    else:
        _reject_unknown_fields(coverage, {"scope", "status", "paths", "excluded_paths", "limitations"}, "coverage", errors)
        _validate_enum(coverage.get("scope"), COVERAGE_SCOPES, "coverage", "scope", errors)
        coverage_status_valid = _validate_enum(coverage.get("status"), COVERAGE_STATUSES, "coverage", "status", errors)
        coverage_lists: dict[str, list[str]] = {}
        normalized_coverage_paths: dict[str, set[str]] = {}
        for field in ("paths", "excluded_paths"):
            if not isinstance(coverage.get(field), list):
                errors.append(f"coverage.{field} must be a list")
                coverage_lists[field] = []
            else:
                coverage_lists[field] = _validate_string_list(coverage[field], f"coverage.{field}", errors)
                coverage_lists[field] = [
                    path
                    for index, path in enumerate(coverage_lists[field])
                    if _validate_repository_relative_path(
                        path,
                        f"coverage.{field}[{index}]",
                        errors,
                        allow_dot=True,
                    )
                ]
                normalized_paths = [_normalize_repository_path(path) for path in coverage_lists[field]]
                normalized_coverage_paths[field] = set(normalized_paths)
                if field == "paths":
                    included_coverage_paths = normalized_coverage_paths[field]
                else:
                    excluded_coverage_paths = normalized_coverage_paths[field]
                if len(normalized_paths) != len(normalized_coverage_paths[field]):
                    errors.append(f"coverage.{field} contains duplicate paths after normalization")
        overlap = normalized_coverage_paths.get("paths", set()) & normalized_coverage_paths.get("excluded_paths", set())
        for path in sorted(overlap):
            errors.append(f"coverage path is both included and excluded: {path}")
        if not coverage_lists.get("paths"):
            errors.append("coverage.paths must be non-empty")
        limitation_items: list[str] = []
        if "limitations" in coverage:
            limitation_items = _validate_string_list(coverage.get("limitations"), "coverage.limitations", errors)
            limitation_items = [
                limitation
                for index, limitation in enumerate(limitation_items)
                if _validate_meaningful_string(limitation, f"coverage.limitations[{index}]", errors)
            ]
        if coverage_status_valid and coverage.get("status") in {"partial", "unknown"} and not limitation_items:
            errors.append("coverage partial or unknown requires limitations")
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
        if _is_sha(document.get("baseline_sha")) and _is_sha(document.get("current_sha")) and document["baseline_sha"] == document["current_sha"]:
            errors.append("change graph baseline_sha and current_sha must differ")
        diff = document.get("diff")
        if not isinstance(diff, dict):
            errors.append("change graph requires a diff object")
    elif "diff" in document:
        errors.append("diff is only allowed for change graph")

    nodes = _as_list(document.get("nodes"))
    edges = _as_list(document.get("edges"))
    if nodes is None:
        errors.append("nodes must be a list")
        nodes = []
    elif not nodes:
        errors.append("nodes must be a non-empty list")
    if edges is None:
        errors.append("edges must be a list")
        edges = []
    elif not edges:
        errors.append("edges must be a non-empty list")

    node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        label = f"nodes[{index}]"
        if not isinstance(node, dict):
            errors.append(f"{label} must be an object")
            continue
        _reject_unknown_fields(node, {"node_id", "kind", "status", "path", "qualified_symbol", "source_anchor", "provider", "git_sha", "confidence", "coverage", "freshness", "verification_evidence", "requirement_refs", "entrypoint", "test_refs", "test_exemption_reason", "blocked_reason", "unresolved_reason", "next_query"}, label, errors)
        node_id = node.get("node_id")
        if _validate_identifier(node_id, f"{label} node_id", errors):
            if node_id in node_ids:
                errors.append(f"duplicate node_id: {node_id}")
            else:
                node_ids.add(node_id)
        _validate_meaningful_string(node.get("kind"), f"{label} kind", errors)
        _validate_repository_relative_path(node.get("path"), f"{label} path", errors)
        _validate_meaningful_string(node.get("qualified_symbol"), f"{label} qualified_symbol", errors)
        confidence = node.get("confidence")
        if not _is_number(confidence) or not 0 <= confidence <= 1:
            errors.append(f"{label} confidence must be between 0 and 1")
        _validate_common(node, label, errors, graph_type if graph_type_valid else "observed")
        if node.get("status") == "removed":
            errors.append(f"{label} removed objects belong only in change graph diff.removed_* references")
        _validate_anchor(node, label, errors, field_required=False)
        anchor = node.get("source_anchor")
        if (
            isinstance(anchor, dict)
            and _is_nonempty_string(anchor.get("path"))
            and _is_nonempty_string(node.get("path"))
            and anchor.get("path") != node.get("path")
        ):
            errors.append(f"{label} source_anchor.path must match node path")
        _validate_recovery_fields(node, label, node.get("status"), errors)
        for field in ("blocked_reason", "unresolved_reason", "next_query"):
            _validate_optional_string(node, field, label, errors, nonempty=True, meaningful=True)
        if map_only and isinstance(node.get("status"), str) and node.get("status") not in {"observed", "verified", "blocked", "unresolved"}:
            errors.append(f"{label} map-only status must be observed, verified, blocked, or unresolved")
        _validate_optional_string(node, "test_exemption_reason", label, errors, nonempty=True, meaningful=True)

    edge_ids: set[str] = set()
    for index, edge in enumerate(edges):
        label = f"edges[{index}]"
        if not isinstance(edge, dict):
            errors.append(f"{label} must be an object")
            continue
        _reject_unknown_fields(edge, {"edge_id", "kind", "from", "to", "status", "provider", "git_sha", "source_anchor", "confidence", "coverage", "freshness", "verification_evidence", "requirement_refs", "unresolved_reason", "next_query", "blocked_reason"}, label, errors)
        edge_id = edge.get("edge_id")
        if _validate_identifier(edge_id, f"{label} edge_id", errors):
            if edge_id in edge_ids:
                errors.append(f"duplicate edge_id: {edge_id}")
            else:
                edge_ids.add(edge_id)
        _validate_enum(edge.get("kind"), EDGE_KINDS, label, "kind", errors)
        from_id = edge.get("from")
        to_id = edge.get("to")
        from_valid = _validate_identifier(from_id, f"{label} from", errors)
        to_valid = _validate_identifier(to_id, f"{label} to", errors)
        if not from_valid or not to_valid or from_id not in node_ids or to_id not in node_ids:
            errors.append(f"{label} endpoint does not reference an existing node")
        confidence = edge.get("confidence")
        if not _is_number(confidence) or not 0 <= confidence <= 1:
            errors.append(f"{label} confidence must be between 0 and 1")
        _validate_common(edge, label, errors, graph_type if graph_type_valid else "observed")
        if edge.get("status") == "removed":
            errors.append(f"{label} removed objects belong only in change graph diff.removed_* references")
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
        _validate_recovery_fields(edge, label, edge.get("status"), errors)
        _validate_optional_string(edge, "unresolved_reason", label, errors, meaningful=True)
        _validate_optional_string(edge, "next_query", label, errors, meaningful=True)
        _validate_optional_string(edge, "blocked_reason", label, errors, nonempty=True, meaningful=True)

    entity_id_sets = [
        ("node", node_ids),
        ("edge", edge_ids),
        (
            "contract",
            {
                contract.get("contract_id")
                for contract in _safe_list(document.get("contracts"))
                if isinstance(contract, dict) and _is_nonempty_string(contract.get("contract_id"))
            },
        ),
        (
            "test chain",
            {
                chain.get("chain_id")
                for chain in _safe_list(document.get("test_chains"))
                if isinstance(chain, dict) and _is_nonempty_string(chain.get("chain_id"))
            },
        ),
    ]
    for left_index, (left_label, left_ids) in enumerate(entity_id_sets):
        for right_label, right_ids in entity_id_sets[left_index + 1 :]:
            for duplicate_id in sorted(left_ids & right_ids):
                errors.append(
                    f"identifier collision: {duplicate_id} is both a {left_label} and an {right_label}"
                )

    for index, node in enumerate(nodes):
        if isinstance(node, dict):
            _validate_path_coverage(
                node.get("path"),
                f"nodes[{index}].path",
                included_coverage_paths,
                excluded_coverage_paths,
                errors,
            )
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict) or not isinstance(edge.get("source_anchor"), dict):
            continue
        _validate_path_coverage(
            edge["source_anchor"].get("path"),
            f"edges[{index}] source_anchor.path",
            included_coverage_paths,
            excluded_coverage_paths,
            errors,
        )
    for index, section in enumerate(_safe_list(document.get("source_coverage"))):
        if not isinstance(section, dict) or not isinstance(section.get("source_anchor"), dict):
            continue
        _validate_path_coverage(
            section["source_anchor"].get("path"),
            f"source_coverage[{index}] source_anchor.path",
            included_coverage_paths,
            excluded_coverage_paths,
            errors,
        )

    expected_evidence_sha = repository_sha
    expected_sha_label = "repository.git_sha"
    if graph_type_valid and graph_type == "change" and _is_sha(document.get("current_sha")):
        current_sha = document["current_sha"]
        expected_evidence_sha = current_sha
        expected_sha_label = "current_sha"
        if repository_sha is not None and repository_sha != current_sha:
            errors.append("repository.git_sha must match change graph current_sha")
    if expected_evidence_sha is not None:
        for index, node in enumerate(nodes):
            if isinstance(node, dict) and _is_sha(node.get("git_sha")) and node.get("git_sha") != expected_evidence_sha:
                errors.append(f"nodes[{index}] git_sha does not match {expected_sha_label}")
        for index, edge in enumerate(edges):
            if isinstance(edge, dict) and _is_sha(edge.get("git_sha")) and edge.get("git_sha") != expected_evidence_sha:
                errors.append(f"edges[{index}] git_sha does not match {expected_sha_label}")

    if graph_type_valid and graph_type == "change" and isinstance(document.get("diff"), dict):
        contracts = [
            contract
            for contract in _safe_list(document.get("contracts"))
            if isinstance(contract, dict)
        ]
        _validate_diff(
            document["diff"],
            "change graph diff",
            errors,
            node_ids=node_ids,
            edge_ids=edge_ids,
            contract_ids={
                contract.get("contract_id")
                for contract in contracts
                if _is_nonempty_string(contract.get("contract_id"))
            },
            node_statuses={node.get("node_id"): node.get("status") for node in nodes if isinstance(node, dict) and _is_nonempty_string(node.get("node_id"))},
            edge_statuses={edge.get("edge_id"): edge.get("status") for edge in edges if isinstance(edge, dict) and _is_nonempty_string(edge.get("edge_id"))},
            contract_statuses={
                contract.get("contract_id"): contract.get("status")
                for contract in contracts
                if _is_nonempty_string(contract.get("contract_id"))
            },
        )

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

    _validate_source_coverage_links(
        document,
        [node for node in nodes if isinstance(node, dict)],
        [edge for edge in edges if isinstance(edge, dict)],
        errors,
    )

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

    _validate_test_chains(
        document,
        errors,
        [node for node in nodes if isinstance(node, dict)],
        [edge for edge in edges if isinstance(edge, dict)],
        map_only=map_only,
    )
    _validate_contracts(
        document,
        errors,
        node_ids,
        {
            node.get("node_id"): node.get("kind")
            for node in nodes
            if isinstance(node, dict)
            and isinstance(node.get("node_id"), str)
            and isinstance(node.get("kind"), str)
        },
        [edge for edge in edges if isinstance(edge, dict)],
        map_only=map_only,
        node_statuses={
            node.get("node_id"): node.get("status")
            for node in nodes
            if isinstance(node, dict) and isinstance(node.get("node_id"), str)
        },
        edge_statuses={
            edge.get("edge_id"): edge.get("status")
            for edge in edges
            if isinstance(edge, dict) and isinstance(edge.get("edge_id"), str)
        },
    )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="graph snapshot JSON file")
    parser.add_argument("--map-only", action="store_true", help="require an observed-only, no-change code map")
    args = parser.parse_args(argv)
    try:
        document = json.loads(
            args.path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_non_json_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
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
