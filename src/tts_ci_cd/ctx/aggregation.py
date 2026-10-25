"""Deterministic repository, workspace, and related-scope aggregation."""

from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from tts_ci_cd.ctx import config
from tts_ci_cd.ctx.analysis import AnalysisFinding, RepositoryAnalysisResult
from tts_ci_cd.ctx.quality import combined_quality


class ScopeAnalysisResult:
    """Versioned aggregate containing consistent per-repository results."""

    def __init__(self, scope: str, standards_revision: str, repositories: Iterable[RepositoryAnalysisResult], findings: Iterable[AnalysisFinding] = ()) -> None:
        self.version = "1.0"
        self.scope = scope
        self.standards_revision = standards_revision
        self.repositories = tuple(repositories)
        self.findings = tuple(findings)

    def to_dict(self) -> Dict[str, object]:
        return {
            "findings": [finding.to_dict() for finding in self.findings],
            "repositories": [repository.to_dict() for repository in self.repositories],
            "scope": self.scope,
            "standards_revision": self.standards_revision,
            "version": self.version,
        }

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


class ScopeResolver:
    """Resolve named quality scopes without network access."""

    def __init__(self, workspace_root: Optional[Path] = None, adapts: Optional[Mapping[str, str]] = None) -> None:
        self.workspace_root = Path(workspace_root or config.get_workspace_root()).expanduser().resolve()
        self.adapts = dict(adapts or config.parse_workspace_map())

    def resolve(self, scope: str, repository: Optional[str] = None) -> Tuple[Path, ...]:
        target = Path(repository or ".").expanduser().resolve()
        if scope == "current":
            return (self._git_root(target),)
        if scope == "repository":
            if target.is_dir() and (target / ".git").exists():
                return (target,)
            matches = [path for path in config.list_git_repos(self.workspace_root) if path.name == (repository or "")]
            if matches:
                return (matches[0],)
            return ()
        if scope == "workspace":
            return tuple(config.list_git_repos(self.workspace_root))
        if scope == "related":
            start = self.resolve("repository", repository)[0] if self.resolve("repository", repository) else None
            if start is None:
                return ()
            names = {start.name}
            core = self.adapts.get(self._relative_name(start)) or self.adapts.get(start.name)
            if core:
                names.add(Path(core).name)
            for child, parent in self.adapts.items():
                if Path(parent).name in names:
                    names.add(Path(child).name)
            return tuple(path for path in config.list_git_repos(self.workspace_root) if path.name in names)
        raise ValueError("unsupported scope: {}".format(scope))

    def _git_root(self, path: Path) -> Path:
        current = path if path.is_dir() else path.parent
        for candidate in (current,) + tuple(current.parents):
            if (candidate / ".git").exists():
                return candidate
        raise ValueError("current path is not inside a Git repository: {}".format(path))

    def _relative_name(self, path: Path) -> str:
        try:
            return path.relative_to(self.workspace_root).as_posix()
        except ValueError:
            return path.name


def analyze_scope(scope: str, repository: Optional[str] = None, standards_revision: str = "documentation-maintenance-v1", resolver: Optional[ScopeResolver] = None) -> ScopeAnalysisResult:
    """Analyze every repository in a resolved scope."""
    if resolver is None:
        workspace_root = Path(repository).expanduser().resolve() if scope == "workspace" and repository else None
        resolver = ScopeResolver(workspace_root=workspace_root)
    try:
        paths = resolver.resolve(scope, repository)
    except (OSError, ValueError) as error:
        finding = AnalysisFinding("scope.invalid", "Unable to resolve scope: {}".format(error), "error", remediation="Choose current, repository, workspace, or related scope and provide an existing repository.", evidence=str(error))
        return ScopeAnalysisResult(scope, standards_revision, (), (finding,))
    if not paths:
        finding = AnalysisFinding("scope.repository_missing", "No repositories matched the requested scope.", "error", remediation="Provide an existing repository or rebuild the workspace index.", evidence=repository or scope)
        return ScopeAnalysisResult(scope, standards_revision, (), (finding,))
    return ScopeAnalysisResult(scope, standards_revision, tuple(combined_quality(str(path), standards_revision) for path in paths))
