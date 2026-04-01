# Standard Library Imports
import os
import shutil
import subprocess
from pathlib import Path

# Installed Dependency Imports
import click
import yaml
import tomllib
from build import ProjectBuilder
from twine.commands.upload import upload as twine_upload
from twine.settings import Settings

# Configuration Constants
CONFIG_PATH = Path.home() / ".tts_config/deploy_locations.yaml"
PYPI_URL = "https://upload.pypi.org/legacy/"

def check_git_status(force=False):
    """Checks if the git repository has uncommitted changes."""
    try:
        # --porcelain gives a stable, script-readable output. 
        # If output is empty, the tree is clean.
        result = subprocess.check_output(["git", "status", "--porcelain"], stderr=subprocess.STDOUT).decode("utf-8").strip()
        
        if result:
            click.echo("⚠️  Git repository is dirty (uncommitted changes found):")
            click.echo(result)
            if force:
                click.echo("⏩ '--force' used. Proceeding anyway...")
            else:
                raise click.ClickException("Clean your git state before deploying or use --force.")
    except subprocess.CalledProcessError:
        # Not a git repo, or git not installed
        click.echo("ℹ️  Note: Not a git repository or git not found. Skipping git check.")

def load_global_config():
    """Loads Artifactory URLs and Auth from the user's home directory YAML."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                config = yaml.load(f, Loader=yaml.SafeLoader)
                return config if config else {}
        except Exception as e:
            click.echo(f"⚠️ Warning: Could not parse {CONFIG_PATH}: {e}")
    return {}

def load_project_info():
    """Reads project name and version from pyproject.toml."""
    if not Path("pyproject.toml").exists():
        raise click.ClickException("pyproject.toml not found in current directory.")
        
    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    
    project = pyproject.get("project", {})
    name = project.get("name", "unknown-package")
    version = project.get("version", "unknown-version")
    return name, version

def build_package():
    """Builds the package using the 'build' library API."""
    dist_path = Path("dist")
    if dist_path.exists():
        shutil.rmtree(dist_path)
    
    click.echo("📦 Building package (sdist and wheel)...")
    try:
        builder = ProjectBuilder(".")
        builder.build("sdist", "dist")
        builder.build("wheel", "dist")
    except Exception as e:
        raise click.ClickException(f"Build failed: {e}")

def upload_package(repo_url: str, is_pypi: bool = False, username=None, password=None):
    """Uses Twine's Python API to upload."""
    config = load_global_config()
    auth_defaults = config.get("auth", {})

    if is_pypi:
        username = "__token__"
        password = (password or os.getenv("PYPI_API_TOKEN") or auth_defaults.get("pypi_token"))
    else:
        username = (username or os.getenv("ARTIFACTORY_USERNAME") or auth_defaults.get("artifactory_username") or click.prompt("🔐 Username"))
        password = (password or os.getenv("ARTIFACTORY_PASSWORD") or auth_defaults.get("artifactory_password") or click.prompt("🔐 Password", hide_input=True))

    if not password:
        raise click.ClickException("No password or token provided.")

    dist_files = [str(p) for p in Path("dist").glob("*") if p.is_file()]
    click.echo(f"🚀 Uploading to {repo_url} as {username}...")

    settings = Settings(
        repository_url=repo_url,
        username=username,
        password=password,
        non_interactive=True,
        disable_progress_bar=False,
        keyring_privileged=False
    )

    try:
        twine_upload(settings, dist_files)
    except Exception:
        click.echo("\n❌ Upload failed.")
        raise click.Abort()

@click.command()
@click.argument("environment", required=False)
@click.option("--yes", is_flag=True, help="Skip confirmation prompts.")
@click.option("--force", is_flag=True, help="Allow deployment even if git is dirty.")
def main(environment, yes, force):
    """Deployer for Artifactory and PyPI with Git safety checks."""
    config = load_global_config()
    artifactory_urls = config.get("artifactory", {})
    
    available_envs = list(artifactory_urls.keys()) + ["pypi"]
    if artifactory_urls:
        available_envs.append("all")

    if not environment:
        click.echo(f"Usage: tts-deploy-lib [{'|'.join(available_envs)}]")
        return

    # --- 1. Git Safety Check ---
    # We enforce a clean git unless --force is used
    check_git_status(force=force)

    name, version = load_project_info()

    # --- 2. Deployment Logic ---
    if environment == "pypi":
        if yes or click.confirm(f"🚀 OFFICIAL PUBLIC RELEASE: {name} v{version}. Proceed?"):
            build_package()
            upload_package(PYPI_URL, is_pypi=True)

    elif environment == "all" and artifactory_urls:
        auth_defaults = config.get("auth", {})
        user = os.getenv("ARTIFACTORY_USERNAME") or auth_defaults.get("artifactory_username") or click.prompt("🔐 Username")
        pwd = os.getenv("ARTIFACTORY_PASSWORD") or auth_defaults.get("artifactory_password") or click.prompt("🔐 Password", hide_input=True)
        
        build_package() 
        for env_name, url in artifactory_urls.items():
            click.echo(f"\n--- {env_name} ---")
            upload_package(url, username=user, password=pwd)

    elif environment in artifactory_urls:
        url = artifactory_urls[environment]
        build_package()
        upload_package(url)
        click.echo(f"✅ Deployment to {environment} successful.")

    else:
        click.echo(f"❌ Unknown environment '{environment}'.")

if __name__ == "__main__":
    main()