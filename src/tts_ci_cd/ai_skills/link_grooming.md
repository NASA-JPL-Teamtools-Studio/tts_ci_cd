---
description: Review or repair Markdown links deterministically without fetching external targets or changing mission-specific prose.
disable-model-invocation: true
---

# Link Grooming

Use this focused workflow when reviewing or repairing Markdown links.

## Steps

1. Read repository guidance, relevant ADRs, and the central documentation-maintenance standard.
2. Inspect `git status --short`; obtain explicit confirmation before editing a dirty repository and record pre-existing changes.
3. Use the Python `MarkdownTraversal` interface or `tts-ctx tree`, `tts-ctx follow`, and `tts-ctx doc-search` to inventory local links and source locations.
4. Resolve relative local links deterministically from the repository resource root. Report external links without fetching them.
5. Normalize only mechanical path or formatting errors. Do not rewrite prose, infer missing operational authority, or remove mission-specific warnings.
6. Show the proposed diff and rerun the relevant traversal command after confirmation.

## Done when

- Local links have deterministic evidence or an explicit remediation.
- External links are listed without network access.
- Pre-existing changes remain distinguishable from grooming edits.
- Safety and domain guardrails were preserved.
