"""Repository-scoped analysis and its versioned result contract."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple, Union


ANALYSIS_RESULT_VERSION = "1.0"
DEFAULT_STANDARDS_REVISION = "documentation-maintenance-v1"
RepositoryPath = Union[str, os.PathLike]


class RepositoryAnalysisConfig:
    """Configuration supplied to a repository analysis.

    Args:
        repository: Directory containing the repository to analyze.
        standards_revision: Human-readable revision of the applicable standard.
        resources: Optional named resources available to analyzers.
    """

    def __init__(
        self,
        repository: RepositoryPath,
        standards_revision: str = DEFAULT_STANDARDS_REVISION,
        resources: Optional[Mapping[str, Any]] = None,
    ) -> None:
        path = Path(repository).expanduser().resolve()
        if not path.is_dir():
            raise ValueError("repository must be an existing directory: {}".format(path))
        if not standards_revision:
            raise ValueError("standards_revision must not be empty")
        self.repository = path
        self.standards_revision = standards_revision
        self.resources = dict(resources or {})


class AnalysisFinding:
    """A stable, actionable observation emitted by an analyzer."""

    def __init__(
        self,
        code: str,
        message: str,
        severity: str = "info",
        path: Optional[str] = None,
        line: Optional[int] = None,
        remediation: Optional[str] = None,
        evidence: Optional[str] = None,
    ) -> None:
        """Create a finding.

        Args:
            code: Stable identifier for the finding.
            message: Human-readable description of the observation.
            severity: Severity label for the observation.
            path: Optional source path associated with the observation.
            line: Optional source line associated with the observation.
            remediation: Optional guidance for addressing the observation.
            evidence: Optional source evidence supporting the observation.
        """
        self.code = code
        self.message = message
        self.severity = severity
        self.path = path
        self.line = line
        self.remediation = remediation
        self.evidence = evidence

    def to_dict(self) -> Dict[str, Any]:
        """Return the public JSON representation of this finding."""
        return {
            "code": self.code,
            "evidence": self.evidence,
            "line": self.line,
            "message": self.message,
            "path": self.path,
            "remediation": self.remediation,
            "severity": self.severity,
        }


class RepositoryAnalysisResult:
    """Versioned output returned by repository-scoped analysis."""

    def __init__(
        self,
        scope: str,
        standards_revision: str,
        metrics: Mapping[str, Union[int, float]],
        findings: Iterable[AnalysisFinding] = (),
        version: str = ANALYSIS_RESULT_VERSION,
    ) -> None:
        """Create a versioned analysis result.

        Args:
            scope: Repository or analysis scope represented by the result.
            standards_revision: Revision of the standards applied to analysis.
            metrics: Named integer metrics collected by the analyzer.
            findings: Observations produced by the analyzer.
            version: Version of the result contract.
        """
        self.version = version
        self.scope = scope
        self.standards_revision = standards_revision
        self.metrics = dict(metrics)
        self.findings = tuple(findings)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-compatible representation with a stable shape."""
        return {
            "findings": [finding.to_dict() for finding in self.findings],
            "metrics": dict(sorted(self.metrics.items())),
            "scope": self.scope,
            "standards_revision": self.standards_revision,
            "version": self.version,
        }

    def to_json(self) -> str:
        """Serialize the result deterministically for tools and CI."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


class RepositoryAnalyzer:
    """Analyze one repository while hiding analyzer implementation details."""

    def analyze(self, config: RepositoryAnalysisConfig) -> RepositoryAnalysisResult:
        """Return a deterministic baseline analysis for the configured repository.

        Args:
            config: Repository and standards configuration for this analysis.
        """
        files = sorted(
            path
            for path in config.repository.rglob("*")
            if path.is_file() and ".git" not in path.parts
        )
        python_files = [path for path in files if path.suffix == ".py"]
        from tts_ci_cd.ctx.metadata import MarkdownMetadataValidator

        metadata_validator = MarkdownMetadataValidator(config.repository)
        markdown_files = metadata_validator.markdown_files()
        test_files = [
            path
            for path in python_files
            if path.name.startswith("test_") or "tests" in path.parts
        ]
        metrics = {
            "files": len(files),
            "markdown_files": len(markdown_files),
            "python_files": len(python_files),
            "test_files": len(test_files),
        }
        findings = metadata_validator.validate()
        from tts_ci_cd.ctx.documentation_quality import DocumentationQualityAnalyzer

        findings += DocumentationQualityAnalyzer(config.repository).analyze(include_metadata=False)
        return RepositoryAnalysisResult(
            scope=str(config.repository),
            standards_revision=config.standards_revision,
            metrics=metrics,
            findings=findings,
        )


def analyze_repository(
    repository: RepositoryPath,
    standards_revision: str = DEFAULT_STANDARDS_REVISION,
    resources: Optional[Mapping[str, Any]] = None,
) -> RepositoryAnalysisResult:
    """Analyze a repository through the public repository-scoped seam.

    Args:
        repository: Directory containing the repository to analyze.
        standards_revision: Human-readable revision of the applicable standard.
        resources: Optional named resources available to analyzers.

    Returns:
        The versioned result produced for the repository.
    """
    config = RepositoryAnalysisConfig(repository, standards_revision, resources)
    return RepositoryAnalyzer().analyze(config)


def render_markdown(result: RepositoryAnalysisResult) -> str:
    """Render a human-readable report from a versioned analysis result.

    Args:
        result: Versioned analysis result to render.

    Returns:
        Human-readable Markdown report text.
    """
    lines = [
        "# Repository analysis",
        "",
        "- Scope: `{}`".format(result.scope),
        "- Standards revision: `{}`".format(result.standards_revision),
        "- Result version: `{}`".format(result.version),
        "",
        "## Metrics",
        "",
    ]
    lines.extend("- {}: {}".format(name, result.metrics[name]) for name in sorted(result.metrics))
    lines.extend(["", "## Findings", ""])
    if result.findings:
        for finding in result.findings:
            location = ""
            if finding.path:
                location = " ({}{})".format(
                    finding.path,
                    ":{}".format(finding.line) if finding.line is not None else "",
                )
            lines.append(
                "- [{}] `{}`: {}{}".format(
                    finding.severity, finding.code, finding.message, location
                )
            )
            if finding.evidence:
                lines.append("  - Evidence: {}".format(finding.evidence))
            if finding.remediation:
                lines.append("  - Next step: {}".format(finding.remediation))
    else:
        lines.append("No findings.")
    return "\n".join(lines) + "\n"
