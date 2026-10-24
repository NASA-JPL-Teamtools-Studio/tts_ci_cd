"""CLI entry point for tts-ctx."""
import typer
from typing import Optional
from tts_ci_cd.ctx import commands
from tts_ci_cd.ctx.index_db import IndexDB

app = typer.Typer(help="TTS Workspace Context Navigator")

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

