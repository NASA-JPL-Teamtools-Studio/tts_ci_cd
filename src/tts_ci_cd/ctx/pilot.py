"""Complete standards-first pilot verification without CI side effects."""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from tts_ci_cd.ctx.analysis import AnalysisFinding
from tts_ci_cd.ctx.metadata import MarkdownMetadataValidator
from tts_ci_cd.ctx.metadata_pilot import MetadataPilot
from tts_ci_cd.ctx.quality import combined_quality
from tts_ci_cd.ctx.resources import MarkdownResourceCatalog
from tts_ci_cd.ctx.traversal import MarkdownTraversal


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
            "Package-install behavior is verified by the installed-package skill test; this pilot records repository-level build evidence.",
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


def _guardrail_evidence(path: Path, name: str) -> Dict[str, object]:
    """Collect non-authoritative evidence that repository guardrails are present."""
    if name != "oco2":
        return {"checked": False}
    agents = path / "AGENTS.md"
    context = path / "CONTEXT.md"
    skills = path / "agent" / "skills"
    agents_text = agents.read_text(encoding="utf-8") if agents.is_file() else ""
    return {
        "checked": True,
        "agents_present": agents.is_file(),
        "context_present": context.is_file(),
        "local_skills_present": skills.is_dir(),
        "human_final_authority": "Humans are always in final authority" in agents_text,
        "maturity_warning": "Maturity Warning" in agents_text,
    }


def _build_evidence(path: Path) -> Dict[str, object]:
    """Run a report-mode MkDocs check when the repository declares MkDocs."""
    evidence = {"mkdocs_config_present": (path / "mkdocs.yml").is_file(), "mkdocs_build": "not_applicable"}
    if not evidence["mkdocs_config_present"]:
        return evidence
    with tempfile.TemporaryDirectory(prefix="tts-pilot-") as site_dir:
        completed = subprocess.run(
            ["mkdocs", "build", "--site-dir", site_dir],
            cwd=str(path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
    evidence["mkdocs_build"] = "passed" if completed.returncode == 0 else "failed"
    return evidence


def verify_pilot(workspace_root: Path, targets: Optional[Mapping[str, Path]] = None) -> PilotVerificationReport:
    """Verify representative repositories using shared deterministic analyzers."""
    metadata_report = MetadataPilot(workspace_root, targets).report()
    MarkdownResourceCatalog().read_standard()
    repositories = []
    findings = []
    for report in metadata_report.repositories:
        findings.extend(report.findings)
        quality_findings = ()
        markdown_documents = 0
        traversal_documents = 0
        grooming_entry_points = []
        guardrails = {"checked": False}
        build_evidence = {"mkdocs_config_present": False, "mkdocs_build": "not_applicable"}
        if report.path.is_dir():
            quality = combined_quality(str(report.path), "documentation-maintenance-v1")
            quality_findings = quality.findings
            markdown_documents = len(MarkdownMetadataValidator(report.path).markdown_files())
            findings.extend(quality_findings)
            traversal_documents = len(MarkdownTraversal(MarkdownResourceCatalog(report.path)).tree())
            grooming_entry_points = [str(path.relative_to(report.path)) for path in sorted((report.path / "agent" / "skills").glob("*.md"))] if (report.path / "agent" / "skills").is_dir() else []
            guardrails = _guardrail_evidence(report.path, report.name)
            build_evidence = _build_evidence(report.path)
        repositories.append({
            "name": report.name,
            "path": str(report.path),
            "dirty": report.dirty,
            "pre_existing_changes": list(report.pre_existing_changes),
            "generated_changes": [],
            "metadata_findings": len(report.findings),
            "quality_findings": len(quality_findings),
            "markdown_documents": markdown_documents,
            "traversal_documents": traversal_documents,
            "grooming_entry_points": grooming_entry_points,
            "guardrails": guardrails,
            "build_evidence": build_evidence,
            "migration_status": report.migration_status,
        })
    return PilotVerificationReport(workspace_root, tuple(repositories), tuple(findings))
