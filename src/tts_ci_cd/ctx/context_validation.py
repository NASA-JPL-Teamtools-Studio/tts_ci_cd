"""Deterministic progressive-versus-exhaustive documentation validation."""

import json
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from tts_ci_cd.ctx.analysis import AnalysisFinding, ANALYSIS_RESULT_VERSION


class ValidationQuestion:
    """A versioned question used to compare documentation contexts."""

    def __init__(self, identifier: str, prompt: str) -> None:
        """Create a validation question.

        Args:
            identifier: Stable question identifier.
            prompt: Human-readable question text.
        """
        self.identifier = identifier
        self.prompt = prompt

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-compatible question representation."""
        return {"id": self.identifier, "prompt": self.prompt}


class ValidationQuestionSet:
    """Versioned central and repository-specific validation questions."""

    def __init__(
        self,
        version: str,
        generic: Iterable[ValidationQuestion],
        repository_questions: Optional[Mapping[str, Iterable[ValidationQuestion]]] = None,
    ) -> None:
        """Create a question set.

        Args:
            version: Stable version identifier for the question set.
            generic: Questions applicable to every repository.
            repository_questions: Optional repository-specific question groups.
        """
        if not version:
            raise ValueError("question set version must not be empty")
        self.version = version
        self.generic = tuple(generic)
        self.repository_questions = {
            key: tuple(value) for key, value in (repository_questions or {}).items()
        }

    def for_repository(self, repository: Optional[str] = None) -> Tuple[ValidationQuestion, ...]:
        """Return generic questions plus the selected repository questions.

        Args:
            repository: Optional repository key selecting additional questions.
        """
        return self.generic + self.repository_questions.get(repository or "", ())

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ValidationQuestionSet":
        """Load a versioned question set from JSON-compatible data.

        Args:
            payload: Mapping containing versioned generic and repository questions.
        """
        if not isinstance(payload, Mapping) or not isinstance(payload.get("version"), str):
            raise ValueError("question set must contain a string version")

        def parse(items: Any) -> Tuple[ValidationQuestion, ...]:
            if not isinstance(items, list):
                raise ValueError("question set questions must be arrays")
            questions = []
            for item in items:
                if not isinstance(item, Mapping) or not isinstance(item.get("id"), str) or not isinstance(item.get("prompt"), str):
                    raise ValueError("each question must contain string id and prompt")
                questions.append(ValidationQuestion(item["id"], item["prompt"]))
            return tuple(questions)

        repository_questions = payload.get("repository_questions", {})
        if not isinstance(repository_questions, Mapping):
            raise ValueError("repository_questions must be an object")
        return cls(
            payload["version"],
            parse(payload.get("generic", [])),
            {key: parse(value) for key, value in repository_questions.items()},
        )


class ContextSnapshot:
    """A progressive or exhaustive context observation."""

    def __init__(
        self,
        scope: str,
        structural_facts: Mapping[str, Any],
        answers: Mapping[str, str],
        evidence: Mapping[str, Iterable[str]],
        missing_context: Iterable[str] = (),
        contradictions: Iterable[str] = (),
        traversal_gaps: Iterable[str] = (),
    ) -> None:
        """Create a context snapshot.

        Args:
            scope: Documentation scope represented by the snapshot.
            structural_facts: Exact-comparison facts such as headings and links.
            answers: Conclusions keyed by validation question identifier.
            evidence: Source paths or anchors supporting each answer.
            missing_context: Paths or context facts that were unavailable.
            contradictions: Source locations with contradictory evidence.
            traversal_gaps: Source paths or anchors the progressive path could not follow.
        """
        self.scope = scope
        self.structural_facts = dict(structural_facts)
        self.answers = dict(answers)
        self.evidence = {key: tuple(value) for key, value in evidence.items()}
        self.missing_context = tuple(missing_context)
        self.contradictions = tuple(contradictions)
        self.traversal_gaps = tuple(traversal_gaps)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ContextSnapshot":
        """Create a snapshot from the documented JSON input shape.

        Args:
            payload: Mapping containing scope, structural facts, answers, and evidence.
        """
        if not isinstance(payload, Mapping):
            raise ValueError("snapshot JSON root must be an object")
        required = ("scope", "structural_facts", "answers", "evidence")
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError("snapshot is missing required fields: {}".format(", ".join(missing)))
        if not isinstance(payload["scope"], str) or not payload["scope"]:
            raise ValueError("snapshot scope must be a non-empty string")
        for field in ("structural_facts", "answers", "evidence"):
            if not isinstance(payload[field], Mapping):
                raise ValueError("snapshot field `{}` must be an object".format(field))
        return cls(
            scope=payload["scope"],
            structural_facts=payload["structural_facts"],
            answers=payload["answers"],
            evidence=payload["evidence"],
            missing_context=payload.get("missing_context", ()),
            contradictions=payload.get("contradictions", ()),
            traversal_gaps=payload.get("traversal_gaps", ()),
        )


class ContextValidationResult:
    """Versioned comparison result classified by deterministic evidence."""

    def __init__(
        self,
        scope: str,
        question_set_version: str,
        classification: str,
        structural_differences: Tuple[str, ...],
        findings: Tuple[AnalysisFinding, ...],
        ai_advisory: Optional[Any] = None,
    ) -> None:
        """Create a context validation result.

        Args:
            scope: Documentation scope compared.
            question_set_version: Version of questions used for comparison.
            classification: `equivalent`, `divergent`, or `indeterminate`.
            structural_differences: Exact structural fact keys that differ.
            findings: Source-located deterministic findings.
            ai_advisory: Optional advisory AI output, never used as the only gate.
        """
        self.version = ANALYSIS_RESULT_VERSION
        self.scope = scope
        self.question_set_version = question_set_version
        self.classification = classification
        self.structural_differences = structural_differences
        self.findings = findings
        self.ai_advisory = ai_advisory

    def to_dict(self) -> Dict[str, Any]:
        """Return a stable JSON-compatible result."""
        return {
            "ai_advisory": self.ai_advisory,
            "classification": self.classification,
            "findings": [finding.to_dict() for finding in self.findings],
            "question_set_version": self.question_set_version,
            "scope": self.scope,
            "structural_differences": list(self.structural_differences),
            "version": self.version,
        }

    def to_json(self) -> str:
        """Serialize the result deterministically."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


DEFAULT_QUESTION_SET = ValidationQuestionSet(
    "context-v1",
    (ValidationQuestion("purpose", "What is the purpose of this documentation scope?"),),
)


class ContextValidator:
    """Compare targeted and exhaustive documentation context deterministically."""

    def compare(
        self,
        progressive: ContextSnapshot,
        exhaustive: ContextSnapshot,
        questions: ValidationQuestionSet,
        repository: Optional[str] = None,
        ai_advisory: Optional[Any] = None,
    ) -> ContextValidationResult:
        """Compare snapshots using exact structure, answers, and evidence overlap.

        Args:
            progressive: Targeted tree/outline/section/link context.
            exhaustive: Complete Markdown context for the same scope.
            questions: Versioned generic and repository-specific questions.
            repository: Optional repository key for repository-specific questions.
            ai_advisory: Optional advisory evaluation retained but not trusted as a gate.
        """
        findings = []
        if progressive.scope != exhaustive.scope:
            findings.append(
                self._finding(
                    "documentation.context.scope_mismatch",
                    "Progressive and exhaustive snapshots have different scopes.",
                    "Create both snapshots from the same documentation scope before comparing them.",
                    progressive.scope,
                )
            )
        structural_differences = tuple(
            key
            for key in sorted(set(progressive.structural_facts) | set(exhaustive.structural_facts))
            if (
                (key in progressive.structural_facts) != (key in exhaustive.structural_facts)
                or progressive.structural_facts.get(key) != exhaustive.structural_facts.get(key)
            )
        )
        if structural_differences:
            findings.append(
                self._finding(
                    "documentation.context.structure_divergence",
                    "Structural facts differ: {}.".format(", ".join(structural_differences)),
                    "Compare tree, outline, and local-link evidence before trusting progressive context.",
                )
            )

        for location in sorted(set(progressive.missing_context) | set(exhaustive.missing_context)):
            findings.append(
                self._finding(
                    "documentation.context.missing_context",
                    "Context is missing: {}.".format(location),
                    "Read the missing document or section and rerun validation.",
                    location,
                )
            )
        for location in sorted(set(progressive.traversal_gaps) | set(exhaustive.traversal_gaps)):
            findings.append(
                self._finding(
                    "documentation.context.traversal_gap",
                    "Traversal gap requires review: {}.".format(location),
                    "Follow the missing local link or read the missing section before comparing context.",
                    location,
                )
            )
        for location in sorted(set(progressive.contradictions) | set(exhaustive.contradictions)):
            findings.append(
                self._finding(
                    "documentation.context.contradiction",
                    "Contradictory evidence requires review: {}.".format(location),
                    "Ask a human to resolve the contradiction before accepting equivalence.",
                    location,
                )
            )

        for question in questions.for_repository(repository):
            progressive_answer = progressive.answers.get(question.identifier)
            exhaustive_answer = exhaustive.answers.get(question.identifier)
            evidence_paths = tuple(
                sorted(
                    set(progressive.evidence.get(question.identifier, ()))
                    | set(exhaustive.evidence.get(question.identifier, ()))
                )
            )
            finding_path = evidence_paths[0] if evidence_paths else question.identifier
            if progressive_answer is None or exhaustive_answer is None:
                missing_sides = []
                if progressive_answer is None:
                    missing_sides.append("progressive")
                if exhaustive_answer is None:
                    missing_sides.append("exhaustive")
                findings.append(
                    self._finding(
                        "documentation.context.missing_answer",
                        "Question `{}` lacks a conclusion in the {} context.".format(
                            question.identifier, " and ".join(missing_sides)
                        ),
                        "Answer the versioned question and cite its source evidence in both contexts.",
                        finding_path,
                    )
                )
            elif progressive_answer != exhaustive_answer:
                findings.append(
                    self._finding(
                        "documentation.context.answer_divergence",
                        "Question `{}` has different conclusions.".format(question.identifier),
                        "Review both answers and their source evidence.",
                        finding_path,
                    )
                )
            overlap = set(progressive.evidence.get(question.identifier, ())) & set(
                exhaustive.evidence.get(question.identifier, ())
            )
            if not overlap:
                findings.append(
                    self._finding(
                        "documentation.context.evidence_gap",
                        "Question `{}` has no overlapping evidence.".format(question.identifier),
                        "Follow local links and cite shared source evidence.",
                        finding_path,
                    )
                )

        has_divergence = any(
            finding.code.endswith("divergence") for finding in findings
        )
        classification = "divergent" if has_divergence else "equivalent"
        if findings and not has_divergence:
            classification = "indeterminate"
        return ContextValidationResult(
            scope=progressive.scope,
            question_set_version=questions.version,
            classification=classification,
            structural_differences=structural_differences,
            findings=tuple(findings),
            ai_advisory=ai_advisory,
        )

    @staticmethod
    def _finding(code: str, message: str, remediation: str, path: str = "") -> AnalysisFinding:
        """Create a context finding with source evidence and remediation."""
        return AnalysisFinding(
            code=code,
            message=message,
            severity="warning",
            path=path or None,
            line=None,
            evidence=path or message,
            remediation=remediation,
        )
