"""
tts-write-agent-pointer

Generate per-repo docs/agents/README.md pointers for the TTS workspace.

Implements Phase 2 of agent files alignment spec:
- Enumerate in-scope repos per capture rule
- Resolve issue tracker, Adapts target, ownership category
- Write idempotent docs/agents/README.md
- Convert 4 legacy repos
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

WORKSPACE_ROOT = Path("/Users/muszynsk/projects/tt_studio/dev")
WORKSPACE_MAP = WORKSPACE_ROOT / "WORKSPACE_MAP.md"
CENTRAL_DOCS = WORKSPACE_ROOT / "tts_core/teamtools_documentation/docs/agents"

CAPTURE_PATTERN = re.compile(r"^(tts_[a-z0-9_]+|[a-z0-9_]+_[a-z0-9_]+)$")

LEGACY_REPOS = {
    "oco2/oco2_tower",
    "oxus/oxus_telemetry_store",
    "tts_core/tts_data_utils",
    "tts_core/tts_tower",
}

EXCLUDED = {
    "mro/mro_sci",
    "m20/mech_data_tools",
    "work_tracking/resume",
}

def list_git_repos(root: Path) -> List[Path]:
    repos = []
    for dirpath, dirnames, _ in os.walk(root):
        p = Path(dirpath)
        if (p / ".git").is_dir():
            # avoid descending into sub-repos
            dirnames[:] = []
            repos.append(p)
    return repos

def get_remote_info(repo_path: Path) -> Tuple[str | None, str | None]:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return None, None
    # parse git@host:owner/repo.git or https://host/owner/repo.git
    m = re.search(r"github\.(?:jpl\.nasa\.gov|com)[/|:]([^/]+)/([^/]+)", out)
    if m:
        host = "github.jpl.nasa.gov" if "jpl.nasa.gov" in out else "github.com"
        owner = m.group(1)
        repo = m.group(2).replace(".git", "")
        return host, f"{owner}/{repo}"
    return None, None

def ownership_category(host: str | None, owner: str | None) -> str:
    if not host or not owner:
        return "no-origin"
    if host == "github.com" and owner == "NASA-JPL-Teamtools-Studio":
        return "public"
    if host == "github.jpl.nasa.gov":
        if owner == "muszynsk":
            return "sandbox"
        return "jpl-internal"
    return "jpl-internal"

def parse_workspace_map() -> Dict[str, str]:
    adapts: Dict[str, str] = {}
    if not WORKSPACE_MAP.exists():
        return adapts
    text = WORKSPACE_MAP.read_text()
    # crude parse: `**repo** *(Adapts `core`)*`
    pattern = re.compile(r"`([^`]+)`.{0,15}\(Adapts\s+`([^`]+)`\)\*")
    for repo, core in pattern.findall(text):
        adapts[repo] = core
    return adapts

def capture_rule(repo_rel: str, core_libs: set[str]) -> bool:
    if repo_rel in EXCLUDED:
        return False
    # check pattern
    name = repo_rel.split("/")[-1]
    if re.match(r"^tts_[a-z0-9_]+$", name):
        return True
    # mission_lib pattern
    m = re.match(r"^([a-z0-9_]+)_([a-z0-9_]+)$", name)
    if not m:
        return False
    mission, lib = m.groups()
    core_name = f"tts_{lib}"
    if core_name in core_libs:
        return True
    return False

def render_pointer(repo_rel: str, host: str | None, repo_ref: str | None, adapts: str | None, ownership: str) -> str:
    if host and repo_ref:
        tracker = f"GitHub Issues at `{host}/{repo_ref}`\n  (host `{host}`, `-R {repo_ref}`)."
    else:
        tracker = f"GitHub Issues assumed at `github.jpl.nasa.gov/muszynsk/{repo_rel.replace('/', '_')}`\n  (host `github.jpl.nasa.gov`, `-R muszynsk/{repo_rel.replace('/', '_')}` via `gh` lookup)."
    adapts_line = adapts or "unknown"
    return f"""# Agent skills

Canonical engineering-skill conventions and the cross-repo dependency map live in
`tts_core/teamtools_documentation/docs/agents/`. This repo holds only the
per-repo instance data a skill needs locally.

- **Issue tracker:** {tracker}
  *If a skill needs more, see `teamtools_documentation/docs/agents/issue-tracker-github-ghe.md`.*
- **Adapts:** `{adapts_line}`
- **Triage labels:** default vocabulary (see `teamtools_documentation/docs/agents/triage-labels.md`)
- **Domain context:** repo-specific domain language is in this repo's `CONTEXT.md`.
- **Ownership:** {ownership}
"""

def write_pointer(repo_path: Path, content: str) -> None:
    agents_dir = repo_path / "docs" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    readme = agents_dir / "README.md"
    if readme.exists() and readme.read_text() == content:
        return
    readme.write_text(content)

def convert_legacy(repo_path: Path) -> None:
    # Delete redundant docs
    for fname in ["issue-tracker.md", "domain.md", "triage-labels.md"]:
        p = repo_path / "docs" / "agents" / fname
        if p.exists():
            p.unlink()
    # Drop ## Agent skills block from AGENTS.md if present
    agents_md = repo_path / "AGENTS.md"
    if agents_md.exists():
        text = agents_md.read_text()
        # naive removal
        text = re.sub(r"## Agent skills.*?(\n## |\Z)", r"\1", text, flags=re.S)
        agents_md.write_text(text)

def main() -> None:
    repos = list_git_repos(WORKSPACE_ROOT)
    core_libs = set()
    for r in repos:
        rel = str(r.relative_to(WORKSPACE_ROOT))
        if rel.startswith("tts_core/tts_"):
            core_libs.add(Path(rel).name)
    adapts_map = parse_workspace_map()
    for repo_path in repos:
        rel = str(repo_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
        if not capture_rule(rel, core_libs):
            continue
        host, repo_ref = get_remote_info(repo_path)
        ownership = ownership_category(host, repo_ref.split("/")[0] if repo_ref else None)
        adapts = adapts_map.get(rel)
        content = render_pointer(rel, host, repo_ref, adapts, ownership)
        write_pointer(repo_path, content)
        if rel in LEGACY_REPOS:
            convert_legacy(repo_path)

if __name__ == "__main__":
    main()
