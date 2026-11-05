---
description: Repair or review visible TTS Metadata sections while preserving human-owned maturity and mission guardrails.
disable-model-invocation: true
---

# Metadata Grooming

Use this focused workflow when repairing or reviewing visible `## TTS Metadata` sections.

## Steps

1. Read the repository's `AGENTS.md`, `CONTEXT.md`, relevant ADRs, and central documentation-maintenance standard.
2. Run `git status --short`. If the repository is dirty, record the pre-existing paths and ask for explicit confirmation before editing.
3. Run `tts-ctx metadata <repository> --json-output` with the workspace default interpreter. If the venv manifest is missing or ambiguous, ask the developer before running `tts-*` commands.
4. Separate mechanical findings from semantic decisions. Mechanical work may repair a missing fence shape, YAML formatting, known enum spelling, or repository-relative path normalization. Use `tts-ctx kinds` to look up kind definitions. Ask a human about document kind, policy meaning, or any disagreement with local guardrails.
5. Propose the exact patch. Do not change `maturity`, remove warnings, or certify operational authority.
6. After confirmation, apply only the approved deterministic edits.
7. Re-run `tts-ctx metadata <repository> --json-output` and show the diff, including any findings left for human review.

## Done when

- Every metadata finding is either deterministically repaired or explained as a human decision.
- Declared maturity is unchanged.
- The final report and `git diff` are available for review.
