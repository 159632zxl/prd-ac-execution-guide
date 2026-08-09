#!/usr/bin/env python3
"""Structural checker for PRDs written with the AC execution guide."""

from __future__ import annotations

import re
import string
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
RAW_TEXT_HTML_TAG_SET = frozenset((*RAW_TEXT_HTML_TAGS, "plaintext"))
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
COMMONMARK_HTML_ATTRIBUTE = (
    r"(?:\s+[A-Za-z_:][A-Za-z0-9:._-]*"
    r"(?:\s*=\s*(?:[^\"'=<>`\x00-\x20]+|'[^']*'|\"[^\"]*\"))?)"
)
COMMONMARK_HTML_OPEN_TAG_RE = re.compile(
    rf"<(?P<tag>[A-Za-z][A-Za-z0-9-]*){COMMONMARK_HTML_ATTRIBUTE}*\s*/?>"
)
COMMONMARK_HTML_CLOSE_TAG_RE = re.compile(
    r"</[A-Za-z][A-Za-z0-9-]*\s*>"
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
COMMONMARK_BLOCK_HTML_TAGS = frozenset(
    {
        "address",
        "article",
        "aside",
        "base",
        "basefont",
        "blockquote",
        "body",
        "caption",
        "center",
        "col",
        "colgroup",
        "dd",
        "details",
        "dialog",
        "dir",
        "div",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "frame",
        "frameset",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "head",
        "header",
        "hr",
        "html",
        "iframe",
        "legend",
        "li",
        "link",
        "main",
        "menu",
        "menuitem",
        "nav",
        "noframes",
        "ol",
        "optgroup",
        "option",
        "p",
        "param",
        "search",
        "section",
        "summary",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "title",
        "tr",
        "track",
        "ul",
    }
)
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


def _html_tag_end(value: str, start: int) -> int | None:
    quote: str | None = None
    cursor = start
    while cursor < len(value):
        character = value[cursor]
        if quote:
            if character == quote:
                quote = None
        elif character in "\"'":
            quote = character
        elif character == ">":
            return cursor
        cursor += 1
    return None


def _raw_text_html_opener(value: str) -> tuple[str, int, int] | None:
    """Return an actual raw-text start tag outside escapes and code spans."""

    cursor = 0
    while cursor < len(value):
        if value[cursor] == "`":
            run_end = cursor + 1
            while run_end < len(value) and value[run_end] == "`":
                run_end += 1
            delimiter_length = run_end - cursor
            search = run_end
            while search < len(value):
                if value[search] != "`":
                    search += 1
                    continue
                close_end = search + 1
                while close_end < len(value) and value[close_end] == "`":
                    close_end += 1
                if close_end - search == delimiter_length:
                    cursor = close_end
                    break
                search = close_end
            else:
                cursor = run_end
            continue

        if value[cursor] != "<":
            cursor += 1
            continue
        backslashes = 0
        backtrack = cursor - 1
        while backtrack >= 0 and value[backtrack] == "\\":
            backslashes += 1
            backtrack -= 1
        if backslashes % 2:
            cursor += 1
            continue

        match = HTML_TAG_NAME_RE.match(value, cursor)
        if not match:
            cursor += 1
            continue
        tag_name = match.group("tag").casefold()
        end = _html_tag_end(value, match.end())
        if end is None:
            tail = value[match.end() :]
            if (
                not match.group("closing")
                and tag_name in RAW_TEXT_HTML_TAG_SET
                and re.fullmatch(r" {0,3}", value[:cursor])
                and (not tail or tail[0].isspace())
            ):
                return tag_name, cursor, len(value) - 1
            return None
        if (
            not match.group("closing")
            and tag_name in RAW_TEXT_HTML_TAG_SET
        ):
            return tag_name, cursor, end
        cursor = end + 1
    return None


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
REFERENCE_CONTAINER_PREFIX_RE = re.compile(
    r"^ {0,3}(?:(?:>[ \t]*)|(?:[-+*][ \t]+)|(?:\d{1,9}[.)][ \t]+))*"
)
REFERENCE_TITLE_RE = re.compile(
    r'(?:"(?:\\.|[^"])*"|\'(?:\\.|[^\'])*\'|\((?:\\.|[^)])*\))'
)


@dataclass(frozen=True)
class TableRow:
    line_number: int
    cells: list[str]


@dataclass(frozen=True)
class MarkdownTable:
    headers: list[str]
    rows: list[TableRow]


@dataclass(frozen=True)
class ReferenceDefinitionSpan:
    start: int
    end: int
    label: str
    quote_depth: int
    title_may_follow: bool


def _reference_label_end(value: str) -> int | None:
    escaped = False
    for index, character in enumerate(value):
        if character == "\\":
            escaped = not escaped
            continue
        if escaped:
            escaped = False
            continue
        if character == "[":
            return -1
        if character == "]":
            if index + 1 < len(value) and value[index + 1] == ":":
                return index
            return -1
    return None


def _parse_reference_destination(value: str) -> tuple[bool, bool]:
    """Return whether a destination is valid and may take a title line."""

    value = value.strip()
    if not value:
        return False, False

    destination_end = 0
    if value.startswith("<"):
        index = 1
        while index < len(value):
            character = value[index]
            if (
                character == "\\"
                and index + 1 < len(value)
                and value[index + 1] in string.punctuation
            ):
                index += 2
                continue
            if character == "<":
                return False, False
            if character == ">":
                destination_end = index + 1
                break
            index += 1
        if not destination_end:
            return False, False
    else:
        parenthesis_depth = 0
        index = 0
        while index < len(value):
            character = value[index]
            if (
                character == "\\"
                and index + 1 < len(value)
                and value[index + 1] in string.punctuation
            ):
                destination_end = index + 2
                index += 2
                continue
            if character.isspace():
                break
            if character == "(":
                parenthesis_depth += 1
            elif character == ")":
                if parenthesis_depth == 0:
                    return False, False
                parenthesis_depth -= 1
            destination_end = index + 1
            index += 1
        if not destination_end or parenthesis_depth:
            return False, False

    remainder = value[destination_end:].strip()
    if not remainder:
        return True, True
    return bool(REFERENCE_TITLE_RE.fullmatch(remainder)), False


def _reference_continuation_body(line: str, *, quote_depth: int) -> str | None:
    container = REFERENCE_CONTAINER_PREFIX_RE.match(line)
    assert container is not None
    prefix = container.group(0)
    if re.search(r"(?:[-+*]|\d{1,9}[.)])[ \t]+", prefix):
        return None
    if prefix.count(">") > quote_depth:
        return None
    return line[container.end() :]


def reference_definition_spans(
    lines: list[str],
) -> list[ReferenceDefinitionSpan]:
    """Return non-rendering Markdown reference-definition line spans."""

    spans: list[ReferenceDefinitionSpan] = []
    index = 0
    while index < len(lines):
        prefix = REFERENCE_CONTAINER_PREFIX_RE.match(lines[index])
        assert prefix is not None
        first = lines[index][prefix.end() :]
        if not first.startswith("["):
            index += 1
            continue
        quote_depth = prefix.group(0).count(">")

        label_parts: list[str] = []
        label_line = first[1:]
        end = index
        while True:
            label_end = _reference_label_end(label_line)
            if label_end == -1:
                break
            if label_end is not None:
                label = "\n".join([*label_parts, label_line[:label_end]])
                tail = label_line[label_end + 2 :]
                definition_end = end
                destination_valid, title_may_follow = _parse_reference_destination(tail)
                if not destination_valid:
                    if tail.strip() or end + 1 >= len(lines):
                        break
                    destination = _reference_continuation_body(
                        lines[end + 1], quote_depth=quote_depth
                    )
                    if destination is None:
                        break
                    destination_valid, title_may_follow = _parse_reference_destination(
                        destination
                    )
                    if not destination_valid:
                        break
                    definition_end = end + 1
                if any(not item.isspace() for item in label):
                    spans.append(
                        ReferenceDefinitionSpan(
                            start=index,
                            end=definition_end,
                            label=label,
                            quote_depth=quote_depth,
                            title_may_follow=title_may_follow,
                        )
                    )
                    index = definition_end
                break
            if end + 1 >= len(lines) or not lines[end + 1].strip():
                break
            label_parts.append(label_line)
            end += 1
            continuation = _reference_continuation_body(
                lines[end], quote_depth=quote_depth
            )
            if continuation is None:
                break
            label_line = continuation
        index += 1
    return spans


def _blank_characters(value: str, spans: list[tuple[int, int]]) -> str:
    if not spans:
        return value
    characters = list(value)
    for start, end in spans:
        for index in range(start, end):
            if characters[index] not in "\r\n":
                characters[index] = " "
    return "".join(characters)


def _backtick_runs(value: str) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    cursor = 0
    while cursor < len(value):
        if value[cursor] != "`":
            cursor += 1
            continue
        end = cursor + 1
        while end < len(value) and value[end] == "`":
            end += 1
        runs.append((cursor, end))
        cursor = end
    return runs


def _blank_code_spans(value: str) -> str:
    runs = _backtick_runs(value)
    if not runs:
        return value

    next_same_length: list[int | None] = [None] * len(runs)
    latest_by_length: dict[int, int] = {}
    for index in range(len(runs) - 1, -1, -1):
        start, end = runs[index]
        length = end - start
        next_same_length[index] = latest_by_length.get(length)
        latest_by_length[length] = index

    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(runs):
        if _escaped_at(value, runs[index][0]):
            index += 1
            continue
        closing_index = next_same_length[index]
        if closing_index is None:
            index += 1
            continue
        spans.append((runs[index][0], runs[closing_index][1]))
        index = closing_index + 1
    return _blank_characters(value, spans)


def _escaped_at(value: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and value[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return bool(backslashes % 2)


def _normalize_reference_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower().upper()


def _matching_inline_label_ends(value: str) -> dict[int, int]:
    openers: list[int] = []
    matches: dict[int, int] = {}
    preceding_backslashes = 0
    for index, character in enumerate(value):
        if character == "\\":
            preceding_backslashes += 1
            continue
        escaped = bool(preceding_backslashes % 2)
        preceding_backslashes = 0
        if escaped:
            continue
        if character == "[":
            openers.append(index)
        elif character == "]" and openers:
            matches[openers.pop()] = index
    return matches


def _inline_link_end(value: str, opener: int) -> int | None:
    cursor = opener + 1
    depth = 0
    quote: str | None = None
    while cursor < len(value):
        character = value[cursor]
        if character in "\r\n" and cursor + 1 < len(value) and value[cursor + 1] in "\r\n":
            return None
        if character == "\\" and cursor + 1 < len(value):
            cursor += 2
            continue
        if quote:
            if character == quote:
                quote = None
        elif character in "\"'":
            quote = character
        elif character == "(":
            depth += 1
            if depth > 32:
                return None
        elif character == ")":
            if depth == 0:
                return cursor + 1
            depth -= 1
        cursor += 1
    return None


def _blank_link_destinations(
    value: str,
    reference_labels: set[str] | frozenset[str] = frozenset(),
) -> str:
    brackets: list[int] = []
    spans: list[tuple[int, int]] = []
    reference_label_ends = (
        _matching_inline_label_ends(value) if reference_labels else {}
    )
    cursor = 0
    while cursor < len(value):
        character = value[cursor]
        if character == "[" and not _escaped_at(value, cursor):
            brackets.append(cursor)
        elif character == "]" and not _escaped_at(value, cursor) and brackets:
            label_start = brackets.pop()
            opener = cursor + 1
            is_image = (
                label_start > 0
                and value[label_start - 1] == "!"
                and not _escaped_at(value, label_start - 1)
            )
            if opener < len(value) and value[opener] == "(":
                end = _inline_link_end(value, opener)
                destination_valid = False
                if end is not None:
                    destination_valid, _ = _parse_reference_destination(
                        value[opener + 1 : end - 1]
                    )
                if end is not None and destination_valid:
                    spans.append((opener, end))
                    if is_image:
                        spans.append((label_start, cursor + 1))
                    cursor = end
                    continue
            elif is_image and reference_labels:
                label = value[label_start + 1 : cursor]
                reference_end = cursor + 1
                if opener < len(value) and value[opener] == "[":
                    explicit_end = reference_label_ends.get(opener)
                    if explicit_end is not None:
                        explicit_label = value[opener + 1 : explicit_end]
                        if explicit_label:
                            label = explicit_label
                        reference_end = explicit_end + 1
                if _normalize_reference_label(label) in reference_labels:
                    spans.append((label_start - 1, reference_end))
                    cursor = reference_end
                    continue
        cursor += 1
    return _blank_characters(value, spans)


def _blank_inline_heading_literals(
    value: str,
    reference_labels: set[str] | frozenset[str] = frozenset(),
) -> str:
    return _blank_link_destinations(
        _blank_code_spans(value), reference_labels=reference_labels
    )


def _reference_definition_lines(lines: list[str]) -> set[int]:
    spans_by_start = {span.start: span for span in reference_definition_spans(lines)}
    masked: set[int] = set()
    title_may_follow = False
    title_quote_depth = 0
    index = 0
    while index < len(lines):
        span = spans_by_start.get(index)
        if span is not None:
            masked.update(range(span.start, span.end + 1))
            index = span.end + 1
            title_may_follow = span.title_may_follow
            title_quote_depth = span.quote_depth
            continue
        title_body = _reference_continuation_body(
            lines[index], quote_depth=title_quote_depth
        )
        if (
            title_may_follow
            and title_body is not None
            and REFERENCE_TITLE_RE.fullmatch(title_body.strip())
        ):
            masked.add(index)
        title_may_follow = False
        title_quote_depth = 0
        index += 1
    return masked


def _commonmark_html_block_start(
    line: str, *, paragraph_open: bool
) -> tuple[str | None, bool] | None:
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return None

    raw_tag = re.match(
        r"<(?P<tag>script|pre|style|textarea)(?=[ \t>]|$)",
        stripped,
        re.I,
    )
    if raw_tag:
        return rf"</\s*{re.escape(raw_tag.group('tag'))}\s*>", False
    if stripped.startswith("<!--"):
        return "-->", False
    if stripped.startswith("<?"):
        return r"\?>", False
    if re.match(r"<![A-Z]", stripped):
        return ">", False
    if stripped.startswith("<![CDATA["):
        return r"\]\]>", False

    match = re.match(
        r"^ {0,3}<(?P<closing>/)?(?P<tag>[A-Za-z][\w:-]*)",
        line,
        re.ASCII,
    )
    if not match:
        return None
    tag = match.group("tag").casefold()
    tail = line[match.end() :]
    if tag in COMMONMARK_BLOCK_HTML_TAGS and (
        not tail
        or tail[0] in " \t>"
        or re.match(r"/\s*>", tail)
    ):
        return None, True
    tag_end = _html_tag_end(line, match.end())
    if paragraph_open or tag_end is None or line[tag_end + 1 :].strip():
        return None
    return None, True


def _quote_prefix_end(line: str, quote_depth: int) -> int | None:
    cursor = 0
    for _ in range(quote_depth):
        marker = re.match(r" {0,3}>[ \t]?", line[cursor:])
        if marker is None:
            return None
        cursor += marker.end()
    return cursor


def _strip_html_block_container(
    line: str,
    quote_depth: int,
    list_content_indent: int | None,
) -> str | None:
    if quote_depth == 0 and list_content_indent is None:
        return line

    cursor = _quote_prefix_end(line, quote_depth)
    if cursor is None:
        return None
    if list_content_indent is not None:
        while (
            cursor < len(line)
            and line[cursor] in " \t"
            and len(line[:cursor].expandtabs(4)) < list_content_indent
        ):
            cursor += 1
        if len(line[:cursor].expandtabs(4)) < list_content_indent:
            return "" if not line[cursor:].strip() else None
    return line[cursor:]


def _mask_markdown_in_html_blocks(
    lines: list[str],
) -> tuple[list[str], dict[int, tuple[int, str]], set[int]]:
    masked: list[str] = []
    raw_html_lines: dict[int, tuple[int, str]] = {}
    opaque_html_lines: set[int] = set()
    html_container: tuple[int, int | None, str | None, bool, int] | None = None
    next_html_block_id = 0
    paragraph_open = False
    previous_container: tuple[int, int | None] | None = None
    for line_index, line in enumerate(lines):
        container = REFERENCE_CONTAINER_PREFIX_RE.match(line)
        assert container is not None
        prefix = container.group(0)
        body = line[container.end() :]
        quote_depth = prefix.count(">")
        has_list_marker = bool(
            re.search(r"(?:[-+*]|\d{1,9}[.)])[ \t]+", prefix)
        )
        prefix_width = len(prefix.expandtabs(4))
        container_key = (quote_depth, prefix_width if has_list_marker else None)
        if (
            previous_container is not None
            and container_key != previous_container
            and not (
                previous_container[0] > 0
                and quote_depth == 0
                and paragraph_open
            )
        ):
            paragraph_open = False
        previous_container = container_key

        if html_container is not None:
            (
                block_quote_depth,
                list_content_indent,
                terminator,
                scan_html,
                block_id,
            ) = html_container
            block_body = _strip_html_block_container(
                line,
                block_quote_depth,
                list_content_indent,
            )
            same_container = block_body is not None
            if (
                same_container
                and terminator is None
                and not block_body.strip()
            ):
                html_container = None
                paragraph_open = False
                masked.append(line)
                continue
            if same_container:
                masked.append(" " * len(line))
                raw_html_lines[line_index] = (block_id, block_body)
                if not scan_html:
                    opaque_html_lines.add(line_index)
                if terminator is not None and re.search(terminator, block_body, re.I):
                    html_container = None
                continue
            html_container = None
            paragraph_open = False

        block_start = _commonmark_html_block_start(
            body, paragraph_open=paragraph_open
        )
        if block_start is not None:
            terminator, scan_html = block_start
            block_id = next_html_block_id
            next_html_block_id += 1
            html_container = (
                quote_depth,
                prefix_width if has_list_marker else None,
                terminator,
                scan_html,
                block_id,
            )
            masked.append(" " * len(line))
            raw_html_lines[line_index] = (block_id, body)
            if not scan_html:
                opaque_html_lines.add(line_index)
            terminator_value = body if body.strip() else line.strip()
            if terminator is not None and re.search(terminator, terminator_value, re.I):
                html_container = None
            paragraph_open = False
        else:
            masked.append(line)
            if not body.strip():
                paragraph_open = False
            elif (
                re.match(r"^ {0,3}#{1,6}(?:[ \t]+|$)", body)
                or _standalone_list_marker(body)
                or _thematic_break(body)
            ):
                paragraph_open = False
            else:
                paragraph_open = True
    return masked, raw_html_lines, opaque_html_lines


def _preserve_html_comments_for_heading_scan(lines: list[str]) -> list[str]:
    """Hide comment payload while retaining its block-level structure."""

    preserved: list[str] = []
    comment_open = False
    for line in lines:
        value, comment_open = _preserve_html_comment_structure(
            line, comment_open=comment_open
        )
        preserved.append(value)
    return preserved


def _preserve_html_comment_structure(
    line: str, *, comment_open: bool
) -> tuple[str, bool]:
    """Hide comment payload while retaining delimiters for block parsing."""

    parts: list[str] = []
    cursor = 0
    while cursor < len(line):
        if comment_open:
            end = line.find("-->", cursor)
            if end < 0:
                cursor = len(line)
                break
            parts.append("-->")
            comment_open = False
            cursor = end + 3
            continue
        start = line.find("<!--", cursor)
        if start < 0:
            parts.append(line[cursor:])
            break
        parts.append(line[cursor:start])
        parts.append("<!--")
        comment_open = True
        cursor = start + 4
    preserved = "".join(parts)
    if not preserved.strip() and line.strip():
        preserved = "<!-- -->"
    return preserved, comment_open


def _mask_inline_heading_literals(
    lines: list[str],
    raw_html_lines: set[int],
    reference_labels: set[str],
) -> list[str]:
    masked = list(lines)
    segment_start = 0
    for index in range(len(lines) + 1):
        boundary = (
            index == len(lines)
            or index in raw_html_lines
            or not lines[index].strip()
        )
        if not boundary:
            continue
        if segment_start < index:
            segment = "\n".join(lines[segment_start:index])
            masked[segment_start:index] = _blank_inline_heading_literals(
                segment, reference_labels=reference_labels
            ).split("\n")
        segment_start = index + 1
    return masked


def _thematic_break(value: str) -> bool:
    return bool(
        re.fullmatch(
            r" {0,3}(?:(?:\*[ \t]*){3,}|(?:_[ \t]*){3,}|(?:-[ \t]*){3,})",
            value,
        )
    )


def _standalone_list_marker(value: str) -> bool:
    return bool(re.fullmatch(r" {0,3}(?:[-+*]|\d{1,9}[.)])[ \t]*", value))


def _container_heading_body(line: str) -> tuple[str, int, bool, bool, int]:
    leading = len(line) - len(line.lstrip(" "))
    if leading > 3:
        return line[leading:], 0, False, True, leading
    cursor = leading
    quote_depth = 0
    list_marker = False
    content_indent = cursor
    while cursor < len(line):
        if line[cursor] == ">":
            quote_depth += 1
            cursor += 1
            if cursor < len(line) and line[cursor] in " \t":
                cursor += 1
            content_indent = cursor
            continue
        marker = re.match(r"(?:[-+*]|\d{1,9}[.)])([ \t]+)", line[cursor:])
        if marker is None:
            break
        list_marker = True
        marker_width = marker.end() - len(marker.group(1))
        padding_width = len(marker.group(1).expandtabs(4))
        if padding_width > 4:
            cursor += marker_width + 1
            remaining_indent = padding_width - 1
            return (
                line[cursor:],
                quote_depth,
                list_marker,
                remaining_indent >= 4,
                cursor,
            )
        cursor += marker.end()
        content_indent = cursor
    remaining_indent = 0
    while cursor < len(line) and line[cursor] in " \t":
        remaining_indent += 4 if line[cursor] == "\t" else 1
        cursor += 1
    return line[cursor:], quote_depth, list_marker, remaining_indent >= 4, content_indent


ContainerFrame = tuple[str, int]


def _container_prefix_frames(line: str) -> tuple[tuple[ContainerFrame, ...], str]:
    """Return explicit CommonMark container frames and the remaining body."""

    value = line.expandtabs(4)
    frames: list[ContainerFrame] = []
    cursor = 0
    while cursor < len(value):
        indent_start = cursor
        while cursor < len(value) and value[cursor] == " " and cursor - indent_start < 3:
            cursor += 1
        indent = cursor - indent_start

        if cursor < len(value) and value[cursor] == ">":
            frames.append(("quote", 0))
            cursor += 1
            if cursor < len(value) and value[cursor] == " ":
                cursor += 1
            continue

        marker = re.match(r"(?:[-+*]|\d{1,9}[.)])", value[cursor:])
        if marker is None:
            cursor = indent_start
            break
        marker_end = cursor + marker.end()
        marker_width = marker.end()
        if marker_end == len(value):
            frames.append(("list", indent + marker_width + 1))
            cursor = marker_end
            continue
        if value[marker_end] != " ":
            cursor = indent_start
            break

        padding_end = marker_end
        while padding_end < len(value) and value[padding_end] == " ":
            padding_end += 1
        padding = padding_end - marker_end
        if padding_end < len(value) and padding <= 4:
            effective_padding = padding
            cursor = padding_end
        else:
            effective_padding = 1
            cursor = marker_end + 1 if padding_end < len(value) else padding_end
        frames.append(("list", indent + marker_width + effective_padding))

    return tuple(frames), value[cursor:]


def _list_container_frames(
    frames: tuple[ContainerFrame, ...],
) -> tuple[ContainerFrame, ...] | None:
    for index in range(len(frames) - 1, -1, -1):
        if frames[index][0] == "list":
            return frames[: index + 1]
    return None


def _strip_container_frames(
    line: str,
    frames: tuple[ContainerFrame, ...],
) -> str | None:
    value = line.expandtabs(4)
    cursor = 0
    for kind, width in frames:
        if kind == "quote":
            indent_start = cursor
            while (
                cursor < len(value)
                and value[cursor] == " "
                and cursor - indent_start < 3
            ):
                cursor += 1
            if cursor >= len(value) or value[cursor] != ">":
                return None
            cursor += 1
            if cursor < len(value) and value[cursor] == " ":
                cursor += 1
            continue

        indent_end = cursor + width
        if indent_end > len(value) or value[cursor:indent_end] != " " * width:
            return None
        cursor = indent_end
    return value[cursor:]


def _continued_list_body(origin_line: str, current_line: str) -> str | None:
    frames, _ = _container_prefix_frames(origin_line)
    if _list_container_frames(frames) is None:
        return None
    return _strip_container_frames(current_line, frames)


def _continues_list_container(origin_line: str, current_line: str) -> bool:
    return _continued_list_body(origin_line, current_line) is not None


def _active_list_continuation(
    line: str,
    frames: tuple[ContainerFrame, ...],
) -> tuple[tuple[ContainerFrame, ...], str] | None:
    """Return the deepest still-open list container and its relative body."""

    for index in range(len(frames) - 1, -1, -1):
        if frames[index][0] != "list":
            continue
        candidate = frames[: index + 1]
        body = _strip_container_frames(line, candidate)
        if body is not None:
            return candidate, body
    return None


def _list_marker_info(line: str) -> tuple[int, str] | None:
    prefix = REFERENCE_CONTAINER_PREFIX_RE.match(line)
    assert prefix is not None
    markers = list(
        re.finditer(r"(?:[-+*]|\d{1,9}[.)])(?=[ \t]+)", prefix.group(0))
    )
    if not markers:
        return None
    return markers[0].start(), markers[-1].group(0)


def _list_marker_can_interrupt_paragraph(line: str) -> bool:
    marker = _list_marker_info(line)
    if marker is None:
        return False
    token = marker[1]
    return token in {"-", "+", "*"} or bool(re.match(r"1[.)]", token))


def _heading_scan_lines(
    lines: list[str],
) -> tuple[list[str], list[str], dict[int, int]]:
    heading_lines = _preserve_html_comments_for_heading_scan(lines)
    markdown_lines, raw_html_contexts, opaque_html_lines = (
        _mask_markdown_in_html_blocks(heading_lines)
    )
    raw_html_blocks = {
        index: block_id
        for index, (block_id, _) in raw_html_contexts.items()
    }
    for index, (_, body) in raw_html_contexts.items():
        heading_lines[index] = body
    reference_labels = {
        _normalize_reference_label(span.label)
        for span in reference_definition_spans(markdown_lines)
    }
    reference_lines = _reference_definition_lines(markdown_lines)
    for index in reference_lines:
        markdown_lines[index] = " " * len(markdown_lines[index])
        heading_lines[index] = " " * len(heading_lines[index])
    for index in opaque_html_lines:
        heading_lines[index] = " " * len(heading_lines[index])
    inline_masked = _mask_inline_heading_literals(
        heading_lines, set(raw_html_blocks), reference_labels
    )
    return markdown_lines, inline_masked, raw_html_blocks


def _starts_inline_block(line: str) -> bool:
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return True
    return bool(
        re.match(r"(?:>|#{1,6}(?:[ \t]+|$)|`{3,}|~{3,})", stripped)
        or re.match(r"(?:[-+*]|\d{1,9}[.)])[ \t]+", stripped)
        or _thematic_break(stripped)
    )


def _html_heading_boundaries(
    lines: list[str], raw_html_blocks: dict[int, int]
) -> set[tuple[int, int]]:
    """Find CommonMark-valid HTML H1/H2 start tags without crossing blocks."""

    boundaries: set[tuple[int, int]] = set()
    segment: list[tuple[int, str]] = []
    segment_is_raw = False
    segment_raw_block_id: int | None = None
    segment_container: tuple[int, int | None] | None = None
    active_list: tuple[int, int] | None = None

    def scan_segment() -> None:
        if not segment:
            return
        value = "\n".join(line for _, line in segment)
        cursor = 0
        while cursor < len(value):
            opener = value.find("<", cursor)
            if opener < 0:
                break
            if _escaped_at(value, opener):
                cursor = opener + 1
                continue
            match = COMMONMARK_HTML_OPEN_TAG_RE.match(value, opener)
            if match is not None:
                tag = match.group("tag").casefold()
                if tag in {"h1", "h2"}:
                    line_offset = value.count("\n", 0, opener)
                    boundaries.add((segment[line_offset][0], int(tag[1])))
                cursor = match.end()
                continue
            closing = COMMONMARK_HTML_CLOSE_TAG_RE.match(value, opener)
            cursor = closing.end() if closing is not None else opener + 1

    for index, line in enumerate(lines):
        raw_block_id = raw_html_blocks.get(index)
        is_raw = index in raw_html_blocks
        if is_raw:
            body = line
            has_list_marker = False
            container_key = None
            lazy_continuation = False
            active_list = None
        else:
            body, quote_depth, has_list_marker, _, content_indent = (
                _container_heading_body(line)
            )
            body_start = len(line) - len(body)
            interrupts_paragraph = bool(
                has_list_marker
                or _starts_inline_block(body)
                or _commonmark_html_block_start(body, paragraph_open=True)
                is not None
            )
            previous_active_list = active_list
            lazy_list_continuation = bool(
                segment
                and not segment_is_raw
                and previous_active_list is not None
                and body.strip()
                and body_start < previous_active_list[1]
                and quote_depth <= previous_active_list[0]
                and not interrupts_paragraph
            )
            if has_list_marker:
                active_list = (quote_depth, content_indent)
            elif active_list is not None and (
                quote_depth != active_list[0]
                or (body.strip() and body_start < active_list[1])
            ) and not lazy_list_continuation:
                active_list = None
            container_key = (
                quote_depth,
                active_list[1]
                if active_list is not None and quote_depth == active_list[0]
                else None,
            )
            lazy_quote_continuation = bool(
                segment
                and segment_container is not None
                and not segment_is_raw
                and body.strip()
                and quote_depth < segment_container[0]
                and not interrupts_paragraph
            )
            lazy_continuation = (
                lazy_list_continuation or lazy_quote_continuation
            )
        starts_new = bool(
            segment
            and (
                not body.strip()
                or is_raw != segment_is_raw
                or (
                    is_raw
                    and raw_block_id != segment_raw_block_id
                )
                or (
                    not is_raw
                    and container_key != segment_container
                    and not lazy_continuation
                )
                or (
                    not is_raw
                    and (has_list_marker or _starts_inline_block(body))
                )
            )
        )
        if starts_new:
            scan_segment()
            segment = []
        if not body.strip():
            continue
        if not segment:
            segment_is_raw = is_raw
            segment_raw_block_id = raw_block_id
            segment_container = container_key
        segment.append((index, body))
    scan_segment()
    return boundaries


def rendered_section_boundaries(
    lines: list[str], *, scan_lines: list[str] | None = None
) -> list[tuple[int, int]]:
    """Return visible rendered H1/H2 boundaries as (line index, level)."""

    source_lines = lines if scan_lines is None else scan_lines
    markdown_lines, html_lines, raw_html_lines = _heading_scan_lines(source_lines)
    boundaries: set[tuple[int, int]] = set()
    contexts: list[tuple[str, int, bool, bool, int]] = []
    paragraph_origins: list[int | None] = []
    paragraph_start: int | None = None
    previous_quote_depth = 0
    active_list_frames: tuple[ContainerFrame, ...] | None = None
    for index, line in enumerate(markdown_lines):
        raw_context = _container_heading_body(line)
        body, quote_depth, has_list_marker, indented_code, content_indent = (
            raw_context
        )
        container_line = line
        raw_frames, _ = _container_prefix_frames(line)
        had_active_list = active_list_frames is not None
        next_active_list_frames = active_list_frames
        rejected_marker_frames = active_list_frames
        continuation = (
            _active_list_continuation(line, active_list_frames)
            if active_list_frames is not None and line.strip()
            else None
        )
        if continuation is not None:
            parent_frames, container_line = continuation
            (
                body,
                inner_quote_depth,
                has_list_marker,
                indented_code,
                inner_content_indent,
            ) = _container_heading_body(container_line)
            quote_depth = sum(kind == "quote" for kind, _ in parent_frames)
            quote_depth += inner_quote_depth
            content_indent = sum(
                width for kind, width in parent_frames if kind == "list"
            ) + inner_content_indent
            inner_frames, _ = _container_prefix_frames(container_line)
            nested_list_frames = _list_container_frames(inner_frames)
            next_active_list_frames = (
                parent_frames + nested_list_frames
                if nested_list_frames is not None
                else parent_frames
            )
            rejected_marker_frames = parent_frames
        else:
            current_list_frames = _list_container_frames(raw_frames)
            if current_list_frames is not None:
                if had_active_list:
                    paragraph_start = None
                next_active_list_frames = current_list_frames
                rejected_marker_frames = None
            elif line.strip():
                next_active_list_frames = None
                rejected_marker_frames = None

        if quote_depth != previous_quote_depth:
            paragraph_start = None
        previous_quote_depth = quote_depth

        ordered_noninterrupting = bool(
            paragraph_start is not None
            and has_list_marker
            and not _list_marker_can_interrupt_paragraph(container_line)
        )
        active_list_frames = (
            rejected_marker_frames
            if ordered_noninterrupting
            else next_active_list_frames
        )

        contexts.append(
            (body, quote_depth, has_list_marker, indented_code, content_indent)
        )

        if not body.strip():
            paragraph_start = None
            paragraph_origins.append(None)
            continue
        if indented_code:
            paragraph_origins.append(paragraph_start)
            continue

        atx = re.match(r"^(#{1,6})(?:[ \t]+|$)", body)
        if atx and not ordered_noninterrupting:
            if len(atx.group(1)) <= 2:
                boundaries.add((index, len(atx.group(1))))
            paragraph_start = None
        elif _thematic_break(body) or _standalone_list_marker(body):
            paragraph_start = None
        elif has_list_marker:
            if paragraph_start is None or _list_marker_can_interrupt_paragraph(
                container_line
            ):
                paragraph_start = index
        elif paragraph_start is None:
            paragraph_start = index
        paragraph_origins.append(paragraph_start)

    for index in range(1, len(contexts)):
        body, quote_depth, has_list_marker, indented_code, content_indent = contexts[
            index
        ]
        underline = re.fullmatch(r"[ \t]*(=+|-+)[ \t]*", body)
        if (
            not underline
            or has_list_marker
            or indented_code
            or _standalone_list_marker(markdown_lines[index])
        ):
            continue
        (
            previous_body,
            previous_quote_depth,
            previous_has_list,
            previous_indented_code,
            previous_content_indent,
        ) = (
            contexts[index - 1]
        )
        previous_text = previous_body.strip()
        paragraph_origin = paragraph_origins[index - 1]
        if (
            not previous_text
            or previous_quote_depth > quote_depth
            or quote_depth != previous_quote_depth
            or (previous_indented_code and paragraph_origin is None)
            or re.match(r"^#{1,6}(?:[ \t]+|$)", previous_text)
            or _thematic_break(previous_body)
            or paragraph_origin is None
        ):
            continue
        origin_context = contexts[paragraph_origin]
        if origin_context[2] and not _continues_list_container(
            markdown_lines[paragraph_origin],
            markdown_lines[index],
        ):
            continue
        level = 1 if underline.group(1).startswith("=") else 2
        start = paragraph_origin
        if (
            start > 0
            and contexts[start - 1][1] > quote_depth
            and start == index - 1
            and not re.match(r"^#{1,6}(?:[ \t]+|$)", contexts[start - 1][0])
            and not re.fullmatch(
                r"[ \t]*(?:=+|-+)[ \t]*", contexts[start - 1][0]
            )
        ):
            continue
        boundaries.add((start, level))

    boundaries.update(_html_heading_boundaries(html_lines, raw_html_lines))
    return sorted(boundaries)


def mask_hidden_html(text: str) -> str:
    """Blank hidden HTML while preserving line count for diagnostics."""

    def blank(value: str) -> str:
        return "".join("\n" if character == "\n" else "" for character in value)

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

        end = _html_tag_end(text, cursor + 1)
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


def mask_fenced_lines(
    text: str, *, preserve_html_comments: bool = False
) -> list[str]:
    text = mask_hidden_html(text)
    masked: list[str] = []
    fence: tuple[str, int, tuple[ContainerFrame, ...]] | None = None
    html_comment = False
    raw_html_tag: str | None = None
    active_list_frames: tuple[ContainerFrame, ...] | None = None
    for line in text.splitlines():
        if fence is not None:
            marker_character, marker_length, parent_frames = fence
            fence_body = _strip_container_frames(line, parent_frames)
            parent_closed = bool(line.strip() and fence_body is None)
            if not parent_closed:
                fence_body = fence_body or ""
                inner_frames, _ = _container_prefix_frames(fence_body)
                body, _, _, indented_code, _ = _container_heading_body(fence_body)
                marker = (
                    re.match(r"^(`{3,}|~{3,})(.*)$", body)
                    if not inner_frames and not indented_code
                    else None
                )
                if marker:
                    token = marker.group(1)
                    if (
                        token[0] == marker_character
                        and len(token) >= marker_length
                        and not marker.group(2).strip()
                    ):
                        fence = None
                masked.append("")
                continue
            fence = None
            if _list_container_frames(parent_frames) is not None:
                active_list_frames = None

        if raw_html_tag is not None:
            if raw_html_tag != "plaintext" and re.search(
                rf"</\s*{re.escape(raw_html_tag)}\s*>", line, re.IGNORECASE
            ):
                raw_html_tag = None
            masked.append("")
            continue

        if preserve_html_comments:
            visible_line, html_comment = _preserve_html_comment_structure(
                line, comment_open=html_comment
            )
        else:
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
        raw_frames, _ = _container_prefix_frames(visible_line)
        continued_body = (
            _strip_container_frames(visible_line, active_list_frames)
            if active_list_frames is not None and visible_line.strip()
            else None
        )
        if continued_body is not None:
            inner_frames, _ = _container_prefix_frames(continued_body)
            line_frames = active_list_frames + inner_frames
            body, _, _, container_indented, _ = _container_heading_body(
                continued_body
            )
            if _list_container_frames(inner_frames) is not None:
                active_list_frames = _list_container_frames(line_frames)
        else:
            line_frames = raw_frames
            body, _, _, container_indented, _ = _container_heading_body(visible_line)
            current_list_frames = _list_container_frames(raw_frames)
            if current_list_frames is not None:
                active_list_frames = current_list_frames
            elif visible_line.strip():
                active_list_frames = None
        mask_as_indented_code = bool(
            container_indented
            and (
                continued_body is not None
                or visible_line.startswith("\t")
                or visible_line.startswith("    ")
            )
        )

        marker = (
            None
            if container_indented
            else re.match(r"^(`{3,}|~{3,})(.*)$", body)
        )
        if marker and marker.group(1).startswith("`") and "`" in marker.group(2):
            marker = None
        raw_opener = (
            None
            if marker or container_indented
            else _raw_text_html_opener(visible_line)
        )
        if marker:
            token = marker.group(1)
            fence = (token[0], len(token), line_frames)
            masked.append("")
        elif mask_as_indented_code:
            masked.append("")
        elif raw_opener:
            tag, opener_start, opener_end = raw_opener
            closing = None
            if tag != "plaintext":
                closing = re.search(
                    rf"</\s*{re.escape(tag)}\s*>",
                    visible_line[opener_end + 1 :],
                    re.IGNORECASE,
                )
            if closing is None:
                raw_html_tag = tag
                masked.append(visible_line[:opener_start])
            else:
                closing_end = opener_end + 1 + closing.end()
                masked.append(
                    visible_line[:opener_start] + visible_line[closing_end:]
                )
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

        designated_fields = (
            *MANIFEST_METADATA_FIELD_NAMES,
            "AI Readiness",
            "No new design decisions required",
            "Validation commands",
            "Blocking ambiguities",
            "Approved by",
            "Approval date",
        )
        fields = {
            field.casefold()
            for field in designated_fields
            if field_values(block, field)
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
    source_lines = text.splitlines()
    reference_spans = {
        span.start: span for span in reference_definition_spans(source_lines)
    }
    lines: list[str] = []
    reference_title_may_follow = False
    reference_title_quote_depth = 0
    index = 0
    while index < len(source_lines):
        if index in reference_spans:
            span = reference_spans[index]
            lines.extend("" for _ in range(span.end - index + 1))
            index = span.end + 1
            reference_title_may_follow = span.title_may_follow
            reference_title_quote_depth = span.quote_depth
            continue
        line = source_lines[index]
        title_body = _reference_continuation_body(
            line, quote_depth=reference_title_quote_depth
        )
        if (
            reference_title_may_follow
            and title_body is not None
            and REFERENCE_TITLE_RE.fullmatch(title_body.strip())
        ):
            lines.append("")
            reference_title_may_follow = False
            reference_title_quote_depth = 0
            index += 1
            continue
        reference_title_may_follow = False
        reference_title_quote_depth = 0
        line = re.sub(r"(`+)(.*?)\1", "", line)
        line = re.sub(r"(?<=\])\((?:\\.|[^)\r\n])*\)", "", line)
        line = re.sub(r"<(?:https?://|mailto:)[^>\r\n]+>", "", line, flags=re.IGNORECASE)
        line = re.sub(r"</?[A-Za-z][^>\r\n]*>", "", line)
        lines.append(line)
        index += 1
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


def normalized_inline_text(value: str) -> str:
    """Normalize rendered inline text for security-sensitive comparisons."""

    value = re.sub(r"!\[([^\]\r\n]*)\]\((?:\\.|[^)\r\n])*\)", r"\1", value)
    value = re.sub(r"!\[([^\]\r\n]*)\]\[[^\]\r\n]*\]", r"\1", value)
    value = re.sub(r"!\[([^\]\r\n]+)\]", r"\1", value)
    value = visible_table_cell(value)
    value = re.sub(r"(?<![!\\])\[([^\[\]\r\n]+)\]", r"\1", value)
    value = re.sub(r"(?<!\\)(?:\*\*|__|~~|[*_])", "", value)
    value = re.sub(r"\\([\\`*{}\[\]()#+\-.!_>])", r"\1", value)
    value = "".join(
        " " if character.isspace() else character
        for character in value
        if character.isspace()
        or unicodedata.category(character)[0] not in {"C", "M"}
    )
    value = normalize_validation_text(unescape(value))
    value = "".join(
        " " if character.isspace() else character
        for character in value
        if character.isspace()
        or unicodedata.category(character)[0] not in {"C", "M"}
    )
    return re.sub(r"\s+", " ", value).strip()


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


def _section_lines_have_content(section_lines: list[str]) -> bool:
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


def has_level_two_section_content_before(
    lines: list[str],
    pattern: str,
    boundary: int | None,
    *,
    content_lines: list[str] | None = None,
) -> bool:
    """Require a populated level-two section before the final acceptance section."""

    scoped_lines = lines[:boundary] if boundary is not None else lines
    scoped_content = content_lines if content_lines is not None else lines
    if boundary is not None:
        scoped_content = scoped_content[:boundary]
    headings = [
        (index, match.group(1))
        for index, line in enumerate(scoped_lines)
        if (match := HEADING_RE.match(line))
    ]
    for position, (start, raw_title) in enumerate(headings):
        title = SECTION_NUMBER_RE.sub("", normalized_inline_text(raw_title)).strip()
        if not re.search(pattern, title, re.IGNORECASE):
            continue
        if NEGATED_HEADING_PREFIX_RE.match(title):
            continue
        # Only a real H2 may satisfy the M/L gate.  Nested H3/H4 headings can
        # describe a subsection, but cannot replace the required top-level
        # boundary chapter.
        end = (
            headings[position + 1][0]
            if position + 1 < len(headings)
            else len(scoped_lines)
        )
        if _section_lines_have_content(scoped_content[start + 1 : end]):
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
        normalized_title = SECTION_NUMBER_RE.sub("", normalized_inline_text(title)).strip()
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
        if _section_lines_have_content(lines[start + 1 : end]):
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
    expected_key = normalized_inline_text(field).casefold()
    values: list[str] = []
    reference_spans = reference_definition_spans(lines)
    reference_lines = {
        index
        for span in reference_spans
        for index in range(span.start, span.end + 1)
    }
    for span in reference_spans:
        if normalized_inline_text(span.label).casefold() == expected_key:
            values.append("")

    for line_index, line in enumerate(lines):
        if line_index in reference_lines:
            continue
        container = REFERENCE_CONTAINER_PREFIX_RE.match(line)
        assert container is not None
        raw_body = line[container.end() :].strip()
        body = unescape(raw_body)
        for separator in re.finditer(r"[:：]", body):
            key = body[: separator.start()]
            if normalized_inline_text(key).casefold() != expected_key:
                continue
            values.append(visible_table_cell(body[separator.end() :]))
            break
    return values


def has_concrete_field(
    lines: list[str], field: str, *, allow_sentinel: bool = True
) -> bool:
    return any(
        bool(value)
        and not table_cell_has_placeholder(value, allow_sentinel=allow_sentinel)
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
    markdown_lines, _, _ = _heading_scan_lines(lines)
    return [
        index
        for index, line in enumerate(markdown_lines)
        if (match := HEADING_RE.match(line))
        and ACCEPTANCE_TITLE_RE.fullmatch(SECTION_NUMBER_RE.sub("", match.group(1)))
    ]


def find_acceptance_section(lines: list[str]) -> tuple[int | None, bool]:
    markdown_lines, _, _ = _heading_scan_lines(lines)
    level_two = [
        (index, match.group(1))
        for index, line in enumerate(markdown_lines)
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
    *,
    heading_lines: list[str] | None = None,
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
            index > acceptance_index
            for index, _ in rendered_section_boundaries(
                visible_lines, scan_lines=heading_lines
            )
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

    acceptance_index, _ = find_acceptance_section(visible_lines)
    if not has_level_two_section_content_before(
        visible_lines,
        r"interface|接口|contract|契约",
        acceptance_index,
        content_lines=semantic_lines,
    ):
        failures.append("M tier requires interfaces and boundaries")
    if not has_level_two_section_content_before(
        visible_lines,
        r"handoff|交接|恢复",
        acceptance_index,
        content_lines=semantic_lines,
    ):
        failures.append("M tier requires Handoff and recovery")

    if tier != "L":
        return

    if not has_level_two_section_content_before(
        visible_lines,
        r"Architecture Constitution|架构宪法",
        acceptance_index,
        content_lines=semantic_lines,
    ):
        failures.append("L tier requires Architecture Constitution")
    if not has_level_two_section_content_before(
        visible_lines,
        r"Boundary Policy|边界策略",
        acceptance_index,
        content_lines=semantic_lines,
    ):
        failures.append("L tier requires Boundary Policy")
    for field in ("Workflow Variant", "Spec Maintenance Mode", "Execution Mode"):
        if not has_concrete_field(field_lines, field):
            failures.append(f"L tier requires {field}")

    if not has_ordered_workflow(text, semantic_lines):
        failures.append(
            "L tier requires complete Proposal -> Requirements -> Design -> Tasks -> Implementation -> Acceptance flow"
        )

    semantic_acceptance_index, _ = find_acceptance_section(semantic_lines)
    milestone_lines = (
        semantic_lines[:semantic_acceptance_index]
        if semantic_acceptance_index is not None
        else semantic_lines
    )
    visible_milestone_lines = (
        visible_lines[:acceptance_index]
        if acceptance_index is not None
        else visible_lines
    )
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
                for line_index, line in enumerate(visible_milestone_lines)
                if (match := HEADING_RE.match(line))
                and (
                    title := SECTION_NUMBER_RE.sub(
                        "", normalized_inline_text(match.group(1))
                    ).strip()
                )
                and not NEGATED_HEADING_PREFIX_RE.match(title)
                and re.search(pattern, title, re.IGNORECASE)
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
        semantic_lines[:semantic_acceptance_index]
        if semantic_acceptance_index is not None
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
    heading_lines = mask_fenced_lines(text, preserve_html_comments=True)
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
    validate_common_structure(
        semantic_text,
        visible_lines,
        tier,
        failures,
        warnings,
        heading_lines=heading_lines,
    )
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
