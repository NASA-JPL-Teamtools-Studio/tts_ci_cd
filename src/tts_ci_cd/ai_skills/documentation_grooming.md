---
description: Route documentation-grooming work to the metadata, links, policy synchronization, or validation workflow; use when improving TTS Markdown documentation while preserving human-owned maturity and mission guardrails.
---

# Documentation Grooming

Use this router when a developer asks to improve, validate, synchronize, or navigate repository documentation.

## Route

Choose one focused workflow and read it before acting:

- `metadata_grooming.md` — visible `TTS Metadata`, schema shape, enum spelling, and repository-relative path normalization.
- `link_grooming.md` — local link discovery, deterministic resolution, and external-link reporting.
- `policy_sync.md` — compare policy identifiers and explanatory Markdown with the central standard.
- `documentation_validation.md` — run deterministic validation and assemble evidence for human review.

If the request spans branches, run them one at a time and preserve each branch's evidence.

## Shared guardrails

1. Inspect the repository status before reading or editing documentation. A dirty repository requires explicit confirmation before modification; record which changes predate grooming.
2. Central generic documentation rules override conflicting generic local rules. Preserve repository and mission safety, operational-authority, maturity-warning, and domain guardrails; those remain authoritative.
3. Make mechanical repairs only when the intended result is deterministic. Surface semantic classifications and policy disagreements for human review.
4. Keep maturity values exactly as declared by humans. Never promote, demote, or certify operational authority.
5. Do not fetch external links during deterministic work.
6. Show the proposed diff and validation evidence before completing any modification.

## Done when

- The selected focused workflow was followed.
- Pre-existing changes and generated changes are distinguishable.
- Every repair is deterministic or explicitly handed to a human.
- The relevant `tts-ctx` report was run and its findings were recorded.
- No maturity or mission guardrail was changed silently.
