# Domain Docs

How engineering skills should consume this repository's domain documentation.

## Layout

This is a single-context repository:

- `CONTEXT.md` at the repository root for repository domain vocabulary
- `docs/adr/` for architecture decision records
- `src/` for implementation

There is currently no separate root `GLOSSARY.md`; use `CONTEXT.md` as the canonical repository vocabulary source.

## Before exploring

- Read `CONTEXT.md` when it exists and is relevant to the work.
- Read ADRs under `docs/adr/` that touch the area being changed.
- Use glossary vocabulary in issue titles, proposals, test names, and other outputs.
- If a needed term is not defined, consider whether it indicates a vocabulary gap rather than inventing a synonym.
- If an output conflicts with an ADR, call out the conflict explicitly.
