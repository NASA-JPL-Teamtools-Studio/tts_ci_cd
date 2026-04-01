import os
import sys
import warnings
import subprocess
import re
import yaml
import tomllib
from pathlib import Path
from git import Repo, InvalidGitRepositoryError, GitCommandError
from rich.console import Console
from rich.table import Table
from rich import box

# --- CONFIGURATION ---
CONFIG_PATH = Path.home() / ".tts_config/deploy_locations.yaml"

def load_dynamic_indexes():
    """
    Loads Artifactory URLs and injects credentials for pip compatibility.
    """
    # Start with Public PyPI as a default
    indexes = {"Public PyPI": "https://pypi.org/simple"}
    
    if not CONFIG_PATH.exists():
        return indexes

    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)
            if not config:
                return indexes
            
            art_config = config.get("artifactory", {})
            auth = config.get("auth", {})
            user = auth.get("artifactory_username")
            pwd = auth.get("artifactory_password")

            for env_name, url in art_config.items():
                # Ensure the URL points to the PEP 503 'simple' API
                normalized_url = url.rstrip('/')
                if not normalized_url.endswith('/simple'):
                    normalized_url += '/simple'
                
                # Inject credentials if available (required for private index lookup)
                if user and pwd and "https://" in normalized_url:
                    auth_prefix = f"https://{user}:{pwd}@"
                    normalized_url = normalized_url.replace("https://", auth_prefix)
                
                indexes[env_name.capitalize()] = normalized_url
    except Exception as e:
        print(f"⚠️  Config Error: {e}")
            
    return indexes

# Load the map of Index Name -> Authenticated URL
ARTIFACTORY_URLS = load_dynamic_indexes()

try:
    from setuptools_scm import get_version
    SETUPTOOLS_SCM_AVAILABLE = True
except ImportError:
    SETUPTOOLS_SCM_AVAILABLE = False

def get_project_metadata(path):
    """Reads the actual package name and version from pyproject.toml."""
    toml_path = Path(path) / "pyproject.toml"
    if not toml_path.exists():
        return os.path.basename(path)
    
    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
            return data.get("project", {}).get("name", os.path.basename(path))
    except Exception:
        return os.path.basename(path)

def get_scm_version(path):
    if not SETUPTOOLS_SCM_AVAILABLE:
        return None, "[red]No Module[/red]"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            version = get_version(root=path, fallback_root=path)
            return version, version
    except LookupError:
        return None, "[dim]N/A[/dim]"
    except Exception:
        return None, "[dim]Error[/dim]"

def get_remote_version(package_name, index_url, local_version=None):
    """Queries a specific index for a package name."""
    cmd = [
        sys.executable, "-m", "pip", "index", "versions", package_name,
        "--index-url", index_url
    ]
    
    try:
        # Use a longer timeout for Artifactory which can be sluggish
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=8 
        )
        
        if result.returncode != 0:
            return None, "[yellow]None[/yellow]"

        # Match "Available versions: 1.2.3, 1.2.2"
        match = re.search(r"Available versions: ([0-9a-zA-Z\.\-_]+)", result.stdout)
        if match:
            raw_ver = match.group(1)
            return raw_ver, colorize_version(raw_ver, local_version)
        
        # Fallback for "package (1.2.3)"
        match_paren = re.search(r"\(([\d\.]+)\)", result.stdout)
        if match_paren:
            raw_ver = match_paren.group(1)
            return raw_ver, colorize_version(raw_ver, local_version)
            
        return None, "[dim]?[/dim]"

    except (subprocess.TimeoutExpired, Exception):
        return None, "[red]Err[/red]"

def colorize_version(remote_version, local_version):
    if local_version is None:
        return f"[cyan]{remote_version}[/cyan]"
    if remote_version == local_version:
        return f"[green]{remote_version}[/green]"
    return f"[yellow]{remote_version}[/yellow]"

def get_git_status(path):
    try:
        repo = Repo(path)
        try:
            for remote in repo.remotes:
                remote.fetch(kill_after_timeout=5)
        except:
            pass 

        try:
            branch = repo.active_branch.name
        except:
            branch = f"({repo.head.commit.hexsha[:7]})"

        ahead = behind = 0
        try:
            tracking = repo.active_branch.tracking_branch()
            if tracking:
                ahead = len(list(repo.iter_commits(f"{tracking.name}..{branch}")))
                behind = len(list(repo.iter_commits(f"{branch}..{tracking.name}")))
        except:
            ahead = behind = "?"

        return {
            "is_repo": True,
            "folder_name": os.path.basename(path),
            "branch": branch,
            "dirty": repo.is_dirty(),
            "untracked": len(repo.untracked_files) > 0,
            "ahead": ahead,
            "behind": behind
        }
    except InvalidGitRepositoryError:
        return {"is_repo": False}

def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    console = Console()
    
    table = Table(title=f"Multi-Index Dashboard: {target_dir}", box=box.ROUNDED)
    table.add_column("Repository", style="cyan", no_wrap=True)
    table.add_column("Local", style="bold dodger_blue1") 
    
    for name in ARTIFACTORY_URLS.keys():
        table.add_column(name, justify="center")

    table.add_column("Branch", style="magenta")
    table.add_column("State", style="bold")
    table.add_column("Sync", justify="center")

    repos_found = False

    with console.status("[bold green]Analyzing Repositories...") as status:
        try:
            dirs = sorted([d for d in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, d))])
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return

        for item in dirs:
            full_path = os.path.join(target_dir, item)
            repo_info = get_git_status(full_path)

            if repo_info.get("is_repo"):
                repos_found = True
                
                # Use pyproject.toml name for index lookups, folder name for table display
                package_name = get_project_metadata(full_path)
                local_ver_raw, local_ver_display = get_scm_version(full_path)

                index_versions = []
                for name, url in ARTIFACTORY_URLS.items():
                    status.update(f"[bold green]{package_name}: Checking {name}...")
                    _, ver_display = get_remote_version(package_name, url, local_ver_raw)
                    index_versions.append(ver_display)

                state_text = "[red]Mod[/red]" if repo_info['dirty'] else "[dim]Clean[/dim]"
                if repo_info['untracked']:
                    state_text += " [yellow]*[/yellow]"

                # Sync Status
                a, b = repo_info['ahead'], repo_info['behind']
                sync_parts = []
                if a != 0: sync_parts.append(f"[yellow]↑{a}[/yellow]")
                if b != 0: sync_parts.append(f"[red]↓{b}[/red]")
                sync_text = " ".join(sync_parts) if sync_parts else "[dim]✓[/dim]"

                table.add_row(
                    repo_info['folder_name'],
                    local_ver_display,
                    *index_versions,
                    repo_info['branch'],
                    state_text,
                    sync_text
                )

    if repos_found:
        console.print(table)
    else:
        console.print(f"[yellow]No git repositories found in {target_dir}[/yellow]")

if __name__ == "__main__":
    main()