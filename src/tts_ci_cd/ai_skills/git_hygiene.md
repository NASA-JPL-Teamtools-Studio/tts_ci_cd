---
description: Guide a developer through git hygiene across a multi-repo TTS workspace — finding homeless WIP, branch mismatches, unpushed commits, and semantically incoherent branches, then interactively resolving each violation with non-destructive git operations.
---

# TTS Git Hygiene Skill

Use this skill when the developer asks to:
- "clean up my git state"
- "figure out what I've been working on"
- "sort out my WIP across repos"
- "run git hygiene"
- or any variation of reviewing, organizing, or deconflicting work-in-progress across multiple repos.

---

## Step 1: Activate the correct Python environment

Before running any `tts-*` commands, find and activate the right Python interpreter.

1. Check for `.venvs.yaml` in the workspace root (the directory containing the `<group>/<repo>` tree).
2. If not found there, check `~/.tts_venvs.yaml`.
3. Read the `default` key. Use that interpreter path.
4. **If neither file exists, or if the correct venv is ambiguous, ask the developer before proceeding.** Do not assume the system Python or any mission-specific venv (e.g., `nisar_dev`) is correct — the developer may be working on TTS core, not a mission adaptation.

Example venv manifest lookup:
```yaml
# .venvs.yaml at workspace root
default: ~/projects/tt_studio/dev/venv/tts_dev_p3.14/bin/python
nisar_dev: ~/projects/tt_studio/dev/venv/nisar_dev/bin/python
```

Use the `default` entry unless the developer has explicitly asked you to work in a mission-specific environment.

---

## Step 2: Fetch all remotes first

Before running the report or inspecting any branch tracking state, fetch all remotes:

```bash
find <workspace_root> -maxdepth 3 -name ".git" -type d | sed 's|/.git||' | while read repo; do
  git -C "$repo" fetch --all --prune 2>/dev/null
done
```

The `--prune` flag is important: it clears stale remote-tracking refs, which is what makes the `[gone]` state visible in `git branch -vv`. Without a fetch, the report may show outdated ahead/behind counts and miss remote-deleted branches.

**The `tts-git-hygiene` CLI must run this fetch as its very first operation.**

---

## Step 3: Run the deterministic report

Run `tts-git-hygiene` with JSON output so you have structured data to reason over:

```bash
<python_interpreter> -m tts_ci_cd.git_hygiene --workspace <workspace_root> --json
```

Or if the CLI entry point is installed in the venv:
```bash
tts-git-hygiene --workspace <workspace_root> --json
```

The JSON output contains one entry per repo with the following fields:
- `repo`: repo name
- `group`: group name (e.g., `tts_core`)
- `branch`: current branch
- `is_default_branch`: true if on `main` or `develop`
- `dirty`: true if there are staged or unstaged changes
- `untracked`: list of untracked files not in `.gitignore`
- `ahead`: number of commits ahead of remote tracking branch
- `behind`: number of commits behind remote tracking branch
- `stashes`: number of stashed changesets
- `recent_commits`: list of last 10 commit messages
- `changed_files`: list of files with uncommitted changes (staged + unstaged)
- `diff_stat`: output of `git diff --stat HEAD` (sizes of changes per file)
- `diff_size_lines`: total line count of `git diff HEAD`
- `remote_url`: the URL of the `origin` remote
- `local_branches_gone`: list of local branches whose remote tracking branch has been deleted (detected via `git branch -vv | grep ': gone]'`)
- `local_branches_unpushed`: list of local branches with no upstream ever configured (no `[...]` in `git branch -vv` output)

---

## Step 4: Identify and present violations

Parse the JSON and classify each repo into violation categories. Present a clear summary to the developer **before taking any action**.

### Violation types (in priority order):

1. **Homeless WIP** — `is_default_branch: true` AND (`dirty: true` OR `untracked` is non-empty)
   > "You have uncommitted changes on `main`/`develop` in `<repo>`. This work should be on a feature branch."

2. **Dirty feature branch** — `is_default_branch: false` AND `dirty: true`
   > "You have uncommitted changes on `<branch>` in `<repo>`. Consider committing or stashing."

3. **Unpushed commits** — `ahead > 0`
   > "`<repo>` has `<N>` commit(s) not yet pushed to remote."

4. **Branch mismatch** — two or more repos have uncommitted changes but are on *different* branch names
   > "`tts_data_utils` is on `feat/jpl-time` but `tts_dexter` is on `main` and also has uncommitted changes. These might belong together."

5. **Orphaned stash** — `stashes > 0`
   > "`<repo>` has `<N>` stashed changeset(s) that may have been forgotten."

6. **Untracked files** — `untracked` is non-empty
   > "`<repo>` has untracked files: `<list>`. Should they be committed or added to `.gitignore`?"

7. **Non-standard branch name** — `is_default_branch: false` AND branch name does not match `<username>/<feature-name>` (e.g., `mrmuszynski/jpl-time`)
   > "Branch `<branch>` in `<repo>` does not follow the `<username>/<feature-name>` naming convention. Consider renaming it."

8. **Remote identity mismatch** — the `origin` remote URL refers to a repo with a different name or a different group/org than the local repo.
   Detection: compare `basename(remote_url)` (strip `.git`) to `folder_name`. Flag if they differ OR if the org/group in the URL doesn't match the workspace group.
   > "`fss/fss_events` points to `oco2-mpst/oco2_events`. The remote repo name and org don't match this repo's name or group. Has this repo been properly initialized with its own remote?"

   Common causes:
   - Repo was cloned from a sibling repo as a template and never re-pointed (most common in mission adaptation groups)
   - Repo is a fork that hasn't been promoted to the org yet
   - Remote was renamed on GitHub but the local config was never updated

9. **Orphaned local branches** — branches that exist locally but have no corresponding branch on the remote. Two subtypes with different urgency:

   **9a. Remote-deleted (`[gone]`)** — the remote tracking branch was deleted, but the local branch still exists. This almost always means the branch's PR was merged and the remote branch cleaned up. These are low-urgency clutter.

   Detection:
   ```bash
   git -C <repo> branch -vv | grep ': gone]'
   ```
   > "`oco2_tower` has 8 local branches whose remote was deleted: `muszynsk/fix_sort`, `muszynsk/misc_little_things`, ... These are likely merged PRs. Safe to delete with `git branch -d <name>`."

   **9b. Never pushed** — local branches with no upstream ever configured (no `[...]` in `git branch -vv`). More urgency — could be work that hasn't been shared anywhere.

   Detection:
   ```bash
   git -C <repo> branch -vv | grep -v ': gone]' | grep -v '\[origin'
   ```

   Heuristics to classify never-pushed branches:
   - Name is `tmp`, `tmp2`, `tmp3`, etc. → almost certainly scratch work, safe to delete
   - Name follows `<username>/<feature>` pattern → real WIP, should be pushed or consciously abandoned
   - Name contains a date (e.g., `2026_01_26`) → likely a snapshot, review before deleting
   - Was just created in this session → expected, no action needed
   > "`demosat_seqdb` has 2 never-pushed branches: `2026_01_26` and `muszynsk/new_strcuture`. The second one has a typo. Are these intentional? Do you want to push them, rename them, or delete them?"

Present all violations in a numbered list. Ask the developer: "How would you like to proceed — should I walk through these one by one, or is there a specific one you want to focus on?"

---

## Step 5: Semantic cohesion check (AI reasoning)

For each repo with uncommitted changes or a feature branch with recent commits, assess whether the changes on that branch logically belong together.

### How to assess:

1. Look at `recent_commits` (last 10 commit messages) and `changed_files`.
2. Check `diff_size_lines`. 
   - If ≤ 300 lines: include the full diff in your reasoning (read it from `git diff HEAD` output).
   - If > 300 lines: use `diff_stat` and `changed_files` only, and tell the developer: "The diff is large (`<N>` lines), so I'm using file names and commit messages rather than the full diff to assess cohesion."
3. Ask yourself: do the commit messages and file paths suggest a single coherent purpose, or do they suggest two distinct features that ended up on the same branch?

### When to flag:

Flag low cohesion if you see clear signals of two unrelated concerns — for example:
- Commit messages mentioning both "jpl_time integration" and "CSV bugfix"
- Changed files spanning both `core/data_frame.py` (data model) and `test/test_csv.py` in a way that suggests a separate fix, not a test for the jpl_time work

**Do not flag cohesion for every repo.** Only raise it when you see a genuine signal. False positives here erode trust.

### How to present:

> "The changes on `feat/jpl-time` in `tts_data_utils` mostly look like they belong together, but I notice `src/tts_data_utils/core/csv_utils.py` was modified and the commit message says 'Fix CSV round-trip bug.' That doesn't obviously relate to the jpl_time work. You may want to consider whether that fix should be on a separate branch or at least committed separately with a clear message. Do you want to think about this, or is it intentional?"

Do not attempt to split the branch automatically. This is a prompt to think, not an action item.

---

## Step 6: Interactive resolution (only with developer confirmation)

Walk through violations one at a time. For each, explain what you want to do, wait for the developer's go-ahead, then act.

### Safe operations you may suggest and execute (after confirmation):

**Create a feature branch from current dirty state:**
```bash
git -C <repo_path> stash
git -C <repo_path> checkout -b <branch_name>
git -C <repo_path> stash pop
```
Use case: homeless WIP on `main`; create a proper feature branch.

**Move dirty state to an existing feature branch:**
```bash
git -C <repo_path> stash
git -C <repo_path> checkout <branch_name>
git -C <repo_path> stash pop
```
Use case: work that belongs on an already-existing branch in another repo.

**Create a matching branch in a repo that is behind:**
```bash
git -C <repo_path> stash   # if dirty
git -C <repo_path> checkout -b <branch_name>
git -C <repo_path> stash pop   # if we stashed
```
Use case: branch mismatch — `tts_data_utils` is on `feat/jpl-time` but `tts_dexter` is on `main`.

### Script for every branch-moving operation:

**Branch name format:** always propose branch names as `<username>/<feature_name>` (e.g., `mrmuszynski/integrate_jpl_time`). Ask the developer to confirm the username if you are not certain who is working in this workspace.

1. State exactly what you intend to do: "I am going to stash your changes in `tts_dexter`, create `mrmuszynski/integrate_jpl_time`, and pop the stash onto it. This is reversible with `git stash` / `git checkout` if anything looks wrong."
2. Wait for explicit confirmation ("yes," "go ahead," "do it," etc.).
3. Execute the commands.
4. Report what happened and what the resulting state is.
5. Ask: "Does that look right, or should we undo any of that?"

### Operations you must NEVER perform without explicit developer instruction:

- `git reset --hard` (any form)
- `git push --force`
- `git branch -D` (delete a branch)
- `git clean -fd` (remove untracked files)
- Any rebase

### Resolving orphaned local branches (violation #9):

For **remote-deleted (`[gone]`)** branches — propose a batch delete after showing the list:
```bash
git -C <repo> branch -d <branch1> <branch2> ...
```
Use `-d` (not `-D`) so git refuses to delete any branch that wasn't actually merged. If `-d` fails for a branch, flag it to the developer — it may have unmerged work.

For **never-pushed** branches — do not delete without developer confirmation. Instead:
1. Show the branch name, last commit message, and commit count ahead of `main`/`develop`.
2. Ask: "Do you want to push this, rename it, or delete it?"
3. Act only on explicit instruction.

### Resolving remote identity mismatch (violation #8):

Never update a remote URL automatically. Present the mismatch and ask:
> "Should I update the remote to `git@github.jpl.nasa.gov:muszynsk/<repo_name>.git`, or is this current remote intentional?"

If the developer confirms, use:
```bash
git -C <repo> remote set-url origin <new_url>
```

---

## Step 7: Final state summary

After all violations have been addressed (or skipped), present a final table:

```
Repo              | Branch           | State   | Pushed?
tts_data_utils    | mrmuszynski/jpl-time    | Clean   | No (3 commits ahead)
tts_dexter        | mrmuszynski/jpl-time    | Dirty   | —
tts_dante         | main             | Clean   | ✓
```

Remind the developer of any remaining items they chose to skip, and of any unpushed commits that should be pushed before ending the session.

---

## Notes for the agent

- **Ask before assuming a venv.** Developers have multiple venvs for different Python versions and missions. The venv manifest is the source of truth; if it's missing or ambiguous, ask.
- **Branch parity is the goal, not a requirement.** If the developer deliberately has `tts_data_utils` on `feat/jpl-time` and `tts_dexter` on `main` for a good reason, respect that after asking.
- **Stash is safe and reversible.** You may suggest it liberally. But always report what you stashed and confirm the pop landed correctly.
- **Semantic cohesion is advisory.** Do not block progress on a cohesion concern. Surface it, let the developer decide.
- **This skill drives `tts-git-hygiene`.** If that command is not found, tell the developer: "I need `tts-git-hygiene` to be installed. Run `pip install tts-ci-cd` in your dev venv, or check that the right venv is active."
