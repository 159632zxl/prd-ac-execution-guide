#!/usr/bin/env python3
"""Structural checker for PRDs written with the AC execution guide."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


LEGACY_REQUIRED_PHRASES = [
    "AI 执行器强制阅读声明",
    "唯一验收依据",
    "实现真源",
    "验收标准总览",
    "Acceptance Criteria",
    "全局禁止项",
    "PASS/FAIL/WARN",
]

AC_CATEGORIES = {
    "happy",
    "edge",
    "error",
    "non-functional",
    "data-integrity",
    "safety",
}

PLACEHOLDER_RE = re.compile(
    r"<\s*(?:\.\.\.|…)\s*>|\.\.\.|…|\bTODO\b|\bTBD\b|待定",
    re.IGNORECASE,
)
AC_ID_RE = re.compile(
    r"^(?:G-\d{2}|(?:P0|M\d+)-[A-Z0-9]+(?:-[A-Z0-9]+)*)$"
)
AC_REFERENCE_RE = re.compile(
    r"\b(?:G-\d+|(?:P0|M\d+)-[A-Z0-9]+(?:-[A-Z0-9]+)*)\b"
)
HEADING_RE = re.compile(r"^##(?!#)\s+(.+?)\s*$")
SECTION_NUMBER_RE = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+")
ACCEPTANCE_TITLE_RE = re.compile(
    r"^(?:验收标准总览(?:[（(]\s*Acceptance Criteria\s*[）)])?|Acceptance Criteria)$",
    re.IGNORECASE,
)


HEADER_ALIASES = {
    "ac": {"ac", "acid", "验收编号"},
    "category": {"category", "类别"},
    "requirement": {"requirement", "criteria", "acceptanceitem", "验收项"},
    "verification": {"verificationmethod", "validation", "验证方法", "验证"},
    "severity": {"severity", "等级"},
    "forbidden": {"forbiddenitem", "forbidden", "禁止项"},
    "task": {"task", "任务"},
    "implements_ac": {"implementsac", "acmapping", "映射ac", "实现ac"},
}


@dataclass(frozen=True)
class TableRow:
    line_number: int
    cells: list[str]


@dataclass(frozen=True)
class MarkdownTable:
    headers: list[str]
    rows: list[TableRow]


def normalized_header(value: str) -> str:
    return re.sub(r"[\s_`*\-/]", "", value).lower()


def header_index(headers: list[str], role: str) -> int | None:
    aliases = HEADER_ALIASES[role]
    for index, header in enumerate(headers):
        if normalized_header(header) in aliases:
            return index
    return None


def split_markdown_row(line: str) -> list[str]:
    content = line.strip()
    if content.startswith("|"):
        content = content[1:]
    if content.endswith("|"):
        content = content[:-1]
    return [cell.strip().replace(r"\|", "|") for cell in re.split(r"(?<!\\)\|", content)]


def is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def mask_fenced_lines(text: str) -> list[str]:
    masked: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)[0]
            if fence is None:
                fence = token
            elif token == fence:
                fence = None
            masked.append("")
        elif fence is None:
            masked.append(line)
        else:
            masked.append("")
    return masked


def parse_markdown_tables(lines: list[str], line_offset: int = 0) -> list[MarkdownTable]:
    tables: list[MarkdownTable] = []
    index = 0
    while index + 1 < len(lines):
        if not lines[index].lstrip().startswith("|"):
            index += 1
            continue

        headers = split_markdown_row(lines[index])
        separators = split_markdown_row(lines[index + 1])
        if len(headers) != len(separators) or not is_separator_row(separators):
            index += 1
            continue

        rows: list[TableRow] = []
        cursor = index + 2
        while cursor < len(lines) and lines[cursor].lstrip().startswith("|"):
            cells = split_markdown_row(lines[cursor])
            rows.append(TableRow(cursor + 1 + line_offset, cells))
            cursor += 1
        tables.append(MarkdownTable(headers, rows))
        index = cursor
    return tables


def has_heading(lines: list[str], pattern: str) -> bool:
    return any(
        re.search(pattern, match.group(1), re.IGNORECASE)
        for line in lines
        if (match := re.match(r"^#{2,6}\s+(.+?)\s*$", line))
    )


def find_acceptance_section(lines: list[str]) -> tuple[int | None, bool]:
    level_two = [
        (index, match.group(1))
        for index, line in enumerate(lines)
        if (match := HEADING_RE.match(line))
    ]
    matches = [
        index
        for index, title in level_two
        if ACCEPTANCE_TITLE_RE.fullmatch(SECTION_NUMBER_RE.sub("", title))
    ]
    if not matches:
        return None, False
    acceptance_index = matches[-1]
    final_level_two = level_two[-1][0] == acceptance_index
    return acceptance_index, final_level_two


def find_milestones(lines: list[str]) -> set[str]:
    milestones: set[str] = set()
    for line in lines:
        match = HEADING_RE.match(line)
        if not match:
            continue
        title = SECTION_NUMBER_RE.sub("", match.group(1))
        milestone = re.match(r"^(P0|M\d+)(?=\s|[:：.\-–—]|$)", title, re.IGNORECASE)
        if milestone:
            milestones.add(milestone.group(1).upper())
    return milestones


def append_unique(items: list[str], message: str) -> None:
    if message not in items:
        items.append(message)


def validate_common_structure(
    text: str,
    visible_lines: list[str],
    tier: str | None,
    failures: list[str],
    warnings: list[str],
) -> None:
    if not has_heading(visible_lines, r"^(?:\d+(?:\.\d+)?\s+)?(?:Goal|目标)\b"):
        failures.append("Missing goal section")
    if not has_heading(visible_lines, r"(?:Non-goals?|非目标)"):
        failures.append("Missing non-goals section")
    if not re.search(r"truth\s+source|事实真源|数据真源|真源", text, re.IGNORECASE):
        failures.append("Missing truth source")
    if not re.search(r"boundary|边界", text, re.IGNORECASE):
        failures.append("Missing system boundary")

    acceptance_index, is_final = find_acceptance_section(visible_lines)
    if acceptance_index is None:
        failures.append("Missing final Acceptance Criteria section")
        acceptance_lines: list[str] = []
    else:
        acceptance_lines = visible_lines[acceptance_index:]
        if not is_final:
            failures.append("Acceptance Criteria must be the final level-two section")

    all_tables = parse_markdown_tables(visible_lines)
    acceptance_tables = parse_markdown_tables(
        acceptance_lines,
        line_offset=acceptance_index or 0,
    )

    task_tables = [
        table
        for table in all_tables
        if header_index(table.headers, "task") is not None
        and header_index(table.headers, "implements_ac") is not None
    ]
    if not task_tables:
        failures.append("Missing Task -> AC mapping table")

    ac_tables = [
        table
        for table in acceptance_tables
        if all(
            header_index(table.headers, role) is not None
            for role in ("ac", "category", "requirement", "verification", "severity")
        )
    ]
    if not ac_tables:
        failures.append("Missing structured AC table")

    global_tables = [
        table
        for table in acceptance_tables
        if header_index(table.headers, "ac") is not None
        and header_index(table.headers, "forbidden") is not None
        and header_index(table.headers, "severity") is not None
    ]
    if not global_tables:
        failures.append("Missing global forbidden-items AC table")

    defined_ids: set[str] = set()
    global_ids: list[str] = []
    found_categories: set[str] = set()

    for table in global_tables:
        ac_column = header_index(table.headers, "ac")
        severity_column = header_index(table.headers, "severity")
        assert ac_column is not None and severity_column is not None
        for row in table.rows:
            if max(ac_column, severity_column) >= len(row.cells):
                failures.append(f"Incomplete global AC row at line {row.line_number}")
                continue
            ac_id = row.cells[ac_column].strip().upper()
            severity = row.cells[severity_column].strip().upper()
            if not re.fullmatch(r"G-\d{2}", ac_id):
                failures.append(f"Malformed global AC ID: {ac_id}")
                continue
            if ac_id in global_ids:
                failures.append(f"Duplicate global AC ID: {ac_id}")
            global_ids.append(ac_id)
            defined_ids.add(ac_id)
            if severity not in {"FAIL", "WARN"}:
                failures.append(f"Invalid AC severity for {ac_id}: {severity or '<empty>'}")

    if global_ids:
        numbers = sorted({int(ac_id[2:]) for ac_id in global_ids})
        missing_numbers = sorted(set(range(1, numbers[-1] + 1)) - set(numbers))
        if missing_numbers:
            formatted = ", ".join(f"G-{number:02d}" for number in missing_numbers)
            warnings.append(f"Global AC ID gap: missing {formatted}")

    if tier in {"S", "M", "L"}:
        canonical_ids = {f"G-{number:02d}" for number in range(1, 9)}
        missing_canonical = sorted(canonical_ids - set(global_ids))
        if missing_canonical:
            failures.append(
                "Missing canonical global AC IDs: " + ", ".join(missing_canonical)
            )

    for table in ac_tables:
        columns = {
            role: header_index(table.headers, role)
            for role in ("ac", "category", "requirement", "verification", "severity")
        }
        assert all(column is not None for column in columns.values())
        last_column = max(column for column in columns.values() if column is not None)
        for row in table.rows:
            if last_column >= len(row.cells):
                failures.append(f"Incomplete AC row at line {row.line_number}")
                continue
            ac_id = row.cells[columns["ac"]].strip().upper()  # type: ignore[index]
            category = row.cells[columns["category"]].strip().lower()  # type: ignore[index]
            requirement = row.cells[columns["requirement"]].strip()  # type: ignore[index]
            verification = row.cells[columns["verification"]].strip()  # type: ignore[index]
            severity = row.cells[columns["severity"]].strip().upper()  # type: ignore[index]

            if not AC_ID_RE.fullmatch(ac_id) or ac_id.startswith("G-"):
                failures.append(f"Invalid AC ID at line {row.line_number}: {ac_id or '<empty>'}")
            elif ac_id in defined_ids:
                failures.append(f"Duplicate AC ID: {ac_id}")
            else:
                defined_ids.add(ac_id)

            if category not in AC_CATEGORIES:
                failures.append(f"Invalid AC category for {ac_id}: {category or '<empty>'}")
            else:
                found_categories.add(category)
            if not requirement:
                failures.append(f"Empty AC requirement for {ac_id}")
            if not verification or PLACEHOLDER_RE.search(verification):
                failures.append(f"Missing or placeholder verification method for {ac_id}")
            if severity not in {"FAIL", "WARN"}:
                failures.append(f"Invalid AC severity for {ac_id}: {severity or '<empty>'}")

    if len(found_categories) < 2:
        warnings.append("Few AC categories found; use additional categories where applicable")

    milestones = find_milestones(
        visible_lines[:acceptance_index] if acceptance_index is not None else visible_lines
    )
    for milestone in sorted(milestones):
        done_pattern = re.compile(rf"^{re.escape(milestone)}-DONE(?:-\d+)?$")
        if not any(done_pattern.fullmatch(ac_id) for ac_id in defined_ids):
            failures.append(f"Missing DONE AC for milestone {milestone}")

    for table in task_tables:
        task_column = header_index(table.headers, "task")
        ac_column = header_index(table.headers, "implements_ac")
        assert task_column is not None and ac_column is not None
        for row in table.rows:
            if max(task_column, ac_column) >= len(row.cells):
                failures.append(f"Incomplete Task -> AC row at line {row.line_number}")
                continue
            task = row.cells[task_column].strip() or f"line {row.line_number}"
            references = [match.upper() for match in AC_REFERENCE_RE.findall(row.cells[ac_column])]
            if not references:
                failures.append(f"Task {task} has no AC reference")
            for reference in references:
                if reference not in defined_ids:
                    append_unique(failures, f"Undefined AC reference: {reference} (task {task})")

    placeholder_count = len(PLACEHOLDER_RE.findall(text))
    if placeholder_count > 10:
        warnings.append(f"Found {placeholder_count} placeholder tokens; complete the draft before approval")

    if not re.search(r"\bWARN\b", text):
        warnings.append("No WARN severity found")


def validate_tier(
    text: str,
    visible_lines: list[str],
    tier: str | None,
    failures: list[str],
) -> None:
    if tier not in {"M", "L"}:
        return

    readiness_fields = (
        "AI Readiness",
        "No new design decisions required",
        "Validation commands",
        "Blocking ambiguities",
    )
    missing_readiness = [field for field in readiness_fields if field.lower() not in text.lower()]
    if missing_readiness:
        failures.append(
            "M tier requires AI Readiness fields: " + ", ".join(missing_readiness)
        )

    approval_fields = ("Spec status", "Approved by", "Approval date", "Implementation allowed")
    missing_approval = [field for field in approval_fields if field.lower() not in text.lower()]
    if missing_approval:
        failures.append("M tier requires Approval fields: " + ", ".join(missing_approval))

    if not has_heading(visible_lines, r"interface|接口|contract|契约"):
        failures.append("M tier requires interfaces and boundaries")
    if not has_heading(visible_lines, r"handoff|交接|恢复"):
        failures.append("M tier requires Handoff and recovery")

    if tier != "L":
        return

    if not has_heading(visible_lines, r"Architecture Constitution|架构宪法"):
        failures.append("L tier requires Architecture Constitution")
    if not has_heading(visible_lines, r"Boundary Policy|边界策略"):
        failures.append("L tier requires Boundary Policy")
    for field in ("Workflow Variant", "Spec Maintenance Mode", "Execution Mode"):
        if field.lower() not in text.lower():
            failures.append(f"L tier requires {field}")

    flow_terms = ("Proposal", "Requirements", "Design", "Tasks", "Implementation", "Acceptance")
    if not all(term.lower() in text.lower() for term in flow_terms):
        failures.append(
            "L tier requires complete Proposal -> Requirements -> Design -> Tasks -> Implementation -> Acceptance flow"
        )

    acceptance_index, _ = find_acceptance_section(visible_lines)
    milestone_lines = visible_lines[:acceptance_index] if acceptance_index is not None else visible_lines
    milestones = find_milestones(milestone_lines)
    if "P0" not in milestones or not any(item.startswith("M") for item in milestones):
        failures.append("L tier requires full P0 + M1..Mn milestone chapters")

    if not has_heading(visible_lines, r"stage report|阶段报告|报告格式") or not re.search(
        r"\breports?(?:/|\\|\b)", text, re.IGNORECASE
    ):
        failures.append("L tier requires stage report format and reports directory")


def check_document(text: str) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    visible_lines = mask_fenced_lines(text)

    tier_match = re.search(r"^\s*Document Tier\s*:\s*([^\s|]+)", text, re.IGNORECASE | re.MULTILINE)
    tier = tier_match.group(1).upper() if tier_match else None
    if tier is None:
        warnings.append("Missing Document Tier; applying backward-compatible base checks")
    elif tier not in {"S", "M", "L"}:
        failures.append(f"Invalid Document Tier: {tier}; expected S, M, or L")

    validate_common_structure(text, visible_lines, tier, failures, warnings)
    validate_tier(text, visible_lines, tier, failures)

    for phrase in LEGACY_REQUIRED_PHRASES:
        if phrase not in text:
            warnings.append(f"Missing legacy recommended phrase: {phrase}")

    return failures, warnings


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_prd_ac.py <markdown-file>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        print(f"ERROR: cannot read {path}: {error}", file=sys.stderr)
        return 2

    failures, warnings = check_document(text)
    if failures:
        print("FAIL")
        for item in failures:
            print(f"- {item}")
        if warnings:
            print("WARN")
            for item in warnings:
                print(f"- {item}")
        return 1

    print("PASS")
    for item in warnings:
        print(f"WARN: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
