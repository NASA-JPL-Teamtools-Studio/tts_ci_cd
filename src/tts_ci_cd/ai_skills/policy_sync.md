---
description: Compare repository documentation with central TTS policy identifiers and surface deterministic drift for human review.
disable-model-invocation: true
---

# Policy Synchronization

Use this focused workflow when documentation claims to explain a central TTS standard or policy.

## Steps

1. Read the repository's domain guidance and the central documentation-maintenance standard through `MarkdownResourceCatalog`.
2. Inspect `git status --short`, record every pre-existing changed path, and request confirmation before editing a dirty repository. Report those paths separately from synchronization changes.
3. Read the central standard with `MarkdownResourceCatalog().read_standard()` and extract its `policy_ids` from the final `TTS Metadata` block. Read the target document's `policy_ids` with `tts-ctx metadata <repository> --json-output`.
4. Compare identifiers as exact strings. Report each missing, extra, or duplicated identifier with target path, central/target value, quoted evidence, and one of `missing`, `extra`, or `duplicate`.
5. Apply only mechanical synchronization: formatting, known identifier spelling, or repository-relative path normalization. Never invent a policy identifier or rewrite explanatory prose.
6. Surface disagreements about policy meaning, local authority, safety, or maturity for human resolution. Never silently rewrite those decisions.
7. Show the proposed diff and run the metadata report after an approved edit.

## Done when

- Every policy mismatch is classified as mechanical or human-owned.
- Mechanical changes are proposed with evidence.
- Policy meaning, maturity, and operational authority remain human decisions.
- The final report identifies unresolved drift and next steps.
