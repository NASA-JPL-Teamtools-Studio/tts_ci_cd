"""Deterministic access to packaged Markdown documentation resources."""

from pathlib import Path
from typing import List, Optional, Tuple, Union


DEFAULT_STANDARDS_REVISION = "documentation-maintenance-v1"
DEFAULT_STANDARD_PATH = "standards/documentation_maintenance.md"
ResourcePath = Union[str, Path]


class ResourceNotFoundError(IOError):
    """Raised when a Markdown resource is missing or outside the resource root."""


class MarkdownResource:
    """A Markdown document returned by a resource catalog."""

    def __init__(self, path: str, text: str, revision: str) -> None:
        """Create a resource document.

        Args:
            path: Resource-relative Markdown path.
            text: Markdown document contents.
            revision: Standards revision associated with the document.
        """
        self.path = path
        self.text = text
        self.revision = revision


class MarkdownResourceCatalog:
    """Read packaged or explicitly supplied Markdown resources deterministically.

    Args:
        resource_root: Directory containing Markdown resources. When omitted,
            the package's bundled resources are used.
        standards_revision: Revision attached to every returned resource.
    """

    def __init__(
        self,
        resource_root: Optional[ResourcePath] = None,
        standards_revision: str = DEFAULT_STANDARDS_REVISION,
    ) -> None:
        if not standards_revision:
            raise ValueError("standards_revision must not be empty")
        self.resource_root = Path(resource_root or Path(__file__).parent / "resources").resolve()
        self.standards_revision = standards_revision

    def list_documents(self) -> Tuple[str, ...]:
        """Return all Markdown resource paths in deterministic order."""
        if not self.resource_root.is_dir():
            return ()
        paths: List[str] = []
        for path in self.resource_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in (".md", ".markdown"):
                paths.append(path.relative_to(self.resource_root).as_posix())
        return tuple(sorted(paths))

    def read_document(self, relative_path: str) -> MarkdownResource:
        """Read one repository-relative Markdown document without network access."""
        candidate = (self.resource_root / relative_path).resolve()
        try:
            candidate.relative_to(self.resource_root)
        except ValueError:
            raise ResourceNotFoundError(
                "Markdown resource is outside the configured resource root: {}".format(relative_path)
            )
        if not candidate.is_file() or candidate.suffix.lower() not in (".md", ".markdown"):
            raise ResourceNotFoundError(
                "Markdown resource not found: {}".format(relative_path)
            )
        normalized_path = candidate.relative_to(self.resource_root).as_posix()
        return MarkdownResource(
            path=normalized_path,
            text=candidate.read_text(encoding="utf-8"),
            revision=self.standards_revision,
        )

    def read(self, relative_path: str) -> MarkdownResource:
        """Alias for :meth:`read_document` for general resource consumers."""
        return self.read_document(relative_path)

    def read_standard(self, relative_path: str = DEFAULT_STANDARD_PATH) -> MarkdownResource:
        """Read a central standards document with its standards revision.

        Args:
            relative_path: Resource-relative path to the standards document.

        Returns:
            The requested standards document and its revision.
        """
        return self.read_document(relative_path)
