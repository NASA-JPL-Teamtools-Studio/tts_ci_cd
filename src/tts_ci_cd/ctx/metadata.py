"""Deterministic validation of visible TTS Markdown metadata."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import yaml

from tts_ci_cd.ctx.analysis import AnalysisFinding


_METADATA_HEADING_RE = re.compile(r"^\s*##\s+TTS Metadata\s*$", re.IGNORECASE)
_HEADING_RE = re.compile(r"^\s*#{1,6}\s+")
_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
_VALID_KINDS = {"standard", "guide", "reference", "repository", "glossary", "roadmap", "incidental"}
_VALID_MATURITY = {"draft", "preliminary", "baseline", "released", "retired"}
_REQUIRED_FIELDS = ("kind", "maturity", "summary")
_EXCLUDED_DIRS = {".git", ".pytest_cache", "build", "dist", "__pycache__"}


class MarkdownMetadataValidator:
    """Validate visible `TTS Metadata` sections in a repository."""

    def __init__(self, repository: Union[str, Path]) -> None:
        """Create a validator for one repository.

        Args:
            repository: Root directory whose Markdown files should be validated.
        """
        self.repository = Path(repository).expanduser().resolve()
        if not self.repository.is_dir():
            raise ValueError("repository must be an existing directory: {}".format(self.repository))

    def markdown_files(self) -> Tuple[Path, ...]:
        """Return in-scope Markdown paths in deterministic order."""
        return tuple(
            path
            for path in sorted(self.repository.rglob("*"))
            if (
                path.is_file()
                and path.suffix.lower() in (".md", ".markdown")
                and not any(part in _EXCLUDED_DIRS for part in path.relative_to(self.repository).parts)
            )
        )

    def validate(self) -> Tuple[AnalysisFinding, ...]:
        """Validate every Markdown document in deterministic path order."""
        findings: List[AnalysisFinding] = []
        for path in self.markdown_files():
            findings.extend(self._validate_document(path))
        return tuple(findings)

    def _validate_document(self, path: Path) -> Tuple[AnalysisFinding, ...]:
        """Validate one Markdown document and return its findings.

        Args:
            path: Absolute path to the Markdown document.
        """
        relative_path = path.relative_to(self.repository).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        headings = self._metadata_headings(lines)
        if not headings:
            return (
                self._finding(
                    "documentation.metadata.missing",
                    relative_path,
                    1,
                    "No bottom-of-file TTS Metadata section found.",
                    "Add exactly one final `## TTS Metadata` section with a fenced YAML block.",
                ),
            )

        findings: List[AnalysisFinding] = []
        if len(headings) > 1:
            findings.append(
                self._finding(
                    "documentation.metadata.duplicate",
                    relative_path,
                    headings[1] + 1,
                    "Multiple TTS Metadata sections found.",
                    "Keep exactly one bottom-of-file TTS Metadata section.",
                )
            )

        heading_index = headings[0]
        section_end = self._section_end(lines, heading_index)
        blocks = self._fenced_blocks(lines, heading_index + 1, section_end)
        yaml_blocks = [block for block in blocks if block[2].strip().lower() == "yaml"]
        if (
            len(yaml_blocks) != 1
            or len(blocks) != 1
            or not self._metadata_section_is_strict(lines, heading_index + 1, section_end)
        ):
            findings.append(
                self._finding(
                    "documentation.metadata.malformed",
                    relative_path,
                    heading_index + 1,
                    "Metadata must contain exactly one fenced YAML block.",
                    "Replace the metadata contents with one valid fenced `yaml` block.",
                )
            )
        closing_line = yaml_blocks[0][1] + 1 if yaml_blocks else heading_index + 1
        last_content = self._last_nonblank_line(lines)
        if len(headings) > 1 or closing_line < last_content:
            findings.append(
                self._finding(
                    "documentation.metadata.misplaced",
                    relative_path,
                    heading_index + 1,
                    "TTS Metadata is not the final substantive section.",
                    "Move the single metadata section to the bottom of the document.",
                )
            )

        if not yaml_blocks:
            return tuple(findings)
        yaml_start, yaml_end, _ = yaml_blocks[0]
        yaml_text = "\n".join(lines[yaml_start + 1 : yaml_end])
        try:
            parsed = yaml.safe_load(yaml_text)
        except yaml.YAMLError as error:
            findings.append(
                self._finding(
                    "documentation.metadata.malformed",
                    relative_path,
                    yaml_start + 1,
                    "Metadata YAML could not be parsed: {}".format(error),
                    "Fix the YAML syntax inside the metadata fence.",
                )
            )
            return tuple(findings)

        if not isinstance(parsed, dict) or not isinstance(parsed.get("tts"), dict):
            findings.append(
                self._finding(
                    "documentation.metadata.malformed",
                    relative_path,
                    yaml_start + 1,
                    "Metadata must contain a mapping under `tts`.",
                    "Add a YAML mapping with a top-level `tts` key.",
                )
            )
            return tuple(findings)

        metadata = parsed["tts"]
        missing = [field for field in _REQUIRED_FIELDS if not metadata.get(field)]
        if missing:
            findings.append(
                self._finding(
                    "documentation.metadata.required",
                    relative_path,
                    yaml_start + 2,
                    "Required metadata fields are missing: {}.".format(", ".join(missing)),
                    "Provide kind, maturity, and summary under `tts`.",
                )
            )
        invalid_types = [
            field
            for field in _REQUIRED_FIELDS
            if field in metadata and not isinstance(metadata[field], str)
        ]
        if invalid_types:
            findings.append(
                self._finding(
                    "documentation.metadata.invalid_field",
                    relative_path,
                    yaml_start + 2,
                    "Metadata fields must be strings: {}.".format(", ".join(invalid_types)),
                    "Use scalar string values for kind, maturity, and summary.",
                )
            )
        if isinstance(metadata.get("kind"), str) and metadata["kind"] not in _VALID_KINDS:
            findings.append(
                self._finding(
                    "documentation.metadata.invalid_kind",
                    relative_path,
                    yaml_start + 2,
                    "Unknown document kind: {}.".format(metadata["kind"]),
                    "Use one of: {}.".format(", ".join(sorted(_VALID_KINDS))),
                )
            )
        if isinstance(metadata.get("maturity"), str) and metadata["maturity"] not in _VALID_MATURITY:
            findings.append(
                self._finding(
                    "documentation.metadata.invalid_maturity",
                    relative_path,
                    yaml_start + 2,
                    "Unknown maturity value: {}.".format(metadata["maturity"]),
                    "Use one of: {}. Maturity is human-owned and will not be changed by this validator.".format(
                        ", ".join(sorted(_VALID_MATURITY))
                    ),
                )
            )
        findings.extend(self._validate_related(relative_path, yaml_start + 2, metadata.get("related")))
        for field in ("audience", "policy_ids"):
            value = metadata.get(field)
            if value is not None and (
                not isinstance(value, list) or any(not isinstance(item, str) for item in value)
            ):
                findings.append(
                    self._finding(
                        "documentation.metadata.optional_invalid",
                        relative_path,
                        yaml_start + 2,
                        "Optional metadata field `{}` must be a list of strings.".format(field),
                        "Use a YAML list containing string values for `{}`.".format(field),
                    )
                )
        return tuple(findings)

    def _validate_related(
        self, relative_path: str, line: int, related: Optional[Any]
    ) -> Tuple[AnalysisFinding, ...]:
        """Validate local related paths without fetching external links.

        Args:
            relative_path: Markdown path containing the metadata.
            line: One-based metadata line for emitted findings.
            related: Parsed related-path metadata value.
        """
        if related is None:
            return ()
        if not isinstance(related, list):
            return (
                self._finding(
                    "documentation.metadata.related_invalid",
                    relative_path,
                    line,
                    "The related field must be a list of paths.",
                    "Use a YAML list containing repository-relative Markdown paths.",
                ),
            )
        findings = []
        for target in related:
            if not isinstance(target, str):
                findings.append(
                    self._finding(
                        "documentation.metadata.related_invalid",
                        relative_path,
                        line,
                        "Related path is not a string: {}.".format(target),
                        "Use a repository-relative path or an external URL.",
                    )
                )
                continue
            parsed = urlparse(target)
            if parsed.scheme or parsed.netloc:
                continue
            target_path = Path(target)
            candidate = (self.repository / target_path).resolve()
            try:
                candidate.relative_to(self.repository)
            except ValueError:
                findings.append(
                    self._finding(
                        "documentation.metadata.related_invalid",
                        relative_path,
                        line,
                        "Related path is not repository-relative: {}.".format(target),
                        "Use a relative path that remains inside the repository.",
                    )
                )
                continue
            if not candidate.is_file():
                findings.append(
                    self._finding(
                        "documentation.metadata.related_missing",
                        relative_path,
                        line,
                        "Related path does not exist: {}.".format(target),
                        "Correct the path or add the referenced document.",
                    )
                )
        return tuple(findings)

    def _finding(self, code: str, path: str, line: int, evidence: str, remediation: str) -> AnalysisFinding:
        """Build a source-located metadata finding.

        Args:
            code: Stable rule identifier.
            path: Repository-relative source path.
            line: One-based source line.
            evidence: Evidence supporting the finding.
            remediation: Next step for resolving the finding.
        """
        return AnalysisFinding(
            code=code,
            message=evidence,
            severity="error",
            path=path,
            line=line,
            remediation=remediation,
            evidence=evidence,
        )

    @staticmethod
    def _metadata_headings(lines: List[str]) -> List[int]:
        """Return metadata heading indexes outside fenced code blocks.

        Args:
            lines: Document lines to scan.
        """
        headings = []
        fence = None
        for index, line in enumerate(lines):
            fence_match = _FENCE_RE.match(line)
            if fence_match:
                marker = fence_match.group(1)
                if fence is None:
                    fence = (marker[0], len(marker))
                elif marker[0] == fence[0] and len(marker) >= fence[1]:
                    fence = None
                continue
            if fence is None and _METADATA_HEADING_RE.match(line):
                headings.append(index)
        return headings

    @staticmethod
    def _section_end(lines: List[str], start: int) -> int:
        """Find the next level-two section boundary.

        Args:
            lines: Document lines to scan.
            start: Zero-based metadata heading index.
        """
        fence = None
        for index in range(start + 1, len(lines)):
            fence_match = _FENCE_RE.match(lines[index])
            if fence_match:
                marker = fence_match.group(1)
                if fence is None:
                    fence = (marker[0], len(marker))
                elif marker[0] == fence[0] and len(marker) >= fence[1]:
                    fence = None
                continue
            if fence is None and re.match(r"^\s*##\s+", lines[index]):
                return index
        return len(lines)

    @staticmethod
    def _metadata_section_is_strict(lines: List[str], start: int, end: int) -> bool:
        """Check that metadata contains only one closed fence and blank lines.

        Args:
            lines: Document lines to scan.
            start: Inclusive zero-based range start.
            end: Exclusive zero-based range end.
        """
        fence = None
        block_count = 0
        for index in range(start, end):
            line = lines[index]
            match = _FENCE_RE.match(line)
            if match:
                marker = match.group(1)
                if fence is None:
                    fence = (marker[0], len(marker))
                    block_count += 1
                elif marker[0] != fence[0]:
                    return False
                elif len(marker) >= fence[1]:
                    fence = None
                continue
            if fence is None and line.strip():
                return False
        return fence is None and block_count == 1

    @staticmethod
    def _fenced_blocks(lines: List[str], start: int, end: int) -> List[Tuple[int, int, str]]:
        """Return fenced blocks in a document range.

        Args:
            lines: Document lines to scan.
            start: Inclusive zero-based range start.
            end: Exclusive zero-based range end.
        """
        blocks = []
        opening = None
        for index in range(start, end):
            match = _FENCE_RE.match(lines[index])
            if not match:
                continue
            marker = match.group(1)
            if opening is None:
                opening = (index, marker[0], len(marker), match.group(2).strip())
            elif marker[0] == opening[1] and len(marker) >= opening[2]:
                blocks.append((opening[0], index, opening[3]))
                opening = None
        return blocks

    @staticmethod
    def _last_nonblank_line(lines: List[str]) -> int:
        """Return the one-based index of the last substantive line.

        Args:
            lines: Document lines to scan.
        """
        for index in range(len(lines) - 1, -1, -1):
            if lines[index].strip():
                return index + 1
        return 0
