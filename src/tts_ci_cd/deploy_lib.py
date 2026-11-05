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
from setuptools_scm import get_version
from twine.commands.upload import upload as twine_upload
from twine.settings import Settings

from tts_ci_cd.native_artifacts import NativeArtifactBuilder, NativeArtifactManifest

# Configuration Constants
CONFIG_PATH = Path.home() / ".tts_config/deploy_locations.yaml"
PYPI_URL = "https://upload.pypi.org/legacy/"

def check_git_status(force=False):
    """Checks if the git repository has uncommitted changes."""
    try:
        result = subprocess.check_output(["git", "status", "--porcelain"], stderr=subprocess.STDOUT).decode("utf-8").strip()
        
        if result:
            click.echo("⚠️  Git repository is dirty (uncommitted changes found):")
            click.echo(result)
            if force:
                click.echo("⏩ '--force' used. Proceeding anyway...")
            else:
                raise click.ClickException("Clean your git state before deploying or use --force.")
    except subprocess.CalledProcessError:
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
    """Read project name and version from pyproject.toml."""
    project_file = Path("pyproject.toml")
    if not project_file.exists():
        raise click.ClickException("pyproject.toml not found in current directory.")

    with project_file.open("rb") as f:
        pyproject = tomllib.load(f)

    project = pyproject.get("project", {})
    name = project.get("name", "unknown-package")
    version = project.get("version")
    if version is None and "version" in project.get("dynamic", []):
        try:
            version = get_version(root=str(project_file.parent))
        except LookupError as error:
            raise click.ClickException("Unable to determine the project version from source control.") from error
    if version is None:
        raise click.ClickException("pyproject.toml does not define a project version.")
    return name, version

def build_package(project_dir=Path(".")):
    """Builds the package using the 'build' library API."""
    project_dir = Path(project_dir)
    dist_path = project_dir / "dist"
    if dist_path.exists():
        shutil.rmtree(dist_path)
    
    click.echo("📦 Building package (sdist and wheel)...")
    try:
        builder = ProjectBuilder(str(project_dir))
        builder.build("sdist", str(dist_path))
        builder.build("wheel", str(dist_path))
        return [path for path in dist_path.iterdir() if path.is_file()]
    except Exception as e:
        raise click.ClickException(f"Build failed: {e}")

def build_release_artifacts(manifest_path=None):
    """Build the wrapper and native packages declared by a manifest."""
    artifacts = build_package()
    if manifest_path is None:
        return artifacts

    manifest = NativeArtifactManifest.load(Path(manifest_path))
    builder = NativeArtifactBuilder()
    projects = []
    for spec in manifest.builds:
        builder.build(manifest, spec)
        projects.append(manifest.path.parent / spec.package.project)
    for project in projects:
        artifacts.extend(build_package(project))
    return artifacts

def upload_package(repo_url: str, is_pypi: bool = False, username=None, password=None, verbose=False, dist_files=None):
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

    if dist_files is None:
        dist_files = [str(p) for p in Path("dist").glob("*") if p.is_file()]
    else:
        dist_files = [str(path) for path in dist_files]
    click.echo(f"🚀 Uploading to {repo_url} as {username}...")

    # Set verbose logging if requested
    settings = Settings(
        repository_url=repo_url,
        username=username,
        password=password,
        non_interactive=True,
        disable_progress_bar=False,
        keyring_privileged=False,
        verbose=verbose  # Pass the verbose flag here
    )

    try:
        twine_upload(settings, dist_files)
    except Exception as e:
        if verbose:
            click.echo(f"❌ Detailed Error: {e}")
        click.echo("\n❌ Upload failed.")
        raise click.Abort()

@click.command()
@click.argument("environment", required=False)
@click.option("--yes", is_flag=True, help="Skip confirmation prompts.")
@click.option("--force", is_flag=True, help="Allow deployment even if git is dirty.")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output for build and upload.")
@click.option(
    "--native-manifest",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Build native artifacts declared by a TTS build manifest.",
)
def main(environment, yes, force, verbose, native_manifest):
    """Deployer for Artifactory and PyPI with Git safety checks."""
    config = load_global_config()
    artifactory_urls = config.get("artifactory", {})
    
    available_envs = list(artifactory_urls.keys()) + ["pypi"]
    if artifactory_urls:
        available_envs.append("all")

    if not environment:
        click.echo(f"Usage: tts-deploy-lib [{'|'.join(available_envs)}] [-v/--verbose]")
        return

    # --- 1. Git Safety Check ---
    check_git_status(force=force)

    name, version = load_project_info()

    # --- 2. Deployment Logic ---
    if environment == "pypi":
        if yes or click.confirm(f"🚀 OFFICIAL PUBLIC RELEASE: {name} v{version}. Proceed?"):
            artifacts = build_release_artifacts(native_manifest)
            upload_package(
                PYPI_URL,
                is_pypi=True,
                verbose=verbose,
                dist_files=artifacts,
            )

    elif environment == "all" and artifactory_urls:
        auth_defaults = config.get("auth", {})
        user = os.getenv("ARTIFACTORY_USERNAME") or auth_defaults.get("artifactory_username") or click.prompt("🔐 Username")
        pwd = os.getenv("ARTIFACTORY_PASSWORD") or auth_defaults.get("artifactory_password") or click.prompt("🔐 Password", hide_input=True)
        
        artifacts = build_release_artifacts(native_manifest)
        for env_name, url in artifactory_urls.items():
            click.echo(f"\n--- {env_name} ---")
            upload_package(
                url,
                username=user,
                password=pwd,
                verbose=verbose,
                dist_files=artifacts,
            )

    elif environment in artifactory_urls:
        url = artifactory_urls[environment]
        artifacts = build_release_artifacts(native_manifest)
        upload_package(url, verbose=verbose, dist_files=artifacts)
        click.echo(f"✅ Deployment to {environment} successful.")

    else:
        click.echo(f"❌ Unknown environment '{environment}'.")

if __name__ == "__main__":
    main()