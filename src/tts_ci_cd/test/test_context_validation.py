"""Behavioral tests for progressive-versus-exhaustive validation."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tts_ci_cd.ctx.cli import app
from tts_ci_cd.ctx.context_validation import (
    ContextSnapshot,
    ContextValidator,
    ValidationQuestion,
    ValidationQuestionSet,
)


@pytest.mark.unreviewed_ai
class TestContextValidation:
    """Verify deterministic context comparison and CLI serialization."""

    def _questions(self) -> ValidationQuestionSet:
        """Build the versioned question set used by these seam tests."""
        return ValidationQuestionSet(
            "context-v1",
            generic=(ValidationQuestion("purpose", "What is the document purpose?"),),
            repository_questions={
                "oco2": (ValidationQuestion("safety", "What safety guardrail applies?"),)
            },
        )

    def test_equivalent_context_requires_exact_structure_and_evidence_overlap(self) -> None:
        """Matching conclusions, structure, and evidence are equivalent."""
        questions = self._questions()
        progressive = ContextSnapshot(
            "docs",
            {"headings": ["Guide"], "links": ["reference.md"]},
            {"purpose": "setup"},
            {"purpose": ("docs/guide.md#purpose",)},
        )
        exhaustive = ContextSnapshot(
            "docs",
            {"headings": ["Guide"], "links": ["reference.md"]},
            {"purpose": "setup"},
            {"purpose": ("docs/guide.md#purpose",)},
        )

        result = ContextValidator().compare(progressive, exhaustive, questions)

        assert result.classification == "equivalent"
        assert result.structural_differences == ()
        assert result.findings == ()
        assert result.question_set_version == "context-v1"

    def test_divergent_context_reports_structure_and_answer_evidence(self) -> None:
        """Different structure or conclusions produce source-located findings."""
        questions = self._questions()
        progressive = ContextSnapshot(
            "docs",
            {"headings": ["Guide"], "links": []},
            {"purpose": "setup"},
            {"purpose": ("docs/guide.md",)},
        )
        exhaustive = ContextSnapshot(
            "docs",
            {"headings": ["Guide", "Install"], "links": ["reference.md"]},
            {"purpose": "operations"},
            {"purpose": ("docs/reference.md",)},
        )

        result = ContextValidator().compare(progressive, exhaustive, questions)

        assert result.classification == "divergent"
        assert result.structural_differences
        assert {finding.code for finding in result.findings} >= {
            "documentation.context.structure_divergence",
            "documentation.context.answer_divergence",
        }

    def test_scope_gaps_and_missing_answers_are_indeterminate(self) -> None:
        """Scope mismatch, traversal gaps, and unanswered questions block equivalence."""
        progressive = ContextSnapshot(
            "docs/progressive",
            {"headings": ["Guide"]},
            {},
            {},
            traversal_gaps=("guide.md#install",),
        )
        exhaustive = ContextSnapshot("docs/exhaustive", {"headings": ["Guide"]}, {}, {})

        result = ContextValidator().compare(progressive, exhaustive, self._questions())

        assert result.classification == "indeterminate"
        assert {finding.code for finding in result.findings} >= {
            "documentation.context.scope_mismatch",
            "documentation.context.traversal_gap",
            "documentation.context.missing_answer",
        }

    def test_invalid_snapshot_cli_failure_is_actionable(self, tmp_path: Path) -> None:
        """Malformed snapshot input returns a clear nonzero CLI result."""
        progressive_path = tmp_path / "progressive.json"
        exhaustive_path = tmp_path / "exhaustive.json"
        progressive_path.write_text("{}")
        exhaustive_path.write_text("{}")

        result = CliRunner().invoke(
            app,
            ["context-validate", str(progressive_path), str(exhaustive_path)],
        )

        assert result.exit_code == 2
        assert "Expected JSON with scope" in result.output

    def test_missing_context_is_indeterminate_and_cli_is_versioned(self, tmp_path: Path) -> None:
        """Missing context blocks equivalence and is exposed through the CLI."""
        progressive = {
            "scope": "docs",
            "structural_facts": {"headings": ["Guide"]},
            "answers": {"purpose": "setup"},
            "evidence": {"purpose": ["guide.md"]},
            "missing_context": ["reference.md"],
        }
        exhaustive = dict(progressive)
        exhaustive["missing_context"] = []
        progressive_path = tmp_path / "progressive.json"
        exhaustive_path = tmp_path / "exhaustive.json"
        progressive_path.write_text(json.dumps(progressive))
        exhaustive_path.write_text(json.dumps(exhaustive))

        result = CliRunner().invoke(
            app,
            [
                "context-validate",
                str(progressive_path),
                str(exhaustive_path),
                "--json-output",
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["version"] == "1.0"
        assert payload["classification"] == "indeterminate"
        assert payload["question_set_version"] == "context-v1"
        assert payload["findings"][0]["code"] == "documentation.context.missing_context"
