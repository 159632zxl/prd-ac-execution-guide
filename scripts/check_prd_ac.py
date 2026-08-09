#!/usr/bin/env python3
"""Structural checker for PRDs written with the AC execution guide."""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date
from html import unescape
from pathlib import Path


AC_CATEGORIES = {
    "happy",
    "edge",
    "error",
    "non-functional",
    "data-integrity",
    "safety",
}

EXPLICIT_PLACEHOLDER_RE = re.compile(
    r"<\s*(?!/?(?:br|code|kbd|em|strong|sub|sup|details|summary)\b)(?!https?://)"
    r"(?:\.\.\.|…|[A-Za-z\u3400-\u9fff][^<>\r\n]*)\s*>|\bTODO\b|\bTBD\b|待定",
    re.IGNORECASE,
)
TABLE_ELLIPSIS_RE = re.compile(r"\.\.\.|…")
NON_CONTENT_RE = re.compile(
    r"^(?:[.\-?]+|n/?a|none|null|nil|无|没有|见上|同上)$",
    re.IGNORECASE,
)
RAW_TEXT_HTML_TAGS = (
    "script",
    "style",
    "pre",
    "textarea",
    "template",
    "xmp",
    "listing",
    "iframe",
    "noembed",
    "noframes",
    "title",
)
RAW_TEXT_HTML_TAG_PATTERN = "|".join(RAW_TEXT_HTML_TAGS)
NON_SEMANTIC_HTML_RE = re.compile(
    rf"<({RAW_TEXT_HTML_TAG_PATTERN})\b[^>]*>.*?</\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
UNTERMINATED_NON_SEMANTIC_HTML_RE = re.compile(
    rf"<(?:{RAW_TEXT_HTML_TAG_PATTERN}|plaintext)\b[^>]*>.*\Z",
    re.IGNORECASE | re.DOTALL,
)
CSS_COMMENT_RE = re.compile(r"/\*.*?(?:\*/|\Z)", re.DOTALL)
CSS_ESCAPE_RE = re.compile(r"\\(?:([0-9A-Fa-f]{1,6})[\t\n\f\r ]?|([^\n\r\f]))")
# This is deliberately a scanner rather than one large regex.  Attribute
# quoting, nested tags, and an omitted closing tag otherwise create easy ways
# for hidden Markdown to be treated as visible evidence.
HTML_TAG_NAME_RE = re.compile(r"<(?P<closing>/)?(?P<tag>[A-Za-z][\w:-]*)", re.ASCII)
HTML_ATTRIBUTE_RE = re.compile(
    r"(?P<name>[A-Za-z_:][\w:.-]*)"
    r"(?:\s*=\s*(?:\"(?P<double>[^\"]*)\"|'(?P<single>[^']*)'|"
    r"(?P<bare>[^\s\"'=<>`]+)))?",
    re.ASCII,
)
VOID_HTML_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
AC_ID_RE = re.compile(
    r"^(?:G-\d{2}|(?:P0|M\d+)-[A-Z0-9]+(?:-[A-Z0-9]+)*)$"
)
AC_REFERENCE_RE = re.compile(
    r"\b(?:G-\d+|(?:P0|M\d+)-[A-Z0-9]+(?:-[A-Z0-9]+)*)\b"
)
CANONICAL_GLOBAL_RULES = {
    "G-01": ("禁止绕过事实真源", "Do not bypass the truth source"),
    "G-02": ("禁止无证据更新长期状态", "Do not update persistent state without evidence"),
    "G-03": ("禁止先做增强层再补核心闭环", "Do not build enhancements before completing the core loop"),
    "G-04": ("禁止覆盖用户已有文件且无说明", "Do not overwrite existing user files without explicit disclosure"),
    "G-05": (
        "禁止未查询即猜测接口、路径、schema 或命令",
        "Do not guess interfaces, paths, schemas, or commands without checking",
        "Do not guess interfaces, paths, schema, or commands without checking",
    ),
    "G-06": ("禁止未确认即臆想业务规则或用户意图", "Do not invent business rules or user intent without confirmation"),
    "G-07": ("禁止未获批准进行 scope expansion 或高风险操作", "Do not expand scope or perform high-risk operations without approval"),
    "G-08": ("禁止无 Validation evidence 宣称完成", "Do not claim completion without validation evidence"),
}
HEADING_RE = re.compile(r"^##(?!#)\s+(.+?)\s*$")
MILESTONE_HEADING_RE = re.compile(r"^#{2,3}(?!#)\s+(.+?)\s*$")
SECTION_NUMBER_RE = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+")
ACCEPTANCE_TITLE_RE = re.compile(
    r"^(?:验收标准总览(?:[（(]\s*Acceptance Criteria\s*[）)])?|Acceptance Criteria)$",
    re.IGNORECASE,
)


def contains_disallowed_control(value: str) -> bool:
    return any(
        unicodedata.category(character).startswith("C")
        and character not in "\t\n\r"
        for character in value
    )


def normalize_validation_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def contains_explicit_placeholder(value: str) -> bool:
    return bool(EXPLICIT_PLACEHOLDER_RE.search(normalize_validation_text(value)))


def is_non_content_text(value: str) -> bool:
    return bool(NON_CONTENT_RE.fullmatch(normalize_validation_text(value).strip()))


def decode_css_escapes(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        hexadecimal = match.group(1)
        if hexadecimal is None:
            return match.group(2) or ""
        codepoint = int(hexadecimal, 16)
        if codepoint == 0 or codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
            return "\N{REPLACEMENT CHARACTER}"
        return chr(codepoint)

    return CSS_ESCAPE_RE.sub(replace, value)


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

READINESS_METADATA_FIELDS = {
    "ai readiness",
    "no new design decisions required",
    "validation commands",
    "blocking ambiguities",
}
APPROVAL_METADATA_FIELDS = {
    "spec status",
    "approved by",
    "approval date",
    "implementation allowed",
}
MANIFEST_METADATA_FIELD_NAMES = (
    "Spec status",
    "Document Tier",
    "Implementation allowed",
)
MANIFEST_METADATA_FIELDS = {field.lower() for field in MANIFEST_METADATA_FIELD_NAMES}
TIER_FIELD_ENUMS = {
    "Document Tier": {"s", "m", "l"},
    "AI Readiness": {"ready", "not-ready"},
    "No new design decisions required": {"yes", "no"},
    "Spec status": {"draft", "approved", "superseded"},
    "Implementation allowed": {"yes", "no"},
    "Workflow Variant": {"requirements-first", "design-first"},
    "Spec Maintenance Mode": {"spec-first", "spec-anchored", "spec-as-source"},
    "Execution Mode": {"step", "batch", "phase"},
}
APPROVAL_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NEGATED_HEADING_PREFIX_RE = re.compile(
    r"^\s*(?:no|not|without|none|missing|omit(?:ted)?|无|无需|不需要|未|没有|缺少)\b",
    re.IGNORECASE,
)
FLOW_TERMS = (
    "Proposal",
    "Requirements",
    "Design",
    "Tasks",
    "Implementation",
    "Acceptance",
)


@dataclass(frozen=True)
class TableRow:
    line_number: int
    cells: list[str]


@dataclass(frozen=True)
class MarkdownTable:
    headers: list[str]
    rows: list[TableRow]


def mask_hidden_html(text: str) -> str:
    """Blank hidden HTML while preserving line count for diagnostics."""

    def blank(value: str) -> str:
        return "".join("\n" if character == "\n" else "" for character in value)

    def tag_end(start: int) -> int | None:
        quote: str | None = None
        cursor = start
        while cursor < len(text):
            character = text[cursor]
            if quote:
                if character == quote:
                    quote = None
            elif character in "\"'":
                quote = character
            elif character == ">":
                return cursor
            cursor += 1
        return None

    def attributes(body: str, name_end: int) -> dict[str, str | None]:
        parsed: dict[str, str | None] = {}
        cursor = name_end
        while cursor < len(body):
            match = HTML_ATTRIBUTE_RE.match(body, cursor)
            if not match:
                cursor += 1
                continue
            attribute_name = match.group("name").casefold()
            value = match.group("double")
            if value is None:
                value = match.group("single")
            if value is None:
                value = match.group("bare")
            # A repeated attribute does not make a visible element visible.
            parsed.setdefault(attribute_name, value)
            cursor = match.end()
        return parsed

    def is_hidden_start(tag_name: str, parsed: dict[str, str | None]) -> bool:
        if "hidden" in parsed:
            return True
        if tag_name.casefold() in {"details", "dialog"} and "open" not in parsed:
            return True
        aria_hidden = parsed.get("aria-hidden")
        if (
            aria_hidden is not None
            and normalize_validation_text(unescape(aria_hidden)).strip().casefold() == "true"
        ):
            return True
        style = parsed.get("style")
        if style is None:
            return False
        style = decode_css_escapes(unescape(style))
        style = CSS_COMMENT_RE.sub("", style)
        for declaration in style.split(";"):
            if ":" not in declaration:
                continue
            property_name, property_value = declaration.split(":", 1)
            property_name = re.sub(r"\s+", "", property_name).casefold()
            property_value = re.sub(r"\s+", "", property_value).casefold()
            if property_value.endswith("!important"):
                property_value = property_value[: -len("!important")]
            if property_name == "display" and property_value == "none":
                return True
            if property_name == "visibility" and property_value in {"hidden", "collapse"}:
                return True
            if property_name == "opacity" and re.fullmatch(r"0(?:\.0+)?", property_value):
                return True
        return False

    # Stack records every non-void element so malformed/nested markup cannot
    # accidentally end a hidden region at the wrong closing tag.
    output: list[str] = []
    stack: list[tuple[str, bool]] = []
    cursor = 0
    hidden_depth = 0
    while cursor < len(text):
        if text.startswith("<!--", cursor):
            end = text.find("-->", cursor + 4)
            end = len(text) if end < 0 else end + 3
            raw = text[cursor:end]
            output.append(blank(raw) if hidden_depth else raw)
            cursor = end
            continue

        if text[cursor] != "<":
            end = text.find("<", cursor)
            end = len(text) if end < 0 else end
            raw = text[cursor:end]
            output.append(blank(raw) if hidden_depth else raw)
            cursor = end
            continue

        match = HTML_TAG_NAME_RE.match(text, cursor)
        if not match:
            output.append("\n" if text[cursor] == "\n" else ("" if hidden_depth else text[cursor]))
            cursor += 1
            continue

        end = tag_end(cursor + 1)
        if end is None:
            # A malformed hidden opener has no safe visible interpretation.
            tail = text[cursor:]
            raw_body = tail[match.end() - cursor :]
            parsed = attributes(raw_body, 0)
            if not match.group("closing") and is_hidden_start(match.group("tag"), parsed):
                output.append(blank(tail))
                break
            output.append(blank(tail) if hidden_depth else tail)
            break

        raw = text[cursor : end + 1]
        tag_name = match.group("tag").casefold()
        closing = bool(match.group("closing"))
        if closing:
            # HTML is forgiving: close the nearest matching open tag and any
            # malformed descendants above it. Hidden content stays masked while
            # those records are removed.
            if hidden_depth:
                output.append(blank(raw))
            else:
                output.append(raw)
            matching_index = next(
                (index for index in range(len(stack) - 1, -1, -1) if stack[index][0] == tag_name),
                None,
            )
            if matching_index is not None:
                for _, was_hidden in stack[matching_index:]:
                    if was_hidden:
                        hidden_depth -= 1
                del stack[matching_index:]
            cursor = end + 1
            continue

        attrs = attributes(text[cursor : end + 1], match.end() - cursor)
        hidden = is_hidden_start(tag_name, attrs)
        currently_hidden = hidden_depth > 0
        output.append(blank(raw) if currently_hidden or hidden else raw)
        self_closing = bool(re.search(r"/\s*>$", raw)) or tag_name in VOID_HTML_TAGS
        if not self_closing:
            stack.append((tag_name, hidden))
            if hidden:
                hidden_depth += 1
        cursor = end + 1

    return "".join(output)


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


def is_markdown_table_row(line: str) -> bool:
    content = line.strip()
    return bool(content) and bool(re.search(r"(?<!\\)\|", content))


def mask_fenced_lines(text: str) -> list[str]:
    text = mask_hidden_html(text)
    masked: list[str] = []
    fence: tuple[str, int] | None = None
    html_comment = False
    raw_html_tag: str | None = None
    for line in text.splitlines():
        if fence is not None:
            marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
            if marker:
                token = marker.group(1)
                if token[0] == fence[0] and len(token) >= fence[1] and not marker.group(2).strip():
                    fence = None
            masked.append("")
            continue

        if raw_html_tag is not None:
            if raw_html_tag != "plaintext" and re.search(
                rf"</\s*{re.escape(raw_html_tag)}\s*>", line, re.IGNORECASE
            ):
                raw_html_tag = None
            masked.append("")
            continue

        visible_parts: list[str] = []
        cursor = 0
        while cursor < len(line):
            if html_comment:
                comment_end = line.find("-->", cursor)
                if comment_end < 0:
                    cursor = len(line)
                    break
                html_comment = False
                cursor = comment_end + 3
                continue
            comment_start = line.find("<!--", cursor)
            if comment_start < 0:
                visible_parts.append(line[cursor:])
                break
            visible_parts.append(line[cursor:comment_start])
            html_comment = True
            cursor = comment_start + 4

        visible_line = "".join(visible_parts)
        raw_opener = re.match(
            rf"^ {{0,3}}<({RAW_TEXT_HTML_TAG_PATTERN}|plaintext)(?=[\s>/])",
            visible_line,
            re.IGNORECASE,
        )
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", visible_line)
        if raw_opener:
            tag = raw_opener.group(1).lower()
            if tag == "plaintext" or not re.search(
                rf"</\s*{re.escape(tag)}\s*>", visible_line, re.IGNORECASE
            ):
                raw_html_tag = tag
            masked.append("")
        elif marker:
            token = marker.group(1)
            fence = (token[0], len(token))
            masked.append("")
        elif visible_line.startswith("\t") or visible_line.startswith("    "):
            masked.append("")
        else:
            masked.append(visible_line)
    return masked


def extract_designated_metadata_lines(text: str) -> list[str]:
    """Return fields from fenced blocks that are explicitly acting as metadata."""

    text = mask_hidden_html(text)
    candidate = re.sub(r"<!--[\s\S]*?(?:-->|$)", "", text)
    candidate = NON_SEMANTIC_HTML_RE.sub("", candidate)
    candidate = re.sub(
        r"^ {0,3}<(?:script|style|pre|textarea|template)(?=[\s>/])[^>]*>[\s\S]*$",
        "",
        candidate,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    lines = candidate.splitlines()
    metadata: list[str] = []
    current_heading = ""
    seen_level_two = False
    index = 0
    while index < len(lines):
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", lines[index])
        if heading:
            current_heading = heading.group(2)
            if len(heading.group(1)) == 2:
                seen_level_two = True
            index += 1
            continue

        opener = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", lines[index])
        if not opener:
            index += 1
            continue
        token = opener.group(1)
        block: list[str] = []
        cursor = index + 1
        closed = False
        while cursor < len(lines):
            closer = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", lines[cursor])
            if (
                closer
                and closer.group(1)[0] == token[0]
                and len(closer.group(1)) >= len(token)
                and not closer.group(2).strip()
            ):
                closed = True
                break
            block.append(lines[cursor])
            cursor += 1
        if not closed:
            break

        fields = {
            match.group(1).strip().lower()
            for line in block
            if (match := re.match(r"^\s*([A-Za-z][A-Za-z ]+?)\s*[:：]", line))
        }
        is_manifest = not seen_level_two and MANIFEST_METADATA_FIELDS <= fields
        is_readiness = (
            bool(re.search(r"AI Readiness", current_heading, re.IGNORECASE))
            and READINESS_METADATA_FIELDS <= fields
        )
        is_approval = (
            bool(re.search(r"Approval Gate", current_heading, re.IGNORECASE))
            and APPROVAL_METADATA_FIELDS <= fields
        )
        if is_manifest or is_readiness or is_approval:
            metadata.extend(block)
        index = cursor + 1
    return metadata


def mask_inline_metadata(text: str) -> str:
    text = mask_hidden_html(text)
    text = NON_SEMANTIC_HTML_RE.sub("", text)
    lines: list[str] = []
    reference_title_may_follow = False
    for line in text.splitlines():
        if re.match(r"^\s{0,3}\[(?!\^)[^\]\r\n]+\]:", line):
            lines.append("")
            reference_title_may_follow = True
            continue
        if reference_title_may_follow and re.fullmatch(
            r"\s{1,3}(?:\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|\((?:\\.|[^)])*\))\s*",
            line,
        ):
            lines.append("")
            reference_title_may_follow = False
            continue
        reference_title_may_follow = False
        line = re.sub(r"(`+)(.*?)\1", "", line)
        line = re.sub(r"(?<=\])\((?:\\.|[^)\r\n])*\)", "", line)
        line = re.sub(r"<(?:https?://|mailto:)[^>\r\n]+>", "", line, flags=re.IGNORECASE)
        line = re.sub(r"</?[A-Za-z][^>\r\n]*>", "", line)
        lines.append(line)
    return "\n".join(lines)


def visible_table_cell(value: str) -> str:
    value = mask_hidden_html(value)
    text = NON_SEMANTIC_HTML_RE.sub("", value)
    text = UNTERMINATED_NON_SEMANTIC_HTML_RE.sub("", text)
    placeholder = EXPLICIT_PLACEHOLDER_RE.search(normalize_validation_text(text))
    text = re.sub(r"!\[[^\]\r\n]*\]\((?:\\.|[^)\r\n])*\)", "", text)
    text = re.sub(r"(?<!!)\[([^\]\r\n]*)\]\((?:\\.|[^)\r\n])*\)", r"\1", text)
    text = re.sub(r"(?<!!)\[([^\]\r\n]*)\]\[[^\]\r\n]*\]", r"\1", text)
    text = re.sub(
        r"<((?:https?://|mailto:)[^>\r\n]+)>",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"</?[A-Za-z][^>\r\n]*>", "", text)
    text = re.sub(r"(`+)(.*?)\1", r"\2", text)
    visible = unescape(text).strip()
    return visible or (placeholder.group(0) if placeholder else "")


def normalized_rule_text(value: str) -> str:
    value = normalize_validation_text(value).strip().casefold()
    value = re.sub(r"[.!?。！？]+$", "", value)
    return re.sub(r"\s+", " ", value)


def parse_markdown_tables(lines: list[str], line_offset: int = 0) -> list[MarkdownTable]:
    tables: list[MarkdownTable] = []
    index = 0
    while index + 1 < len(lines):
        if not is_markdown_table_row(lines[index]):
            index += 1
            continue

        headers = split_markdown_row(lines[index])
        separators = split_markdown_row(lines[index + 1])
        if len(headers) != len(separators) or not is_separator_row(separators):
            index += 1
            continue

        rows: list[TableRow] = []
        cursor = index + 2
        while cursor < len(lines) and is_markdown_table_row(lines[cursor]):
            cells = split_markdown_row(lines[cursor])
            rows.append(TableRow(cursor + 1 + line_offset, cells))
            cursor += 1
        tables.append(MarkdownTable(headers, rows))
        index = cursor
    return tables


def table_cell_has_placeholder(value: str, *, allow_sentinel: bool = False) -> bool:
    normalized = normalize_validation_text(value)
    return bool(
        EXPLICIT_PLACEHOLDER_RE.search(normalized)
        or TABLE_ELLIPSIS_RE.search(normalized)
        or contains_disallowed_control(value)
        or (not allow_sentinel and is_non_content_text(value))
    )


def count_placeholders(text: str, tables: list[MarkdownTable]) -> int:
    text = normalize_validation_text(mask_hidden_html(text))
    count = len(EXPLICIT_PLACEHOLDER_RE.findall(text))
    for table in tables:
        cells = [*table.headers, *(cell for row in table.rows for cell in row.cells)]
        for cell in cells:
            normalized_cell = normalize_validation_text(cell)
            without_explicit = EXPLICIT_PLACEHOLDER_RE.sub("", normalized_cell)
            count += len(TABLE_ELLIPSIS_RE.findall(without_explicit))
    return count


def has_heading(lines: list[str], pattern: str) -> bool:
    return any(
        re.search(pattern, match.group(1), re.IGNORECASE)
        for line in lines
        if (match := re.match(r"^#{2,6}\s+(.+?)\s*$", line))
    )


def has_level_two_section_content_before(
    lines: list[str], pattern: str, boundary: int | None
) -> bool:
    """Require a populated level-two section before the final acceptance section."""

    scoped_lines = lines[:boundary] if boundary is not None else lines
    for line in scoped_lines:
        match = HEADING_RE.match(line)
        if not match or not re.search(pattern, match.group(1), re.IGNORECASE):
            continue
        title = SECTION_NUMBER_RE.sub("", match.group(1)).strip()
        if NEGATED_HEADING_PREFIX_RE.match(title):
            continue
        # Only a real H2 may satisfy the M/L gate.  Nested H3/H4 headings can
        # describe a subsection, but cannot replace the required top-level
        # boundary chapter.
        if has_section_content(scoped_lines, rf"^{re.escape(title)}$"):
            return True
    return False


def has_section_content(
    lines: list[str], pattern: str, *, required_level: int | None = 2
) -> bool:
    headings: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^(#{2,6})\s+(.+?)\s*$", line)
        if match:
            headings.append((index, len(match.group(1)), match.group(2)))

    for position, (start, level, title) in enumerate(headings):
        normalized_title = SECTION_NUMBER_RE.sub("", title).strip()
        if (
            required_level is not None
            and level != required_level
        ) or not re.search(pattern, normalized_title, re.IGNORECASE):
            continue
        if NEGATED_HEADING_PREFIX_RE.match(normalized_title):
            continue
        end = len(lines)
        for next_start, next_level, _ in headings[position + 1 :]:
            if next_level <= level:
                end = next_start
                break
        section_lines = lines[start + 1 : end]
        for offset, line in enumerate(section_lines):
            stripped = line.strip()
            if not stripped or re.match(r"^#{2,6}\s+", stripped):
                continue
            if re.fullmatch(r"[-*_]{3,}", stripped):
                continue
            if is_markdown_table_row(stripped):
                cells = split_markdown_row(stripped)
                if is_separator_row(cells):
                    continue
                # A Markdown table header is structure, not section content.
                if offset + 1 < len(section_lines) and is_markdown_table_row(
                    section_lines[offset + 1]
                ):
                    separators = split_markdown_row(section_lines[offset + 1])
                    if len(cells) == len(separators) and is_separator_row(separators):
                        continue
            value = visible_table_cell(stripped)
            if value and not table_cell_has_placeholder(value):
                return True
    return False


def has_declaration(text: str, lines: list[str], pattern: str) -> bool:
    if has_section_content(lines, pattern):
        return True
    field_pattern = re.compile(
        r"^\s*(?:[-*+>]\s*)?(?:"
        + pattern
        + r")\s*(?:[:：]|\bis\b|为)\s*(.*?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    return any(
        value and not table_cell_has_placeholder(value)
        for match in field_pattern.finditer(text)
        if (value := visible_table_cell(match.group(1)))
    )


def field_values(lines: list[str], field: str) -> list[str]:
    pattern = re.compile(
        rf"^\s*(?:[-*+>]\s*)?{re.escape(field)}\s*[:：]\s*(.*?)\s*$",
        re.IGNORECASE,
    )
    values: list[str] = []
    for line in lines:
        match = pattern.match(line)
        if not match:
            continue
        value = visible_table_cell(match.group(1))
        if value:
            values.append(value)
    return values


def has_concrete_field(
    lines: list[str], field: str, *, allow_sentinel: bool = True
) -> bool:
    return any(
        not table_cell_has_placeholder(value, allow_sentinel=allow_sentinel)
        for value in field_values(lines, field)
    )


def validate_field_enum(
    lines: list[str],
    field: str,
    failures: list[str],
) -> None:
    allowed = TIER_FIELD_ENUMS[field]
    expected = ", ".join(sorted(allowed))
    for value in field_values(lines, field):
        if value.lower() not in allowed:
            failures.append(f"Invalid {field}: {value}; expected {expected}")


def validate_metadata(
    field_lines: list[str],
    tier: str | None,
    failures: list[str],
) -> None:
    normalized_values: dict[str, set[str]] = {}
    for field, allowed in TIER_FIELD_ENUMS.items():
        validate_field_enum(field_lines, field, failures)
        values = {
            value.lower()
            for value in field_values(field_lines, field)
            if value.lower() in allowed
        }
        normalized_values[field] = values
        if len(values) > 1:
            failures.append(f"Conflicting {field} declarations: {', '.join(sorted(values))}")

    if tier == "S":
        missing = [
            field
            for field in ("Spec status", "Implementation allowed")
            if not has_concrete_field(field_lines, field)
        ]
        if missing:
            failures.append("S tier requires metadata fields: " + ", ".join(missing))

    def single_value(field: str) -> str | None:
        values = normalized_values[field]
        return next(iter(values)) if len(values) == 1 else None

    spec_status = single_value("Spec status")
    implementation_allowed = single_value("Implementation allowed")
    readiness = single_value("AI Readiness")
    no_design_decisions = single_value("No new design decisions required")

    if implementation_allowed == "yes" and spec_status != "approved":
        failures.append("Implementation allowed: yes requires Spec status: approved")
    if readiness == "ready" and no_design_decisions != "yes":
        failures.append(
            "AI Readiness: ready requires No new design decisions required: yes"
        )
    if implementation_allowed == "yes" and readiness == "not-ready":
        failures.append("Implementation allowed: yes requires AI Readiness: ready")
    if implementation_allowed == "yes" and no_design_decisions == "no":
        failures.append(
            "Implementation allowed: yes requires No new design decisions required: yes"
        )


def acceptance_section_indices(lines: list[str]) -> list[int]:
    return [
        index
        for index, line in enumerate(lines)
        if (match := HEADING_RE.match(line))
        and ACCEPTANCE_TITLE_RE.fullmatch(SECTION_NUMBER_RE.sub("", match.group(1)))
    ]


def find_acceptance_section(lines: list[str]) -> tuple[int | None, bool]:
    level_two = [
        (index, match.group(1))
        for index, line in enumerate(lines)
        if (match := HEADING_RE.match(line))
    ]
    matches = acceptance_section_indices(lines)
    if not matches:
        return None, False
    acceptance_index = matches[-1]
    final_level_two = level_two[-1][0] == acceptance_index
    return acceptance_index, final_level_two


def find_milestones(lines: list[str]) -> set[str]:
    milestones: set[str] = set()
    for line in lines:
        match = MILESTONE_HEADING_RE.match(line)
        if not match:
            continue
        title = SECTION_NUMBER_RE.sub("", match.group(1))
        milestone = re.match(r"^(P0|M\d+)(?=\s|[:：.\-–—]|$)", title, re.IGNORECASE)
        if milestone:
            milestones.add(milestone.group(1).upper())
    return milestones


def milestone_sections(lines: list[str]) -> list[tuple[str, int, int, str]]:
    """Return canonical milestone headings in document order."""

    result: list[tuple[str, int, int, str]] = []
    for index, line in enumerate(lines):
        match = MILESTONE_HEADING_RE.match(line)
        if not match:
            continue
        title = SECTION_NUMBER_RE.sub("", match.group(1)).strip()
        milestone = re.match(
            r"^(P0|M\d+)(?=\s|[:：.\-–—]|$)", title, re.IGNORECASE
        )
        if milestone:
            result.append((milestone.group(1).upper(), index, len(line) - len(line.lstrip("#")), title))
    return result


def heading_sections(lines: list[str]) -> list[tuple[int, int, str]]:
    sections: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            sections.append((index, len(match.group(1)), match.group(2)))
    return sections


def section_has_content(lines: list[str], start: int, level: int) -> bool:
    sections = heading_sections(lines)
    current_position = next(
        (position for position, (index, item_level, _) in enumerate(sections)
         if index == start and item_level == level),
        None,
    )
    if current_position is None:
        return False
    end = len(lines)
    for next_start, next_level, _ in sections[current_position + 1 :]:
        if next_level <= level:
            end = next_start
            break
    for line in lines[start + 1 : end]:
        stripped = line.strip()
        if not stripped or re.match(r"^#{1,6}\s+", stripped):
            continue
        if re.fullmatch(r"[-*_]{3,}", stripped):
            continue
        value = visible_table_cell(stripped)
        if value and not table_cell_has_placeholder(value):
            return True
    return False


def has_ordered_workflow(text: str, lines: list[str]) -> bool:
    escaped = [re.escape(term) for term in FLOW_TERMS]
    arrow_pattern = r"\s*(?:->|=>|→)\s*"
    if re.search(arrow_pattern.join(escaped), text, re.IGNORECASE):
        return True
    positions: list[int] = []
    for term in FLOW_TERMS:
        candidates = [
            index
            for index, line in enumerate(lines)
            if re.match(r"^##\s+", line)
            and re.search(rf"\b{re.escape(term)}\b", line, re.IGNORECASE)
        ]
        if not candidates:
            return False
        positions.append(candidates[0])
    return positions == sorted(positions) and len(set(positions)) == len(positions)


def find_milestone_mentions(lines: list[str]) -> set[str]:
    mentions: set[str] = set()
    for line in lines:
        match = MILESTONE_HEADING_RE.match(line)
        if not match:
            continue
        mentions.update(
            milestone.upper()
            for milestone in re.findall(r"\bM\d+\b", match.group(1), re.IGNORECASE)
        )
    return mentions


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
    semantic_lines = text.splitlines()
    acceptance_index, is_final = find_acceptance_section(visible_lines)
    pre_acceptance_lines = (
        semantic_lines[:acceptance_index]
        if acceptance_index is not None
        else semantic_lines
    )
    if not has_section_content(
        pre_acceptance_lines,
        r"^(?:Goal|目标)\b",
        required_level=None,
    ):
        failures.append("Missing goal section")
    if not has_section_content(
        pre_acceptance_lines,
        r"(?:Non-goals?|非目标)",
        required_level=None,
    ):
        failures.append("Missing non-goals section")
    if not has_declaration(
        text,
        semantic_lines,
        r"truth\s+source|事实真源|数据真源|真源",
    ):
        failures.append("Missing truth source")
    if not has_declaration(
        text,
        semantic_lines,
        r"system\s+boundary|scope\s+boundary|boundary|系统边界|执行边界|边界",
    ):
        failures.append("Missing system boundary")

    if len(acceptance_section_indices(visible_lines)) > 1:
        failures.append("Document must contain exactly one Acceptance Criteria level-two section")
    if acceptance_index is None:
        failures.append("Missing final Acceptance Criteria section")
        acceptance_lines: list[str] = []
    else:
        acceptance_lines = visible_lines[acceptance_index:]
        if not is_final:
            append_unique(failures, "Acceptance Criteria must be the final section")
        # H3-H6 headings are children of the final H2 acceptance section. A
        # later H1 or H2 starts a new document section and invalidates it.
        if any(
            re.match(r"^#{1,2}(?!#)\s+", line)
            for line in visible_lines[acceptance_index + 1 :]
        ):
            append_unique(failures, "Acceptance Criteria must be the final section")

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
    else:
        for table in task_tables:
            if not table.rows:
                failures.append("Task -> AC mapping table must contain at least one row")
            elif acceptance_index is not None and all(
                row.line_number > acceptance_index for row in table.rows
            ):
                failures.append(
                    "Task -> AC mapping table must be before Acceptance Criteria"
                )

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
    else:
        for table in ac_tables:
            if not table.rows:
                failures.append("AC table must contain at least one row")

    global_tables = [
        table
        for table in acceptance_tables
        if header_index(table.headers, "ac") is not None
        and header_index(table.headers, "forbidden") is not None
        and header_index(table.headers, "severity") is not None
    ]
    if not global_tables:
        failures.append("Missing global forbidden-items AC table")
    else:
        for table in global_tables:
            if not table.rows:
                failures.append("Global forbidden-items AC table must contain at least one row")

    defined_ids: set[str] = set()
    global_ids: list[str] = []
    found_categories: set[str] = set()

    for table in global_tables:
        ac_column = header_index(table.headers, "ac")
        forbidden_column = header_index(table.headers, "forbidden")
        severity_column = header_index(table.headers, "severity")
        assert ac_column is not None and forbidden_column is not None and severity_column is not None
        for row in table.rows:
            if max(ac_column, forbidden_column, severity_column) >= len(row.cells):
                failures.append(f"Incomplete global AC row at line {row.line_number}")
                continue
            ac_id = row.cells[ac_column].strip().upper()
            forbidden_item = visible_table_cell(row.cells[forbidden_column])
            severity = row.cells[severity_column].strip().upper()
            if not re.fullmatch(r"G-\d{2}", ac_id):
                failures.append(f"Malformed global AC ID: {ac_id}")
                continue
            if ac_id in global_ids:
                failures.append(f"Duplicate global AC ID: {ac_id}")
            global_ids.append(ac_id)
            defined_ids.add(ac_id)
            if not forbidden_item or table_cell_has_placeholder(forbidden_item):
                failures.append(f"Missing or placeholder forbidden item for {ac_id}")
            if severity not in {"FAIL", "WARN"}:
                failures.append(f"Invalid AC severity for {ac_id}: {severity or '<empty>'}")
            if tier in {"S", "M", "L"} and ac_id in CANONICAL_GLOBAL_RULES:
                allowed_meanings = {
                    normalized_rule_text(item)
                    for item in CANONICAL_GLOBAL_RULES[ac_id]
                }
                if normalized_rule_text(forbidden_item) not in allowed_meanings:
                    failures.append(
                        f"Canonical global AC {ac_id} has non-canonical meaning"
                    )
                if severity != "FAIL":
                    failures.append(
                        f"Canonical global AC {ac_id} must use severity FAIL"
                    )

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
            requirement = visible_table_cell(row.cells[columns["requirement"]])  # type: ignore[index]
            verification = visible_table_cell(row.cells[columns["verification"]])  # type: ignore[index]
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
            elif table_cell_has_placeholder(requirement):
                failures.append(f"Placeholder requirement for {ac_id}")
            if not verification or table_cell_has_placeholder(verification):
                failures.append(f"Missing or placeholder verification method for {ac_id}")
            if severity not in {"FAIL", "WARN"}:
                failures.append(f"Invalid AC severity for {ac_id}: {severity or '<empty>'}")

    if len(found_categories) < 2:
        warnings.append("Few AC categories found; use additional categories where applicable")

    narrative_lines = (
        visible_lines[:acceptance_index] if acceptance_index is not None else visible_lines
    )
    milestones = find_milestones(narrative_lines)
    for milestone in sorted(milestones):
        done_pattern = re.compile(rf"^{re.escape(milestone)}-DONE(?:-\d+)?$")
        done_ids = sorted(ac_id for ac_id in defined_ids if done_pattern.fullmatch(ac_id))
        if not done_ids:
            failures.append(f"Missing DONE AC for milestone {milestone}")
        elif len(done_ids) > 1:
            failures.append(
                f"Multiple DONE ACs for milestone {milestone}: {', '.join(done_ids)}"
            )

    mentioned_milestones = find_milestone_mentions(narrative_lines)
    ac_milestones = {
        match.group(1)
        for ac_id in defined_ids
        if (match := re.match(r"^(M\d+)-", ac_id))
    }
    noncanonical_milestones = (mentioned_milestones & ac_milestones) - milestones
    for milestone in sorted(noncanonical_milestones):
        warnings.append(
            f"{milestone} AC rows exist but no canonical {milestone} milestone heading was found"
        )

    for table in task_tables:
        task_column = header_index(table.headers, "task")
        ac_column = header_index(table.headers, "implements_ac")
        assert task_column is not None and ac_column is not None
        for row in table.rows:
            if max(task_column, ac_column) >= len(row.cells):
                failures.append(f"Incomplete Task -> AC row at line {row.line_number}")
                continue
            task_value = visible_table_cell(row.cells[task_column])
            task = task_value or f"line {row.line_number}"
            ac_mapping = visible_table_cell(row.cells[ac_column])
            if not task_value:
                failures.append(f"Empty task at line {row.line_number}")
            elif table_cell_has_placeholder(task_value):
                failures.append(f"Placeholder task at line {row.line_number}")
            if table_cell_has_placeholder(ac_mapping):
                failures.append(f"Task {task} has a placeholder AC mapping")
            references = [match.upper() for match in AC_REFERENCE_RE.findall(ac_mapping)]
            if not references:
                failures.append(f"Task {task} has no AC reference")
            for reference in references:
                if reference not in defined_ids:
                    append_unique(failures, f"Undefined AC reference: {reference} (task {task})")

    placeholder_count = count_placeholders(text, all_tables)
    if placeholder_count > 10:
        warnings.append(f"Found {placeholder_count} placeholder tokens; complete the draft before approval")


def validate_tier(
    text: str,
    semantic_lines: list[str],
    visible_lines: list[str],
    field_lines: list[str],
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
    missing_readiness = [
        field
        for field in readiness_fields
        if not has_concrete_field(
            field_lines,
            field,
            allow_sentinel=field not in {"Validation commands"},
        )
    ]
    if missing_readiness:
        failures.append(
            "M tier requires AI Readiness fields: " + ", ".join(missing_readiness)
        )

    approval_fields = ("Spec status", "Approved by", "Approval date", "Implementation allowed")
    missing_approval = [
        field
        for field in approval_fields
        if not has_concrete_field(field_lines, field, allow_sentinel=False)
    ]
    if missing_approval:
        failures.append("M tier requires Approval fields: " + ", ".join(missing_approval))

    for value in field_values(field_lines, "Approval date"):
        if not APPROVAL_DATE_RE.fullmatch(value.strip()):
            failures.append(f"Approval field Approval date must be an ISO date: {value}")
            continue
        try:
            date.fromisoformat(value.strip())
        except ValueError:
            failures.append(f"Approval field Approval date is invalid: {value}")

    acceptance_index, _ = find_acceptance_section(semantic_lines)
    if not has_level_two_section_content_before(
        semantic_lines, r"interface|接口|contract|契约", acceptance_index
    ):
        failures.append("M tier requires interfaces and boundaries")
    if not has_level_two_section_content_before(
        semantic_lines, r"handoff|交接|恢复", acceptance_index
    ):
        failures.append("M tier requires Handoff and recovery")

    if tier != "L":
        return

    if not has_level_two_section_content_before(
        semantic_lines, r"Architecture Constitution|架构宪法", acceptance_index
    ):
        failures.append("L tier requires Architecture Constitution")
    if not has_level_two_section_content_before(
        semantic_lines, r"Boundary Policy|边界策略", acceptance_index
    ):
        failures.append("L tier requires Boundary Policy")
    for field in ("Workflow Variant", "Spec Maintenance Mode", "Execution Mode"):
        if not has_concrete_field(field_lines, field):
            failures.append(f"L tier requires {field}")

    if not has_ordered_workflow(text, semantic_lines):
        failures.append(
            "L tier requires complete Proposal -> Requirements -> Design -> Tasks -> Implementation -> Acceptance flow"
        )

    acceptance_index, _ = find_acceptance_section(semantic_lines)
    milestone_lines = semantic_lines[:acceptance_index] if acceptance_index is not None else semantic_lines
    milestones = find_milestones(milestone_lines)
    ordered_milestones = milestone_sections(milestone_lines)
    milestone_numbers = sorted(
        int(item[1:])
        for item in milestones
        if re.fullmatch(r"M\d+", item)
    )
    missing_milestones = (
        set(range(1, milestone_numbers[-1] + 1)) - set(milestone_numbers)
        if milestone_numbers
        else {1}
    )
    if (
        "P0" not in milestones
        or not milestone_numbers
        or milestone_numbers[0] != 1
        or missing_milestones
    ):
        failures.append("L tier requires full P0 + M1..Mn milestone chapters")

    ordered_ids = [milestone for milestone, _, _, _ in ordered_milestones]
    expected_order = ["P0", *(f"M{number}" for number in range(1, len(milestone_numbers) + 1))]
    if ordered_ids != expected_order:
        failures.append("L tier milestone chapters must be unique and ordered P0 -> M1..Mn")
    if any(
        not section_has_content(milestone_lines, start, level)
        for _, start, level, _ in ordered_milestones
    ):
        failures.append("L tier milestone chapters must contain content")

    first_milestone_index = min(
        (start for _, start, _, _ in ordered_milestones),
        default=None,
    )
    gate_indices: list[int] = []
    for pattern in (r"Architecture Constitution|架构宪法", r"Boundary Policy|边界策略"):
        index = next(
            (
                line_index
                for line_index, line in enumerate(milestone_lines)
                if (match := HEADING_RE.match(line))
                and not NEGATED_HEADING_PREFIX_RE.match(
                    SECTION_NUMBER_RE.sub("", match.group(1)).strip()
                )
                and re.search(pattern, match.group(1), re.IGNORECASE)
            ),
            None,
        )
        if index is not None:
            gate_indices.append(index)
    if (
        first_milestone_index is not None
        and (len(gate_indices) != 2 or any(index > first_milestone_index for index in gate_indices))
    ):
        failures.append("L tier gates must precede milestone chapters")

    visible_acceptance_index, _ = find_acceptance_section(visible_lines)
    pre_acceptance_lines = (
        visible_lines[:visible_acceptance_index]
        if visible_acceptance_index is not None
        else visible_lines
    )
    semantic_pre_acceptance_lines = (
        semantic_lines[:acceptance_index]
        if acceptance_index is not None
        else semantic_lines
    )
    reports_directory = any(
        re.search(
            r"\breports(?:[/\\]|\s+(?:directory\b|目录))",
            visible_table_cell(line),
            re.IGNORECASE,
        )
        for line in pre_acceptance_lines
    )
    if (
        not has_level_two_section_content_before(
            semantic_pre_acceptance_lines, r"stage report|阶段报告|报告格式", None
        )
        or not reports_directory
    ):
        failures.append("L tier requires stage report format and reports directory")


def check_document(text: str) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    visible_lines = mask_fenced_lines(text)
    visible_text = "\n".join(visible_lines)
    semantic_text = mask_inline_metadata(visible_text)
    semantic_lines = semantic_text.splitlines()
    metadata_lines = extract_designated_metadata_lines(text)
    field_lines = [*visible_lines, *metadata_lines]
    tier_values = field_values(field_lines, "Document Tier")
    tier = next(
        (value.upper() for value in tier_values if value.lower() in TIER_FIELD_ENUMS["Document Tier"]),
        None,
    )
    if not tier_values:
        warnings.append("Missing Document Tier; applying backward-compatible base checks")

    if tier in {"M", "L"}:
        first_h2 = next(
            (index for index, line in enumerate(visible_lines) if HEADING_RE.match(line)),
            len(visible_lines),
        )
        preamble_lines = visible_lines[:first_h2]
        raw_preamble = "\n".join(text.splitlines()[:first_h2])
        preamble_field_lines = [
            *preamble_lines,
            *extract_designated_metadata_lines(raw_preamble),
        ]
        if any(
            field_values(field_lines, field)
            and not field_values(preamble_field_lines, field)
            for field in MANIFEST_METADATA_FIELD_NAMES
        ):
            failures.append("M/L metadata must precede the first level-two section")

    validate_metadata(field_lines, tier, failures)
    validate_common_structure(semantic_text, visible_lines, tier, failures, warnings)
    validate_tier(semantic_text, semantic_lines, visible_lines, field_lines, tier, failures)

    return failures, warnings


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_prd_ac.py <markdown-file>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        print("FAIL")
        print(f"- cannot read {path}: {error}")
        return 1

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
