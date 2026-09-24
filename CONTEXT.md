# tts_ci_cd

`tts_ci_cd` is the CI/CD and developer-tooling layer of Teamtools Studio. It ships command-line tools, Sphinx build automation, packaging helpers, and AI skill playbooks that standardize how TTS libraries are built, tested, deployed, and maintained across a multi-repo workspace.

## Language

**Workspace**:
A developer's root directory organized as a two-level tree: `<workspace>/<group>/<repo>`. The workspace root is not itself a git repository; it is the container for all the developer's checked-out repos. The canonical TTS workspace is cloned and installed by `tts-dev-setup`.
_Avoid_: "monorepo," "project root," "dev folder"

**Group**:
A top-level subdirectory inside the workspace that organizes related repos (e.g., `tts_core/`, `fss/`, `nisar/`, `demosat/`). Group names match the top-level keys in `dev_setup.yaml`. A group is a filesystem convention, not a Python namespace. Groups fall into two kinds: **core groups** (e.g., `tts_core/`) containing shared TTS infrastructure libraries, and **mission groups** (e.g., `fss/`, `nisar/`) containing mission-specific adaptation layers. The tooling treats all groups identically; the distinction is architectural.
_Avoid_: "namespace," "module group," "category," "layer" (use "core group" or "mission group" when the distinction matters)

**Hygiene violation**:
A detected git state in one or more repos that signals incomplete, unreviewed, or intertwined work. The set of violations checked by `tts-git-hygiene`. The word "violation" implies the state is actionable — it should be resolved, not ignored.
_Avoid_: "issue," "problem," "warning," "finding"

**Homeless WIP**:
A hygiene violation: uncommitted changes (staged, modified, or untracked files) on a default branch (`main` or `develop`). Indicates that feature work was done without creating a feature branch. The highest-priority violation because it mixes potentially unrelated changes on the branch that all other developers share.
_Avoid_: "uncommitted main changes," "dirty main"

**Feature branch**:
Any branch that is not a default branch (`main`, `develop`). A feature branch signals that the work on it belongs to a coherent, named unit of work. Branch name is the canonical identifier of a feature across repos. **All feature branches must follow the naming convention `<github_username>/<feature_name>`** (e.g., `mrmuszynski/jpl-time`). Branches that do not follow this convention are flagged as hygiene violations.
_Avoid_: "topic branch," "dev branch," "non-main branch"

**Branch parity**:
The state in which all repos that participate in the same feature are checked out on branches with the same name. Branch parity is the target state after running `tts-git-hygiene --interactive` on a set of repos with related uncommitted work.
_Avoid_: "synchronized branches," "consistent branches," "aligned branches"

**Semantic cohesion**:
The degree to which all the changes on a branch — committed and uncommitted — logically belong to the same feature or purpose. A branch has low semantic cohesion if, for example, it contains both a jpl_time integration and an unrelated CSV bugfix. `tts-git-hygiene` AI mode checks for low semantic cohesion and prompts the user to consider splitting the branch.
_Avoid_: "branch cleanliness," "change coherence," "single-purpose"

**AI skill**:
A portable Markdown playbook shipped inside the `tts_ci_cd` package at `src/tts_ci_cd/ai_skills/`. AI skills follow the Matt Pocock skill format (YAML frontmatter + structured Markdown instructions) so they can be loaded by any AI toolset (Windsurf, Cursor, Claude, etc.) without toolset-specific plugins. Skills are installed to the user's global AI tool directory by `tts-install-skills`.
_Avoid_: "AI plugin," "agent script," "LLM prompt," "Windsurf skill" (too toolset-specific)

**Venv manifest**:
A developer-local YAML file (`.venvs.yaml`) that maps project names to Python interpreter paths. Not committed to any repository after initial template setup. Checked at the workspace root first, then the home directory (`~/.tts_venvs.yaml`), with the workspace file taking precedence. Agents use the venv manifest to select the correct interpreter without asking the developer every time; when the manifest is absent or ambiguous, agents must ask.
_Avoid_: "venv config," "python path file," "environment file"
