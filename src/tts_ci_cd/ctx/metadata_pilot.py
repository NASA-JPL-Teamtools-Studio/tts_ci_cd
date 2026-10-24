"""Report-only metadata migration pilot across representative repositories."""

import json
import subprocess
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple, Union

from tts_ci_cd.ctx.analysis import AnalysisFinding
from tts_ci_cd.ctx.metadata import MarkdownMetadataValidator


RepositoryPath = Union[str, Path]
_DEFAULT_TARGET_NAMES = ("central", "core", "tts_ci_cd", "oco2")


class PilotRepositoryReport:
    """Report for one representative repository in the pilot."""

    def __init__(
        self,
        name: str,
        path: Path,
        dirty: bool,
        pre_existing_changes: Tuple[str, ...],
        findings: Tuple[AnalysisFinding, ...],
        migration_status: str,
    ) -> None:
        """Create a repository pilot report.

        Args:
            name: Representative role used to identify the repository.
            path: Repository path.
            dirty: Whether the checkout has pre-existing changes.
            pre_existing_changes: Changed paths observed before migration.
            findings: Metadata findings for the repository.
            migration_status: Report status such as `validated` or `blocked_dirty`.
        """
        self.name = name
        self.path = path
        self.dirty = dirty
        self.pre_existing_changes = pre_existing_changes
        self.findings = findings
        self.migration_status = migration_status

    def to_dict(self) -> dict:
        """Return a JSON-compatible repository report."""
        return {
            "dirty": self.dirty,
            "findings": [finding.to_dict() for finding in self.findings],
            "git_state_known": self.migration_status != "git_state_unknown",
            "migration_diff": "",
            "migration_status": self.migration_status,
            "name": self.name,
            "path": str(self.path),
            "pre_existing_changes": list(self.pre_existing_changes),
        }


class MetadataPilotReport:
    """Stable report for a representative metadata migration pilot."""

    def __init__(self, scope: Path, repositories: Tuple[PilotRepositoryReport, ...]) -> None:
        """Create a pilot report.

        Args:
            scope: Workspace scope used for the pilot.
            repositories: Per-repository reports in deterministic order.
        """
        self.scope = scope
        self.repositories = repositories
        self.mode = "report"
        self.version = "1.0"

    def to_dict(self) -> dict:
        """Return a stable JSON-compatible pilot report."""
        return {
            "mode": self.mode,
            "repositories": [repository.to_dict() for repository in self.repositories],
            "scope": str(self.scope),
            "version": self.version,
        }

    def to_json(self) -> str:
        """Serialize the report with deterministic key ordering."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    def to_markdown(self) -> str:
        """Render a human-reviewable pilot summary."""
        lines = ["# Metadata migration pilot", "", "- Scope: `{}`".format(self.scope), ""]
        for repository in self.repositories:
            lines.extend(
                [
                    "## {}".format(repository.name),
                    "",
                    "- Path: `{}`".format(repository.path),
                    "- Status: `{}`".format(repository.migration_status),
                    "- Dirty: `{}`".format(repository.dirty),
                    "- Next step: {}".format(self._next_step(repository)),
                    "- Pre-existing changes: {}".format(
                        ", ".join(repository.pre_existing_changes) or "none"
                    ),
                    "- Findings: {}".format(len(repository.findings)),
                    "- Migration diff: report-only; no files were modified",
                    "",
                ]
            )
            for finding in repository.findings:
                lines.append(
                    "  - `{}` {}:{} — {}".format(
                        finding.code, finding.path, finding.line, finding.message
                    )
                )
                if finding.remediation:
                    lines.append("    - Next step: {}".format(finding.remediation))
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _next_step(repository: PilotRepositoryReport) -> str:
        """Describe the next human action for one pilot repository.

        Args:
            repository: Repository report requiring a next-step message.
        """
        if repository.migration_status == "missing":
            return "Provide the expected representative repository path or configuration."
        if repository.migration_status == "git_state_unknown":
            return "Resolve the Git status error before considering migration."
        if repository.migration_status == "blocked_dirty":
            return "Review and record the pre-existing changes before any migration."
        if repository.migration_status == "needs_review":
            return "Review findings and approve deterministic repairs through the grooming skill."
        return "No metadata findings; retain the report as pilot evidence."


class MetadataPilot:
    """Inspect representative repositories without silently modifying them."""

    def __init__(
        self,
        workspace_root: RepositoryPath,
        targets: Optional[Mapping[str, RepositoryPath]] = None,
    ) -> None:
        """Create a report-only metadata pilot.

        Args:
            workspace_root: TTS workspace root containing repository groups.
            targets: Optional named target paths; defaults to central/core/tts_ci_cd/oco2 discovery.
        """
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        if not self.workspace_root.is_dir():
            raise ValueError("workspace root must be an existing directory: {}".format(self.workspace_root))
        self.targets = {
            name: Path(path).expanduser().resolve() for name, path in (targets or self._discover_targets()).items()
        }

    def report(self) -> MetadataPilotReport:
        """Inspect all targets and return a deterministic report without editing files."""
        reports = []
        for name, path in sorted(self.targets.items()):
            if not path.is_dir():
                reports.append(PilotRepositoryReport(name, path, False, (), (), "missing"))
                continue
            changes = self._git_changes(path)
            if changes is None:
                reports.append(PilotRepositoryReport(name, path, False, (), (), "git_state_unknown"))
                continue
            dirty = bool(changes)
            findings = MarkdownMetadataValidator(path).validate()
            if dirty:
                status = "blocked_dirty"
            elif findings:
                status = "needs_review"
            else:
                status = "validated"
            reports.append(PilotRepositoryReport(name, path, dirty, changes, findings, status))
        return MetadataPilotReport(self.workspace_root, tuple(reports))

    def _discover_targets(self) -> Dict[str, Path]:
        """Discover the central, core, package, and OCO-2 pilot targets.

        Returns:
            Named representative paths, including missing placeholders.
        """
        targets: Dict[str, Path] = {
            "central": self.workspace_root / "tts_core" / "teamtools_documentation",
            "tts_ci_cd": self.workspace_root / "tts_core" / "tts_ci_cd",
            "core": self._first_repository(
                self.workspace_root / "tts_core",
                preferred="tts_utilities",
                exclude={"tts_ci_cd", "teamtools_documentation"},
            ),
            "oco2": self._first_repository(
                self.workspace_root / "oco2", preferred="oco2_mission_documentation"
            ),
        }
        return targets

    @staticmethod
    def _first_repository(
        group: Path,
        preferred: Optional[str] = None,
        exclude: Optional[Iterable[str]] = None,
    ) -> Path:
        """Return the first directory containing a Git checkout.

        Args:
            group: Workspace group directory to search.
            preferred: Repository name to select when present.
            exclude: Repository names that are not representative candidates.

        Returns:
            The preferred candidate path or a missing placeholder.
        """
        excluded = set(exclude or ())
        if not group.is_dir():
            return group / "missing"
        candidates = [
            path
            for path in sorted(group.iterdir())
            if path.name not in excluded and (path / ".git").exists()
        ]
        if preferred:
            for candidate in candidates:
                if candidate.name == preferred:
                    return candidate
        if preferred:
            return group / "missing_{}".format(preferred)
        return candidates[0] if candidates else group / "missing"

    @staticmethod
    def _git_changes(repository: Path) -> Optional[Tuple[str, ...]]:
        """Return changed paths from a checkout without modifying it.

        Args:
            repository: Git checkout to inspect.

        Returns:
            Sorted repository-relative changed paths.
        """
        if not (repository / ".git").exists():
            return ()
        try:
            output = subprocess.check_output(
                ["git", "-C", str(repository), "status", "--short"],
                universal_newlines=True,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return tuple(sorted(line[3:] if len(line) >= 3 else line for line in output.splitlines() if line))
