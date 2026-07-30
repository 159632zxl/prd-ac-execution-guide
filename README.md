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
| ------ | --------- |
| `SKILL.md` | The full methodology — the guide an agent reads to write a PRD |
| `references/prd_template.md` | The L-tier full template; trim it for S/M documents |
| `references/example_prd_filled.md` | A complete M-tier personal-ledger CLI example |
| `scripts/check_prd_ac.py` | Lightweight structural checker for a drafted PRD |
| `agents/openai.yaml` | Agent interface descriptor (display name, default prompt) |

## Key Concepts

- **Document Tiers** — select by risk, ambiguity, external side effects, and recovery cost: `S` keeps the minimum executable goal/tasks/AC loop, `M` adds readiness/approval/interfaces/handoff, and `L` uses the full architecture/milestone/report flow.
- **AI Readiness Gate** — a PRD is `not-ready` if the agent must invent architecture, pick a truth source, guess file locations, define tests, or decide safety boundaries. No implementation until it's `ready`.
- **Acceptance Criteria (AC)** — stable IDs (`G-01`, `P0-01`, `M2-EG-01`), each row carries requirement + verification method + severity (`FAIL`/`WARN`). Any `FAIL` blocks the next milestone.
- **Global Forbidden Items (`G-*`)** — irreversible or architecture-breaking mistakes, checked every phase.
- **EARS requirements** — `WHEN <condition>, THE SYSTEM SHALL <behavior>` — every EARS line maps to at least one AC row.
- **Milestone pattern** — prefer `P0 + M1..Mn` over many tiny phases; each milestone has a `DONE` gate.
- After an optional section number,
  milestone headings must start with `P0` or `M<n>`.
- **Execution Mode** — `step | batch | phase`, declared up front so the agent knows where to stop and check.
- **Handoff / Recovery** — a resume block so an interrupted task can be picked up without re-reading history.

## Usage

### As a Claude Code skill

Clone into your personal skills directory:

```bash
git clone https://github.com/159632zxl/prd-ac-execution-guide ~/.claude/skills/prd-ac-execution-guide
```

Open a new Claude Code session — it auto-loads. The skill triggers when you're **creating or rewriting PRDs, implementation guides, refactor guides, handoff specs, or agent-executable plans**. You can also invoke it directly with `/prd-ac-execution-guide`.

### As a Codex skill

Clone into your personal Codex skills directory.

On macOS or Linux:

```bash
mkdir -p ~/.agents/skills
git clone https://github.com/159632zxl/prd-ac-execution-guide ~/.agents/skills/prd-ac-execution-guide
```

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\.agents\skills" | Out-Null
git clone https://github.com/159632zxl/prd-ac-execution-guide "$HOME\.agents\skills\prd-ac-execution-guide"
```

Codex detects newly installed skills automatically. If the skill does not
appear, restart Codex. It can trigger automatically for matching PRD and
execution-guide tasks; in the Codex CLI or IDE extension, run `/skills` to
browse installed skills or type `$prd-ac-execution-guide` to invoke it
explicitly.

### Standalone

1. Select `S`, `M`, or `L` using the Document Tiers rules in `SKILL.md`.
2. Use `references/prd_template.md` for the L-tier full shape; trim it for S/M, and consult `references/example_prd_filled.md` for a completed M-tier document.
3. Validate the filled draft:

```bash
python scripts/check_prd_ac.py path/to/your-prd.md
```

The blank L-tier template is expected to fail because its AC requirements and
verification methods still contain placeholders. Fill the draft before using
the checker as an approval gate.

The checker applies tier-specific structural gates, validates AC IDs/categories/severity and every verification method, rejects dangling Task → AC references and missing milestone `DONE` gates, detects malformed or duplicate `G-*` IDs, and warns about intentional G-ID gaps or excessive placeholder residue. The final heading may use `验收标准总览`, its bilingual form, or the English equivalent `Acceptance Criteria`, with an optional section number and full-width or ASCII parentheses. It prints `PASS` or `FAIL` with specific findings and does not require legacy Chinese phrases.

The checker validates structural completeness, cross-reference integrity, and
gate relationships. It does not replace human review of AC semantics,
business correctness, or risk decisions.

### Canonical G-ID migration

**Breaking change:** tiered documents now reserve `G-01` through `G-08` for the
canonical cross-document rules in `SKILL.md`. A document that declares
`Document Tier` but defines only part of that range, or reuses those IDs for
project rules, now fails validation. Restore all eight canonical rows, renumber
project-specific rules from `G-09`, update every Task -> AC reference, and run
the checker again. Historical documents without `Document Tier` retain the
backward-compatible base checks.

## Document Shape (at a glance)

```text
Revision note → Directory → AI executor statement → Spec authority
→ AI readiness → Overview (goal / non-goals / boundaries)
→ Evidence files → Target structure & interfaces → Approval status
→ P0 + Milestones (M1..Mn) → Handoff/recovery → Appendix
→ final chapter: 验收标准总览 (Acceptance Criteria)  ← the only validation authority
  §AC.0 → §AC.P0 → §AC.M1 ...
```

## License

Personal skill, shared as-is. Use and adapt freely.
