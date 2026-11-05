---
description: Run deterministic tts-ctx documentation-quality checks, separate extracted facts from inference, and identify candidate follow-up tickets for additional rules.
disable-model-invocation: true
---

# tts-ctx Quality

Use this focused workflow when a developer wants a deterministic standards check of a repository's documentation and code-quality evidence.

## Steps

1. Read the repository's `AGENTS.md`, `CONTEXT.md`, relevant ADRs, and the central documentation-maintenance standard.
2. Read the workspace `.venvs.yaml` or `~/.tts_venvs.yaml` and use its `default` interpreter. If the manifest is missing or ambiguous, ask the developer before running `tts-*` commands.
3. Run `git status --short` in the target repository. Record every pre-existing changed path before interpreting the report.
4. Run `tts-ctx kinds --json-output` to load the canonical document-kind definitions.
5. Run `tts-ctx standards --json-output`, `tts-ctx quality <repository> --json-output`, `tts-ctx coverage <repository> --json-output`, and `tts-ctx test-quality <repository> --json-output`. Use `tts-ctx next <repository> --json-output` for ranked work, `tts-ctx metadata <repository> --json-output` for metadata-only evidence, and traversal commands for source context. Treat `tts-ctx check --strict` as an explicit threshold gate, not as the default report.
6. Separate findings into two spaces:
   - **Deterministic space**: facts the tool can verify mechanically, such as metadata shape and enum values, local link resolution, parse errors, public API docstring presence, test-file inventory, test markers, coverage-artifact state, and released-document evidence fields.
   - **Inference space**: judgments the tool cannot establish from syntax and paths alone, such as whether a kind or summary is semantically right, whether prose is true, whether a maturity value is deserved, whether a procedure is safe or complete, or whether a mission authority boundary is respected.
7. Report each finding with its stable rule ID, source path, line, evidence, remediation, and space classification. Treat deterministic findings as candidate mechanical work; hand inference-space findings to the human owner.
8. For repeated inference-space gaps that the team wants checked mechanically, propose a follow-up ticket for an agent to extract that rule into deterministic space. Each proposed ticket should state the source evidence, the desired executable check, and the human decision that remains outside automation. Do not create tickets unless the developer explicitly asks.
9. Show the report and distinguish pre-existing changes from any generated artifacts. Do not modify documentation, maturity, authority, or mission guardrails during this workflow.

## Done when

- The selected repository, standards revision, and interpreter are recorded.
- `tts-ctx quality` evidence is available in stable JSON and human-readable form when requested.
- Every finding is classified as deterministic or inference-space with source evidence.
- Candidate extraction tickets are listed for worthwhile recurring inference gaps.
- The developer is explicitly told to consider writing tickets if they want an agent to extract additional rules into deterministic checks.
- No files or semantic decisions were changed by the quality check.
