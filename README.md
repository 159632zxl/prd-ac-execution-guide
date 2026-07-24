# PRD AC Execution Guide

> A skill for writing **spec-driven PRDs** that AI agents can execute — with numbered Acceptance Criteria, phase gates, global forbidden items, and Codex/Claude-ready validation rules.

Turn vague "make it work" briefs into documents where **completion is decided by explicit gates, not by "looks reasonable."**

> **How this was built** — Synthesized by having Codex survey prior art across GitHub (implementation-guide / spec-driven / agent-handoff patterns), then filtered and hardened against real hands-on usage. Not theory: the forbidden items and common-mistakes tables come from patterns that actually broke.

---

## The Problem

When you hand a task to a coding agent (Codex, Claude, etc.), things go wrong in predictable ways:

- The agent invents architecture you never agreed to.
- "Done" means "it ran once," not "it passed a check."
- Acceptance criteria are buried in prose, so nothing actually gates completion.
- A long task drifts: the implementation plan quietly becomes its own source of truth.
- When work is interrupted, the next agent re-guesses everything.

This skill encodes a fix: **the PRD + numbered Acceptance Criteria (AC) is the single source of truth.** Narrative chapters explain; AC gates decide.

## Core Principle

```text
Spec is the source of truth.
Implementation, tests, reports, and handoffs must reference PRD/AC IDs.
If implementation conflicts with PRD/AC, revise the PRD or get approval before coding.
```

## What's Inside

| Path | Purpose |
|------|---------|
| `SKILL.md` | The full methodology — the guide an agent reads to write a PRD |
| `references/prd_template.md` | A ready-to-fill PRD skeleton (目录 → AC 总览) |
| `scripts/check_prd_ac.py` | Lightweight structural checker for a drafted PRD |
| `agents/openai.yaml` | Agent interface descriptor (display name, default prompt) |

## Key Concepts

- **AI Readiness Gate** — a PRD is `not-ready` if the agent must invent architecture, pick a truth source, guess file locations, define tests, or decide safety boundaries. No implementation until it's `ready`.
- **Acceptance Criteria (AC)** — stable IDs (`G-01`, `P0-01`, `M2-EG-01`), each row carries requirement + verification method + severity (`FAIL`/`WARN`). Any `FAIL` blocks the next milestone.
- **Global Forbidden Items (`G-*`)** — irreversible or architecture-breaking mistakes, checked every phase.
- **EARS requirements** — `WHEN <condition>, THE SYSTEM SHALL <behavior>` — every EARS line maps to at least one AC row.
- **Milestone pattern** — prefer `P0 + M1..Mn` over many tiny phases; each milestone has a `DONE` gate.
- **Execution Mode** — `step | batch | phase`, declared up front so the agent knows where to stop and check.
- **Handoff / Recovery** — a resume block so an interrupted task can be picked up without re-reading history.

## Usage

### As a Claude Code skill

Clone into your personal skills directory:

```bash
git clone https://github.com/159632zxl/prd-ac-execution-guide ~/.claude/skills/prd-ac-execution-guide
```

Open a new Claude Code session — it auto-loads. The skill triggers when you're **creating or rewriting PRDs, implementation guides, refactor guides, handoff specs, or agent-executable plans**. You can also invoke it directly with `/prd-ac-execution-guide`.

### Standalone

1. Copy `references/prd_template.md` as the starting point for a new PRD.
2. Fill it in following `SKILL.md` (readiness gate → milestones → AC总览).
3. Validate the draft:

```bash
python scripts/check_prd_ac.py path/to/your-prd.md
```

The checker verifies the mandatory pieces are present: the AI-executor reading statement, the AC总览 chapter, global forbidden items, `FAIL`/`WARN` severities, AC ID patterns, and the AC table header. It prints `PASS` or `FAIL` with the specific gaps — a fast structural gut-check before you hand the PRD to an agent.

## Document Shape (at a glance)

```text
Revision note → Directory → AI executor statement → Spec authority
→ AI readiness → Overview (goal / non-goals / boundaries)
→ Evidence files → Target structure & interfaces → Approval status
→ P0 + Milestones (M1..Mn) → Handoff/recovery → Appendix
→ 12. 验收标准总览 (Acceptance Criteria)  ← the only validation authority
```

## License

Personal skill, shared as-is. Use and adapt freely.
