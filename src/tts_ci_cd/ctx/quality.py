"""Standards-aware quality reports and explicit threshold checks."""

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from tts_ci_cd.ctx.analysis import RepositoryAnalysisResult, analyze_repository
from tts_ci_cd.ctx.test_quality import TestQualityAnalyzer


_POLICY_PATH = Path(__file__).parent / "resources" / "standards" / "quality_policy.json"


class QualityPolicy:
    """Versioned thresholds and policy identifiers for local quality checks."""

    def __init__(self, data: Mapping[str, Any]) -> None:
        self.version = str(data["version"])
        self.revision = str(data["revision"])
        self.policy_ids = tuple(str(item) for item in data["policy_ids"])
        self.thresholds = dict(data["thresholds"])

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "QualityPolicy":
        """Load the packaged quality policy without network access."""
        policy_path = path or _POLICY_PATH
        with policy_path.open("r") as policy_file:
            return cls(json.load(policy_file))

    def to_dict(self) -> Dict[str, Any]:
        """Return the stable policy representation."""
        return {
            "policy_ids": list(self.policy_ids),
            "revision": self.revision,
            "thresholds": dict(sorted(self.thresholds.items())),
            "version": self.version,
        }


def combined_quality(repository: str, standards_revision: str) -> RepositoryAnalysisResult:
    """Combine documentation and test-quality analyzers in one result."""
    documentation = analyze_repository(repository, standards_revision=standards_revision)
    tests = TestQualityAnalyzer(repository).analyze()
    metrics = dict(documentation.metrics)
    metrics.update({"test_{}".format(name): value for name, value in tests.metrics.items()})
    return RepositoryAnalysisResult(
        scope=documentation.scope,
        standards_revision=standards_revision,
        metrics=metrics,
        findings=tuple(documentation.findings) + tuple(tests.findings),
    )


def coverage_result(repository: str, standards_revision: str) -> RepositoryAnalysisResult:
    """Return a result focused on documentation and test coverage metrics."""
    result = TestQualityAnalyzer(repository).analyze()
    metrics = {name: value for name, value in result.metrics.items() if "coverage" in name or name in ("test_files", "source_files")}
    findings = tuple(finding for finding in result.findings if finding.code.startswith("testing.coverage."))
    return RepositoryAnalysisResult(str(Path(repository).expanduser().resolve()), standards_revision, metrics, findings)


def ranked_result(repository: str, standards_revision: str) -> RepositoryAnalysisResult:
    """Return combined findings in deterministic actionable order."""
    result = combined_quality(repository, standards_revision)
    return RepositoryAnalysisResult(result.scope, result.standards_revision, result.metrics, result.findings)


def threshold_violations(result: RepositoryAnalysisResult, policy: QualityPolicy) -> Tuple[str, ...]:
    """Return threshold descriptions without changing the diagnostic result."""
    errors = sum(1 for finding in result.findings if finding.severity == "error")
    warnings = sum(1 for finding in result.findings if finding.severity == "warning")
    violations = []
    if errors > int(policy.thresholds["max_error_findings"]):
        violations.append("error findings exceed policy threshold")
    if warnings > int(policy.thresholds["max_warning_findings"]):
        violations.append("warning findings exceed policy threshold")
    coverage = result.metrics.get("test_coverage_line_rate")
    if coverage is not None and float(coverage) < float(policy.thresholds["minimum_coverage_line_rate"]):
        violations.append("coverage is below policy threshold")
    return tuple(violations)
