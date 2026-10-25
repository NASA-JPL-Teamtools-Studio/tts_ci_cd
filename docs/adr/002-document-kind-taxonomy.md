# ADR 002: Explicit Document-Kind Taxonomy

**Status:** Accepted  
**Date:** 2026-08-11

---

## Context

TTS Markdown metadata uses `kind` to identify the primary job a document performs in a documentation corpus. The original vocabulary used `guide` for several different concepts: human-facing procedures, agent-executable playbooks, and sometimes repository orientation. It also classified ADRs as `standard`, even though an ADR records a decision rather than defining the resulting norm.

Agents need a precise, discoverable vocabulary so that metadata classification is consistent across repositories and can be reviewed without relying on directory names or audience labels.

## Decision

Use the following canonical document kinds:

| Kind | Meaning |
| --- | --- |
| `standard` | Defines rules, constraints, policies, or required conventions. |
| `procedure` | Explains how a human performs a task or follows a workflow. |
| `agent_skill` | Provides an agent-executable playbook with invocation metadata, steps, guardrails, and completion criteria. |
| `reference` | Provides factual or lookup-oriented information without primarily prescribing behavior. |
| `training` | Builds knowledge or skill through structured learning material, exercises, or assessment. |
| `repository` | Orients readers to a repository's purpose, layout, audience, workflow, and entry points. |
| `glossary` | Defines domain terms and distinguishes overloaded or commonly confused meanings. |
| `roadmap` | Describes intended future work, sequencing, priorities, or planned capabilities. |
| `decision_record` | Records an architectural or governance decision, including context, alternatives, consequences, and status. |
| `incidental` | Is in scope for inventory but is not intended to be maintained as a documentation artifact. |

Classification uses the document's primary job. Audience and filesystem location do not determine `kind`. ADRs use `decision_record`, including superseded and retired ADRs. Structured playbooks intended for an agent to execute use `agent_skill`; human-facing instructions use `procedure`; structured learning material, exercises, and assessments use `training`. Use `reference` for lookup-oriented facts that do not require a learning progression.

The canonical definitions are encoded in `tts_ci_cd.ctx.metadata.DOCUMENT_KINDS` and exposed through `tts-ctx kinds` for both human-readable and JSON output.

## Consequences

- Metadata validation rejects ambiguous legacy values such as `guide`.
- Agents can query the definitions with `tts-ctx kinds --json-output` rather than copying an undocumented enum.
- Repository orientation, human procedures, agent skills, and decision records can be distinguished without inferring meaning from paths.
- Existing documents require deliberate classification during metadata grooming; tooling must not infer or change semantic kinds automatically.

## TTS Metadata

```yaml
tts:
  kind: decision_record
  maturity: baseline
  summary: "Canonical document-kind taxonomy for TTS Markdown metadata."
  audience:
    - agent
    - human
    - reviewer
  related:
    - ../../src/tts_ci_cd/ctx/resources/standards/documentation_maintenance.md
  policy_ids:
    - documentation.metadata
```
