"""Deterministic documentation-quality analysis for a repository."""

import ast
import re
from pathlib import Path
from typing import List, Tuple, Union

import yaml
from urllib.parse import urlparse

from tts_ci_cd.ctx.analysis import AnalysisFinding
from tts_ci_cd.ctx.metadata import MarkdownMetadataValidator
from tts_ci_cd.ctx.traversal import _LINK_RE


class DocumentationQualityAnalyzer:
    """Analyze public API documentation and Markdown quality evidence."""

    def __init__(self, repository: Union[str, Path]) -> None:
        """Create a quality analyzer.

        Args:
            repository: Root directory whose source and Markdown files are analyzed.
        """
        self.repository = Path(repository).expanduser().resolve()
        if not self.repository.is_dir():
            raise ValueError("repository must be an existing directory: {}".format(self.repository))

    def analyze(self, include_metadata: bool = True) -> Tuple[AnalysisFinding, ...]:
        """Return deterministic API and Markdown quality findings.

        Args:
            include_metadata: Whether to include shared metadata-validator findings.
        """
        findings: List[AnalysisFinding] = []
        if include_metadata:
            findings.extend(MarkdownMetadataValidator(self.repository).validate())
        for path in self._python_files():
            findings.extend(self._analyze_python(path))
        for path in self._markdown_files():
            findings.extend(self._analyze_markdown(path))
        return tuple(findings)

    def _python_files(self) -> Tuple[Path, ...]:
        """Return in-scope Python source paths."""
        return tuple(
            path
            for path in sorted(self.repository.rglob("*.py"))
            if not any(part in {".git", ".pytest_cache", "build", "dist", "__pycache__"} for part in path.relative_to(self.repository).parts)
            and "test" not in path.parts
            and "tests" not in path.parts
            and not path.name.startswith("test_")
        )

    def _markdown_files(self) -> Tuple[Path, ...]:
        """Return in-scope Markdown paths."""
        return MarkdownMetadataValidator(self.repository).markdown_files()

    def _analyze_python(self, path: Path) -> Tuple[AnalysisFinding, ...]:
        """Analyze public definitions in one Python file.

        Args:
            path: Python source path to analyze.
        """
        relative_path = path.relative_to(self.repository).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as error:
            return (self._finding("documentation.api.parse_error", relative_path, 1, str(error), "Fix the source parse error."),)
        findings: List[AnalysisFinding] = []
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                findings.extend(self._check_definition(node, relative_path, "class"))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                kind = "method" if isinstance(parents.get(node), ast.ClassDef) else "function"
                findings.extend(self._check_definition(node, relative_path, kind))
        return tuple(findings)

    def _check_definition(self, node: Union[ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef], path: str, kind: str) -> Tuple[AnalysisFinding, ...]:
        """Check one public definition and its callable parameters.

        Args:
            node: AST definition to inspect.
            path: Repository-relative source path.
            kind: Definition kind used in stable rule IDs.
        """
        findings: List[AnalysisFinding] = []
        docstring = ast.get_docstring(node)
        if not docstring:
            findings.append(self._finding("documentation.api.{}_missing".format(kind), path, node.lineno, "Public {} lacks documentation.".format(kind), "Add a docstring describing the public {}.".format(kind)))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            documented = docstring or ""
            positional_only = getattr(node.args, "posonlyargs", [])
            arguments = [
                argument.arg
                for argument in positional_only + node.args.args + node.args.kwonlyargs
                if argument.arg not in {"self", "cls"}
            ]
            if node.args.vararg and node.args.vararg.arg not in {"self", "cls"}:
                arguments.append(node.args.vararg.arg)
            if node.args.kwarg:
                arguments.append(node.args.kwarg.arg)
            for argument in arguments:
                if not re.search(r"(?:[:@]param\s+|\b){}\b\s*[:\-]".format(re.escape(argument)), documented):
                    findings.append(self._finding("documentation.api.parameter_missing", path, node.lineno, "Public parameter `{}` lacks documentation.".format(argument), "Document parameter `{}` in the callable docstring.".format(argument)))
        return tuple(findings)

    def _analyze_markdown(self, path: Path) -> Tuple[AnalysisFinding, ...]:
        """Analyze links, maturity conflicts, and released evidence.

        Args:
            path: Markdown path to analyze.
        """
        relative_path = path.relative_to(self.repository).as_posix()
        text = path.read_text(encoding="utf-8")
        findings: List[AnalysisFinding] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            for match in _LINK_RE.finditer(line):
                target = match.group(2)
                parsed = urlparse(target)
                if parsed.scheme or parsed.netloc:
                    continue
                target_path = (path.parent / parsed.path).resolve()
                try:
                    target_path.relative_to(self.repository)
                except ValueError:
                    findings.append(self._finding("documentation.link.invalid", relative_path, line_number, "Local link escapes repository: {}.".format(target), "Use a repository-relative local link."))
                    continue
                if not target_path.is_file():
                    findings.append(self._finding("documentation.link.missing", relative_path, line_number, "Local link does not exist: {}.".format(target), "Correct the link or add the referenced document."))
        metadata_match = re.search(
            r"^## TTS Metadata\s*$.*?^```yaml\s*$\n(?P<yaml>.*?)^```\s*$",
            text,
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        metadata = {}
        if metadata_match:
            try:
                parsed = yaml.safe_load(metadata_match.group("yaml"))
                metadata = parsed.get("tts", {}) if isinstance(parsed, dict) else {}
            except yaml.YAMLError:
                metadata = {}
        maturity = metadata.get("maturity") if isinstance(metadata, dict) else None
        maturity_line = text[: metadata_match.start()].count("\n") + 1 if metadata_match else 1
        body = text[: metadata_match.start()] if metadata_match else text
        if maturity == "released":
            if re.search(r"draft|review\s+needed|SME review", body, re.IGNORECASE):
                findings.append(self._finding("documentation.maturity.conflict", relative_path, maturity_line, "Released document contains a draft or review warning.", "Ask a human to reconcile the warning with the declared maturity."))
            if not any(metadata.get(field) for field in ("review_evidence", "human_review", "sme_review")):
                findings.append(self._finding("documentation.released.evidence_missing", relative_path, maturity_line, "Released document lacks named review evidence.", "Add human or SME review evidence after human confirmation."))
        return tuple(findings)

    @staticmethod
    def _finding(code: str, path: str, line: int, evidence: str, remediation: str) -> AnalysisFinding:
        """Create a source-located quality finding."""
        return AnalysisFinding(code=code, message=evidence, severity="warning", path=path, line=line, evidence=evidence, remediation=remediation)
