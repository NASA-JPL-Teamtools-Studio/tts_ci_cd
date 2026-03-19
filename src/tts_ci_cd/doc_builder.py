#!/usr/bin/env python3
"""
Documentation Builder Tool

This script builds documentation for repositories defined in a YAML file
and can optionally push them to GitHub Pages.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import shutil
import io
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import logging
import docker
from docker.errors import DockerException, ImageNotFound, APIError

# Import the base RepoManager class
from .repo_manager import RepoManager, RepoInfo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("doc_builder")

# Documentation build dependencies
DOC_DEPS = [
    'sphinx', 
    'sphinx-rtd-theme', 
    'pydata-sphinx-theme',
    'myst-parser', 
    'toml', 
    'setuptools', 
    'wheel',
    'GitPython',
    'jinja2',
    'packaging'
]

# Default pip index URLs
DEFAULT_INDEX_URL = "https://pypi.org/simple"

class DocBuilder(RepoManager):
    """Documentation builder class.
    
    Extends the RepoManager base class to add documentation building capabilities.
    """
    
    def __init__(self, config_path: Optional[Path] = None, extra_index_url: Optional[str] = None, 
                 pypi_token: Optional[str] = None, trusted_host: Optional[str] = None,
                 interactive: bool = False):
        """
        Initialize the DocBuilder.
        
        Args:
            config_path: Path to the YAML configuration file.
            extra_index_url: Additional PyPI index URL for private packages.
            pypi_token: Authentication token for PyPI or Artifactory.
            trusted_host: Host to trust with self-signed certificates.
            interactive: If True, drop into an interactive shell in the container before finishing.
        """
        # Initialize the base class
        super().__init__(config_path)
        
        # DocBuilder specific attributes
        self.extra_index_url = extra_index_url
        self.pypi_token = pypi_token
        self.trusted_host = trusted_host
        
        # Directory for temporary files
        self.temp_dir = None
        
        # Docker client
        self.docker_client = None
        
        # Interactive mode
        self.interactive = interactive

    # Methods like load_config, load_repos, construct_git_url, and clone_repo
    # are now inherited from RepoManager
        
    def build_docs(self, repo_dir: Path, output_dir: Path, push: bool = False, ignore_errors: bool = True) -> bool:
        """
        Build documentation for a repository.
        
        Args:
            repo_dir: Path to the repository.
            output_dir: Directory to store output files.
            push: Whether to push the documentation to GitHub Pages.
            ignore_errors: Whether to continue if individual versions have errors.
            
        Returns:
            True if successful, False otherwise.
        """
        # Check if we're running in GitHub Actions
        in_github_actions = os.environ.get('GITHUB_ACTIONS') == 'true'
        
        # Copy the build_sphinx_docs.py script to the repo
        script_path = Path(__file__).parent / "build_sphinx_docs.py"
        template_path = Path(__file__).parent / "sphinx_index_template.html"
        
        if not script_path.exists():
            logger.error(f"Documentation build script not found: {script_path}")
            return False
            
        if not template_path.exists():
            logger.error(f"HTML template not found: {template_path}")
            return False
        
        if in_github_actions:
            # In GitHub Actions, build directly
            return self._build_docs_directly(repo_dir, script_path, template_path, push, ignore_errors)
        else:
            # For local execution, use Docker
            return self._build_docs_with_docker(repo_dir, script_path, template_path, push, ignore_errors)
    
    def _build_docs_directly(self, repo_dir: Path, script_path: Path, template_path: Path, push: bool, ignore_errors: bool = True) -> bool:
        """
        Build documentation directly without Docker.
        
        Args:
            repo_dir: Path to the repository.
            script_path: Path to the build script.
            template_path: Path to the HTML template.
            push: Whether to push the documentation to GitHub Pages.
            ignore_errors: Whether to continue if individual versions have errors.
            
        Returns:
            True if successful, False otherwise.
        """
        # Copy the build script and template to the repository
        repo_script_path = repo_dir / "build_sphinx_docs.py"
        repo_template_path = repo_dir / "sphinx_index_template.html"
        
        shutil.copy(script_path, repo_script_path)
        shutil.copy(template_path, repo_template_path)
        
        # Build the documentation
        logger.info(f"Building documentation directly for {repo_dir.name}...")
        cmd = [sys.executable, "build_sphinx_docs.py"]
        
        if push:
            cmd.append("--push")
            
        if not ignore_errors:
            cmd.append("--no-ignore-errors")
        
        try:
            subprocess.run(
                cmd,
                cwd=repo_dir,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info(f"Documentation built successfully for {repo_dir.name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to build documentation for {repo_dir.name}: {e.stderr.decode()}")
            return False
        finally:
            # Clean up temporary files
            if repo_script_path.exists():
                repo_script_path.unlink()
            if repo_template_path.exists():
                repo_template_path.unlink()
    
    def _build_docs_with_docker(self, repo_dir: Path, script_path: Path, template_path: Path, push: bool, ignore_errors: bool = True) -> bool:
        """
        Build documentation using Docker.
        
        Args:
            repo_dir: Path to the repository.
            script_path: Path to the build script.
            template_path: Path to the HTML template.
            push: Whether to push the documentation to GitHub Pages.
            ignore_errors: Whether to continue even if individual versions have errors (like run_doc_builder does).
            
        Returns:
            True if successful, False otherwise.
        """
        logger.info(f"Building documentation with Docker for {repo_dir.name}...")
        
        # Prepare pip install commands with extra index URL if provided
        pip_install_cmd = "pip install --no-cache-dir"
        
        # Handle trusted host for self-signed certificates
        trusted_host_option = ""
        if self.trusted_host:
            trusted_host_option = f" --trusted-host {self.trusted_host}"
            logger.info(f"Using trusted host: {self.trusted_host}")
        elif self.extra_index_url and "artifactory" in self.extra_index_url.lower():
            # Auto-extract host from Artifactory URL for convenience
            from urllib.parse import urlparse
            parsed_url = urlparse(self.extra_index_url)
            host = parsed_url.netloc.split('@')[-1]  # Remove any auth info
            trusted_host_option = f" --trusted-host {host}"
            logger.info(f"Auto-configuring trusted host: {host}")
        
        # Handle extra index URL
        if self.extra_index_url:
            # Check if this is Artifactory URL (needs special handling)
            if "artifactory" in self.extra_index_url.lower():
                # Try to extract Artifactory URL components for better auth
                from urllib.parse import urlparse
                parsed_url = urlparse(self.extra_index_url)
                
                # If URL contains credentials, extract them
                netloc = parsed_url.netloc
                if "@" in netloc:
                    # URL already contains auth - use as is
                    pip_install_cmd += f" --extra-index-url {self.extra_index_url}{trusted_host_option}"
                else:
                    # No auth in URL - check for environment variables
                    artifactory_token = None
                    for env_var in ['ARTIFACTORY_TOKEN', 'ARTIFACTORY_API_KEY', 'ARTIFACTORY_PASSWORD']:
                        if env_var in os.environ:
                            artifactory_token = os.environ[env_var]
                            logger.info(f"Using Artifactory token from {env_var}")
                            break
                    
                    # Construct authenticated URL if we have a token
                    if self.pypi_token:
                        # Use provided token
                        user = os.environ.get('ARTIFACTORY_USER', 'token')
                        auth_url = f"{parsed_url.scheme}://{user}:{self.pypi_token}@{netloc}{parsed_url.path}"
                        pip_install_cmd += f" --extra-index-url {auth_url}{trusted_host_option}"
                        logger.info("Using provided PyPI token for Artifactory authentication")
                    elif artifactory_token:
                        # Use token from environment
                        user = os.environ.get('ARTIFACTORY_USER', 'token')
                        auth_url = f"{parsed_url.scheme}://{user}:{artifactory_token}@{netloc}{parsed_url.path}"
                        pip_install_cmd += f" --extra-index-url {auth_url}{trusted_host_option}"
                        logger.info("Using environment token for Artifactory authentication")
                    else:
                        # No auth - use as provided and hope for netrc or pip.conf
                        pip_install_cmd += f" --extra-index-url {self.extra_index_url}{trusted_host_option}"
                        logger.info("Using Artifactory URL without explicit authentication")
            else:
                # Not Artifactory - use as is with trusted host if provided
                pip_install_cmd += f" --extra-index-url {self.extra_index_url}{trusted_host_option}"
        
        # Create a temporary Dockerfile with minimal steps to avoid hanging
        dockerfile_content = f"""FROM python:3.13-slim

# Set environment variables for better network behavior
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHTTPSVERIFY=0

# Install system dependencies with timeouts and no recommends
RUN apt-get update --quiet && \
    apt-get install -y --no-install-recommends git openssh-client make curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Setup SSH and Git config for private repositories
RUN mkdir -p /root/.ssh && \
    chmod 700 /root/.ssh && \
    echo "StrictHostKeyChecking no" > /root/.ssh/config && \
    chmod 600 /root/.ssh/config

# Set working directory
WORKDIR /workspace

# NOTE: Python dependencies will be installed at runtime, not during image build
# This dramatically speeds up the image build process
"""
        
        dockerfile_path = Path(self.temp_dir) / "Dockerfile.sphinx"
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile_content)
        
        # Build the Docker image
        image_tag = f"sphinx-doc-builder-{repo_dir.name}:latest"
        try:
            # First check if image already exists to avoid rebuilding
            try:
                image = self.docker_client.images.get(image_tag)
                logger.info(f"Using existing Docker image: {image_tag}")
            except ImageNotFound:
                # Need to build the image
                logger.info("Building Docker image for documentation (this might take a moment)...")
                
                # Create a build context from the Dockerfile
                with open(dockerfile_path, 'rb') as df:
                    # Build the Docker image with a timeout
                    try:
                        # Always log the build output now for better debugging
                        logger.info("Docker build starting - detailed logs follow:")
                        image, build_logs = self.docker_client.images.build(
                            fileobj=io.BytesIO(df.read()),
                            tag=image_tag,
                            rm=True,
                            forcerm=True,
                            pull=True,  # Always try to pull latest base image
                            buildargs={
                                "BUILDKIT_INLINE_CACHE": "1"  # Enable cache
                            }
                        )
                        
                        # Always log build output for better debugging
                        for log in build_logs:
                            if 'stream' in log and log['stream'].strip():
                                logger.info(f"[Docker Build] {log['stream'].strip()}")
                            elif 'error' in log:
                                logger.error(f"[Docker Build Error] {log['error'].strip()}")
                    except Exception as e:
                        logger.error(f"Docker build error: {str(e)}")
                        # Provide more helpful message
                        if "context canceled" in str(e).lower():
                            logger.error("Build timed out or was interrupted")
                        elif "connection" in str(e).lower():
                            logger.error("Network connectivity issue - check your connection to Docker and registries")
                        raise
        except (DockerException, APIError) as e:
            logger.error(f"Failed to build Docker image: {str(e)}")
            return False
        
        # Copy build script and template to repo
        repo_script_path = repo_dir / "build_sphinx_docs.py"
        repo_template_path = repo_dir / "sphinx_index_template.html"
        
        shutil.copy(script_path, repo_script_path)
        shutil.copy(template_path, repo_template_path)
        
        # Prepare volumes and environment for the container
        # Mount the repository at /workspace/{group}/{name} to match the expected structure
        repo_name = repo_dir.name
        repo_group = repo_dir.parent.name
        container_path = f"/workspace/{repo_group}/{repo_name}"
        
        # Create a more structured mount point
        volumes = {str(repo_dir): {'bind': container_path, 'mode': 'rw'}}
        
        # Prepare environment variables (for PyPI token)
        environment = {}
        if self.pypi_token:
            environment['PIP_INDEX_URL'] = f"https://__token__:{self.pypi_token}@pypi.org/simple/"
            logger.info("Using PyPI token for authentication")
        
        # Always mount SSH directory for git operations (cloning dependencies, etc.)
        ssh_path = os.path.expanduser("~/.ssh")
        if os.path.exists(ssh_path):
            volumes[ssh_path] = {'bind': '/root/.ssh', 'mode': 'ro'}
            logger.info("Mounting SSH credentials for Git operations")
        else:
            logger.warning("SSH directory not found at ~/.ssh - Git operations may fail")
        
        # Mount Git configuration if it exists
        git_config_path = os.path.expanduser("~/.gitconfig")
        if os.path.exists(git_config_path):
            volumes[git_config_path] = {'bind': '/root/.gitconfig', 'mode': 'ro'}
            logger.info("Mounting Git configuration")
            
        # Mount pip configuration if it exists (for credentials)
        pip_config_paths = [
            os.path.expanduser("~/.pip/pip.conf"),  # Linux/Mac
            os.path.expanduser("~/.config/pip/pip.conf"),  # Linux/Mac alternative
            os.path.expanduser("~/Library/Application Support/pip/pip.conf"),  # Mac
            os.path.expanduser("~/.netrc"),  # netrc for pip auth
        ]
        
        for pip_path in pip_config_paths:
            if os.path.exists(pip_path):
                base_name = os.path.basename(os.path.dirname(pip_path))
                if base_name == ".pip" or base_name == "pip":
                    # For pip.conf files
                    target_dir = "/root/.pip"
                    os.makedirs(f"{self.temp_dir}/.pip", exist_ok=True)
                    shutil.copy(pip_path, f"{self.temp_dir}/.pip/pip.conf")
                    volumes[f"{self.temp_dir}/.pip"] = {'bind': target_dir, 'mode': 'ro'}
                    logger.info(f"Mounting pip configuration from {pip_path}")
                elif os.path.basename(pip_path) == ".netrc":
                    # For .netrc file
                    volumes[pip_path] = {'bind': '/root/.netrc', 'mode': 'ro'}
                    logger.info("Mounting .netrc file for authentication")
        
        # Prepare command - now with a setup script that includes more verbose logging
        ignore_errors_flag = ' --no-ignore-errors' if not ignore_errors else ''
        
        # Add a sleep command at the end if interactive mode is enabled
        interactive_wait = ""
        if self.interactive:
            interactive_wait = """
        # Keep container running for interactive mode
        if [ -f "/.dockerenv" ]; then
            echo "=== Build completed, container ready for interactive session ==="
            echo "Container will wait for 1 hour or until manually exited"
            # Sleep but allow the container to be stopped gracefully
            sleep 3600 & wait
        fi
        """
        
        setup_script = f"""
        #!/bin/bash
        set -e  # Exit on error for the setup part
        set -x  # Echo commands for debugging
        
        echo "=== Installing documentation dependencies ==="
        # First install doc dependencies
        {pip_install_cmd} {' '.join(DOC_DEPS)}
        
        echo "=== Installing repository package ==="
        # Then install the package with the mounted credentials
        cd {container_path} && {pip_install_cmd} -e .
        
        echo "=== Running documentation builder ==="
        # Run the documentation builder using the script we copied to the repo directory
        python {container_path}/build_sphinx_docs.py{' --push' if push else ''}{ignore_errors_flag}
        {interactive_wait}
        """
        
        setup_script_path = Path(self.temp_dir) / f"setup_{repo_dir.name}.sh"
        with open(setup_script_path, "w") as f:
            f.write(setup_script)
        os.chmod(setup_script_path, 0o755)  # Make executable
        
        volumes[str(setup_script_path)] = {'bind': '/setup.sh', 'mode': 'ro'}
        
        # Use bash to run our setup script
        command = ["/bin/bash", "/setup.sh"]
        
        try:
            # Run the container with a timeout
            logger.info(f"Running Docker container for {repo_dir.name}...")
            # Add this message to help users understand what's happening
            logger.info("This will install packages inside the container - it may take several minutes")
            
            container = self.docker_client.containers.run(
                image=image_tag,
                command=command,
                volumes=volumes,
                environment=environment,
                remove=False,  # Don't auto-remove for better debugging
                detach=True,
                tty=True,      # Enable TTY for interactive mode
                stdin_open=True  # Keep STDIN open for interactive mode
            )
            
            # Set a timeout for the container run
            import threading
            timeout_sec = 600  # 10 minutes timeout
            timeout_triggered = False
            
            def check_timeout():
                nonlocal timeout_triggered
                logger.warning(f"Container execution timed out after {timeout_sec} seconds")
                try:
                    container.stop(timeout=10)
                    timeout_triggered = True
                except Exception as e:
                    logger.error(f"Error stopping container: {str(e)}")
            
            # Set the timeout
            timer = threading.Timer(timeout_sec, check_timeout)
            timer.daemon = True
            timer.start()
            
            try:
                # Stream logs from the container with line buffering
                buffer = ""
                for log in container.logs(stream=True, follow=True):
                    decoded = log.decode('utf-8', errors='replace')
                    buffer += decoded
                    
                    # Process complete lines
                    if '\n' in buffer:
                        lines = buffer.split('\n')
                        # Keep the last incomplete line in the buffer
                        buffer = lines.pop()
                        
                        # Log complete lines
                        for line in lines:
                                line = line.replace('�', '-')
                                logger.info(f"[Docker] {line}")
                
                # Process any remaining content in the buffer
                if buffer.strip():
                    logger.info(f"[Docker] {buffer.strip()}")
                    
                # Cancel the timeout timer if we got here naturally
                timer.cancel()
                
                # If interactive mode is enabled, we need to handle the container differently
                if self.interactive:
                    # Don't wait for exit code yet, as we want to interact with the running container
                    logger.info(f"Documentation build process completed for {repo_dir.name}")
                    
                    # Check if container is still running
                    container.reload()
                    if container.status == "running":
                        logger.info("\n\n==== INTERACTIVE MODE ENABLED ====\n")
                        logger.info("Dropping you into an interactive shell in the container.")
                        logger.info("Type 'exit' to exit the shell and continue.\n")
                        
                        # Use Docker exec to create an interactive shell
                        import subprocess
                        try:
                            # Use subprocess to create an interactive terminal
                            subprocess.run(
                                ["docker", "exec", "-it", container.id, "/bin/bash"],
                                check=False  # Don't raise exception on non-zero exit
                            )
                            logger.info("\n\n==== EXITED INTERACTIVE SHELL ====\n")
                        except Exception as e:
                            logger.error(f"Failed to create interactive shell: {str(e)}")
                    else:
                        logger.error("Container is not running anymore. Cannot start interactive shell.")
                        logger.error("Try adding a sleep or wait command at the end of your setup script.")
                    
                # Now get the exit code
                result = container.wait(timeout=10)
                exit_code = result.get('StatusCode', 1)
                
                if timeout_triggered:
                    logger.error("Container execution timed out - see previous logs for details")
                    return False
                elif exit_code == 0:
                    logger.info(f"Documentation built successfully with Docker for {repo_dir.name}")
                    return True
                else:
                    logger.error(f"Docker container exited with code {exit_code}")
                    # Try to fetch the last few logs for more context
                    try:
                        final_logs = container.logs(tail=20).decode('utf-8', errors='replace')
                        logger.error(f"Last container logs:\n{final_logs}")
                    except Exception:
                        pass
                    
                    # If interactive mode is enabled, drop into a shell even on failure
                    if self.interactive:
                        # Check if container is still running
                        try:
                            container.reload()
                            if container.status == "running":
                                logger.info("\n\n==== INTERACTIVE MODE ENABLED (DEBUG FAILURE) ====\n")
                                logger.info("Dropping you into an interactive shell to debug the failure.")
                                logger.info("Type 'exit' to exit the shell and continue.\n")
                                
                                import subprocess
                                try:
                                    subprocess.run(
                                        ["docker", "exec", "-it", container.id, "/bin/bash"],
                                        check=False
                                    )
                                    logger.info("\n\n==== EXITED INTERACTIVE SHELL ====\n")
                                except Exception as e:
                                    logger.error(f"Failed to create interactive shell: {str(e)}")
                            else:
                                logger.error("\n\n==== CANNOT START INTERACTIVE SHELL ====\n")
                                logger.error("Container exited before interactive shell could be started.")
                                logger.error("The build failed and the container has already stopped.")
                        except Exception as e:
                            logger.error(f"Error checking container status: {str(e)}")
                    
                    return False
            finally:
                # Clean up the container if still running
                try:
                    container.remove(force=True)
                except Exception:
                    pass
        except (DockerException, APIError) as e:
            logger.error(f"Failed to run Docker container: {str(e)}")
            # Provide more specific error information
            if "network timeout" in str(e).lower():
                logger.error("Network timeout - check your connection to Docker and package repositories")
            return False
        finally:
            # Clean up temporary files
            if repo_script_path.exists():
                repo_script_path.unlink()
            if repo_template_path.exists():
                repo_template_path.unlink()
    
    def check_docker_availability(self) -> None:
        """
        Check if Docker is available and exit immediately if it's not.
        """
        # Check if we're running in GitHub Actions
        in_github_actions = os.environ.get('GITHUB_ACTIONS') == 'true'
        
        if not in_github_actions:
            # For local execution, Docker is required
            logger.info("Checking Docker availability...")
            try:
                # Initialize Docker client
                self.docker_client = docker.from_env()
                # Get Docker version info
                version_info = self.docker_client.version()
                docker_version = f"Docker {version_info.get('Version', 'unknown')}"
                logger.info(f"Docker is available: {docker_version}")
            except DockerException as e:
                logger.error(f"ERROR: Docker is required but not available: {str(e)}")
                logger.error("Documentation builder cannot run without Docker in local environments.")
                sys.exit(1)
    
    def ensure_dependencies(self) -> None:
        """
        Ensure all required dependencies are installed.
        """
        # Check if we're running in GitHub Actions
        in_github_actions = os.environ.get('GITHUB_ACTIONS') == 'true'
        
        if in_github_actions:
            # In GitHub Actions, install dependencies directly
            logger.info("Running in GitHub Actions - installing dependencies directly...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade"] + DOC_DEPS,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        else:
            # For local execution, Docker will handle the dependencies
            logger.info("Running locally - Docker will handle dependencies")
    
    def prepare_environment(self) -> None:
        """
        Prepare the build environment.
        """
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {self.temp_dir}")
        
        # Ensure dependencies are available
        self.ensure_dependencies()
        
        # Check if we're running in GitHub Actions
        in_github_actions = os.environ.get('GITHUB_ACTIONS') == 'true'
        
        if not in_github_actions:
            # For local execution, prepare Docker
            logger.info("Preparing Docker environment for local execution...")
            # Create a Dockerfile in the temp directory if needed
            # This could be enhanced to generate a Dockerfile dynamically if needed
    
    def cleanup(self) -> None:
        """Clean up temporary resources."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
    
    def run(self, 
            repo_names: Optional[List[str]] = None, 
            workspace_dir: Optional[Path] = None,
            protocol: str = "ssh",
            push: bool = False,
            ignore_errors: bool = True) -> Dict[str, bool]:
        """
        Run the documentation build process.
        
        Args:
            repo_names: List of repository names to build documentation for. If None, all repositories will be processed.
            workspace_dir: Directory to clone repositories into. If None, a temporary directory will be used.
            protocol: Git protocol to use for cloning.
            push: Whether to push the documentation to GitHub Pages.
            ignore_errors: Whether to continue if individual versions have errors in conf.py.
            
        Returns:
            Dict mapping repository names to success status.
        """
        # Check Docker availability first - this will exit immediately if Docker is not available
        self.check_docker_availability()
        
        try:
            # Prepare the environment
            self.prepare_environment()
            
            # Use the provided workspace or create a temporary one
            if workspace_dir:
                work_dir = Path(workspace_dir)
                work_dir.mkdir(exist_ok=True, parents=True)
            else:
                work_dir = Path(self.temp_dir)
            
            # Determine which repositories to process
            repos_to_process = {}
            if repo_names:
                # Filter the repositories by name
                for name in repo_names:
                    if name in self.repos:
                        repos_to_process[name] = self.repos[name]
                    else:
                        logger.warning(f"Repository not found: {name}")
            else:
                # Process all repositories
                repos_to_process = self.repos
            
            # Process each repository
            results = {}
            output_dir = work_dir / "output"
            output_dir.mkdir(exist_ok=True)
            
            for repo_name, repo_info in repos_to_process.items():
                logger.info(f"Processing {repo_name}...")
                try:
                    # Clone the repository
                    repo_dir = self.clone_repo(repo_info, work_dir, protocol)
                    
                    # Build the documentation
                    success = self.build_docs(repo_dir, output_dir, push, ignore_errors)
                    results[repo_name] = success
                    
                    if success:
                        logger.info(f"Successfully built documentation for {repo_name}")
                    else:
                        logger.error(f"Failed to build documentation for {repo_name}")
                except Exception as e:
                    logger.error(f"Error processing {repo_name}: {str(e)}")
                    results[repo_name] = False
            
            # Summarize results
            success_count = sum(1 for success in results.values() if success)
            logger.info(f"Documentation build complete: {success_count}/{len(results)} successful")
            
            for repo_name, success in results.items():
                status = "✅ Success" if success else "❌ Failed"
                logger.info(f"{status}: {repo_name}")
            
            return results
        finally:
            # Always clean up
            self.cleanup()

def main():
    """Main entry point for the command-line tool."""
    parser = argparse.ArgumentParser(
        description="Documentation Builder - Generate and publish documentation for repositories",    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="Path to the YAML configuration file"
    )
    
    parser.add_argument(
        "--workspace",
        type=str,
        default=None,
        help="Directory to clone repositories into. If not provided, a temporary directory will be used"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all repositories"
    )

    parser.add_argument(
        "--repos",
        nargs="+",
        help="List of repository names to process. If not provided, all repositories will be processed"
    )
    
    parser.add_argument(
        "--protocol",
        choices=["ssh", "https"],
        default="ssh",
        help="Git protocol to use for cloning repositories"
    )
    
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push the generated documentation to GitHub Pages"
    )
    
    parser.add_argument(
        "--extra-index-url",
        type=str,
        help="Additional PyPI index URL for private packages"
    )
    
    parser.add_argument(
        "--pypi-token",
        type=str,
        help="Authentication token for PyPI or Artifactory"
    )
    
    parser.add_argument(
        "--trusted-host",
        type=str,
        help="Host to trust even without valid SSL certificates (for Artifactory)"
    )
        
    parser.add_argument(
        "--no-ignore-errors",
        action="store_true",
        help="Do not ignore syntax errors in conf.py and fail immediately"
    )
    
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Drop into an interactive shell in the container before finishing"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.repos and args.all:
        logger.error("--repos and --all are mutually exclusive. Please choose one or the other.")
        sys.exit(1)

    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Get PyPI token from environment if not provided via CLI
    pypi_token = args.pypi_token
    if not pypi_token:
        # Check common environment variable names for PyPI tokens
        for env_var in ['PYPI_TOKEN', 'ARTIFACTORY_TOKEN', 'ARTIFACTORY_API_KEY', 'PIP_TOKEN']:
            if env_var in os.environ:
                pypi_token = os.environ[env_var]
                logger.info(f"Using PyPI token from environment variable {env_var}")
                break
                
    # Check if artifactory URL is provided and no token
    if args.extra_index_url and "artifactory" in args.extra_index_url.lower() and not pypi_token:
        logger.warning("Artifactory URL specified but no token provided.")
        logger.warning("Authentication may fail. Consider setting ARTIFACTORY_TOKEN environment variable.")
        logger.warning("Example: export ARTIFACTORY_TOKEN=your_token_here")
    
    # Initialize the builder
    config_path = Path(args.config) if args.config else None
    builder = DocBuilder(
        config_path=config_path, 
        extra_index_url=args.extra_index_url,
        pypi_token=pypi_token,
        trusted_host=args.trusted_host,
        interactive=args.interactive
    )
    
    # Determine workspace directory
    workspace_dir = Path(args.workspace) if args.workspace else None
    
    # Run the builder
    builder.run(
        repo_names=args.repos,
        workspace_dir=workspace_dir,
        protocol=args.protocol,
        push=args.push,
        ignore_errors=not args.no_ignore_errors
    )

if __name__ == "__main__":
    main()
