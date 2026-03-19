"""Repository manager for TTS CI/CD tools.

This module provides a base class for managing Git repositories,
which is used by both DocBuilder and DevSetup.
"""

import sys
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from git import Repo, GitCommandError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("repo_manager")

# Default configuration
DEFAULT_GIT_HOST = "github.com"

class RepoInfo:
    """Class to hold repository information."""
    
    def __init__(self, name: str, repo_data: Dict[str, Any], group: str = ""):
        """Initialize repository information."""
        self.name = name
        self.repo_path = repo_data.get('repo_path', '')
        self.branch = repo_data.get('branch', 'main')
        self.dependencies = repo_data.get('dependencies', [])
        self.group = group
        self.git_url = None
        self.local_path = None

class RepoManager:
    """Base class for repository management.
    
    This class provides common functionality for managing Git repositories,
    including loading configuration, constructing Git URLs, and cloning repositories.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the RepoManager.
        
        Args:
            config_path: Path to the YAML configuration file.
        """
        self.config_path = config_path or Path(__file__).parent.joinpath("support_files/dev_setup.yaml")
        self.config = self.load_config(self.config_path)
        self.git_host = self.config.get('git_host', DEFAULT_GIT_HOST)
        self.repos = self.load_repos()
        self.extra_index_urls = self.config.get('extra_index_urls', [])
        
        # Cache for repository information
        self._group_cache = {}
        
        # Build the group cache
        self._build_group_cache()
    
    def _build_group_cache(self) -> None:
        """Build cache of repository groups for faster lookups."""
        for repo_name, repo_info in self.repos.items():
            self._group_cache[repo_name] = repo_info.group
    
    def load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load the configuration from a YAML file.
        
        Args:
            config_path: Path to the YAML configuration file.
            
        Returns:
            Dict containing the parsed YAML data.
            
        Raises:
            SystemExit: If the configuration file is not found or cannot be parsed.
        """
        if not config_path.exists():
            logger.error(f"Configuration file not found: {config_path}")
            sys.exit(1)
            
        with open(config_path, 'r') as f:
            try:
                return yaml.safe_load(f)
            except yaml.YAMLError as e:
                logger.error(f"Error parsing YAML configuration: {e}")
                sys.exit(1)
    
    def load_repos(self) -> Dict[str, RepoInfo]:
        """Load repository information from the configuration.
        
        Returns:
            Dict mapping repository names to RepoInfo objects.
        """
        repos = {}
        
        for group_name, group_content in self.config.items():
            if group_name not in ['git_host', 'extra_index_urls'] and isinstance(group_content, dict):
                for repo_name, repo_data in group_content.items():
                    repos[repo_name] = RepoInfo(repo_name, repo_data, group_name)
        
        return repos
    
    def find_repo_group(self, target: str) -> Optional[str]:
        """Find which group a repository belongs to in the configuration.
        
        Args:
            target: Name of the repository to find
            
        Returns:
            Group name or None if not found
        """
        return self._group_cache.get(target)
    
    def get_repo_info(self, target: str) -> Optional[RepoInfo]:
        """Get repository info from the configuration.
        
        Args:
            target: Name of the repository
            
        Returns:
            Repository information or None if not found
        """
        return self.repos.get(target)
    
    def get_recursive_dependencies(self, target: str, visited: Optional[Set[str]] = None, 
                                  resolved: Optional[List[str]] = None) -> List[str]:
        """Get all dependencies for a target repository recursively.
        
        Args:
            target: Target repository name
            visited: Set of already visited repositories (for recursion)
            resolved: List of resolved dependencies (for recursion)
            
        Returns:
            List of repository names in dependency order
        """
        if visited is None: visited = set()
        if resolved is None: resolved = []

        if target in visited:
            return resolved
        
        visited.add(target)
        
        repo_info = self.repos.get(target)
        if repo_info:
            for dep in repo_info.dependencies:
                if dep not in resolved:
                    self.get_recursive_dependencies(dep, visited, resolved)
            
            if target not in resolved:
                resolved.append(target)
        
        return resolved
    
    def construct_git_url(self, repo_path: str, protocol: str = "ssh", host: Optional[str] = None) -> str:
        """Construct a Git URL for the repository.
        
        Args:
            repo_path: Repository path in the format "org/repo".
            protocol: Git protocol to use ("ssh" or "https").
            host: Git host (defaults to self.git_host)
            
        Returns:
            Complete Git URL.
            
        Raises:
            ValueError: If the protocol is unknown.
        """
        if host is None:
            host = self.git_host
            
        # Clean any accidental .git suffix
        if repo_path.endswith(".git"):
            repo_path = repo_path[:-4]
            
        if protocol == "ssh":
            return f"git@{host}:{repo_path}.git"
        elif protocol == "https":
            return f"https://{host}/{repo_path}.git"
        else:
            raise ValueError(f"Unknown protocol: {protocol}")
    
    def clone_repo(self, repo: RepoInfo, workspace_dir: Path, protocol: str = "ssh") -> Path:
        """Clone a repository.
        
        Args:
            repo: Repository information.
            workspace_dir: Directory to clone into.
            protocol: Git protocol to use.
            
        Returns:
            Path to the cloned repository.
            
        Raises:
            GitCommandError: If there's an error with Git operations.
        """
        # Construct the URL
        git_url = self.construct_git_url(repo.repo_path, protocol)
        repo.git_url = git_url
        
        # Create the target directory
        group_dir = workspace_dir / repo.group
        group_dir.mkdir(exist_ok=True, parents=True)
        repo_dir = group_dir / repo.name
        repo.local_path = repo_dir
        
        # Clone if not already present
        if not repo_dir.exists():
            logger.info(f"Cloning {repo.name} from {git_url} (branch: {repo.branch})...")
            try:
                # Use GitPython to clone the repository
                Repo.clone_from(
                    url=git_url,
                    to_path=str(repo_dir),
                    branch=repo.branch
                )
            except GitCommandError as e:
                logger.error(f"Failed to clone {repo.name}: {str(e)}")
                raise
        else:
            logger.info(f"Repository {repo.name} already exists at {repo_dir}")
            
            # Update the repository to the latest version
            logger.info(f"Updating {repo.name} to the latest version...")
            try:
                git_repo = Repo(repo_dir)
                git_repo.git.fetch("--all")
                git_repo.git.checkout(repo.branch)
                git_repo.git.pull("origin", repo.branch)
            except GitCommandError as e:
                logger.error(f"Failed to update {repo.name}: {str(e)}")
                raise
        
        return repo_dir
    
    def merge_config(self, additional_config_path: Path) -> None:
        """Merge another configuration file into the current configuration.
        
        Args:
            additional_config_path: Path to the additional configuration file.
            
        Raises:
            SystemExit: If the additional configuration file is not found or cannot be parsed.
        """
        additional_data = self.load_config(additional_config_path)
        
        # Merge the configurations
        for group_name, group_content in additional_data.items():
            if group_name not in ['git_host', 'extra_index_urls'] and isinstance(group_content, dict):
                if group_name not in self.config:
                    self.config[group_name] = {}
                
                for repo_name, repo_info in group_content.items():
                    if repo_name not in self.config[group_name]:
                        self.config[group_name][repo_name] = repo_info
        
        # Update extra_index_urls if present
        if 'extra_index_urls' in additional_data:
            self.extra_index_urls.extend(additional_data['extra_index_urls'])
        
        # Reload repositories with the new configuration
        self.repos = self.load_repos()
        self._build_group_cache()
