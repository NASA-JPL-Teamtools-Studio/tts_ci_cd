"""
Validate agent pointer conventions across TTS repos.

Checks:
- docs/agents/README.md exists for in-scope repos
- File contains required 5 fields: Issue tracker, Adapts, Triage labels, Domain context, Ownership
- No legacy docs/agents/{issue-tracker,domain,triage-labels}.md remain
- ## Agent skills block not present in AGENTS.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

WORKSPACE_ROOT = Path("/Users/muszynsk/projects/tt_studio/dev")

REQUIRED_FIELDS = ["Issue tracker:", "Adapts:", "Triage labels:", "Domain context:", "Ownership:"]

def is_in_scope(rel: str) -> bool:
    name = Path(rel).name
    if re.match(r"^tts_[a-z0-9_]+$", name):
        return True
    m = re.match(r"^([a-z0-9_]+)_([a-z0-9_]+)$", name)
    if m:
        mission, lib = m.groups()
        core_name = f"tts_{lib}"
        # check if core exists in workspace
        # simplistic: look for tts_core/tts_lib
        if (WORKSPACE_ROOT / "tts_core" / core_name).exists():
            return True
    return False

def validate_repo(repo_path: Path, rel: str) -> list[str]:
    issues = []
    agents_dir = repo_path / "docs" / "agents"
    readme = agents_dir / "README.md"
    if not readme.exists():
        issues.append(f"Missing docs/agents/README.md")
        return issues
    content = readme.read_text()
    for field in REQUIRED_FIELDS:
        if field not in content:
            issues.append(f"Missing field '{field}' in README.md")
    # check legacy files
    for legacy in ["issue-tracker.md", "domain.md", "triage-labels.md"]:
        if (agents_dir / legacy).exists():
            issues.append(f"Legacy file still present: {legacy}")
    # check AGENTS.md for ## Agent skills block
    agents_md = repo_path / "AGENTS.md"
    if agents_md.exists():
        txt = agents_md.read_text()
        if re.search(r"^## Agent skills", txt, re.M):
            issues.append("AGENTS.md still contains ## Agent skills block")
    return issues

def main(argv: list[str] | None = None):
    repos = []
    for root, dirs, _ in Path(WORKSPACE_ROOT).walk():
        if (Path(root) / ".git").exists():
            repo_path = Path(root)
            rel = str(repo_path.relative_to(WORKSPACE_ROOT))
            if is_in_scope(rel):
                repos.append((repo_path, rel))
            # do not descend
            dirs[:] = []
    ok = True
    for repo_path, rel in sorted(repos, key=lambda x: x[1]):
        issues = validate_repo(repo_path, rel)
        if issues:
            ok = False
            print(f"[FAIL] {rel}")
            for i in issues:
                print(f"  - {i}")
        else:
            print(f"[OK] {rel}")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
