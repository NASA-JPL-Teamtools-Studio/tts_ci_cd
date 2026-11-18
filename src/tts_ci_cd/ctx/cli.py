"""CLI entry point for tts-ctx."""
import json
from pathlib import Path

import typer
from typing import Optional
from tts_ci_cd.ctx import commands
from tts_ci_cd.ctx.index_db import IndexDB

app = typer.Typer(help="TTS Workspace Context Navigator")

@app.command()
def kinds(json_output: bool = False) -> None:
    """List document kinds and their definitions."""
    commands.run_kinds(as_json=json_output)


@app.command()
def start_here():
    """Bootstrap orientation: workspace overview and navigation menu."""
    db = IndexDB()
    commands.run_start_here(db)

@app.command()
def core():
    """List shared core libraries and their key classes."""
    db = IndexDB()
    commands.run_core(db)

@app.command()
def adaptations():
    """List mission adaptation repos and their core targets."""
    db = IndexDB()
    commands.run_adaptations(db)

@app.command()
def concepts():
    """Show key platform abstractions and concepts."""
    db = IndexDB()
    commands.run_concepts(db)

@app.command()
def repo(name: str):
    """Key classes and metadata for one repository."""
    db = IndexDB()
    commands.run_repo(db, name)

@app.command()
def deps(name: str):
    """Recursive truthful dependency map for a library."""
    db = IndexDB()
    commands.run_deps(db, name)

@app.command()
def class_info(path: str, depth: int = 1):
    """Inspect a class's MRO and progressive source. Use 'class' as alias."""
    db = IndexDB()
    commands.run_class(db, path, depth)

@app.command("class")
def class_alias(path: str, depth: int = 1):
    """Alias for class_info."""
    class_info(path, depth)

@app.command()
def search(query: str):
    """Fuzzy search any symbol across all repos."""
    db = IndexDB()
    commands.run_search(db, query)

@app.command()
def analyze(
    path: str = typer.Argument("."),
    standards_revision: str = "documentation-maintenance-v1",
    json_output: bool = False,
) -> None:
    """Analyze a repository and print a report or stable JSON result.

    Args:
        path: Repository path to analyze.
        standards_revision: Human-readable revision of the applicable standard.
        json_output: Whether to print stable JSON instead of Markdown.
    """
    commands.run_analysis(path, standards_revision, as_json=json_output)


@app.command()
def tree(
    repository: str = typer.Argument("."),
    json_output: bool = False,
) -> None:
    """List Markdown documents and their outlines.

    Args:
        repository: Repository or documentation root to inspect.
        json_output: Whether to print stable JSON instead of Markdown.
    """
    commands.run_tree(repository, as_json=json_output)


@app.command()
def outline(
    path: str,
    repository: str = typer.Option("."),
    depth: int = typer.Option(1),
    json_output: bool = False,
) -> None:
    """Show a Markdown outline through a selected heading depth.

    Args:
        path: Markdown path relative to the repository root.
        repository: Repository or documentation root to inspect.
        depth: Maximum Markdown heading level to include.
        json_output: Whether to print stable JSON instead of Markdown.
    """
    commands.run_outline(repository, path, depth, as_json=json_output)


@app.command()
def section(
    path: str,
    selector: str,
    repository: str = typer.Option("."),
    json_output: bool = False,
) -> None:
    """Read a selected Markdown section.

    Args:
        path: Markdown path relative to the repository root.
        selector: Heading title or anchor to select.
        repository: Repository or documentation root to inspect.
        json_output: Whether to print stable JSON instead of Markdown.
    """
    commands.run_section(repository, path, selector, as_json=json_output)


@app.command()
def follow(
    source_path: str,
    target: str,
    repository: str = typer.Option("."),
    json_output: bool = False,
) -> None:
    """Follow a local link or report an external link without fetching it.

    Args:
        source_path: Markdown path containing the link.
        target: Link target to resolve.
        repository: Repository or documentation root to inspect.
        json_output: Whether to print stable JSON instead of Markdown.
    """
    commands.run_follow(repository, source_path, target, as_json=json_output)


@app.command("doc-search")
def doc_search(
    query: str,
    repository: str = typer.Option("."),
    json_output: bool = False,
) -> None:
    """Search Markdown text, headings, metadata, and links.

    Args:
        query: Case-insensitive text to locate.
        repository: Repository or documentation root to inspect.
        json_output: Whether to print stable JSON instead of Markdown.
    """
    commands.run_doc_search(repository, query, as_json=json_output)


@app.command()
def read(
    path: str,
    repository: str = typer.Option("."),
    json_output: bool = False,
) -> None:
    """Read a complete Markdown document.

    Args:
        path: Markdown path relative to the repository root.
        repository: Repository or documentation root to inspect.
        json_output: Whether to print stable JSON instead of Markdown.
    """
    commands.run_read(repository, path, as_json=json_output)


@app.command("context-validate")
def context_validate(
    progressive_path: str,
    exhaustive_path: str,
    repository: str = typer.Option(None),
    question_set: str = typer.Option(None),
    json_output: bool = False,
) -> None:
    """Compare targeted and exhaustive documentation-context snapshots.

    Args:
        progressive_path: JSON file containing targeted context evidence.
        exhaustive_path: JSON file containing complete-scope context evidence.
        repository: Optional repository key selecting repository-specific questions.
        question_set: Optional JSON file containing a versioned question set.
        json_output: Whether to print stable JSON instead of Markdown.
    """
    try:
        commands.run_context_validate(
            progressive_path,
            exhaustive_path,
            as_json=json_output,
            repository=repository,
            question_set_path=question_set,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        typer.echo(
            "Unable to validate context snapshots: {}. Expected JSON with scope, "
            "structural_facts, answers, and evidence.".format(error),
            err=True,
        )
        raise typer.Exit(code=2)


@app.command()
def pilot(
    workspace: str = typer.Argument("."),
    json_output: bool = False,
) -> None:
    """Verify the representative standards-first pilot without GitHub Actions."""
    commands.run_pilot(workspace, as_json=json_output)


@app.command()
def standards(json_output: bool = False) -> None:
    """Explain applicable documentation standards and thresholds."""
    commands.run_standards(as_json=json_output)


@app.command()
def quality(
    repository: str = typer.Argument("."),
    standards_revision: str = "documentation-maintenance-v1",
    scope: str = typer.Option("repository"),
    json_output: bool = False,
) -> None:
    """Run combined documentation-quality analysis.

    Args:
        repository: Repository path to analyze.
        standards_revision: Human-readable revision of the applicable standard.
        json_output: Whether to print stable JSON instead of Markdown.
    """
    if scope == "repository" and Path(repository).is_dir():
        commands.run_quality(repository, standards_revision, as_json=json_output)
    else:
        commands.run_scope_quality(scope, repository, standards_revision, as_json=json_output)


@app.command()
def coverage(
    repository: str = typer.Argument("."),
    standards_revision: str = "documentation-maintenance-v1",
    json_output: bool = False,
) -> None:
    """Report documentation and test coverage metrics."""
    commands.run_coverage(repository, standards_revision, as_json=json_output)


@app.command()
def next(
    repository: str = typer.Argument("."),
    standards_revision: str = "documentation-maintenance-v1",
    json_output: bool = False,
) -> None:
    """Rank actionable quality findings."""
    commands.run_next(repository, standards_revision, as_json=json_output)


@app.command()
def check(
    repository: str = typer.Argument("."),
    standards_revision: str = "documentation-maintenance-v1",
    strict: bool = typer.Option(False),
    json_output: bool = False,
) -> None:
    """Report quality diagnostics and optionally apply policy thresholds."""
    if commands.run_check(repository, standards_revision, strict=strict, as_json=json_output):
        raise typer.Exit(code=1)


@app.command("test-quality")
def test_quality(
    repository: str = typer.Argument("."),
    coverage_path: Optional[str] = typer.Option(None),
    run_tests: bool = typer.Option(False),
    test_command: Optional[str] = typer.Option(None),
    json_output: bool = False,
) -> None:
    """Analyze test inventory, markers, certification, and coverage evidence.

    Args:
        repository: Repository path to analyze.
        coverage_path: Optional coverage XML or JSON artifact.
        run_tests: Whether to run the explicit test command first.
        test_command: Shell-like test command used only with run_tests.
        json_output: Whether to print stable JSON instead of Markdown.
    """
    import shlex

    commands.run_test_quality(
        repository,
        coverage_path=coverage_path,
        run_tests=run_tests,
        test_command=shlex.split(test_command) if test_command else None,
        as_json=json_output,
    )


@app.command("metadata-repair")
def metadata_repair(
    repository: str = typer.Argument("."),
    confirm: bool = typer.Option(False),
    json_output: bool = False,
) -> None:
    """Plan mechanical metadata repairs; write only with --confirm."""
    commands.run_metadata_repair(repository, confirm=confirm, as_json=json_output)


@app.command()
def metadata(
    repository: str = typer.Argument("."),
    standards_revision: str = "documentation-maintenance-v1",
    json_output: bool = False,
) -> None:
    """Validate Markdown metadata and print a report.

    Args:
        repository: Repository path to validate.
        standards_revision: Human-readable revision of the applicable standard.
        json_output: Whether to print stable JSON instead of Markdown.
    """
    commands.run_metadata(repository, standards_revision, as_json=json_output)


@app.command("metadata-pilot")
def metadata_pilot(
    workspace: str = typer.Argument("."),
    json_output: bool = False,
) -> None:
    """Report representative metadata migration readiness without editing files.

    Args:
        workspace: Workspace root containing representative repositories.
        json_output: Whether to print stable JSON instead of Markdown.
    """
    commands.run_metadata_pilot(workspace, as_json=json_output)


@app.command()
def index():
    """Build the symbol index from scratch."""
    commands.run_index()

@app.command("migrate-metadata")
def migrate_metadata(force: bool = False):
    """Suggest/apply [tool.tts-ctx] type tags across the workspace."""
    from tts_ci_cd.ctx.migrate_metadata import run_migration
    run_migration(force=force)

if __name__ == "__main__":
    app()

def main():
    app()

