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

