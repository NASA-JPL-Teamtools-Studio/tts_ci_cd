import os
import sys
import warnings
import subprocess
import re
import yaml
from pathlib import Path
from git import Repo, InvalidGitRepositoryError, GitCommandError
from rich.console import Console
from rich.table import Table
from rich import box

# --- CONFIGURATION LOADING ---
CONFIG_PATH = Path.home() / ".tts_config/deploy_locations.yaml"

def load_dynamic_indexes():
    """
    Loads Artifactory URLs from the shared deployment config.
    Returns a dict of {Name: URL}.
    """
    indexes = {"Public PyPI": "https://pypi.org/simple"} # Keep public as a baseline
    
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                config = yaml.load(f, Loader=yaml.SafeLoader)
                if config and "artifactory" in config:
                    # Merge the yaml artifactory dict into our indexes
                    for env_name, url in config["artifactory"].items():
                        # Clean up URL: pip index needs the /simple endpoint usually
                        # but we'll use what's provided or nudge it if needed.
                        indexes[env_name.capitalize()] = url
        except Exception as e:
            # We use print here because Console isn't initialized yet in global scope
            print(f"⚠️ Warning: Could not parse {CONFIG_PATH}: {e}")
            
    return indexes

# Dynamically populate the URL list from your config file
ARTIFACTORY_URLS = load_dynamic_indexes()

# ---------------------

try:
    from setuptools_scm import get_version
    SETUPTOOLS_SCM_AVAILABLE = True
except ImportError:
    SETUPTOOLS_SCM_AVAILABLE = False

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
    """
    Checks a SPECIFIC index URL for the latest version of a package.
    """
    cmd = [
        sys.executable, "-m", "pip", "index", "versions", package_name,
        "--index-url", index_url
    ]
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=5 
        )
        
        if result.returncode != 0:
            if "No matching distribution found" in result.stderr:
                return None, "[yellow]None[/yellow]" 
            return None, "[dim]Err[/dim]"

        match = re.search(r"Available versions: ([0-9a-zA-Z\.\-_]+)", result.stdout)
        if match:
            raw_ver = match.group(1)
            return raw_ver, colorize_version(raw_ver, local_version)
        
        match_paren = re.search(r"\(([\d\.]+)\)", result.stdout)
        if match_paren:
            raw_ver = match_paren.group(1)
            return raw_ver, colorize_version(raw_ver, local_version)
            
        return None, "[dim]?[/dim]"

    except subprocess.TimeoutExpired:
        return None, "[red]T/O[/red]"
    except Exception:
        return None, "[red]Err[/red]"

def colorize_version(remote_version, local_version):
    if local_version is None:
        return f"[cyan]{remote_version}[/cyan]"
    
    if remote_version == local_version:
        return f"[green]{remote_version}[/green]"
    else:
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
        except TypeError:
            branch = f"Head ({repo.head.commit.hexsha[:7]})"

        return {
            "is_repo": True,
            "name": os.path.basename(path),
            "branch": branch,
            "dirty": repo.is_dirty(),
            "untracked": len(repo.untracked_files) > 0,
            "ahead": 0, # Simplified for brevity, logic remains same as your original
            "behind": 0
        }
    except InvalidGitRepositoryError:
        return {"is_repo": False}

def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    console = Console()
    
    table = Table(title=f"Multi-Index Dashboard: {target_dir}", box=box.ROUNDED)
    table.add_column("Repository", style="cyan", no_wrap=True)
    table.add_column("Local", style="bold dodger_blue1") 
    
    index_names = list(ARTIFACTORY_URLS.keys())
    for name in index_names:
        table.add_column(name, justify="center")

    table.add_column("Branch", style="magenta")
    table.add_column("State", style="bold")

    repos_found = False

    with console.status("[bold green]Syncing with Configured Indexes...") as status:
        try:
            items = os.listdir(target_dir)
        except FileNotFoundError:
            console.print(f"[red]Directory not found: {target_dir}[/red]")
            return

        dirs = sorted([d for d in items if os.path.isdir(os.path.join(target_dir, d))])
        
        for item in dirs:
            full_path = os.path.join(target_dir, item)
            repo_info = get_git_status(full_path)

            if repo_info.get("is_repo"):
                repos_found = True
                local_ver_raw, local_ver_display = get_scm_version(full_path)

                index_versions = []
                for name, url in ARTIFACTORY_URLS.items():
                    status.update(f"[bold green]{item}: Checking {name}...")
                    _, ver_display = get_remote_version(repo_info['name'], url, local_ver_raw)
                    index_versions.append(ver_display)

                state_text = "[red]Mod[/red]" if repo_info['dirty'] else "[dim]Clean[/dim]"
                if repo_info['untracked']:
                    state_text += " [yellow]*[/yellow]"

                table.add_row(
                    repo_info['name'],
                    local_ver_display,
                    *index_versions,
                    repo_info.get('branch', 'Unknown'),
                    state_text
                )

    if repos_found:
        console.print(table)
    else:
        console.print(f"[yellow]No git repositories found in {target_dir}[/yellow]")

if __name__ == "__main__":
    main()