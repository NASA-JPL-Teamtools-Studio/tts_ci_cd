# ADR 001: AI Skill Infrastructure — Minimal Package-Level Skills Over a Registry

**Status:** Accepted  
**Date:** 2026-08-08

---

## Context

`tts_ci_cd` ships CLI tools that benefit from AI augmentation, starting with `tts-git-hygiene`. That tool has two modes: a deterministic report mode (pure Python, no AI) and an interactive AI mode that reasons over git state to guide the developer through hygiene violations and deconfliction.

The AI mode needs a *playbook* — a structured document that tells an agent what to do, in what order, with what safeguards. That playbook must be:

1. **Portable** — usable from Windsurf, Cursor, Claude, or any other AI toolset without rewriting
2. **Versioned with the package** — so teams on an older version of `tts_ci_cd` get the skill that matches that version's CLI behavior
3. **Discoverable by agents** — agents working in a TTS workspace should find the skill without the developer explicitly pointing to it

Two structural approaches were considered:

### Option A: Minimal — package-level `.md` files + `AGENTS.md`

Ship skill playbooks as Markdown files inside the installed package at `src/tts_ci_cd/ai_skills/`. Add an `AGENTS.md` at the repo root instructing agents to look there. Optionally add a `tts-install-skills` CLI command to copy skills into the user's global AI tool directory.

**Pros:** Zero infrastructure, works with any AI toolset, versioned naturally with the package.  
**Cons:** No discovery mechanism beyond AGENTS.md; agents must be told where to look; no cross-repo registry.

### Option B: Skill registry — `tts_skills` subpackage or standalone repo

Build a registry (manifest + install mechanism) that catalogs TTS skills by name, version, and compatible CLI range. Skills are installed centrally and discoverable by any agent working in any TTS workspace.

**Pros:** True discoverability; clean separation of skill lifecycle from tool lifecycle.  
**Cons:** Significant infrastructure investment; the feature is experimental and the skill catalog is small (one skill at time of writing); risk of over-engineering before the skill format stabilizes.

---

## Decision

Use **Option A** for this iteration.

Skills live at `src/tts_ci_cd/ai_skills/<skill_name>.md`. Each skill follows the Matt Pocock format (YAML frontmatter `description:` + structured Markdown body) so it can be loaded natively by Windsurf and adapted for other toolsets. An `AGENTS.md` at the repo root tells agents where to look. A `tts-install-skills` CLI command (to be added as a small follow-on) copies skills to the user's global AI tool directory for use outside the `tts_ci_cd` working directory.

We declined Option B **not because a registry is a bad idea**, but because the skill catalog is a single entry, the format is experimental, and the investment is premature. A registry is the correct long-term direction.

> **Future consideration (open ticket):** Once `tts_ci_cd` accumulates 3–5 skills and the format has stabilized in practice, revisit whether a `tts_skills` registry — or a standalone `tts_ai_skills` repo — makes sense. The registry question should not be reopened until the skill format has been validated across at least two different AI toolsets.

---

## Consequences

- Skill files are co-versioned with the CLI tools they drive. A breaking CLI change and its corresponding skill update ship in the same release. This is a feature.
- Agents working in a TTS workspace will find skills via `AGENTS.md`. Agents working outside this repo (e.g., in a mission-specific workspace) will need `tts-install-skills` to have run, or a reference in that workspace's `AGENTS.md`.
- The `ai_skills/` directory inside the package becomes the canonical location for all future TTS AI playbooks, not just `git_hygiene`. Maintain one skill per concern; do not consolidate unrelated playbooks into a single file.
