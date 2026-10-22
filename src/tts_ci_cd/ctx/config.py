"""Configuration and discovery for tts-ctx.

Resolves the workspace root, enumerates repos, parses git remotes,
and reads the WORKSPACE_MAP.md for Adapts relationships.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Workspace root (overridable via env, matching write_agent_pointer.py convention)
_DEFAULT_WORKSPACE_ROOT = Path("/Users/muszynsk/projects/tt_studio/dev")

# Regex for finding repos with Adapts relationships in WORKSPACE_MAP.md
_ADAPTS_RE = re.compile(r"`([^`]+)`.{0,15}\(Adapts\s+`([^`]+)`\)\*")


def get_workspace_root() -> Path:
    """Return the TTS workspace root directory."""
    env_override = os.environ.get("TTS_WORKSPACE_ROOT")
    if env_override:
        return Path(env_override)
    # Try walking up for .venvs.yaml
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / ".venvs.yaml").exists():
            return parent
    return _DEFAULT_WORKSPACE_ROOT


def get_current_mission() -> Optional[str]:
    """Return the current mission context, from env var or default to None."""
    return os.environ.get("TTS_CTX_MISSION")


def list_git_repos(root: Optional[Path] = None) -> List[Path]:
    """Walk the workspace and return all directories containing a .git subdirectory."""
    root = root or get_workspace_root()
    repos = []
    for dirpath, dirnames, _ in os.walk(root):
        p = Path(dirpath)
        if (p / ".git").is_dir():
            # Don't descend into sub-repos
            dirnames[:] = []
            repos.append(p)
    return sorted(repos)


def get_remote_info(repo_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """Return (host, owner/repo) from a repo's git remote."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None

    # git@host:owner/repo.git or https://host/owner/repo.git
    m = re.search(r"github\.(?:jpl\.nasa\.gov|com)[/|:]([^/]+)/([^/]+)", out)
    if m:
        host = "github.jpl.nasa.gov" if "jpl.nasa.gov" in out else "github.com"
        owner = m.group(1)
        repo = m.group(2).replace(".git", "")
        return host, f"{owner}/{repo}"
    return None, None


def ownership_category(host: Optional[str], repo_ref: Optional[str]) -> str:
    """Classify repo ownership: public, jpl-internal, sandbox, no-origin."""
    if not host or not repo_ref:
        return "no-origin"
    owner = repo_ref.split("/")[0]
    if host == "github.com" and owner == "NASA-JPL-Teamtools-Studio":
        return "public"
    if host == "github.jpl.nasa.gov":
        if owner == "muszynsk":
            return "sandbox"
        return "jpl-internal"
    return "jpl-internal"


def parse_workspace_map() -> Dict[str, str]:
    """Parse WORKSPACE_MAP.md for Adapts relationships.

    Returns: {repo_rel_path: adapted_core_repo_name}
    """
    root = get_workspace_root()
    map_path = root / "WORKSPACE_MAP.md"
    adapts: Dict[str, str] = {}
    if not map_path.exists():
        return adapts
    for repo, core in _ADAPTS_RE.findall(map_path.read_text()):
        adapts[repo] = core
    return adapts


def get_overrides() -> Dict[str, str]:
    """Read .ttsctx_overrides.yaml from the workspace root.
    
    Returns: {repo_name: summary}
    """
    root = get_workspace_root()
    overrides_path = root / ".ttsctx_overrides.yaml"
    if not overrides_path.exists():
        return {}
    try:
        import yaml
        with open(overrides_path, "r") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except ImportError:
        print("⚠ pyyaml not installed; cannot read .ttsctx_overrides.yaml")
        return {}
    except Exception as e:
        print(f"⚠ Error reading .ttsctx_overrides.yaml: {e}")
        return {}


def get_db_path() -> Path:
    """Path to the SQLite index database."""
    return get_workspace_root() / ".ttsctx_index.sqlite3"


def get_csv_dump_dir() -> Path:
    """Directory for CSV dumps of index tables."""
    return get_workspace_root() / ".ttsctx_dump"


def get_knowledge_dir() -> Path:
    """Directory containing static knowledge cards."""
    return Path(__file__).parent / "knowledge"


def get_src_dirs(repo_path: Path) -> List[Path]:
    """Find `src/<package>` directories in a repo."""
    src_root = repo_path / "src"
    if not src_root.exists() or not src_root.is_dir():
        return []
    return [d for d in src_root.iterdir() if d.is_dir() and (d / "__init__.py").exists()]


def get_all_python_files(src_dirs: List[Path]) -> List[Path]:
    """Recursively find all .py files in source directories."""
    py_files = []
    for src_dir in src_dirs:
        py_files.extend(src_dir.rglob("*.py"))
    return sorted(py_files)


def relative_dotted_path(repo_path: Path, py_file: Path, src_dir: Path) -> str:
    """Convert a .py file path to a dotted module path relative to src_dir.

    e.g. src/tts_data_utils/core/data_frame.py -> tts_data_utils.core.data_frame
    """
    rel = py_file.relative_to(src_dir)
    parts = list(rel.parts[:-1])  # remove .py extension
    if py_file.name == "__init__.py":
        # __init__.py represents the package itself
        return ".".join(parts) if parts else ""
    else:
        return ".".join(parts + [py_file.stem])
