# Agent Skills — tts_ci_cd

This document tells AI agents how to find skills, documentation, and configuration when working in the `tts_ci_cd` repository.

## TTS-wide documentation

Before making decisions that touch broader TTS conventions (testing policy, coding standards, naming, philosophy), read the `teamtools_documentation` repo at `tts_core/teamtools_documentation/` in the workspace. Key files:

- `CONTEXT.md` — canonical TTS-wide coding standards, glossary, and agent rules
- `docs/collaboration/testing.md` — `@pytest.mark.inspection` and `@pytest.mark.unreviewed_ai` rules
- `docs/collaboration/ci_cd_policy.md` — CI/CD policy baseline
- `docs/philosophy.md` — design principles that govern all TTS decisions

## Domain vocabulary

Read `CONTEXT.md` at the repo root before making design or naming decisions. It defines the canonical terms for this repo (workspace, group, hygiene violation, AI skill, venv manifest, etc.).

## AI skills

Skills are portable Markdown playbooks that agents can execute. They live at:

```
src/tts_ci_cd/ai_skills/
```

Available skills:

| Skill file | When to use |
|------------|-------------|
| `git_hygiene.md` | Developer wants to review and clean up WIP across multiple repos — finding homeless WIP, branch mismatches, unpushed commits, or semantically incoherent branches. |

To use a skill: read the `.md` file and follow its steps. Skills are self-contained; each one tells you what CLI tools to call, what to do with the output, and what safeguards to apply.

## Python interpreter / venv

Before running any `tts-*` CLI command or Python module in this repo:

1. Check for `.venvs.yaml` in the **workspace root** (the directory containing the `<group>/<repo>` tree).
2. If not found, check `~/.tts_venvs.yaml`.
3. Use the `default` key unless the developer has told you to use a specific environment.
4. **If neither file exists or the right interpreter is ambiguous, ask the developer.** Do not assume the system Python, a mission venv (e.g., `nisar_dev`), or any other interpreter is correct.

A template for the venv manifest is at:
```
src/tts_ci_cd/support_files/.venvs.yaml.example
```

## Architecture decisions

ADRs for this repo live at `docs/adr/`. Read relevant ADRs before proposing structural changes.

| ADR | Topic |
|-----|-------|
| `001-ai-skill-infrastructure.md` | Why skills are package-level `.md` files rather than a registry |

## Branch naming convention

All feature branches must follow the format `<username>/<feature_-_name>` (e.g., `mrmuszynski/jpl_time`). When creating or renaming branches, always use this format. Ask the developer to confirm their GitHub username if you are not certain.

## Workspace layout convention

TTS workspaces follow a two-level layout: `<workspace>/<group>/<repo>`. Group names match the top-level keys in `dev_setup.yaml`. This layout is enforced by `tts-dev-setup` and assumed by `tts-git-hygiene`. Groups may be **core library groups** (e.g., `tts_core/`) or **mission adaptation groups** (e.g., `fss/`, `nisar/`, `demosat/`) — the distinction matters for understanding repo purpose but not for workspace tooling.

Example:
```
dev/              ← workspace root
  tts_core/       ← group
    tts_data_utils/
    tts_dexter/
    tts_dante/
  fss/            ← group
    fss_dante/
    fss_query/
  nisar/          ← group
    nisar_data_utils/
```
