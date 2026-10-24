# Documentation Maintenance

This page defines the conventions that make TTS documentation useful to humans and AI agents. It is the central source for Markdown metadata, documentation maturity, progressive traversal, grooming, and context validation.

Repository-specific documentation may add domain rules, but it must preserve this baseline. Mission safety, operational-authority, and domain guardrails remain authoritative over generic documentation workflows.

## Document metadata

Every Markdown document in an in-scope repository has one visible metadata section at the bottom of the file:

````markdown
## TTS Metadata

```yaml
tts:
  kind: standard
  maturity: baseline
  summary: "The one-sentence purpose of this document."
  audience:
    - agent
    - human
  related:
    - docs/collaboration/testing.md
  policy_ids:
    - documentation.metadata
```
````

The metadata section appears exactly once, is the final substantive section, uses exactly one fenced `yaml` block, remains visible, uses repository-relative paths for local references, and must not be confused with YAML examples elsewhere in the document.

The initial universal fields are:

| Field | Requirement | Meaning |
| --- | --- | --- |
| `kind` | Required | What role the document plays in the documentation corpus. |
| `maturity` | Required | How complete and operationally trusted the document is. |
| `summary` | Required | A concise description of the document's purpose. |
| `audience` | Optional initially | The readers or agents the document serves. |
| `related` | Optional initially | Repository-relative neighboring documents. |
| `policy_ids` | Optional initially | Stable standards or policy rules explained by the document. |

## Document kinds

The initial `kind` vocabulary is:

- `standard` — a normative convention or policy;
- `guide` — procedural or explanatory instruction;
- `reference` — factual material consulted while working;
- `repository` — documentation about a repository or library;
- `glossary` — definitions and terminology;
- `roadmap` — planned or proposed future work; and
- `incidental` — material in scope for inventory but not intended to define a standard.

## Documentation maturity

`maturity` is a human-owned lifecycle value. Tooling validates the value and reports contradictions, but never changes it or automatically promotes or demotes a document.

| Maturity | Meaning |
| --- | --- |
| `draft` | Exploratory, incomplete, or scaffolding; not authoritative. |
| `preliminary` | Coherent but under active work. |
| `baseline` | Close to complete, but active changes may remain. |
| `released` | Operationally trusted and highly stable. |
| `retired` | No longer in use and retained for historical purposes. |

Existing warnings such as `Draft — SME review needed` remain until a human changes them. Tooling reports disagreement between warnings and declared maturity rather than deleting or rewriting either one.

## Traversal and context

Documentation tools should support the same progressive reading path a person would use:

1. inspect the document tree;
2. inspect a page outline;
3. choose a heading or section;
4. follow relevant local links; and
5. read the complete document when required.

The traversal vocabulary is `tree`, `outline`, `section`, `follow`, `search`, and `read`. Outline depth maps directly to Markdown heading levels: depth 1 includes `#`, depth 2 includes `#` and `##`, and depth 3 includes `#`, `##`, and `###`.

Traversal follows relative local Markdown links and reports external links without fetching them. Network access must not be required for deterministic documentation analysis. Results preserve source paths, headings, sections, and anchors where applicable.

## Standards and policy identifiers

A document may use `policy_ids` to identify stable standards or policy rules it explains. Policy identifiers should be stable, specific, and reusable across reports.

## Grooming responsibilities

Centralized documentation-grooming skills own generic metadata, traversal, link, policy-synchronization, and validation mechanics. They may repair deterministic formatting and schema errors, normalize known enum values and repository-relative paths, and report missing metadata, broken links, and policy drift.

They must not change maturity, certify operational authority, erase mission-specific warnings, override safety or operational-authority guardrails, or fetch external links during deterministic analysis.

## Tooling and CI expectations

The documentation-maintenance contract is designed for library and CLI use. Tooling should produce human-readable Markdown plus versioned machine-readable results. Report mode explains findings without treating every below-target metric as a failure; an explicit strict mode may apply documented thresholds for CI.

The existing MkDocs setup remains the publication path. Metadata is visible fenced Markdown, not front matter, so this convention does not require a front-matter plugin or a change to existing navigation and theme.

## TTS Metadata

```yaml
tts:
  kind: standard
  maturity: baseline
  summary: "Standards for maintaining TTS Markdown documentation for humans and AI agents."
  audience:
    - agent
    - human
    - reviewer
  related:
    - docs/collaboration/documentation.md
    - docs/collaboration/testing.md
    - docs/collaboration/ci_cd_policy.md
  policy_ids:
    - documentation.metadata
    - documentation.maturity
    - documentation.traversal
    - documentation.context_validation
```
