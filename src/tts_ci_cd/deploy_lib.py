# Standard Library Imports
import os
import subprocess
import shutil
from pathlib import Path

# Installed Dependency Imports
import click
import yaml  # Requires: pip install pyyaml
import tomllib  # Keep this for reading pyproject.toml (standard in 3.11+)

# Configuration Constants
# Changed extension to .yaml
CONFIG_PATH = Path.home() / ".tts_config/deploy_locations.yaml"
PYPI_URL = "https://upload.pypi.org/legacy/"

def load_global_config():
    """Loads Artifactory URLs and Auth from the user's home directory YAML."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                # Use SafeLoader to prevent execution of arbitrary code in YAML
                return yaml.load(f, Loader=yaml.SafeLoader) or {}
        except Exception as e:
            click.echo(f"⚠️ Warning: Could not parse {CONFIG_PATH}: {e}")
    return {}

def load_project_info():
    """Reads project name and version from pyproject.toml."""
    if not Path("pyproject.toml").exists():
        click.echo("❌ Error: pyproject.toml not found in current directory.")
        raise click.Abort()
        
    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    
    project = pyproject.get("project", {})
    name = project.get("name", "unknown-package")
    version = project.get("version", "unknown-version")
    return name, version

def build_package(repo_url: str):
    """Cleans dist/ and builds the wheel/sdist."""
    dist_path = Path("dist")
    if dist_path.exists():
        shutil.rmtree(dist_path)
    
    click.echo(f"📦 Building package for {repo_url}...")
    os.environ["PIP_EXTRA_INDEX_URL"] = f"{repo_url}/simple"
    subprocess.check_call(["python", "-m", "build"])

def upload_package(repo_url: str, is_pypi: bool = False, username=None, password=None):
    """Handles the Twine upload using logic for either Artifactory or PyPI."""
    config = load_global_config()
    auth_defaults = config.get("auth", {})

    if is_pypi:
        username = "__token__"
        password = (password or 
                    os.getenv("PYPI_API_TOKEN") or 
                    auth_defaults.get("pypi_token"))
        
        if not password:
            password = click.prompt("🔐 Enter PyPI API Token", hide_input=True)
    else:
        username = (username or 
                    os.getenv("ARTIFACTORY_USERNAME") or 
                    auth_defaults.get("artifactory_username") or 
                    click.prompt("🔐 Enter Artifactory username"))
        
        password = (password or 
                    os.getenv("ARTIFACTORY_PASSWORD") or 
                    click.prompt("🔐 Enter Artifactory password", hide_input=True))

    click.echo(f"🚀 Uploading to {repo_url} as {username}")
    
    subprocess.check_call([
        "python", "-m", "twine", "upload",
        "--repository-url", repo_url,
        "-u", username, "-p", password,
        "dist/*"
    ])

@click.command()
@click.argument("environment", required=False)
def main(environment):
    """
    Deployer for Artifactory and PyPI using YAML config.
    """
    config = load_global_config()
    artifactory_urls = config.get("artifactory", {})
    
    available_envs = list(artifactory_urls.keys()) + ["pypi"]
    if artifactory_urls:
        available_envs.append("all")

    if not environment:
        click.echo(f"Usage: python deploy.py [{'|'.join(available_envs)}]")
        return

    name, version = load_project_info()

    if environment == "pypi":
        click.echo(f"🚀 OFFICIAL PUBLIC RELEASE: {name} v{version}")
        if click.confirm("This will be visible to the world. Proceed?"):
            build_package(PYPI_URL)
            upload_package(PYPI_URL, is_pypi=True)
            click.echo("✅ PyPI deployment complete.")

    elif environment == "all" and artifactory_urls:
        click.echo(f"🔧 Deploying {name} to all internal environments...")
        auth_defaults = config.get("auth", {})
        user = os.getenv("ARTIFACTORY_USERNAME") or auth_defaults.get("artifactory_username") or click.prompt("🔐 Username")
        pwd = os.getenv("ARTIFACTORY_PASSWORD") or click.prompt("🔐 Password", hide_input=True)
        
        for env_name, url in artifactory_urls.items():
            click.echo(f"\n--- Processing: {env_name} ---")
            build_package(url)
            upload_package(url, username=user, password=pwd)
        click.echo("\n✅ All internal deployments finished.")

    elif environment in artifactory_urls:
        url = artifactory_urls[environment]
        click.echo(f"🔧 Deploying {name} v{version} to [{environment}]")
        build_package(url)
        upload_package(url)
        click.echo(f"✅ Done.")

    else:
        click.echo(f"❌ Unknown environment '{environment}'.")
        click.echo(f"Check your YAML configuration at {CONFIG_PATH}")

if __name__ == "__main__":
    main()