---
description: Produce deterministic Markdown documentation evidence and next steps without silently changing content or authority.
disable-model-invocation: true
---

# Documentation Validation

Use this focused workflow when producing deterministic documentation-quality evidence without silently repairing content.

## Steps

1. Read repository guidance, relevant ADRs, and the central documentation-maintenance standard.
2. Inspect `git status --short`, record every pre-existing changed path, and preserve a clear boundary around those changes in the final report.
3. Run the smallest useful report first: `tts-ctx metadata <repository> --json-output`, then use `tts-ctx tree`, `outline`, `section`, `follow`, `doc-search`, or `read` for evidence.
4. Check metadata structure, document paths, headings, local links, external-link reporting, and policy identifiers. Do not fetch the network.
5. Classify each observation as deterministic, human-owned semantic work, or mission/safety-sensitive work. Rank next steps by evidence and impact.
6. Produce a human-readable report and stable JSON evidence. The JSON contract is the shared result shape: `version`, `scope`, `standards_revision`, `metrics`, and `findings`; each finding includes `code`, `path`, `line`, `evidence`, and `remediation` when available. Request confirmation before any repair.

## Done when

- The selected scope and standards revision are recorded.
- Findings have source paths, line or section evidence, stable rule IDs where available, and next steps.
- No document maturity or authority decision was changed by validation.
- The report distinguishes deterministic findings from human review.
