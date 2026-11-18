"""Behavioral tests for repository and workspace quality scopes."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tts_ci_cd.ctx.aggregation import ScopeResolver, analyze_scope
from tts_ci_cd.ctx.cli import app


@pytest.mark.unreviewed_ai
class TestQualityAggregation:
    """Verify deterministic repository, workspace, and related scopes."""

    def _workspace(self, tmp_path: Path) -> Path:
        core = tmp_path / "tts_core" / "tts_core_lib"
        mission = tmp_path / "mission" / "mission_core_lib"
        for repository in (core, mission):
            (repository / ".git").mkdir(parents=True)
            (repository / "README.md").write_text("# Repo\n")
        return tmp_path

    def test_workspace_and_related_scopes_preserve_repository_identity(self, tmp_path: Path) -> None:
        """Workspace and adaptation scopes return consistent per-repository results."""
        workspace = self._workspace(tmp_path)
        resolver = ScopeResolver(workspace, {"mission/mission_core_lib": "tts_core_lib"})

        workspace_result = analyze_scope("workspace", resolver=resolver)
        related_result = analyze_scope("related", str(workspace / "tts_core" / "tts_core_lib"), resolver=resolver)

        assert len(workspace_result.repositories) == 2
        assert len(related_result.repositories) == 2
        assert {result.scope for result in related_result.repositories} == {
            str(workspace / "tts_core" / "tts_core_lib"),
            str(workspace / "mission" / "mission_core_lib"),
        }
        payload = json.loads(related_result.to_json())
        assert payload["repositories"][0]["standards_revision"] == "documentation-maintenance-v1"

    def test_missing_scope_is_source_located_and_deterministic(self, tmp_path: Path) -> None:
        """A missing named repository yields a stable actionable finding."""
        result = analyze_scope("repository", "missing", resolver=ScopeResolver(tmp_path, {}))

        assert result.repositories == ()
        assert result.findings[0].code == "scope.repository_missing"

    def test_workspace_excludes_unrelated_git_checkouts(self, tmp_path: Path) -> None:
        """Workspace scope includes only TTS-style repositories."""
        workspace = self._workspace(tmp_path)
        unrelated = workspace / "other" / "random_repo"
        (unrelated / ".git").mkdir(parents=True)
        (unrelated / "README.md").write_text("# Other\n")

        result = analyze_scope("workspace", resolver=ScopeResolver(workspace, {}))

        assert {path.name for path in [Path(item.scope) for item in result.repositories]} == {"tts_core_lib", "mission_core_lib"}

    def test_related_scope_reaches_fixed_point_without_basename_matching(self, tmp_path: Path) -> None:
        """Related scope follows multi-hop relationships deterministically."""
        workspace = self._workspace(tmp_path)
        third = workspace / "mission" / "third_lib"
        (third / ".git").mkdir(parents=True)
        (third / "README.md").write_text("# Third\n")
        relations = {
            "mission/mission_core_lib": "tts_core_lib",
            "mission/third_lib": "mission/mission_core_lib",
        }
        resolver = ScopeResolver(workspace, relations)

        result = analyze_scope("related", str(workspace / "tts_core" / "tts_core_lib"), resolver=resolver)

        assert {Path(item.scope).name for item in result.repositories} == {"tts_core_lib", "mission_core_lib", "third_lib"}

    def test_named_repository_scope_reports_missing_paths_through_cli(self, tmp_path: Path) -> None:
        """A missing explicit repository returns a stable result instead of raising."""
        result = CliRunner().invoke(app, ["quality", "missing", "--scope", "repository", "--json-output"])

        assert result.exit_code == 0
        assert json.loads(result.stdout)["findings"][0]["code"] == "scope.repository_missing"

    def test_cli_accepts_explicit_workspace_scope(self, tmp_path: Path) -> None:
        """The quality CLI exposes aggregate scope selection."""
        workspace = self._workspace(tmp_path)

        result = CliRunner().invoke(app, ["quality", str(workspace), "--scope", "workspace", "--json-output"])

        assert result.exit_code == 0
        assert len(json.loads(result.stdout)["repositories"]) == 2
