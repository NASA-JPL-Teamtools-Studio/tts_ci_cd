"""Dry-run-first deterministic repairs for visible Markdown metadata."""

import difflib
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tts_ci_cd.ctx.metadata import MarkdownMetadataValidator


_KIND_ALIASES = {}


class RepairOperation:
    """One mechanical metadata replacement."""

    def __init__(self, path: str, rule_id: str, before: str, after: str) -> None:
        self.path = path
        self.rule_id = rule_id
        self.before = before
        self.after = after

    def to_dict(self) -> dict:
        return {"after": self.after, "before": self.before, "path": self.path, "rule_id": self.rule_id}


class RepairPlan:
    """Reviewable in-memory repair plan; creating one never writes files."""

    def __init__(self, repository: Path, operations: Tuple[RepairOperation, ...], diff: str, unresolved: Tuple[str, ...], pre_existing_changes: Tuple[str, ...]) -> None:
        self.repository = repository
        self.operations = operations
        self.diff = diff
        self.unresolved = unresolved
        self.pre_existing_changes = pre_existing_changes
        self.mode = "dry-run"

    def to_dict(self) -> dict:
        return {
            "diff": self.diff,
            "mode": self.mode,
            "operations": [operation.to_dict() for operation in self.operations],
            "pre_existing_changes": list(self.pre_existing_changes),
            "repository": str(self.repository),
            "unresolved": list(self.unresolved),
            "version": "1.0",
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


class RepairResult:
    """Evidence returned after an explicitly confirmed write."""

    def __init__(self, plan: RepairPlan, pre_existing_changes: Tuple[str, ...], generated_changes: Tuple[str, ...]) -> None:
        self.plan = plan
        self.pre_existing_changes = pre_existing_changes
        self.generated_changes = generated_changes

    def to_dict(self) -> dict:
        payload = self.plan.to_dict()
        payload.update({
            "generated_changes": list(self.generated_changes),
            "mode": "applied",
            "pre_existing_changes": list(self.pre_existing_changes),
        })
        return payload


class MetadataRepairEngine:
    """Plan and explicitly apply only known mechanical metadata repairs."""

    def __init__(self, repository: Path) -> None:
        self.repository = Path(repository).expanduser().resolve()
        if not self.repository.is_dir():
            raise ValueError("repository must be an existing directory: {}".format(self.repository))

    def plan(self) -> RepairPlan:
        """Build a dry-run plan from deterministic validator findings."""
        findings = MarkdownMetadataValidator(self.repository).validate()
        operations: List[RepairOperation] = []
        unresolved = []
        replacements: Dict[Path, str] = {}
        for finding in findings:
            if finding.code != "documentation.metadata.invalid_kind" or not finding.path:
                unresolved.append(finding.code)
                continue
            path = self.repository / finding.path
            text = replacements.get(path, path.read_text(encoding="utf-8"))
            changed = False
            for before, after in _KIND_ALIASES.items():
                old_line = "  kind: {}".format(before)
                new_line = "  kind: {}".format(after)
                if old_line in text:
                    text = text.replace(old_line, new_line, 1)
                    operations.append(RepairOperation(finding.path, finding.code, old_line, new_line))
                    changed = True
                    break
            if changed:
                replacements[path] = text
            else:
                unresolved.append(finding.code)
        diff_lines: List[str] = []
        for path, after in sorted(replacements.items()):
            before = path.read_text(encoding="utf-8")
            diff_lines.extend(
                difflib.unified_diff(
                    before.splitlines(True), after.splitlines(True),
                    fromfile=str(path), tofile=str(path),
                )
            )
        return RepairPlan(
            self.repository,
            tuple(operations),
            "".join(diff_lines),
            tuple(sorted(unresolved)),
            self._git_changes(),
        )

    def apply(self, plan: RepairPlan, confirm: bool = False) -> RepairResult:
        """Apply a plan only after explicit confirmation, preserving dirty paths."""
        if not confirm:
            raise ValueError("explicit confirmation is required before applying repairs")
        pre_existing = plan.pre_existing_changes
        generated = []
        for operation in plan.operations:
            path = self.repository / operation.path
            text = path.read_text(encoding="utf-8")
            if operation.before not in text:
                raise ValueError("repair precondition changed: {}".format(operation.path))
            path.write_text(text.replace(operation.before, operation.after, 1), encoding="utf-8")
            generated.append(operation.path)
        return RepairResult(plan, pre_existing, tuple(sorted(generated)))

    def _git_changes(self) -> Tuple[str, ...]:
        if not (self.repository / ".git").exists():
            return ()
        try:
            output = subprocess.check_output(
                ["git", "-C", str(self.repository), "status", "--short"],
                universal_newlines=True,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.CalledProcessError):
            return ()
        return tuple(sorted(line[3:] if len(line) >= 3 else line for line in output.splitlines() if line))
