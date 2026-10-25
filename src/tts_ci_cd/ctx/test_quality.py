"""Deterministic test-quality evidence for a repository."""

import ast
import json
import sqlite3
import subprocess
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

from tts_ci_cd.ctx.analysis import AnalysisFinding, RepositoryAnalysisResult


PathLike = Union[str, Path]
_TEST_MARKERS = {
    "unreviewed_ai": "unreviewed_ai_tests",
    "inspection": "inspection_tests",
    "skip": "skipped_tests",
    "xfail": "xfailed_tests",
}


class TestQualityAnalyzer:
    """Analyze test inventory, markers, certification, and coverage artifacts."""

    __test__ = False

    def __init__(self, repository: PathLike, coverage_path: Optional[PathLike] = None) -> None:
        """Create an analyzer for one repository.

        Args:
            repository: Root directory to inspect.
            coverage_path: Optional explicit coverage XML or JSON artifact.
        """
        self.repository = Path(repository).expanduser().resolve()
        if not self.repository.is_dir():
            raise ValueError("repository must be an existing directory: {}".format(self.repository))
        self.coverage_path = Path(coverage_path).expanduser().resolve() if coverage_path else None

    def analyze(
        self,
        run_tests: bool = False,
        test_command: Optional[Sequence[str]] = None,
    ) -> RepositoryAnalysisResult:
        """Return stable test-quality metrics and findings.

        Args:
            run_tests: Whether to run the explicitly supplied test command first.
            test_command: Test command used only when `run_tests` is true.
        """
        findings: List[AnalysisFinding] = []
        source_files = self._source_files()
        test_files = self._test_files()
        metrics: Dict[str, Union[int, float]] = {
            "source_files": len(source_files),
            "test_files": len(test_files),
            "matched_test_files": 0,
            "unmatched_source_files": 0,
            "public_symbols": 0,
            "referenced_symbols": 0,
            "unreferenced_symbols": 0,
            "unreviewed_ai_tests": 0,
            "inspection_tests": 0,
            "certified_inspection_artifacts": 0,
            "skipped_tests": 0,
            "xfailed_tests": 0,
            "coverage_artifact_present": 0,
        }

        if run_tests:
            findings.extend(self._run_tests(test_command))

        source_symbols = self._source_symbols(source_files)
        referenced_symbols = self._referenced_symbols(test_files, source_symbols)
        metrics["public_symbols"] = len(source_symbols)
        metrics["referenced_symbols"] = len(referenced_symbols)
        metrics["unreferenced_symbols"] = len(source_symbols - referenced_symbols)
        for symbol in sorted(source_symbols - referenced_symbols):
            findings.append(
                self._finding(
                    "testing.inventory.symbol_reference_missing",
                    "tests",
                    1,
                    "Public symbol `{}` has no textual test reference.".format(symbol),
                    "Add or identify a test that exercises `{}`.".format(symbol),
                )
            )

        for source in source_files:
            expected_name = "test_{}.py".format(source.stem)
            if any(test.name == expected_name for test in test_files):
                metrics["matched_test_files"] += 1
            else:
                metrics["unmatched_source_files"] += 1
                findings.append(
                    self._finding(
                        "testing.inventory.source_test_missing",
                        source.relative_to(self.repository).as_posix(),
                        1,
                        "No conventional test file found for {}.".format(source.name),
                        "Add a matching test_{}.py file or document the alternative test location.".format(source.stem),
                    )
                )

        for path in test_files:
            text = path.read_text(encoding="utf-8")
            relative = path.relative_to(self.repository).as_posix()
            marker_counts = self._test_case_marker_counts(text)
            for marker, metric in _TEST_MARKERS.items():
                count = marker_counts.get(marker, 0)
                metrics[metric] += count
            if marker_counts.get("inspection", 0) and not self._certified_inspection_artifacts():
                findings.append(
                    self._finding(
                        "testing.inspection.certification_missing",
                        relative,
                        1,
                        "Inspection test has no certified .sha256 artifact.",
                        "Review the inspection artifact and add its human certification sidecar.",
                    )
                )

        metrics["certified_inspection_artifacts"] = len(self._certified_inspection_artifacts())
        findings.extend(self._coverage_findings(metrics))
        ordered_findings = sorted(findings, key=lambda finding: (finding.code, finding.path or "", finding.line or 0, finding.message))
        integer_metrics = {key: value for key, value in metrics.items() if isinstance(value, int)}
        float_metrics = {key: value for key, value in metrics.items() if isinstance(value, float)}
        return RepositoryAnalysisResult(
            scope=str(self.repository),
            standards_revision="documentation-maintenance-v1",
            metrics=dict(integer_metrics, **float_metrics),
            findings=ordered_findings,
        )

    def _source_files(self) -> Tuple[Path, ...]:
        return tuple(path for path in sorted(self.repository.rglob("*.py")) if not self._is_test(path) and not self._excluded(path))

    def _test_files(self) -> Tuple[Path, ...]:
        return tuple(path for path in sorted(self.repository.rglob("*.py")) if self._is_test(path) and not self._excluded(path))

    def _source_symbols(self, paths: Iterable[Path]) -> Set[str]:
        symbols: Set[str] = set()
        for path in paths:
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
                    symbols.add(node.name)
        return symbols

    @staticmethod
    def _referenced_symbols(paths: Iterable[Path], symbols: Set[str]) -> Set[str]:
        referenced: Set[str] = set()
        for path in paths:
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in symbols:
                    referenced.add(node.id)
                elif isinstance(node, ast.Attribute) and node.attr in symbols:
                    referenced.add(node.attr)
        return referenced

    def _coverage_findings(self, metrics: Dict[str, Union[int, float]]) -> List[AnalysisFinding]:
        path = self.coverage_path or next((candidate for candidate in (self.repository / "coverage.xml", self.repository / "coverage.json", self.repository / ".coverage") if candidate.exists()), None)
        if path is None:
            return [self._finding("testing.coverage.missing", "", 1, "No coverage artifact was found.", "Provide coverage.xml or coverage.json, or run the opt-in test command that produces one.")]
        try:
            if path.suffix.lower() == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                if "line_rate" in data:
                    metrics["coverage_line_rate"] = float(data["line_rate"])
                    metrics["coverage_branch_rate"] = float(data.get("branch_rate", 0.0))
                else:
                    totals = data["totals"]
                    metrics["coverage_line_rate"] = float(totals["percent_covered"])
                    metrics["coverage_branch_rate"] = float(totals.get("percent_covered", 0.0))
            elif path.suffix.lower() == ".xml":
                root = ElementTree.fromstring(path.read_text(encoding="utf-8"))
                metrics["coverage_line_rate"] = float(root.attrib["line-rate"]) * 100.0
                metrics["coverage_branch_rate"] = float(root.attrib.get("branch-rate", 0.0)) * 100.0
            elif path.name == ".coverage":
                self._validate_sqlite_coverage(path)
            else:
                raise ValueError("unsupported coverage artifact format")
            metrics["coverage_artifact_present"] = 1
        except (OSError, KeyError, TypeError, ValueError, sqlite3.Error, ElementTree.ParseError) as error:
            return [self._finding("testing.coverage.malformed", path.relative_to(self.repository).as_posix(), 1, "Coverage artifact could not be parsed: {}".format(error), "Regenerate a valid coverage XML, JSON, or SQLite .coverage artifact.")]
        return []

    @staticmethod
    def _validate_sqlite_coverage(path: Path) -> None:
        connection = sqlite3.connect(str(path))
        try:
            tables = {row[0] for row in connection.execute("select name from sqlite_master where type = 'table'")}
            if not {"file", "line_bits"}.issubset(tables):
                raise ValueError("SQLite coverage artifact lacks file and line_bits tables")
        finally:
            connection.close()

    def _run_tests(self, test_command: Optional[Sequence[str]]) -> List[AnalysisFinding]:
        if not test_command:
            return [self._finding("testing.execution.command_missing", "", 1, "Opt-in test execution was requested without a command.", "Provide an explicit test command when enabling test execution.")]
        try:
            completed = subprocess.run(test_command, cwd=str(self.repository), universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError as error:
            return [self._finding("testing.execution.failed", "", 1, str(error), "Use an executable test command available in the configured environment.")]
        if completed.returncode:
            return [self._finding("testing.execution.failed", "", 1, "Test command exited with status {}.".format(completed.returncode), "Inspect the test command output and resolve the failing tests.")]
        return []

    def _inspection_artifacts(self) -> Tuple[Path, ...]:
        return tuple(
            path
            for path in sorted(self.repository.rglob("*"))
            if path.is_file() and path.suffix.lower() in (".html", ".csv") and "test_files" in path.parts
        )

    def _certified_inspection_artifacts(self) -> Tuple[Path, ...]:
        return tuple(
            artifact
            for artifact in self._inspection_artifacts()
            if artifact.with_name(artifact.name + ".sha256").is_file()
        )

    @staticmethod
    def _test_case_marker_counts(text: str) -> Dict[str, int]:
        counts = {marker: 0 for marker in _TEST_MARKERS}
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return counts

        def visit(statements: Iterable[ast.stmt], inherited: Set[str]) -> None:
            for statement in statements:
                if isinstance(statement, ast.ClassDef):
                    class_markers = inherited | {
                        TestQualityAnalyzer._decorator_name(decorator)
                        for decorator in statement.decorator_list
                    }
                    visit(statement.body, class_markers)
                elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    markers = inherited | {
                        TestQualityAnalyzer._decorator_name(decorator)
                        for decorator in statement.decorator_list
                    }
                    if statement.name.startswith("test"):
                        if "unreviewed_ai" in markers:
                            counts["unreviewed_ai"] += 1
                        if "inspection" in markers:
                            counts["inspection"] += 1
                        if {"skip", "skipif"} & markers or TestQualityAnalyzer._calls_marker(statement, "skip"):
                            counts["skip"] += 1
                        if "xfail" in markers or TestQualityAnalyzer._calls_marker(statement, "xfail"):
                            counts["xfail"] += 1

        visit(tree.body, set())
        return counts

    @staticmethod
    def _decorator_name(node: ast.AST) -> str:
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            return TestQualityAnalyzer._decorator_name(node.func)
        return ""

    @staticmethod
    def _calls_marker(node: ast.AST, marker: str) -> bool:
        return any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == marker
            for child in ast.walk(node)
        )

    @staticmethod
    def _is_test(path: Path) -> bool:
        return path.name.startswith("test_") or "tests" in path.parts or "test" in path.parts

    @staticmethod
    def _excluded(path: Path) -> bool:
        return any(part in {".git", ".pytest_cache", "build", "dist", "__pycache__"} for part in path.parts)

    @staticmethod
    def _finding(code: str, path: str, line: int, evidence: str, remediation: str) -> AnalysisFinding:
        return AnalysisFinding(code=code, message=evidence, severity="warning", path=path or None, line=line, evidence=evidence, remediation=remediation)
