import os
import sys
import warnings
import subprocess
import re
from git import Repo, InvalidGitRepositoryError, GitCommandError
from rich.console import Console
from rich.table import Table
from rich import box

# --- CONFIGURATION ---
# Dictionary of Index Name -> Index URL
# The script will generate a column for every key defined here.
ARTIFACTORY_URLS = {
    "Public PyPI": "https://pypi.org/simple" # You can even compare against public

}

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
    Uses --index-url to ensure we only see what is on that specific server.
    Returns (raw_version, formatted_version) tuple.
    If local_version is provided, colorizes based on match.
    """
    # We use --index-url to REPACE the default index. 
    # This ensures the result is strictly from this artifact server.
    cmd = [
        sys.executable, "-m", "pip", "index", "versions", package_name,
        "--index-url", index_url
    ]
    
    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=5 # Short timeout per index to keep things moving
        )
        
        if result.returncode != 0:
            # If package isn't found on this specific index, pip errors out
            if "No matching distribution found" in result.stderr:
                return None, "[yellow]None[/yellow]" 
            return None, "[dim]Err[/dim]"

        # Regex to find the latest version
        # Output format: "package (1.0.0) Available versions: 1.2.0, 1.1.0"
        match = re.search(r"Available versions: ([0-9a-zA-Z\.\-_]+)", result.stdout)
        if match:
            raw_ver = match.group(1)
            formatted_ver = colorize_version(raw_ver, local_version)
            return raw_ver, formatted_ver
        
        # Fallback for single version output
        match_paren = re.search(r"\(([\d\.]+)\)", result.stdout)
        if match_paren:
            raw_ver = match_paren.group(1)
            formatted_ver = colorize_version(raw_ver, local_version)
            return raw_ver, formatted_ver
            
        return None, "[dim]?[/dim]"

    except subprocess.TimeoutExpired:
        return None, "[red]T/O[/red]"
    except Exception:
        return None, "[red]Err[/red]"

def colorize_version(remote_version, local_version):
    """
    Colorize a remote version based on comparison with local version.
    - Green if matches local
    - Yellow/Red if different
    """
    if local_version is None:
        return f"[cyan]{remote_version}[/cyan]"
    
    if remote_version == local_version:
        return f"[green]{remote_version}[/green]"
    else:
        return f"[yellow]{remote_version}[/yellow]"

def get_git_status(path):
    """
    Analyzes git status: fetch, branch, dirty check, and sync status.
    """
    try:
        repo = Repo(path)
        
        # Attempt fetch
        try:
            for remote in repo.remotes:
                remote.fetch(kill_after_timeout=5)
        except (GitCommandError, Exception):
            pass 

        # Branch
        try:
            branch = repo.active_branch.name
        except TypeError:
            branch = f"Head ({repo.head.commit.hexsha[:7]})"

        # Dirty/Untracked
        is_dirty = repo.is_dirty() 
        has_untracked = len(repo.untracked_files) > 0
        
        # Ahead/Behind
        ahead_count = 0
        behind_count = 0
        try:
            tracking = repo.active_branch.tracking_branch()
            if tracking:
                ahead_count = len(list(repo.iter_commits(f"{tracking.name}..{branch}")))
                behind_count = len(list(repo.iter_commits(f"{branch}..{tracking.name}")))
        except:
            ahead_count = "?"
            behind_count = "?"

        return {
            "is_repo": True,
            "name": os.path.basename(path),
            "branch": branch,
            "dirty": is_dirty,
            "untracked": has_untracked,
            "ahead": ahead_count,
            "behind": behind_count
        }
    except InvalidGitRepositoryError:
        return {"is_repo": False}
    except Exception as e:
        return {"is_repo": True, "error": str(e), "name": os.path.basename(path)}

def main():
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    console = Console()
    
    # Setup Table
    table = Table(title=f"Multi-Index Dashboard: {target_dir}", box=box.ROUNDED)
    table.add_column("Repository", style="cyan", no_wrap=True)
    table.add_column("Local", style="bold dodger_blue1") 
    
    # Dynamically add columns for each configured Artifact Index
    index_names = list(ARTIFACTORY_URLS.keys())
    for name in index_names:
        table.add_column(name, justify="center", style="green")

    table.add_column("Branch", style="magenta")
    table.add_column("State", style="bold")
    table.add_column("Sync", justify="center")

    repos_found = False

    with console.status("[bold green]Initializing scan...") as status:
        try:
            items = os.listdir(target_dir)
        except FileNotFoundError:
            console.print(f"[red]Directory not found: {target_dir}[/red]")
            return

        dirs = sorted([d for d in items if os.path.isdir(os.path.join(target_dir, d))])
        
        for item in dirs:
            full_path = os.path.join(target_dir, item)
            
            # 1. Check Git
            status.update(f"[bold green]Git scan: {item}...")
            repo_info = get_git_status(full_path)

            if repo_info.get("is_repo"):
                repos_found = True
                
                # 2. Get Local Version
                local_ver_raw, local_ver_display = get_scm_version(full_path)

                # 3. Check Each Artifactory Index
                # We store results in a list to add to the row later
                index_versions = []
                for name, url in ARTIFACTORY_URLS.items():
                    status.update(f"[bold green]{item}: Checking {name}...")
                    # We assume folder name == package name
                    _, ver_display = get_remote_version(repo_info['name'], url, local_ver_raw)
                    index_versions.append(ver_display)

                # 4. Status Formatting
                if repo_info.get("error"):
                    state_text = f"[red]Error[/red]"
                    sync_text = "-"
                else:
                    state_text = "[red]Mod[/red]" if repo_info['dirty'] else "[dim]Clean[/dim]"
                    if repo_info['untracked']:
                        state_text += " [yellow]*[/yellow]"

                    # Sync
                    ahead = repo_info['ahead']
                    behind = repo_info['behind']
                    parts = []
                    if ahead == "?": parts.append("?")
                    elif ahead > 0: parts.append(f"[yellow]↑{ahead}[/yellow]")
                    
                    if behind == "?": parts.append("?")
                    elif behind > 0: parts.append(f"[red]↓{behind}[/red]")
                    
                    sync_text = " ".join(parts) if parts else "[dim]✓[/dim]"

                # Construct Row
                # Name, Local, [Index1, Index2, ...], Branch, State, Sync
                row_data = [
                    repo_info['name'],
                    local_ver_display,
                    *index_versions, # Unpack the list of remote versions
                    repo_info.get('branch', 'Unknown'),
                    state_text,
                    sync_text
                ]
                
                table.add_row(*row_data)

    if repos_found:
        console.print(table)
    else:
        console.print(f"[yellow]No git repositories found in {target_dir}[/yellow]")

if __name__ == "__main__":
    main()