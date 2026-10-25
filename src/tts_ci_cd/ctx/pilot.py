"""Complete standards-first pilot verification without CI side effects."""

import json
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from tts_ci_cd.ctx.analysis import AnalysisFinding
from tts_ci_cd.ctx.metadata import MarkdownMetadataValidator
from tts_ci_cd.ctx.metadata_pilot import MetadataPilot
from tts_ci_cd.ctx.quality import combined_quality
from tts_ci_cd.ctx.resources import MarkdownResourceCatalog


class PilotVerificationReport:
    """Stable report for the complete representative documentation pilot."""

    def __init__(self, scope: Path, repositories: Tuple[Dict[str, object], ...], findings: Tuple[AnalysisFinding, ...]) -> None:
        self.version = "1.0"
        self.scope = scope
        self.repositories = repositories
        self.findings = findings
        self.remaining_gaps = (
            "Migration diff generation remains report-only until the deterministic repair follow-up is implemented.",
            "Mission safety, authority, and maturity decisions remain human-owned.",
            "MkDocs and package-install checks are reported separately from deterministic analysis.",
        )

    def to_dict(self) -> dict:
        return {
            "findings": [finding.to_dict() for finding in self.findings],
            "mode": "verify",
            "no_github_action": True,
            "remaining_gaps": list(self.remaining_gaps),
            "repositories": list(self.repositories),
            "scope": str(self.scope),
            "version": self.version,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    def to_markdown(self) -> str:
        lines = ["# Standards-first pilot verification", "", "- Scope: `{}`".format(self.scope), "- Mode: `verify`", ""]
        for repository in self.repositories:
            lines.extend([
                "## {}".format(repository["name"]),
                "",
                "- Path: `{}`".format(repository["path"]),
                "- Metadata findings: {}".format(repository["metadata_findings"]),
                "- Quality findings: {}".format(repository["quality_findings"]),
                "- Markdown documents: {}".format(repository["markdown_documents"]),
                "- Pre-existing changes: {}".format(", ".join(repository["pre_existing_changes"]) or "none"),
                "- Generated changes: none; verification is read-only",
                "",
            ])
        lines.extend(["## Remaining gaps", ""])
        lines.extend("- {}".format(gap) for gap in self.remaining_gaps)
        return "\n".join(lines) + "\n"


def verify_pilot(workspace_root: Path, targets: Optional[Mapping[str, Path]] = None) -> PilotVerificationReport:
    """Verify representative repositories using shared deterministic analyzers."""
    metadata_report = MetadataPilot(workspace_root, targets).report()
    MarkdownResourceCatalog().read_standard()
    repositories = []
    findings = []
    for report in metadata_report.repositories:
        quality_findings = ()
        markdown_documents = 0
        if report.path.is_dir():
            quality = combined_quality(str(report.path), "documentation-maintenance-v1")
            quality_findings = quality.findings
            markdown_documents = len(MarkdownMetadataValidator(report.path).markdown_files())
            findings.extend(quality_findings)
        repositories.append({
            "name": report.name,
            "path": str(report.path),
            "dirty": report.dirty,
            "pre_existing_changes": list(report.pre_existing_changes),
            "generated_changes": [],
            "metadata_findings": len(report.findings),
            "quality_findings": len(quality_findings),
            "markdown_documents": markdown_documents,
            "migration_status": report.migration_status,
        })
    return PilotVerificationReport(workspace_root, tuple(repositories), tuple(findings))
