#!/usr/bin/env python3
"""Lightweight structural checker for PRD AC execution guides."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_PHRASES = [
    "AI 执行器强制阅读声明",
    "唯一验收依据",
    "实现真源",
    "验收标准总览",
    "Acceptance Criteria",
    "全局禁止项",
    "PASS/FAIL/WARN",
]

RECOMMENDED_PHRASES = [
    "Spec status",
    "Implementation allowed",
    "AI Readiness",
    "No new design decisions required",
    "Architecture Constitution",
    "Workflow Variant",
    "Spec Maintenance Mode",
    "Boundary Policy",
    "Always",
    "Ask First",
    "Never",
    "未批准",
    "Execution Mode",
    "EARS",
    "THE SYSTEM SHALL",
    "handoff",
    "可恢复入口",
    "Task",
    "Implements AC",
    "Execution Attitude",
    "不得猜测接口",
    "不得臆想业务",
    "Human confirmation",
    "Reuse existing interfaces",
    "Validation evidence",
    "scope expansion",
    "High-risk confirmation",
    "honest blocking",
    "cautious refactor",
    "Change Packet",
    "Stage Packet",
    "Context Provider",
    "Code Network",
    "Ghost Interface",
    "Orphan Node",
    "pre-change",
    "post-change",
    "contract closure",
    "Observed Graph",
    "Target Graph",
    "Change Graph",
    "graph-snapshot.json",
    "graph-diff.json",
    "Source Coverage",
    "Reader/Writer",
    "reader visibility",
    "Runtime Visibility",
    "State reachability",
    "intentionally empty",
    "schema enum",
    "independent evidence",
    "Code Map Only Workflow",
    "Map Completeness Gate",
    "code-map-only",
    "observed-only",
    "Implementation allowed: no",
    "No source modifications",
    "dependency graph",
    "task graph",
    "不得强制完整阅读",
    "Audit Hardening",
    "NULL semantics",
    "PRAGMA foreign_key_check",
    "strategy parameters",
    "degraded-with-warning",
    "data-corrupted",
    "premise verification",
    "audit coverage",
    "owner task",
]

AC_CATEGORIES = [
    "happy",
    "edge",
    "error",
    "non-functional",
    "data-integrity",
    "safety",
]

AC_PATTERNS = [
    r"\bG-\d{2}\b",
    r"\bP0-DONE\b",
    r"\bM\d+-DONE(?:-\d+)?\b",
]


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_prd_ac.py <markdown-file>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    failures: list[str] = []
    warnings: list[str] = []

    for phrase in REQUIRED_PHRASES:
        if phrase not in text:
            failures.append(f"Missing required phrase: {phrase}")

    for phrase in RECOMMENDED_PHRASES:
        if phrase not in text:
            warnings.append(f"Missing recommended phrase: {phrase}")

    for pattern in AC_PATTERNS:
        if not re.search(pattern, text):
            failures.append(f"Missing AC pattern: {pattern}")

    if not re.search(r"\|\s*AC\s*\|", text):
        failures.append("Missing AC table header")

    if not re.search(r"\|\s*类别\s*\|", text) and not re.search(r"\|\s*Category\s*\|", text, re.I):
        warnings.append("No AC category column found")

    found_categories = [name for name in AC_CATEGORIES if name in text]
    if len(found_categories) < 2:
        warnings.append("Few or no AC categories found: expected happy/edge/error/non-functional/data-integrity/safety as applicable")

    if "FAIL" not in text:
        failures.append("No FAIL severity found")

    if "WARN" not in text:
        warnings.append("No WARN severity found")

    if "实现前先输出" not in text and "implementation plan" not in text.lower():
        warnings.append("No explicit pre-implementation plan requirement found")

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
