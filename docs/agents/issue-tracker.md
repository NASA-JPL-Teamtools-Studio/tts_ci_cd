# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Repository

- **Remote:** `git@github.com:NASA-JPL-Teamtools-Studio/tts_ci_cd.git`
- **Canonical repository:** `NASA-JPL-Teamtools-Studio/tts_ci_cd`
- **Host:** `github.com`

## Conventions

- **Create an issue:** `gh issue create --repo NASA-JPL-Teamtools-Studio/tts_ci_cd --title "..." --body-file <file>`
- **Read an issue:** `gh issue view <number> --repo NASA-JPL-Teamtools-Studio/tts_ci_cd --json number,title,body,labels,comments`
- **List issues:** `gh issue list --repo NASA-JPL-Teamtools-Studio/tts_ci_cd`
- **Comment on an issue:** `gh issue comment <number> --repo NASA-JPL-Teamtools-Studio/tts_ci_cd --body-file <file>`
- **Apply or remove labels:** `gh issue edit <number> --repo NASA-JPL-Teamtools-Studio/tts_ci_cd --add-label "..."` / `--remove-label "..."`
- **Close an issue:** `gh issue close <number> --repo NASA-JPL-Teamtools-Studio/tts_ci_cd --comment "..."`

## Pull requests as a triage surface

**No.** Pull requests are not included as a request surface by default.

## When a skill says “publish to the issue tracker”

Create or update a GitHub issue in `NASA-JPL-Teamtools-Studio/tts_ci_cd`.

## When a skill says “fetch the relevant ticket”

Use `gh issue view` with the repository specified above.
